import typer
import questionary
import os
from rich.console import Console
from rich.prompt import Prompt
from dotenv import load_dotenv

from gfr.utils.console import get_multiline_input
from gfr.utils.config import GFRConfig
from gfr.utils.github.api import GitHubAPI
from gfr.utils.github.exceptions import GitHubError
from gfr.utils.git.operations import GitOperations, GitError

app = typer.Typer()
console = Console()

@app.callback(invoke_without_command=True)
def main():
    """
    Initializes the current directory as a Git repo, creates a corresponding
    GitHub repository, and sets up 'develop' and 'doc' branches.
    """
    try:
        # --- Initialize APIs ---
        git_ops = GitOperations()
        config = GFRConfig()
        load_dotenv()
        org_in_env = os.getenv("GITHUB_ORGANIZATION")

        # --- Pre-flight Check ---
        if git_ops.is_git_repo():
            console.print("[bold red]Error:[/bold red] This directory is already a Git repository.")
            raise typer.Exit(code=1)
        
        org_name = Prompt.ask(f"[bold yellow]Enter organization name[/bold yellow]", default=org_in_env)
        if not org_name:
            console.print("[bold red]Organization name cannot be empty. Aborting.[/bold red]")
            raise typer.Exit()

        config.set_organization(org_name)
        github_api = GitHubAPI(org_name)
        console.print(f"Authenticated as [bold green]{github_api.username}[/bold green] for organization [bold green]{github_api.org_name}[/bold green].")
        
        # --- Get Repository Details ---
        # Default repo name to the current directory's name
        default_repo_name = os.path.basename(os.getcwd())
        repo_name = Prompt.ask("[bold cyan]Enter repository name[/bold cyan]", default=default_repo_name)
        if not repo_name:
            console.print("[bold red]Repository name cannot be empty. Aborting.[/bold red]")
            raise typer.Exit()

        description = Prompt.ask("[bold cyan]Enter repository description[/bold cyan]")

        is_private = questionary.select(
            "Select repository visibility:",
            choices=[
                {"name": "Public", "value": False},
                {"name": "Private", "value": True},
            ],
            use_indicator=True
        ).ask()

        if is_private is None:
            console.print("[bold red]No selection made. Aborting.[/bold red]")
            raise typer.Exit()

        # --- Workflow Steps ---
        with console.status("[bold yellow]Starting project initialization...[/bold yellow]", spinner="dots") as status:
            # Step 1: Create GitHub Repository
            status.update("[bold yellow]Creating GitHub repository...[/bold yellow]")
            repo = github_api.repos.create(repo_name, description, is_private)
            console.print(f"✔ Repository '{repo.full_name}' created on GitHub.")

            # Step 2: Initialize Local Repository
            status.update("[bold yellow]Initializing local repository...[/bold yellow]")
            git_ops.init()
            git_ops.add_remote(repo.clone_url)
            console.print("✔ Local repository initialized and remote added.")

            # Step 3: Sync with Remote to get the 'main' branch
            status.update("[bold yellow]Fetching from remote...[/bold yellow]")
            git_ops.fetch()
            git_ops.switch_branch("main")
            console.print("✔ Synced with remote and switched to 'main' branch.")

            # Step 4: Create and Push New Branches
            status.update("[bold yellow]Creating and pushing branches...[/bold yellow]")
            git_ops.create_branch("develop", start_point="main")
            git_ops.create_branch("doc", start_point="main")
            console.print("✔ 'develop' and 'doc' branches created locally.")

            git_ops.push_branch("develop", set_upstream=True)
            git_ops.push_branch("doc", set_upstream=True)
            console.print("✔ 'develop' and 'doc' branches pushed to remote.")
            
            status.update("[bold yellow]Setting 'develop' as default branch...[/bold yellow]")
            github_api.repos.edit(repo, default_branch="develop")
            console.print("✔ Default branch set to 'develop' on GitHub.")

            # Step 5: Switch to Develop Branch
            status.update("[bold yellow]Switching to 'develop' branch...[/bold yellow]")
            git_ops.switch_branch("develop")
            console.print("✔ Switched to 'develop' branch.")

        console.print(f"\n[bold green]✔ Success![/bold green] Project '{repo_name}' is ready.")
        console.print("You are now on the 'develop' branch.")

    except (GitHubError, GitError) as e:
        console.print(f"\n[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Operation cancelled by user.[/bold yellow]")
        raise typer.Exit()
