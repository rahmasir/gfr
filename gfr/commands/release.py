import typer
import questionary
import os
import re
from datetime import datetime
from rich.console import Console

from gfr.utils.git.operations import GitOperations, GitError
from gfr.utils.github.api import GitHubAPI, GitHubError
from gfr.utils.config import GFRConfig
from gfr.utils.command_helpers import validate_and_get_repo_details, format_git_url_to_http
from gfr.utils.console import get_multiline_input
from gfr.assets.changelog import CHANGELOG_TEMPLATE

app = typer.Typer(name="release", help="Start or finish a release.", no_args_is_help=True)
console = Console()

def _get_next_version(current_version: str, release_type: str) -> str:
    """Calculates the next semantic version number."""
    if not current_version:
        return "0.1.0" if release_type == "minor" else "1.0.0"

    major, minor, patch = map(int, current_version.lstrip('v').split('.'))
    if release_type == "major":
        major += 1
        minor = 0
        patch = 0
    else: # minor
        minor += 1
        patch = 0
    return f"{major}.{minor}.{patch}"

def _prompt_for_changes(category: str) -> list[str]:
    """Prompts the user for a list of changes for a specific category."""
    console.print(f"\n[bold cyan]Enter '{category}' items (one per line, empty line to finish):[/bold cyan]")
    items = []
    while True:
        item = input()
        if not item:
            break
        items.append(item)
    return items

def _start_release(git_ops: GitOperations, config: GFRConfig, microservice_name: str):
    """Handles the logic for starting a new release."""
    target_path, target_name, repo_name_for_github = validate_and_get_repo_details(git_ops, config, microservice_name)

    console.print("[bold yellow]Starting release process...[/bold yellow]")
    # --- Get latest version from Git tags ---
    console.print("[bold yellow]Fetching latest tag...[/bold yellow]")
    current_version = git_ops.get_latest_tag(path=target_path)
    console.print(f"Current version from tag: [bold yellow]{current_version or '0.0.0'}[/bold yellow]")

    # --- Ask for release type ---
    release_type = questionary.select(
        "What type of release is this?",
        choices=["minor", "major"]
    ).ask()
    if not release_type:
        raise typer.Exit()

    next_version = _get_next_version(current_version, release_type)
    console.print(f"Next version will be: [bold green]{next_version}[/bold green]")

    # --- Create release branch ---
    branch_name = f"release/{next_version}"
    console.print(f"[bold yellow]Creating branch '{branch_name}'...[/bold yellow]")
    
    
    git_ops.create_branch(branch_name, path=target_path)
    git_ops.switch_branch(branch_name, path=target_path)
    console.print(f"✔ Switched to new branch [bold yellow]{branch_name}[/bold yellow].")

    # --- Gather Changelog Info ---
    added = _prompt_for_changes("Added")
    changed = _prompt_for_changes("Changed")
    fixed = _prompt_for_changes("Fixed")

    # --- Update CHANGELOG.md ---
    console.print("[bold yellow]Updating CHANGELOG.md...[/bold yellow]")
    changelog_path = os.path.join(target_path, "CHANGELOG.md")
    
    remote_url = git_ops.get_remote_url(path=target_path)
    http_url = format_git_url_to_http(remote_url)
    
    release_date = datetime.now().strftime("%Y-%m-%d")
    release_link = f"{http_url}/releases/tag/v{next_version}"
    new_entry = f"## [{next_version}]({release_link}) - {release_date}\n"

    if added:
        new_entry += "### Added\n" + "\n".join(f"- {item}" for item in added) + "\n"
    if changed:
        new_entry += "### Changed\n" + "\n".join(f"- {item}" for item in changed) + "\n"
    if fixed:
        new_entry += "### Fixed\n" + "\n".join(f"- {item}" for item in fixed) + "\n"

    if os.path.exists(changelog_path):
        with open(changelog_path, 'r+') as f:
            content = f.read()
            f.seek(0, 0)
            f.write(re.sub(r'(# Changelog\n\n.*?\n\n)', fr'\1{new_entry}\n', content, 1, re.DOTALL))
    else:
        with open(changelog_path, 'w') as f:
            f.write(CHANGELOG_TEMPLATE.strip() + "\n\n" + new_entry)
    
    config.set_last_used_microservice(target_path)
    console.print("✔ Updated CHANGELOG.md.")

    console.print(f"\n[bold green]✔ Success![/bold green] Release {next_version} has been started.")
    console.print("Review CHANGELOG.md, then run 'ggg add' and 'ggg commit'.")


def _finish_release(git_ops: GitOperations, github_api: GitHubAPI, config: GFRConfig, microservice_name: str):
    """Handles the logic for finishing a release."""
    target_path, target_name, repo_name_for_github = validate_and_get_repo_details(git_ops, config, microservice_name)
    
    console.print("[bold yellow]Finishing release process...[/bold yellow]")
    current_branch = git_ops.get_current_branch(path=target_path)
    if not current_branch.startswith("release/"):
        console.print(f"[bold red]Error:[/bold red] You must be on a release branch to finish a release.")
        raise typer.Exit(code=1)
    
    version = current_branch.split('/')[-1]
    tag_name = f"v{version}"
    repo = github_api.repos.get(repo_name_for_github)
    release_label = github_api.repos.get_or_create_label(repo, "release", "0FB8B2", "Indicates a release pull request")

    # --- Push, PR, and Merge ---
    console.print(f"[bold yellow]Pushing '{current_branch}' to remote...[/bold yellow]")
    git_ops.push_branch(current_branch, set_upstream=True, path=target_path)

    for base_branch in ["develop", "main"]:
        console.print(f"[bold yellow]Creating and merging PR to '{base_branch}'...[/bold yellow]")
        pr = github_api.prs.create(repo, f"Release {tag_name}", f"Release branch for version {version}", head=current_branch, base=base_branch, labels=[release_label])
        github_api.prs.merge(pr)
        console.print(f"✔ Merged PR to [bold yellow]{base_branch}[/bold yellow].")

    # --- Tagging and GitHub Release ---
    console.print("[bold yellow]Tagging new release...[/bold yellow]")
    git_ops.switch_branch("main", path=target_path)
    git_ops.pull("main", path=target_path)
    git_ops.create_tag(tag_name, f"Release {version}", path=target_path)
    git_ops.push_tags(path=target_path)
    console.print(f"✔ Created and pushed tag [bold yellow]{tag_name}[/bold yellow].")

    console.print("[bold yellow]Generating release notes...[/bold yellow]")
    previous_tag = git_ops.get_latest_tag(path=target_path).splitlines()[1] if len(git_ops.get_latest_tag(path=target_path).splitlines()) > 1 else None
    commit_log = github_api.repos.compare_commits(repo, previous_tag, tag_name) if previous_tag else ["- Initial Release"]
    
    console.print("\n[bold cyan]Enter any additional notes for the GitHub Release:[/bold cyan]")
    extra_notes = get_multiline_input()
    commits_link = f"{repo.html_url}/commits/{tag_name}"
    release_notes = (
        f"## Changelog\n"
        f"See the [CHANGELOG.md]({repo.html_url}/blob/main/CHANGELOG.md) for detailed changes.\n\n"
        f"## Commits\n"
        f"[View the full list of commits for this release]({commits_link})\n\n"
        f"## Notes\n{extra_notes}"
    )
    
    console.print("[bold yellow]Creating GitHub Release...[/bold yellow]")
    github_api.repos.create_release(repo, tag_name, f"Release {version}", release_notes)
    console.print("✔ Created GitHub Release.")

    # --- Cleanup ---
    console.print("[bold yellow]Cleaning up branches...[/bold yellow]")
    git_ops.delete_remote_branch(current_branch, path=target_path)
    git_ops.delete_local_branch(current_branch, path=target_path)
    git_ops.switch_branch("develop", path=target_path)
    git_ops.pull("develop", path=target_path)
    console.print(f"✔ Cleaned up branches and switched to [bold yellow]develop[/bold yellow].")

    console.print(f"\n[bold green]✔ Success![/bold green] Release {version} has been published.")


@app.callback(invoke_without_command=True)
def release(
    microservice_name: str = typer.Argument(..., help="The target service (use '.' for parent, '-' for last used)."),
    action: str = typer.Argument(..., help="The action to perform: 'start' or 'finish'.")
):
    """
    Manages the release workflow by starting or finishing a release.
    """
    try:
        git_ops = GitOperations()
        github_api = GitHubAPI()
        config = GFRConfig()

        if action.lower() == "start":
            _start_release(git_ops, config, microservice_name)
        elif action.lower() == "finish":
            _finish_release(git_ops, github_api, config, microservice_name)
        else:
            console.print(f"[bold red]Error:[/bold red] Invalid action '{action}'. Please use 'start' or 'finish'.")
            raise typer.Exit(code=1)

    except (GitError, GitHubError) as e:
        console.print(f"\n[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)
