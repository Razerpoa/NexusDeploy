# NexusDeploy Configuration Guide

This document is designed to guide developers (and AI assistants) on how to properly construct the `manifest.yaml` file and leverage custom configurations in the NexusDeploy orchestrator.

## 1. Directory Structure
A typical application deployed via NexusDeploy should look like this:
```text
my-awesome-app/
├── manifest.yaml        # (Required) The core configuration file
└── custom.conf          # (Optional) Custom Nginx server block directives
```

To deploy the application, pass the **directory path** to the CLI:
```bash
nexus deploy my-awesome-app/
```

---

## 2. The `manifest.yaml` Specification

The `manifest.yaml` uses a strict schema validated by Pydantic. Here is the complete feature set:

```yaml
# ---------------------------------------------------------
# CORE IDENTITY
# ---------------------------------------------------------
project_name: "my-awesome-app"  # (Required) Unique identifier used for the Docker container and Nginx config file.
image: "nginx:alpine"           # (Required) The Docker image to pull and deploy.

# ---------------------------------------------------------
# ROUTING CONFIGURATION
# ---------------------------------------------------------
routing:
  address: "0.0.0.0"            # (Optional) Bind IP address for the Nginx proxy. Defaults to 0.0.0.0.
  
  # WARNING: If port is omitted, NexusDeploy will auto-assign 
  # an available host port starting from 9000.
  port: 8080                    # (Optional) The host port Nginx will listen on.
  
  path: "/dashboard"            # (Optional) The URL subpath. Nginx uses `rewrite` to strip this path 
                                # before proxying to the container's root `/`. Defaults to `/`.
                                
  domain: "myapp.local"         # (Optional) The domain name for Nginx Virtual Hosting (`server_name`). 
                                # Defaults to `_` (catch-all for the IP).
                                
  ssl: false                    # (Optional) Reserved for future HTTPS implementations. Defaults to false.

# ---------------------------------------------------------
# INFRASTRUCTURE MANAGEMENT
# NexusDeploy uses the Docker SDK to automatically 
# create these resources if they do not exist.
# ---------------------------------------------------------
infrastructure:
  networks:                     # (Optional) List of Docker networks to attach.
    - name: "backend-net"       # The name of the network
      driver: "bridge"          # The network driver (defaults to bridge)
      
  volumes:                      # (Optional) List of Docker volumes to mount.
    - name: "app-data"          # The name of the Docker volume
      mount_path: "/usr/share/nginx/html" # The absolute path inside the container

# ---------------------------------------------------------
# ENVIRONMENT VARIABLES
# ---------------------------------------------------------
env_vars:                       # (Optional) Key-value pairs passed directly to the container.
  DEBUG: "true"
  API_KEY: "secret123"
```

---

## 3. Advanced Nginx Overrides (`custom.conf`)

NexusDeploy generates an Nginx Virtual Host based on the manifest. If you place a file named `custom.conf` in the same directory as your `manifest.yaml`, its contents will be injected directly into the bottom of the generated Nginx `server { ... }` block.

**Example `custom.conf`:**
```nginx
# Increase file upload size for this specific application
client_max_body_size 50M;

# Add custom security headers
add_header X-Frame-Options "SAMEORIGIN";
add_header X-Content-Type-Options "nosniff";

# Deny access to hidden files
location ~ /\. {
    deny all;
}
```

### AI Assistant Instructions
When generating a new application for a user using NexusDeploy:
1. Always create a directory for the app.
2. Always generate a valid `manifest.yaml` using the schema above.
3. If the user does not specify a port, omit the `port` field in the manifest so NexusDeploy dynamically allocates one.
4. If the user requires specific Nginx directives (like websockets or max body size), generate a `custom.conf` file alongside the manifest.
