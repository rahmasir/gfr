import typer
from typing_extensions import Annotated
import os
import re
from datetime import datetime

from rich.console import Console

from gfr.utils.command_helpers import validate_and_get_repo_details, format_git_url_to_http, _extract_issue_number
from gfr.utils.console import get_multiline_input
from gfr.utils.config import GFRConfig
from gfr.utils.git.operations import GitOperations, GitError
from gfr.utils.github.api import GitHubAPI, GitHubError
from gfr.assets.changelog import CHANGELOG_TEMPLATE

app = typer.Typer(name="hotfix", help="Start or finish a hotfix.", no_args_is_help=True)
console = Console()

def _get_next_patch_version(current_version: str) -> str:
    """Calculates the next patch version number."""
    if not current_version:
        # Cannot create a patch without a prior version
        return "0.0.1"

    major, minor, patch = map(int, current_version.lstrip('v').split('.'))
    patch += 1
    return f"{major}.{minor}.{patch}"

def _prompt_for_changelog_items() -> list[str]:
    """Prompts the user for a list of changes for the 'Fixed' category."""
    console.print(f"\n[bold cyan]Enter 'Fixed' items for the changelog (one per line, empty line to finish):[/bold cyan]")
    items = []
    while True:
        item = input()
        if not item:
            break
        items.append(item)
    return items

def _start_hotfix(
    microservice_name: str,
    hotfix_name: str,
    git_ops: GitOperations,
    github_api: GitHubAPI,
    config: GFRConfig
):
    """Handles the logic for starting a new hotfix."""
    target_path, target_name, repo_name_for_github = validate_and_get_repo_details(git_ops, config, microservice_name)

    # --- Pre-flight Check: Must be on the main branch ---
    current_branch = git_ops.get_current_branch(path=target_path)
    if current_branch != 'main':
        console.print(f"[bold red]Error:[/bold red] You must be on the 'main' branch in '{target_name}' to start a hotfix. You are currently on '{current_branch}'.")
        raise typer.Exit(code=1)

    with console.status(f"[bold yellow]Starting hotfix '{hotfix_name}'...[/bold yellow]", spinner="dots") as status:
        # --- Create GitHub Issue ---
        status.update(f"[bold yellow]Creating issue in '{repo_name_for_github}'...[/bold yellow]")
        repo = github_api.repos.get(repo_name_for_github)
        issue_body = f"Hotfix to address: {hotfix_name}"
        labels = ["bug", "hotfix"]
        issue = github_api.issues.create(repo, hotfix_name, issue_body, labels)
        console.print(f"✔ Created hotfix issue [bold cyan]#{issue.number}[/bold cyan]: {issue.html_url}")

        # --- Create and Switch to Branch from main ---
        branch_name = f"hotfix/{issue.number}-{hotfix_name.lower().replace(' ', '-')}"
        status.update(f"[bold yellow]Creating and switching to branch '{branch_name}' from 'main'...[/bold yellow]")

        git_ops.create_branch(branch_name, start_point="main", path=target_path)
        git_ops.switch_branch(branch_name, path=target_path)
        console.print(f"✔ Switched to new branch [bold yellow]{branch_name}[/bold yellow] in [bold cyan]{target_name}[/bold cyan].")

    config.set_last_used_microservice(target_path)
    console.print(f"\n[bold green]✔ Success![/bold green] You are ready to work on the hotfix.")

def _finish_hotfix(
    microservice_name: str,
    git_ops: GitOperations,
    github_api: GitHubAPI,
    config: GFRConfig
):
    """Handles the logic for finishing a hotfix."""
    target_path, target_name, repo_name_for_github = validate_and_get_repo_details(git_ops, config, microservice_name)

    # --- Pre-flight Check: Must be on a hotfix branch ---
    current_branch = git_ops.get_current_branch(path=target_path)
    if not current_branch.startswith("hotfix/"):
        console.print(f"[bold red]Error:[/bold red] You must be on a hotfix branch to finish it.")
        raise typer.Exit(code=1)

    console.print("[bold yellow]Finishing hotfix...[/bold yellow]")
    # --- Determine Version and Update Changelog ---
    console.print("[bold yellow]Determining version and updating changelog...[/bold yellow]")
    latest_tag = git_ops.get_latest_tag(path=target_path)
    next_version = _get_next_patch_version(latest_tag)
    tag_name = f"v{next_version}"

    fixed_items = _prompt_for_changelog_items()
    if not fixed_items:
        console.print("[bold red]Error:[/bold red] Changelog cannot be empty for a hotfix.")
        raise typer.Exit(code=1)

    changelog_path = os.path.join(target_path, "CHANGELOG.md")
    remote_url = git_ops.get_remote_url(path=target_path)
    http_url = format_git_url_to_http(remote_url)
    release_date = datetime.now().strftime("%Y-%m-%d")
    release_link = f"{http_url}/releases/tag/{tag_name}"
    new_entry = f"## [{next_version}]({release_link}) - {release_date}\n### Fixed\n" + "\n".join(f"- {item}" for item in fixed_items) + "\n"

    if os.path.exists(changelog_path):
        with open(changelog_path, 'r+') as f:
            content = f.read()
            f.seek(0, 0)
            f.write(re.sub(r'(# Changelog\n\n.*?\n\n)', fr'\1{new_entry}\n', content, 1, re.DOTALL))
    else:
        with open(changelog_path, 'w') as f:
            f.write(CHANGELOG_TEMPLATE.strip() + "\n\n" + new_entry)

    console.print("✔ Updated CHANGELOG.md.")

    # --- Commit Changelog ---
    console.print("[bold yellow]Committing changelog...[/bold yellow]")
    git_ops.add(["CHANGELOG.md"], path=target_path)
    git_ops.commit(f"docs: update changelog for version {next_version}", path=target_path)
    console.print("✔ Committed changelog.")

    # --- Get PR Details ---
    issue_number = _extract_issue_number(current_branch)
    console.print(f"\n[bold cyan]Enter description for the hotfix pull requests.[/bold cyan]")
    description = get_multiline_input()

    pr_body = description
    if issue_number:
        pr_body = f"Closes #{issue_number}\n\n{description}"
        console.print(f"This PR will automatically close issue [bold yellow]#{issue_number}[/bold yellow].")

    # --- Push, PR, and Merge into main and develop ---
    console.print(f"[bold yellow]Pushing branch '{current_branch}'...[/bold yellow]")
    git_ops.push_branch(current_branch, set_upstream=True, path=target_path)
    repo = github_api.repos.get(repo_name_for_github)

    for base_branch in ["main", "develop"]:
        console.print(f"[bold yellow]Creating and merging PR to '{base_branch}'...[/bold yellow]")
        pr = github_api.prs.create(repo, f"Hotfix: {current_branch}", pr_body, head=current_branch, base=base_branch, labels=["bug", "hotfix"])
        github_api.prs.merge(pr)
        console.print(f"✔ Merged PR to [bold yellow]{base_branch}[/bold yellow].")

    # --- Sync local main and develop branches ---
    console.print("[bold yellow]Syncing local 'main' and 'develop' branches...[/bold yellow]")
    git_ops.switch_branch("main", path=target_path)
    git_ops.pull("main", path=target_path)
    console.print("✔ Synced local 'main' branch.")
    git_ops.switch_branch("develop", path=target_path)
    git_ops.pull("develop", path=target_path)
    console.print("✔ Synced local 'develop' branch.")

    # --- Tagging and GitHub Release from main ---
    console.print("[bold yellow]Tagging new release on 'main'...[/bold yellow]")
    git_ops.switch_branch("main", path=target_path)
    git_ops.create_tag(tag_name, f"Release {next_version}", path=target_path)
    git_ops.push_tags(path=target_path)
    console.print(f"✔ Created and pushed tag [bold yellow]{tag_name}[/bold yellow].")
    
    release_notes = f"## Changelog\n- " + "\n- ".join(fixed_items)
    github_api.repos.create_release(repo, tag_name, f"Release {next_version}", release_notes)
    console.print("✔ Created GitHub Release.")
    
    # --- Merging into other local branches ---
    console.print("[bold yellow]Merging hotfix into other local branches...[/bold yellow]")
    all_branches = git_ops.get_all_branches(path=target_path)
    branches_to_merge_into = [b for b in all_branches if b not in ['main', 'develop', 'doc', current_branch] and not b.startswith('remotes/')]
    
    for branch in branches_to_merge_into:
        try:
            git_ops.switch_branch(branch, path=target_path)
            git_ops.merge_branch_locally('main', path=target_path)
            console.print(f"✔ Merged 'main' into local branch [bold yellow]{branch}[/bold yellow].")
        except GitError as e:
            if "merge conflict" in str(e).lower():
                console.print(f"\n[bold yellow]Merge conflict detected in branch '{branch}'. The program will continue, but you must resolve this manually.[/bold yellow]")
                console.print("To resolve:")
                console.print(f"  1. In a separate terminal, navigate to the '{target_name}' directory.")
                console.print(f"  2. Run 'git status' to see the conflicted files.")
                console.print(f"  3. Open the files, resolve the conflicts, then save them.")
                console.print(f"  4. Run 'ggg add {microservice_name} .' to stage the resolved files.")
                console.print(f"  5. Run 'git commit' to complete the merge.")
            else:
                console.print(f"[bold red]Could not auto-merge into '{branch}': {e}. Please merge manually.[/bold red]")

    # --- Cleanup ---
    console.print("[bold yellow]Cleaning up branches...[/bold yellow]")
    git_ops.delete_remote_branch(current_branch, path=target_path)
    git_ops.delete_local_branch(current_branch, path=target_path)
    git_ops.switch_branch("main", path=target_path)
    console.print(f"✔ Cleaned up branches and switched back to [bold yellow]main[/bold yellow].")

    config.set_last_used_microservice(target_path)
    console.print(f"\n[bold green]✔ Success![/bold green] Hotfix {next_version} has been published and merged.")


@app.callback(invoke_without_command=True)
def hotfix(
    microservice_name: Annotated[str, typer.Argument(help="The target service (use '.' for parent, '-' for last used).")],
    action: Annotated[str, typer.Argument(help="The action to perform: 'start' or 'finish'.")],
    hotfix_name: Annotated[str, typer.Argument(help="The name of the hotfix (e.g., 'Critical Security Patch'). Required for 'start'.")] = ""
):
    """
    Manages the hotfix workflow: starts a new hotfix from main or finishes the current one.
    """
    try:
        git_ops = GitOperations()
        github_api = GitHubAPI()
        config = GFRConfig()

        if action.lower() == "start":
            if not hotfix_name:
                console.print("[bold red]Error:[/bold red] The 'hotfix_name' argument is required when starting a hotfix.")
                raise typer.Exit(code=1)
            _start_hotfix(microservice_name, hotfix_name, git_ops, github_api, config)
        elif action.lower() == "finish":
            _finish_hotfix(microservice_name, git_ops, github_api, config)
        else:
            console.print(f"Error: Invalid action '{action}'. Please use 'start' or 'finish'.")
            raise typer.Exit(code=1)

    except (GitError, GitHubError) as e:
        console.print(f"\n[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Operation cancelled by user.[/bold yellow]")
        raise typer.Exit()

