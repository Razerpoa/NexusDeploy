import os
import yaml
import subprocess
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from pydantic import ValidationError
from typing import Dict, Any

from .schema import Manifest
from .docker_mgr import (
    pre_flight_checks, 
    get_container_ip_and_port, 
    reload_nginx, 
    get_client,
    find_available_port,
    is_port_available,
    wait_for_container_health
)
from .logger import logger, LOG_FILE

# Define base paths
BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
GATEWAY_CONF_D = BASE_DIR / "gateway" / "conf.d"

env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))

def load_manifest(app_dir: Path) -> Manifest:
    manifest_path = app_dir / "manifest.yaml"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found at {manifest_path}")

    with open(manifest_path, "r") as f:
        data = yaml.safe_load(f)

    try:
        manifest = Manifest(**data)
        return manifest
    except ValidationError as e:
        print("Manifest validation failed:")
        print(e)
        raise

def deploy_app(app_dir: str, dry_run: bool = False):
    app_path = Path(app_dir).resolve()
    print(f"{'[DRY RUN] ' if dry_run else ''}Deploying from {app_path}...")
    
    # 1. Validation
    manifest = load_manifest(app_path)
    print(f"Validated manifest for project: {manifest.project_name}")

    # 2. Port Allocation
    from .state_mgr import get_app_state
    existing_state = get_app_state(manifest.project_name)

    if manifest.routing.port is None:
        print("No port specified. Finding available port...")
        if not dry_run:
            manifest.routing.port = find_available_port(manifest.routing.address)
        else:
            manifest.routing.port = 9000  # Mock port for dry run
        print(f"Assigned dynamic port: {manifest.routing.port}")
    elif not dry_run:
        port_available = is_port_available(manifest.routing.address, manifest.routing.port)
        # It's only a conflict if the port is taken and NOT by this same project
        is_own_port = existing_state and existing_state.get('port') == manifest.routing.port
        
        if not port_available and not is_own_port:
            raise RuntimeError(f"Port {manifest.routing.port} is already in use by another process on {manifest.routing.address}")


    # 3. Infrastructure
    if not dry_run:
        pre_flight_checks(manifest.infrastructure.networks, manifest.infrastructure.volumes)
    else:
        print(f"[DRY RUN] Would check/create {len(manifest.infrastructure.networks)} networks and {len(manifest.infrastructure.volumes)} volumes.")

    # 4. Generate docker-compose.yaml
    compose_tpl = env.get_template("app-compose.j2")
    compose_out = compose_tpl.render(manifest=manifest)
    
    compose_file = app_path / "docker-compose.yaml"
    if not dry_run:
        with open(compose_file, "w") as f:
            f.write(compose_out)
        print(f"Generated {compose_file}")
    else:
        print(f"\n[DRY RUN] Rendered docker-compose.yaml:\n{'-'*40}\n{compose_out}\n{'-'*40}")

    # 5. Start Container via Docker Compose
    print(f"{'[DRY RUN] Would start' if dry_run else 'Starting'} docker-compose for {manifest.project_name}...")
    if not dry_run:
        subprocess.run(
            ["docker", "compose", "-p", manifest.project_name, "up", "-d"],
            cwd=app_path,
            check=True
        )
        
        # Wait for container to be ready
        try:
            wait_for_container_health(manifest.project_name)
        except Exception as e:
            # If container fails to start, we should probably stop the compose to not leave it half-baked
            print(f"Container failed health check: {e}. Tearing down...")
            subprocess.run(["docker", "compose", "-p", manifest.project_name, "down"], cwd=app_path)
            raise

    # 6. Generate Nginx Route
    if not dry_run:
        ip, port = get_container_ip_and_port(manifest.project_name)
        if not ip:
            print(f"Warning: Could not determine internal IP for container {manifest.project_name}.")
            ip = "127.0.0.1"
            port = 80
    else:
        ip = "172.18.0.2" # Mock IP for dry run
        port = 80

    custom_conf_path = app_path / "custom.conf"
    custom_conf = ""
    if custom_conf_path.exists():
        with open(custom_conf_path, "r") as f:
            custom_conf = f.read()

    vhost_tpl = env.get_template("nginx-vhost.j2")
    vhost_out = vhost_tpl.render(
        manifest=manifest,
        container_ip=ip,
        container_port=port,
        custom_conf=custom_conf
    )

    conf_file = GATEWAY_CONF_D / f"{manifest.project_name}.conf"
    
    if dry_run:
        print(f"\n[DRY RUN] Rendered Nginx vhost config:\n{'-'*40}\n{vhost_out}\n{'-'*40}")
        print(f"🎉 [DRY RUN] Simulated deployment of {manifest.project_name} at http://{manifest.routing.address}:{manifest.routing.port}{manifest.routing.path}")
        return

    # Keep track if we overwrite an existing config so we can roll back
    old_conf_data = None
    if conf_file.exists():
        with open(conf_file, "r") as f:
            old_conf_data = f.read()

    with open(conf_file, "w") as f:
        f.write(vhost_out)
    print(f"Generated Nginx vhost config at {conf_file}")

    # 7. Reload Nginx Safety Net
    success, message = reload_nginx()
    if success:
        # Save State
        from .state_mgr import add_app_state
        add_app_state(manifest.project_name, {
            "source_dir": str(app_path),
            "port": manifest.routing.port,
            "domain": manifest.routing.domain,
            "path": manifest.routing.path
        })
        print(f"🎉 Successfully deployed {manifest.project_name} at http://{manifest.routing.address}:{manifest.routing.port}{manifest.routing.path}")
    else:
        print(f"🚨 Nginx configuration check failed. Rolling back configuration...")
        
        if old_conf_data is not None:
            # Restore previous config
            with open(conf_file, "w") as f:
                f.write(old_conf_data)
        else:
            # Delete new bad config
            os.remove(conf_file)
            
        # Try to reload Gateway back to stable state
        reload_nginx()
        
        # FIX (Bug 4): If this was a NEW deployment (no old_conf), we should also stop the container 
        # to avoid "zombie" containers blocking future binds.
        if old_conf_data is None and not dry_run:
            print(f"Cleanup: Removing failed deployment container '{manifest.project_name}'...")
            try:
                subprocess.run(["docker", "compose", "-p", manifest.project_name, "down", "-v"], cwd=app_path, capture_output=True)
            except Exception as e:
                print(f"Warning: Failed to cleanup container: {e}")

        print(f"Sub-optimal state: Docker container is running, but Nginx routing failed.\nReason: {message}")
        print("Please check your custom.conf syntax and try deploying again.")
        raise RuntimeError("Nginx Safety Net aborted deployment.")


def remove_app(app_name: str):
    print(f"Removing application '{app_name}'...")
    
    from .state_mgr import get_app_state, remove_app_state
    state = get_app_state(app_name)
    
    # 1. Stop and remove docker container
    client = get_client()
    try:
        container = client.containers.get(app_name)
        container.stop()
        container.remove(v=True)
        print(f"Docker container '{app_name}' stopped and removed.")
    except Exception as e:
        print(f"Container '{app_name}' not found or could not be removed: {e}")

    # 2. Cleanup Docker Compose (if we know the source directory)
    if state and "source_dir" in state:
        app_path = Path(state["source_dir"])
        if (app_path / "docker-compose.yaml").exists():
            print(f"Cleaning up compose project in {app_path}")
            subprocess.run(
                ["docker", "compose", "-p", app_name, "down", "-v"],
                cwd=app_path,
                capture_output=True
            )

    # 3. Delete Nginx VHost
    conf_file = GATEWAY_CONF_D / f"{app_name}.conf"
    if conf_file.exists():
        os.remove(conf_file)
        print(f"Removed Nginx config {conf_file}")
    else:
        print(f"Nginx config for '{app_name}' not found.")

    # 4. Reload Nginx
    success, _ = reload_nginx()
    if success:
        remove_app_state(app_name)
        print(f"🗑️ Successfully removed {app_name}.")
