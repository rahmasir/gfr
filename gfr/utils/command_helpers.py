from rich.console import Console
import typer
import os
import re
from .console import get_multiline_input

from .git.operations import GitOperations, GitError
from .github.api import GitHubAPI, GitHubError
from .config import GFRConfig

console = Console()

def switch_to_branch(target_branch: str):
    """
    A helper function to switch the current repository to a specified branch.
    Contains shared logic for commands like 'dev' and 'doc'.
    """
    try:
        git_ops = GitOperations()

        if not git_ops.is_git_repo():
            console.print("[bold red]Error:[/bold red] This command must be run from within a Git repository.")
            raise typer.Exit(code=1)

        current_branch = git_ops.get_current_branch()

        if current_branch == target_branch:
            console.print(f"[bold yellow]You are already on the '{target_branch}' branch.[/bold yellow]")
            raise typer.Exit()

        console.print(f"Switching to branch [bold yellow]{target_branch}[/bold yellow]...")
        git_ops.switch_branch(target_branch)
        console.print(f"✔ Successfully switched to branch [bold yellow]{target_branch}[/bold yellow].")

    except GitError as e:
        if "did not match any file(s) known to git" in str(e):
             console.print(f"[bold red]Error:[/bold red] Branch '{target_branch}' does not exist locally. Try running `git fetch` or creating it first.")
        else:
            console.print(f"\n[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Operation cancelled by user.[/bold yellow]")
        raise typer.Exit()

def start_new_task(task_type: str, microservice_name: str, task_name: str):
    """
    A shared helper function to start a new feature or bugfix.
    - Creates a GitHub issue.
    - Creates and switches to a new local branch.
    """
    try:
        git_ops = GitOperations()
        github_api = GitHubAPI()
        config = GFRConfig()

        # --- Refactored: Use the helper to determine target repository ---
        target_path, target_name, repo_name_for_github = validate_and_get_repo_details(git_ops, config, microservice_name)

        # --- Get Issue Details ---
        console.print(f"\n[bold cyan]Enter description for the {task_type} '{task_name}'.[/bold cyan]")
        description = get_multiline_input()
        
        labels = ["enhancement", "feature"] if task_type == "feature" else ["bug", "bugfix"]

        with console.status(f"[bold yellow]Creating {task_type} on GitHub...[/bold yellow]", spinner="dots") as status:
            # --- Create GitHub Issue ---
            status.update(f"[bold yellow]Finding repository '{repo_name_for_github}'...[/bold yellow]")
            repo = github_api.repos.get(repo_name_for_github)
            
            status.update(f"[bold yellow]Creating issue in '{repo.full_name}'...[/bold yellow]")
            issue = github_api.issues.create(repo, task_name, description, labels)
            console.print(f"✔ Created {task_type} issue [bold cyan]#{issue.number}[/bold cyan]: {issue.html_url}")

            # --- Create and Switch to Branch ---
            branch_name = f"{task_type}/{issue.number}-{task_name.lower().replace(' ', '-')}"
            status.update(f"[bold yellow]Creating and switching to branch '{branch_name}'...[/bold yellow]")
            
            git_ops.create_branch(branch_name, path=target_path)
            git_ops.switch_branch(branch_name, path=target_path)
            console.print(f"✔ Switched to new branch [bold yellow]{branch_name}[/bold yellow] in [bold cyan]{target_name}[/bold cyan].")

        # --- Set last used microservice with the resolved path ---
        config.set_last_used_microservice(target_path)

        console.print(f"\n[bold green]✔ Success![/bold green] You are ready to start working on the {task_type}.")

    except (GitError, GitHubError) as e:
        console.print(f"\n[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Operation cancelled by user.[/bold yellow]")
        raise typer.Exit()

def finish_task(task_type: str, microservice_name: str):
    """
    A shared helper function to finish a feature or bugfix.
    - Pushes the branch.
    - Creates and merges a pull request.
    - Cleans up the branch.
    """
    try:
        git_ops = GitOperations()
        github_api = GitHubAPI()
        config = GFRConfig()

        # --- Determine target repository ---
        target_path, target_name, repo_name_for_github = validate_and_get_repo_details(git_ops, config, microservice_name)

        # --- Pre-flight Checks ---
        current_branch = git_ops.get_current_branch(path=target_path)
        if not current_branch.startswith(f"{task_type}/"):
            console.print(f"[bold red]Error:[/bold red] You are not on a {task_type} branch in '{target_name}'.")
            raise typer.Exit(code=1)

        # --- Get PR Details ---
        pr_title = " ".join(current_branch.split('/')[1].split('-')[1:]).capitalize()
        issue_number = _extract_issue_number(current_branch)
        console.print(f"Finishing [bold cyan]{current_branch}[/bold cyan] in [bold cyan]{target_name}[/bold cyan].")
        console.print(f"\n[bold cyan]Enter description for the pull request (PR Title: {pr_title}).[/bold cyan]")
        description = get_multiline_input()
        
        # --- Auto-generate PR body to close issue ---
        final_description = description
        if issue_number:
            final_description = f"Closes #{issue_number}\n\n{description}"
            console.print(f"This PR will automatically close issue [bold yellow]#{issue_number}[/bold yellow].")

        labels = ["enhancement", "feature"] if task_type == "feature" else ["bug", "bugfix"]

        with console.status(f"[bold yellow]Finishing {task_type} on GitHub...[/bold yellow]", spinner="dots") as status:
            # --- Push Branch ---
            status.update(f"[bold yellow]Pushing branch '{current_branch}'...[/bold yellow]")
            git_ops.push_branch(current_branch, set_upstream=True, path=target_path)
            console.print("✔ Branch pushed to remote.")

            # --- Create Pull Request ---
            status.update("[bold yellow]Creating pull request...[/bold yellow]")
            repo = github_api.repos.get(repo_name_for_github)
            pr = github_api.prs.create(repo, pr_title, final_description, head=current_branch, base="develop", labels=labels)
            console.print(f"✔ Created Pull Request: {pr.html_url}")

            # --- Merge Pull Request ---
            status.update("[bold yellow]Merging pull request...[/bold yellow]")
            github_api.prs.merge(pr)
            console.print("✔ Pull request merged.")

            # --- Local Cleanup ---
            status.update("[bold yellow]Cleaning up local repository...[/bold yellow]")
            git_ops.switch_branch("develop", path=target_path)
            git_ops.pull("develop", path=target_path)
            git_ops.delete_local_branch(current_branch, path=target_path)
            console.print(f"✔ Switched to 'develop', pulled latest, and deleted local branch '{current_branch}'.")

            # --- Remote Cleanup ---
            status.update("[bold yellow]Deleting remote branch...[/bold yellow]")
            git_ops.delete_remote_branch(current_branch, path=target_path)
            console.print(f"✔ Deleted remote branch '{current_branch}'.")

            if target_path != ".":
                status.update(f"[bold yellow]Updating parent repository...[/bold yellow]")
                parent_branch = git_ops.get_current_branch(path=".")
                git_ops.add([target_path], path=".")
                commit_message = f"Update '{target_name}' submodule after finishing '{current_branch}'"
                git_ops.commit(commit_message, path=".")
                git_ops.push_branch(parent_branch, path=".")
                console.print(f"✔ Updated, committed, and pushed parent repository on branch '{parent_branch}'.")

        config.set_last_used_microservice(target_path)
        console.print(f"\n[bold green]✔ Success![/bold green] The {task_type} has been finished and merged.")

    except (GitError, GitHubError) as e:
        console.print(f"\n[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Operation cancelled by user.[/bold yellow]")
        raise typer.Exit()

def validate_and_get_repo_details(git_ops: GitOperations, config: GFRConfig, microservice_name: str) -> tuple[str, str, str]:
    """
    Validates that the command is run in a git repo and the service name is valid.
    The calling function is responsible for setting the last used microservice.

    Returns a tuple containing:
    - target_path (str): The local file path for git operations.
    - target_name (str): The display name for console output.
    - repo_name_for_github (str): The repository name for GitHub API calls.
    """
    if not git_ops.is_git_repo():
        console.print("[bold red]Error:[/bold red] This command must be run from within a Git repository.")
        raise typer.Exit(code=1)

    if microservice_name == '.':
        target_path = "."
        target_name = "root project"
        repo_name_for_github = os.path.basename(git_ops.get_root())
    elif microservice_name == '-':
        target_path = config.get_last_used_microservice()
        if not target_path:
            console.print("[bold red]Error:[/bold red] No last used microservice found. Please specify a service.")
            raise typer.Exit(code=1)
        
        # Resolve the details from the retrieved path
        if target_path == '.':
            target_name = "root project"
            repo_name_for_github = os.path.basename(git_ops.get_root())
        else:
            target_name = target_path
            repo_name_for_github = target_path
    else:
        target_path = microservice_name
        target_name = microservice_name
        repo_name_for_github = microservice_name
        # Validate that the named microservice is a real submodule
        submodules = git_ops.get_submodules()
        if target_path not in submodules:
            console.print(f"[bold red]Error:[/bold red] '{target_name}' is not a valid submodule in this project.")
            raise typer.Exit(code=1)
    
    return target_path, target_name, repo_name_for_github
    
    
def _extract_issue_number(branch_name: str) -> str | None:
    """Extracts an issue number from a branch name like 'feature/6-login-page'."""
    match = re.search(r'/(\d+)-', branch_name)
    return match.group(1) if match else None

def format_git_url_to_http(url: str) -> str:
    """Converts a git URL (SSH or HTTPS) to a web-viewable HTTPS URL."""
    if url.endswith(".git"):
        url = url[:-4]
    if url.startswith("git@"):
        url = url.replace(":", "/").replace("git@", "https://")
    return url
