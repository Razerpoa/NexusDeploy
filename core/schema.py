from typing import Dict, List, Optional
from pydantic import BaseModel, Field

class RoutingConfig(BaseModel):
    address: str = "0.0.0.0"
    port: Optional[int] = None
    path: str = "/"
    domain: str = "_"

class NetworkConfig(BaseModel):
    name: str
    driver: str = "bridge"

class VolumeConfig(BaseModel):
    name: str
    mount_path: str

class InfrastructureConfig(BaseModel):
    networks: Optional[List[NetworkConfig]] = Field(default_factory=list)
    volumes: Optional[List[VolumeConfig]] = Field(default_factory=list)

class Manifest(BaseModel):
    project_name: str
    image: str
    routing: RoutingConfig
    infrastructure: InfrastructureConfig = Field(default_factory=InfrastructureConfig)
    env_vars: Optional[Dict[str, str]] = Field(default_factory=dict)
