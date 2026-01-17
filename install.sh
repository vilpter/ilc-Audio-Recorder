#!/bin/bash
# Automated Installation Script for Audio Recorder
# Handles username detection and configuration automatically

set -e  # Exit on error

echo "=========================================="
echo "Audio Recorder - Automated Installation"
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

# Configure ALSA
echo "Configuring ALSA for UCA202..."
sudo cp configs/asound.conf /etc/asound.conf
echo "  ✓ ALSA configuration installed"
echo ""

# Optional: udev rule
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
echo ""

# Detect and configure audio device
echo "Detecting audio devices..."
./configure_audio.sh
echo ""

# Create log directory
echo "Creating log directory..."
sudo mkdir -p /var/log/audio-recorder
sudo chown -R $CURRENT_USER:$CURRENT_USER /var/log/audio-recorder
echo "  ✓ Log directory created"
echo ""

# Generate systemd service file with current user
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
echo ""

# Install and start service
echo "Installing systemd service..."
sudo systemctl daemon-reload
sudo systemctl enable audio-recorder
sudo systemctl start audio-recorder
echo "  ✓ Service installed and started"
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
echo "✓ Installation Complete!"
echo "=========================================="
echo ""
echo "Access the web interface at:"
echo "  http://$IP_ADDR:5000"
echo "  or"
echo "  http://$HOSTNAME.local:5000"
echo ""
echo "Next steps:"
echo "  1. Open web UI in your browser"
echo "  2. Test a recording from the Dashboard"
echo "  3. Create your first scheduled recording"
echo ""
echo "Logs are available at:"
echo "  /var/log/audio-recorder/app.log"
echo "  /var/log/audio-recorder/error.log"
echo ""
echo "Manage the service with:"
echo "  sudo systemctl status audio-recorder"
echo "  sudo systemctl restart audio-recorder"
echo "  sudo systemctl stop audio-recorder"
echo ""
