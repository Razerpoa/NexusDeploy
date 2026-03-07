import docker
from docker.errors import NotFound, APIError
from typing import List, Tuple
from .schema import NetworkConfig, VolumeConfig

def get_client():
    return docker.from_env()

def ensure_network_exists(network_cfg: NetworkConfig):
    client = get_client()
    try:
        client.networks.get(network_cfg.name)
        print(f"Network '{network_cfg.name}' already exists.")
    except NotFound:
        print(f"Creating network '{network_cfg.name}' (driver: {network_cfg.driver})...")
        try:
            client.networks.create(name=network_cfg.name, driver=network_cfg.driver)
            print(f"Network '{network_cfg.name}' created.")
        except APIError as e:
            print(f"Failed to create network '{network_cfg.name}': {e}")
            raise

def ensure_volume_exists(volume_cfg: VolumeConfig):
    client = get_client()
    try:
        client.volumes.get(volume_cfg.name)
        print(f"Volume '{volume_cfg.name}' already exists.")
    except NotFound:
        print(f"Creating volume '{volume_cfg.name}'...")
        try:
            client.volumes.create(name=volume_cfg.name)
            print(f"Volume '{volume_cfg.name}' created.")
        except APIError as e:
            print(f"Failed to create volume '{volume_cfg.name}': {e}")
            raise

import socket
import time
from .logger import logger

def is_port_available(address: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((address, port))
            return True
        except socket.error:
            return False

def find_available_port(address: str, start_port: int = 9000) -> int:
    port = start_port
    while not is_port_available(address, port):
        port += 1
        if port > 65535:
            raise RuntimeError("No available ports found")
    return port

def wait_for_container_health(project_name: str, timeout: int = 30):
    client = get_client()
    start_time = time.time()
    print(f"Waiting for {project_name} to be healthy...")
    
    while time.time() - start_time < timeout:
        try:
            container = client.containers.get(project_name)
            health = container.attrs.get('State', {}).get('Health', {}).get('Status')
            status = container.attrs.get('State', {}).get('Status')
            
            # If a healthcheck is defined, wait for 'healthy'
            if health:
                if health == 'healthy':
                    print(f"Container {project_name} is healthy.")
                    return True
                elif health == 'unhealthy':
                    raise RuntimeError(f"Container {project_name} is unhealthy.")
            # If no healthcheck, just wait for 'running'
            elif status == 'running':
                print(f"Container {project_name} is running.")
                return True
                
        except NotFound:
            pass
        time.sleep(1)
    
    raise TimeoutError(f"Timed out waiting for {project_name} to start.")

def get_container_logs(project_name: str, tail: int = 100):
    client = get_client()
    try:
        container = client.containers.get(project_name)
        return container.logs(tail=tail).decode('utf-8')
    except NotFound:
        return f"Container {project_name} not found."

def prune_resources():
    client = get_client()
    print("Pruning unused Docker resources...")
    networks = client.networks.prune()
    volumes = client.volumes.prune()
    return networks, volumes

def pre_flight_checks(networks: List[NetworkConfig], volumes: List[VolumeConfig]):
    client = get_client()
    client.ping()  # Ensure docker daemon is accessible
    
    for net in networks:
        ensure_network_exists(net)
        
    for vol in volumes:
        ensure_volume_exists(vol)

def get_gateway_container():
    client = get_client()
    try:
        return client.containers.get("nexus-gateway")
    except NotFound:
        return None

def reload_nginx():
    gateway = get_gateway_container()
    if not gateway:
        print("Gateway container 'nexus-gateway' not found. Cannot reload Nginx.")
        return False
    
    print("Reloading Nginx in gateway container...")
    exit_code, output = gateway.exec_run("nginx -s reload")
    if exit_code == 0:
        print("Nginx reloaded successfully.")
        return True
    else:
        print(f"Failed to reload Nginx: {output.decode('utf-8')}")
        return False

def get_container_ip_and_port(project_name: str):
    client = get_client()
    try:
        container = client.containers.get(project_name)
        # We need the inner IP. If it's connected to a network, find its IP there.
        # Nginx gateway is on host mode. However, docker-compose sets up a custom network for the app 
        # or puts it in 'default' bridge.
        # Since nexus-gateway is network_mode: host, it can reach bridge IPs directly in Linux.
        
        # Let's inspect the networks
        networks = container.attrs['NetworkSettings']['Networks']
        if not networks:
            return None, None
            
        # Get the first network's IP
        first_network = list(networks.values())[0]
        ip_addr = first_network['IPAddress']
        
        # Usually we proxy to the lowest exposed port or a specific one. Let's assume port 80 if exposed, else the first exposed.
        ports = container.attrs['Config']['ExposedPorts']
        port = None
        if ports:
            port_strings = list(ports.keys())
            # prioritize 80/tcp
            if '80/tcp' in port_strings:
                port = 80
            else:
                port = int(port_strings[0].split('/')[0])
                
        return ip_addr, port
    except Exception as e:
        print(f"Error getting container info for {project_name}: {e}")
        return None, None

def get_managed_containers():
    client = get_client()
    # Find all generic containers we manage (assuming they're created via project_name and not marked deeply, 
    # but we can filter via something if needed. Here we just return all running user containers except gateway)
    managed = []
    containers = client.containers.list()
    for c in containers:
        if c.name != "nexus-gateway" and not c.name.startswith("system_"):
            # For simplicity, returning just name/status right now
            managed.append({
                "name": c.name,
                "status": c.status,
                "id": c.short_id
            })
    return managed
