#!/usr/bin/env bash
set -e

echo "🚀 Starting NexusDeploy Bootstrap..."

# 1. Update & Install system dependencies
if [ -f /etc/os-release ]; then
    . /etc/os-release
    if [ "$ID" = "ubuntu" ] || [ "$ID" = "debian" ]; then
        echo "📦 Installing prerequisites for $PRETTY_NAME..."
        sudo apt-get update
        sudo apt-get install -y ca-certificates curl gnupg python3-pip python3-venv git

        # Install Docker if not present
        if ! command -v docker &> /dev/null; then
            echo "🐳 Installing Docker..."
            sudo install -m 0755 -d /etc/apt/keyrings
            curl -fsSL "https://download.docker.com/linux/$ID/gpg" | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
            sudo chmod a+r /etc/apt/keyrings/docker.gpg
            echo \
              "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/$ID \
              $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
              sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
            sudo apt-get update
            sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
        else
            echo "✅ Docker is already installed."
        fi
        
        echo "👤 Adding $USER to the docker group..."
        sudo usermod -aG docker $USER
        echo "⚠️ Note: You may need to log out and back in for group changes to take effect."
    elif [ "$ID" = "arch" ]; then
        echo "📦 Installing prerequisites for Arch Linux..."
        sudo pacman -Sy --noconfirm docker docker-compose python-pip git
        sudo systemctl enable --now docker
        sudo usermod -aG docker $USER
        echo "⚠️ Note: You may need to log out and back in for group changes to take effect."
    else
        echo "❌ Unsupported OS: $PRETTY_NAME (Supported: Ubuntu/Debian/Arch)"
        exit 1
    fi
else
    echo "❌ Cannot detect OS."
    exit 1
fi

# 2. Python Environment Setup
echo "🐍 Setting up Python virtual environment..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate

echo "📦 Installing Python dependencies from pyproject.toml..."
pip install --upgrade pip
pip install -e .

# 3. Start Gateway Nginx
echo "🌐 Starting global Gateway Nginx..."
cd gateway
sudo docker compose -p nexus-gateway up -d
echo "✅ NexusDeploy Gateway is running."

echo "🎉 Bootstrap complete! Run 'source .venv/bin/activate' to use NexusDeploy."
