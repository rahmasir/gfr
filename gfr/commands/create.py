import typer
import questionary
from rich.console import Console
from rich.prompt import Prompt
from dotenv import load_dotenv
import os

from gfr.utils.github.api import GitHubAPI, GitHubError
from gfr.utils.git.operations import GitOperations
from gfr.utils.config import GFRConfig

# Create a Typer app for the 'create' command
app = typer.Typer()
console = Console()

@app.callback(invoke_without_command=True)
def main():
    """
    Creates a new GitHub repository in your organization.
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

        # --- Get Repository Name ---
        repo_name = Prompt.ask("[bold cyan]Enter repository name[/bold cyan]")

        # --- Get Repository Description ---
        description = Prompt.ask("\n[bold cyan]Enter repository description[/bold cyan]")

        # --- Get Repository Visibility ---
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

        readmefile = Prompt.ask("Do you want to add a readme file?", choices=['y', 'n'], default='n').lower() == 'y'

        # --- Create Repository ---
        with console.status("[bold yellow]Creating repository...[/bold yellow]", spinner="dots"):
            repo = github_api.repos.create(repo_name, description, is_private, readmefile)
        
        console.print(f"\n[bold green]✔ Repository '{repo.full_name}' created successfully![/bold green]")
        console.print(f"  [link={repo.html_url}]{repo.html_url}[/link]")
        
        
        with console.status("[bold yellow]Cloning repository...[/bold yellow]", spinner="dots"):
            repo_path = git_ops.clone(repo.html_url, repo_name)
            
        console.print(f"\n[bold green]✔ Repository '{repo.full_name}' cloned successfully![/bold green]")

    except GitHubError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Operation cancelled by user.[/bold yellow]")
        raise typer.Exit()

