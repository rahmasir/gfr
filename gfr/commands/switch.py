import typer
import questionary
from rich.console import Console

from gfr.utils.git.operations import GitOperations, GitError
from gfr.utils.config import GFRConfig
from gfr.utils.command_helpers import validate_and_get_repo_details

app = typer.Typer(name="switch", help="Switch to a different branch in a repository.", no_args_is_help=True)
console = Console()

@app.callback(invoke_without_command=True)
def switch(
    microservice_name: str = typer.Argument(..., help="The target service (use '.' for root, '-' for last used).")
):
    """
    Switches to a different branch in the selected repository.
    """
    try:
        git_ops = GitOperations()
        config = GFRConfig()

        target_path, target_name, _ = validate_and_get_repo_details(git_ops, config, microservice_name)

        current_branch = git_ops.get_current_branch(path=target_path)
        console.print(f"Currently on branch [bold yellow]{current_branch}[/bold yellow] in [bold cyan]{target_name}[/bold cyan].")

        with console.status("[bold yellow]Fetching branches...[/bold yellow]", spinner="dots"):
            all_branches = git_ops.get_all_branches(path=target_path)

        if not all_branches:
            console.print("[bold red]Error:[/bold red] No branches found in the repository.")
            raise typer.Exit(code=1)

        target_branch = questionary.select(
            "Which branch would you like to switch to?",
            choices=all_branches,
            use_indicator=True
        ).ask()

        if not target_branch:
            console.print("[bold red]No selection made. Aborting.[/bold red]")
            raise typer.Exit()

        if current_branch == target_branch:
            console.print(f"[bold yellow]You are already on the '{target_branch}' branch.[/bold yellow]")
            raise typer.Exit()

        console.print(f"Switching to branch [bold yellow]{target_branch}[/bold yellow]...")
        git_ops.switch_branch(target_branch, path=target_path)
        console.print(f"✔ Successfully switched to branch [bold yellow]{target_branch}[/bold yellow].")

    except (GitError) as e:
        console.print(f"\n[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Operation cancelled by user.[/bold yellow]")
        raise typer.Exit()