import typer
from pathlib import Path
import sys

# Depending on how the package is run (via module or directly).
# For dev purposes in this directory structure:
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.engine import deploy_app, remove_app
from core.docker_mgr import get_managed_containers

app = typer.Typer(help="NexusDeploy - Zero-touch Docker orchestration system")

@app.command()
def deploy(folder: str):
    """
    Deploy an application from a specified folder containing manifest.yaml
    """
    try:
        deploy_app(folder)
    except Exception as e:
        typer.echo(f"Deployment failed: {e}", err=True)
        raise typer.Exit(code=1)

@app.command()
def remove(app_name: str):
    """
    Remove an active deployed application
    """
    try:
        remove_app(app_name)
    except Exception as e:
        typer.echo(f"Removal failed: {e}", err=True)
        raise typer.Exit(code=1)

@app.command()
def list():
    """
    List all active Nexus-managed containers
    """
    containers = get_managed_containers()
    if not containers:
        typer.echo("No active Nexus deployments found.")
        return

    typer.echo(f"{'App Name':<20} | {'Status':<15} | {'Container ID':<15}")
    typer.echo("-" * 55)
    for c in containers:
        typer.echo(f"{c['name']:<20} | {c['status']:<15} | {c['id']:<15}")

if __name__ == "__main__":
    app()
