# NexusDeploy Orchestrator

NexusDeploy is a zero-touch "out-of-the-box" Docker orchestration system designed to turn any Linux machine into a fully automated application hosting platform. It provisions your server, manages Docker infrastructure, and provides a powerful Typer-based CLI for deploying containerized applications with dynamic Nginx reverse-proxying.

---

## 🚀 Features

- **Automated Bootstrapping:** A single shell script (`bootstrap.sh`) installs Docker, provisions a Python virtual environment, and starts the persistent Nginx ingress Gateway.
- **Declarative Deployments:** Define your whole app's infrastructure (networks, volumes, routing) in a simple `manifest.yaml`.
- **Dynamic Routing & Path Stripping:** Built-in Nginx proxying handles complex routing like `http://address:port/path` automatically mapping to the container's root.
- **Dynamic Port Allocation:** Omit the `port` in your manifest, and NexusDeploy will automatically find an available open port on your host (starting from 9000).
- **Application Health Awareness:** The CLI actively waits for Docker container healthchecks to pass before finalizing deployment.
- **Multi-Domain Support:** Host multiple applications on the same IP and port using standard Nginx `server_name` virtual hosting by defining a `domain` in the manifest.
- **Log Management & Pruning:** Built-in CLI commands to tail application logs (`nexus logs`) and clean up unused Docker resources (`nexus prune`).

---

## 🛠️ Installation

NexusDeploy is designed to be installed on Debian, Ubuntu, or Arch Linux hosts.

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd nexus-deploy
   ```

2. **Run the bootstrapper:**
   This script will verify system requirements, install Docker if missing, configure permissions, format your Python environment, and start the Gateway.
   ```bash
   ./bootstrap.sh
   ```

3. **Activate the environment:**
   To use the `nexus` CLI, activate the virtual environment created during bootstrap:
   ```bash
   source .venv/bin/activate
   ```

---

## 📦 Usage

### Deploying an Application
Structure your application in a dedicated folder containing a `manifest.yaml` file (and optionally a `custom.conf` file for Nginx overrides).

```bash
nexus deploy apps/sample-app/
```

### Listing Active Deployments
View all containers currently managed by NexusDeploy:
```bash
nexus list
```

### Viewing Logs
Stream the logs of a deployed application:
```bash
nexus logs <app-name>
# Example: nexus logs hello-world
```

### Removing an Application
Safely tear down a deployment and remove its Nginx configuration:
```bash
nexus remove <app-name>
```

### Infrastructure Cleanup
Remove unused Docker networks and volumes dangling on your host:
```bash
nexus prune
```

---

## 📄 Configuration Reference

To learn how to write the `manifest.yaml` file, define infrastructure, or use `custom.conf` to inject Nginx rules, please read the [MANIFEST_SPEC.md](./MANIFEST_SPEC.md). This guide acts as the complete reference for both developers and AI assistants.

---

## 🚨 Troubleshooting
If a deployment fails, or a command exits unexpectedly, a detailed Python stack trace is saved to `nexus-error.log` in your current working directory. You can provide this file when opening issues or debugging container startup sequences.
