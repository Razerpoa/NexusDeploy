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

def deploy_app(app_dir: str):
    app_path = Path(app_dir).resolve()
    print(f"Deploying from {app_path}...")
    
    # 1. Validation
    manifest = load_manifest(app_path)
    print(f"Validated manifest for project: {manifest.project_name}")

    # 2. Port Allocation
    if manifest.routing.port is None:
        print("No port specified. Finding available port...")
        manifest.routing.port = find_available_port(manifest.routing.address)
        print(f"Assigned dynamic port: {manifest.routing.port}")
    elif not is_port_available(manifest.routing.address, manifest.routing.port):
        raise RuntimeError(f"Port {manifest.routing.port} is already in use on {manifest.routing.address}")

    # 3. Infrastructure
    pre_flight_checks(manifest.infrastructure.networks, manifest.infrastructure.volumes)

    # 4. Generate docker-compose.yaml
    compose_tpl = env.get_template("app-compose.j2")
    compose_out = compose_tpl.render(manifest=manifest)
    
    compose_file = app_path / "docker-compose.yaml"
    with open(compose_file, "w") as f:
        f.write(compose_out)
    print(f"Generated {compose_file}")

    # 5. Start Container via Docker Compose
    print(f"Starting docker-compose for {manifest.project_name}...")
    subprocess.run(
        ["docker", "compose", "-p", manifest.project_name, "up", "-d"],
        cwd=app_path,
        check=True
    )
    
    # Wait for container to be ready
    wait_for_container_health(manifest.project_name)

    # 6. Generate Nginx Route
    ip, port = get_container_ip_and_port(manifest.project_name)
    if not ip:
        print(f"Warning: Could not determine internal IP for container {manifest.project_name}.")
        # Use service name as a fallback? With default bridge, they aren't resolvable by name to host net gateway.
        # But we assume get_container_ip works.
        ip = "127.0.0.1"
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
    with open(conf_file, "w") as f:
        f.write(vhost_out)
    print(f"Generated Nginx vhost config at {conf_file}")

    # 7. Reload Nginx
    success = reload_nginx()
    if success:
        print(f"🎉 Successfully deployed {manifest.project_name} at http://{manifest.routing.address}:{manifest.routing.port}{manifest.routing.path}")
    else:
        print(f"⚠️ Deployment finished, but failed to reload Nginx Gateway. Please check `nexus-gateway` logs.")

def remove_app(app_name: str):
    print(f"Removing application '{app_name}'...")
    
    # 1. Stop and remove docker container
    client = get_client()
    try:
        container = client.containers.get(app_name)
        container.stop()
        container.remove(v=True)
        print(f"Docker container '{app_name}' stopped and removed.")
    except Exception as e:
        print(f"Container '{app_name}' not found or could not be removed: {e}")

    # Try to remove the compose project natively if possible, but SDK removal is usually enough
    # To fully clean up compose networks, we might leave dangling "default" networks, 
    # but that's typical without the original dir.
    
    # 2. Delete Nginx VHost
    conf_file = GATEWAY_CONF_D / f"{app_name}.conf"
    if conf_file.exists():
        os.remove(conf_file)
        print(f"Removed Nginx config {conf_file}")
    else:
        print(f"Nginx config for '{app_name}' not found.")

    # 3. Reload Nginx
    success = reload_nginx()
    if success:
        print(f"🗑️ Successfully removed {app_name}.")
