import typer
from gfr.commands import (
    hello, create,
    init, addmicro,
    add, commit, push, ac, acp,
    status, link,
    addasset,
    doc, dev,
    feature, bugfix, release,
    switch,
)

# Create the main Typer application
app = typer.Typer(
    name="ggg",
    help="Git Flow Assistant of Rahmasir (gfr) helps with git and GitHub workflows.",
    add_completion=False,
)

# Add subcommands from the commands module
app.add_typer(hello.app, name="hello")
app.add_typer(create.app, name="create")
app.add_typer(init.app, name="init")
app.add_typer(addmicro.app, name="addmicro")
app.add_typer(addmicro.app, name="am")
app.add_typer(add.app, name="add")
app.add_typer(commit.app, name='commit')
app.add_typer(ac.app, name='ac')
app.add_typer(push.app, name='push')
app.add_typer(acp.app, name='acp')
app.add_typer(status.app, name='status')
app.add_typer(link.app, name='link')
app.add_typer(addasset.app, name='addasset')
app.add_typer(addasset.app, name='adda')
app.add_typer(dev.app, name='dev')
app.add_typer(doc.app, name='doc')
app.add_typer(feature.app, name='feature')
app.add_typer(bugfix.app, name='bugfix')
app.add_typer(release.app, name='release')
app.add_typer(switch.app, name='switch')

if __name__ == "__main__":
    app()
