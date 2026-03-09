import typer
from pathlib import Path
import sys
from typing import List

# Depending on how the package is run (via module or directly).
# For dev purposes in this directory structure:
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.engine import deploy_app, remove_app
from core.docker_mgr import get_managed_containers
from core.logger import logger, LOG_FILE

app = typer.Typer(help="NexusDeploy - Zero-touch Docker orchestration system")

@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """Show help when no subcommand is provided."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()

@app.command()
def deploy(
    folder: str,
    dry_run: bool = typer.Option(False, "--dry-run", help="Simulate deployment without modifying resources")
):
    """
    Deploy an application from a specified folder containing manifest.yaml
    """
    try:
        deploy_app(folder, dry_run=dry_run)
    except Exception as e:
        logger.exception("Deployment failed")
        typer.echo(f"Deployment failed. See {LOG_FILE} for details.", err=True)
        raise typer.Exit(code=1)

@app.command()
def remove(app_name: str):
    """
    Remove an active deployed application
    """
    try:
        remove_app(app_name)
    except Exception as e:
        logger.exception(f"Removal failed for {app_name}")
        typer.echo(f"Removal failed. See {LOG_FILE} for details.", err=True)
        raise typer.Exit(code=1)

@app.command()
def logs(app_name: str, tail: int = 100):
    """
    View logs for a deployed application
    """
    from core.docker_mgr import get_container_logs
    try:
        content = get_container_logs(app_name, tail=tail)
        typer.echo(content)
    except Exception as e:
        logger.exception(f"Failed to fetch logs for {app_name}")
        typer.echo(f"Log fetch failed. See {LOG_FILE} for details.", err=True)
        raise typer.Exit(code=1)

@app.command()
def prune():
    """
    Remove unused Docker networks and volumes
    """
    from core.docker_mgr import prune_resources
    try:
        nets, vols = prune_resources()
        typer.echo(f"Deleted networks: {len(nets.get('NetworksDeleted', []) or [])}")
        typer.echo(f"Deleted volumes: {len(vols.get('VolumesDeleted', []) or [])}")
    except Exception as e:
        logger.exception("Prune failed")
        typer.echo(f"Prune failed. See {LOG_FILE} for details.", err=True)
        raise typer.Exit(code=1)

@app.command()
def reload():
    """
    Manually trigger an Nginx configuration test and reload on the Gateway
    """
    from core.docker_mgr import reload_nginx
    try:
        typer.echo("Initiating Nginx Gateway reload sequence...")
        success, message = reload_nginx()
        if success:
            typer.echo("✅ Nginx reloaded successfully.")
        else:
            typer.echo(f"🚨 Nginx reload failed: {message}", err=True)
            raise typer.Exit(code=1)
    except Exception as e:
        logger.exception("Reload command failed")
        typer.echo(f"Reload command failed. See {LOG_FILE} for details.", err=True)
        raise typer.Exit(code=1)

@app.command()
def list():
    """
    List all active Nexus-managed containers
    """
    from core.state_mgr import load_state
    try:
        state = load_state()
        
        if not state:
            typer.echo("No NexusDeploy applications are currently running.")
            return

        typer.echo(f"{'PROJECT NAME':<20} | {'DOMAIN':<15} | {'PORT':<10} | {'PATH':<15} | {'SOURCE'}")
        typer.echo("-" * 85)
        
        for app_name, app_data in state.items():
            domain = app_data.get('domain', '_')
            port = str(app_data.get('port', 'N/A'))
            path = app_data.get('path', '/')
            source = app_data.get('source_dir', 'Unknown')
            
            typer.echo(f"{app_name:<20} | {domain:<15} | {port:<10} | {path:<15} | {source}")
    except Exception as e:
        logger.exception("Failed to list containers")
        typer.echo(f"List failed. See {LOG_FILE} for details.", err=True)
        raise typer.Exit(code=1)

@app.command()
def exec(
    app_name: str,
    command: List[str] = typer.Argument(..., help="The command to run inside the container")
):
    """
    Run a command inside a Nexus-managed container
    """
    from core.docker_mgr import exec_container
    try:
        exit_code, output = exec_container(app_name, command)
        typer.echo(output)
        if exit_code != 0:
            raise typer.Exit(code=exit_code)
    except Exception as e:
        logger.exception(f"Exec failed for {app_name}")
        typer.echo(f"Exec failed: {e}", err=True)
        raise typer.Exit(code=1)

if __name__ == "__main__":
    app()
