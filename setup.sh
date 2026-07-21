#!/usr/bin/env bash
# Unified setup script with OS package manager auto-installation for cloudflared

set -e
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE_DIR"

# Check if cloudflared is installed
if ! command -v cloudflared &> /dev/null; then
    INSTALL_ENABLED="true"
    # Try parsing config.toml if it exists
    if [ -f "config.toml" ]; then
        INSTALL_ENABLED=$(python3 -c "
try:
    import tomllib
    with open('config.toml', 'rb') as f:
        cfg = tomllib.load(f)
        val = cfg.get('tunnel', {}).get('install_if_missing', True)
        print(str(val).lower())
except Exception:
    print('true')
" 2>/dev/null || echo "true")
    fi

    if [ "$INSTALL_ENABLED" = "true" ]; then
        echo "[INFO] cloudflared is missing. Attempting auto-installation..."
        
        # OS Detection
        if [ -f /etc/os-release ]; then
            . /etc/os-release
            OS_ID=$ID
            OS_LIKE=$ID_LIKE
        else
            OS_ID=$(uname -s)
            OS_LIKE=""
        fi

        # Determine architecture
        ARCH=$(uname -m)

        if command -v pacman &> /dev/null; then
            echo "[INFO] Arch Linux detected. Installing cloudflared..."
            sudo pacman -S --noconfirm cloudflared || {
                echo "[WARN] Automatic installation via pacman failed."
                echo "Please install cloudflared manually: sudo pacman -S cloudflared"
            }
        elif command -v apt-get &> /dev/null; then
            echo "[INFO] Debian/Ubuntu/Raspberry Pi OS detected. Installing cloudflared..."
            DEB_ARCH="amd64"
            if [ "$ARCH" = "x86_64" ]; then
                DEB_ARCH="amd64"
            elif [ "$ARCH" = "aarch64" ]; then
                DEB_ARCH="arm64"
            elif [[ "$ARCH" =~ armv7* ]] || [ "$ARCH" = "armv6l" ]; then
                DEB_ARCH="arm"
            fi
            
            DEB_URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${DEB_ARCH}.deb"
            TEMP_DEB=$(mktemp /tmp/cloudflared-XXXXXX.deb)
            echo "[INFO] Downloading cloudflared deb from $DEB_URL..."
            if curl -L -o "$TEMP_DEB" "$DEB_URL"; then
                sudo dpkg -i "$TEMP_DEB" || {
                    echo "[INFO] Resolving missing dependencies..."
                    sudo apt-get install -f -y
                }
                rm -f "$TEMP_DEB"
            else
                echo "[WARN] Failed to download deb package."
                echo "Please install cloudflared manually: curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${DEB_ARCH}.deb && sudo dpkg -i cloudflared.deb"
            fi
        elif command -v dnf &> /dev/null; then
            echo "[INFO] Fedora/RHEL detected. Installing cloudflared..."
            RPM_ARCH="x86_64"
            if [ "$ARCH" = "aarch64" ]; then
                RPM_ARCH="aarch64"
            fi
            RPM_URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${RPM_ARCH}.rpm"
            echo "[INFO] Installing cloudflared rpm from $RPM_URL..."
            sudo dnf install -y "$RPM_URL" || {
                echo "[WARN] Automatic installation via dnf failed."
                echo "Please install cloudflared manually: sudo dnf install -y https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${RPM_ARCH}.rpm"
            }
        else
            echo "[WARN] Unsupported platform or package manager."
            echo "Please install cloudflared manually from: https://github.com/cloudflare/cloudflared/releases"
        fi
    else
        echo "[INFO] cloudflared is missing, and auto-installation is disabled (install_if_missing = false)."
        echo "Please install cloudflared manually from https://github.com/cloudflare/cloudflared/releases"
    fi
else
    echo "[INFO] cloudflared is already installed."
fi

# Run the standard CLI setup
./camz setup
