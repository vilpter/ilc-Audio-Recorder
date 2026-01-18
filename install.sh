#!/bin/bash
# Automated Installation Script for Audio Recorder
# Handles username detection and configuration automatically
# Supports both fresh install and upgrade modes

set -e  # Exit on error

echo "=========================================="
echo "Audio Recorder - Installation Script"
echo "=========================================="
echo ""

# Detect current user
CURRENT_USER=$(whoami)
CURRENT_HOME=$(eval echo ~$CURRENT_USER)

echo "Detected configuration:"
echo "  Username: $CURRENT_USER"
echo "  Home directory: $CURRENT_HOME"
echo ""

# Check if running as root
if [ "$CURRENT_USER" = "root" ]; then
    echo "❌ Please run this script as your normal user, not as root!"
    echo "   Usage: ./install.sh"
    exit 1
fi

# Define paths for existing installation detection
INSTALL_DIR="$CURRENT_HOME/audio-recorder"
SERVICE_FILE="/etc/systemd/system/audio-recorder.service"
ASOUND_CONF="/etc/asound.conf"
UDEV_RULE="/etc/udev/rules.d/85-usb-audio.rules"
LOG_DIR="/var/log/audio-recorder"

# Check for existing installation
EXISTING_INSTALL=false
if [ -d "$INSTALL_DIR" ] || [ -f "$SERVICE_FILE" ]; then
    EXISTING_INSTALL=true
fi

# Installation mode selection
INSTALL_MODE=""
if [ "$EXISTING_INSTALL" = true ]; then
    echo "=========================================="
    echo "Existing installation detected!"
    echo "=========================================="
    echo ""
    echo "Please select an installation option:"
    echo ""
    echo "  1) Fresh Install"
    echo "     - Removes existing installation completely"
    echo "     - Overwrites all configuration files"
    echo "     - Use this if you want to start from scratch"
    echo ""
    echo "  2) Upgrade"
    echo "     - Updates application code only"
    echo "     - Preserves existing configuration files:"
    echo "       * /etc/asound.conf (ALSA config)"
    echo "       * /etc/udev/rules.d/85-usb-audio.rules"
    echo "       * Systemd service customizations"
    echo "     - Preserves existing recordings and logs"
    echo ""
    while true; do
        read -p "Enter your choice [1 or 2]: " choice
        case $choice in
            1)
                INSTALL_MODE="fresh"
                echo ""
                echo "Selected: Fresh Install"
                echo ""
                read -p "⚠️  This will delete existing configuration. Continue? [y/N] " -n 1 -r
                echo
                if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                    echo "Installation cancelled."
                    exit 0
                fi
                break
                ;;
            2)
                INSTALL_MODE="upgrade"
                echo ""
                echo "Selected: Upgrade (preserving configuration)"
                break
                ;;
            *)
                echo "Invalid choice. Please enter 1 or 2."
                ;;
        esac
    done
else
    INSTALL_MODE="fresh"
    echo "No existing installation detected. Performing fresh install."
fi
echo ""

# Stop existing service if running (for both modes)
if systemctl is-active --quiet audio-recorder 2>/dev/null; then
    echo "Stopping existing audio-recorder service..."
    sudo systemctl stop audio-recorder
    echo "  ✓ Service stopped"
    echo ""
fi

# Check prerequisites
echo "Checking prerequisites..."

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install it first:"
    echo "   sudo apt install python3"
    exit 1
fi
echo "  ✓ Python 3 found"

# Check FFmpeg
if ! command -v ffmpeg &> /dev/null; then
    echo "❌ FFmpeg not found. Please install it first:"
    echo "   sudo apt install ffmpeg"
    exit 1
fi
echo "  ✓ FFmpeg found"

# Check ALSA
if ! command -v arecord &> /dev/null; then
    echo "❌ ALSA tools not found. Please install them first:"
    echo "   sudo apt install alsa-utils"
    exit 1
fi
echo "  ✓ ALSA tools found"

echo ""

# Install Python dependencies
echo "Installing Python dependencies..."
pip3 install --break-system-packages -r requirements.txt
echo "  ✓ Python packages installed"
echo ""

# Configure ALSA (skip in upgrade mode if config exists)
if [ "$INSTALL_MODE" = "upgrade" ] && [ -f "$ASOUND_CONF" ]; then
    echo "Preserving existing ALSA configuration..."
    echo "  ✓ Kept existing /etc/asound.conf"
else
    echo "Configuring ALSA for UCA202..."
    sudo cp configs/asound.conf /etc/asound.conf
    echo "  ✓ ALSA configuration installed"
fi
echo ""

# Optional: udev rule (skip in upgrade mode if rule exists)
if [ "$INSTALL_MODE" = "upgrade" ] && [ -f "$UDEV_RULE" ]; then
    echo "Preserving existing udev rule..."
    echo "  ✓ Kept existing udev rule"
else
    read -p "Install udev rule for consistent device numbering? (recommended) [Y/n] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        sudo cp configs/85-usb-audio.rules /etc/udev/rules.d/
        sudo udevadm control --reload-rules
        sudo udevadm trigger
        echo "  ✓ udev rule installed"
    else
        echo "  ⊘ udev rule skipped"
    fi
fi
echo ""

# Detect and configure audio device (skip in upgrade mode)
if [ "$INSTALL_MODE" = "upgrade" ]; then
    echo "Skipping audio device detection (upgrade mode)..."
    echo "  ✓ Existing audio configuration preserved"
else
    echo "Detecting audio devices..."
    ./configure_audio.sh
fi
echo ""

# Create log directory (safe for both modes - mkdir -p is idempotent)
if [ ! -d "$LOG_DIR" ]; then
    echo "Creating log directory..."
    sudo mkdir -p /var/log/audio-recorder
    sudo chown -R $CURRENT_USER:$CURRENT_USER /var/log/audio-recorder
    echo "  ✓ Log directory created"
else
    echo "Log directory already exists..."
    echo "  ✓ Preserving existing logs"
fi
echo ""

# Generate systemd service file with current user (skip in upgrade mode if exists)
if [ "$INSTALL_MODE" = "upgrade" ] && [ -f "$SERVICE_FILE" ]; then
    echo "Preserving existing systemd service file..."
    echo "  ✓ Kept existing service configuration"
    # Still reload daemon in case application files changed
    sudo systemctl daemon-reload
else
    echo "Generating systemd service file..."
    cat > /tmp/audio-recorder.service <<EOF
[Unit]
Description=Audio Recorder - Dual-Mono Recording System
After=network.target sound.target
Wants=network.target

[Service]
Type=simple
User=$CURRENT_USER
Group=$CURRENT_USER
WorkingDirectory=$CURRENT_HOME/audio-recorder
Environment="PATH=/usr/local/bin:/usr/bin:/bin"
ExecStart=/usr/bin/python3 $CURRENT_HOME/audio-recorder/app.py

# Restart policy
Restart=always
RestartSec=10

# Logging
StandardOutput=append:/var/log/audio-recorder/app.log
StandardError=append:/var/log/audio-recorder/error.log

# Security settings
NoNewPrivileges=true
PrivateTmp=true

# Resource limits
LimitNOFILE=4096

[Install]
WantedBy=multi-user.target
EOF

    sudo cp /tmp/audio-recorder.service /etc/systemd/system/
    rm /tmp/audio-recorder.service
    echo "  ✓ Service file generated for user: $CURRENT_USER"
fi
echo ""

# Install and start service
if [ "$INSTALL_MODE" = "upgrade" ]; then
    echo "Restarting systemd service..."
    sudo systemctl daemon-reload
    sudo systemctl restart audio-recorder
    echo "  ✓ Service restarted with updated code"
else
    echo "Installing systemd service..."
    sudo systemctl daemon-reload
    sudo systemctl enable audio-recorder
    sudo systemctl start audio-recorder
    echo "  ✓ Service installed and started"
fi
echo ""

# Wait for service to start
echo "Waiting for service to start..."
sleep 3

# Check service status
if sudo systemctl is-active --quiet audio-recorder; then
    echo "✓ Service is running!"
else
    echo "⚠ Service may have issues. Checking status..."
    sudo systemctl status audio-recorder --no-pager
fi
echo ""

# Get IP address
IP_ADDR=$(hostname -I | awk '{print $1}')
HOSTNAME=$(hostname)

echo "=========================================="
if [ "$INSTALL_MODE" = "upgrade" ]; then
    echo "✓ Upgrade Complete!"
else
    echo "✓ Installation Complete!"
fi
echo "=========================================="
echo ""

if [ "$INSTALL_MODE" = "upgrade" ]; then
    echo "Preserved configurations:"
    [ -f "$ASOUND_CONF" ] && echo "  ✓ /etc/asound.conf"
    [ -f "$UDEV_RULE" ] && echo "  ✓ /etc/udev/rules.d/85-usb-audio.rules"
    [ -f "$SERVICE_FILE" ] && echo "  ✓ /etc/systemd/system/audio-recorder.service"
    echo ""
    echo "Updated components:"
    echo "  ✓ Python packages"
    echo "  ✓ Application code"
    echo ""
fi

echo "Access the web interface at:"
echo "  http://$IP_ADDR:5000"
echo "  or"
echo "  http://$HOSTNAME.local:5000"
echo ""

if [ "$INSTALL_MODE" = "upgrade" ]; then
    echo "Next steps:"
    echo "  1. Verify the web UI loads correctly"
    echo "  2. Test a recording to confirm functionality"
    echo ""
else
    echo "Next steps:"
    echo "  1. Open web UI in your browser"
    echo "  2. Test a recording from the Dashboard"
    echo "  3. Create your first scheduled recording"
    echo ""
fi

echo "Logs are available at:"
echo "  /var/log/audio-recorder/app.log"
echo "  /var/log/audio-recorder/error.log"
echo ""
echo "Manage the service with:"
echo "  sudo systemctl status audio-recorder"
echo "  sudo systemctl restart audio-recorder"
echo "  sudo systemctl stop audio-recorder"
echo ""
