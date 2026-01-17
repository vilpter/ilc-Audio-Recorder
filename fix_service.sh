#!/bin/bash
# Fix systemd service for current user

echo "=========================================="
echo "Audio Recorder - Service Configuration Fix"
echo "=========================================="
echo ""

# Get current username
CURRENT_USER=$(whoami)
echo "Current user: $CURRENT_USER"
echo ""

# Path to service file
SERVICE_FILE="/etc/systemd/system/audio-recorder.service"

if [ ! -f "$SERVICE_FILE" ]; then
    echo "❌ Service file not found at $SERVICE_FILE"
    echo "   Please install the service first."
    exit 1
fi

echo "Updating service file..."
echo ""

# Create temp service file with correct user
sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=Audio Recorder - Dual-Mono Recording System
After=network.target sound.target
Wants=network.target

[Service]
Type=simple
User=$CURRENT_USER
Group=$CURRENT_USER
WorkingDirectory=/home/$CURRENT_USER/audio-recorder
Environment="PATH=/usr/local/bin:/usr/bin:/bin"
ExecStart=/usr/bin/python3 /home/$CURRENT_USER/audio-recorder/app.py

# Restart policy
Restart=always
RestartSec=10

# Logging
StandardOutput=append:/var/log/audio-recorder/app.log
StandardError=append:/var/log/audio-recorder/error.log

# Security settings (optional but recommended)
NoNewPrivileges=true
PrivateTmp=true

# Resource limits
LimitNOFILE=4096

[Install]
WantedBy=multi-user.target
EOF

echo "✓ Service file updated with user: $CURRENT_USER"
echo ""

# Fix log directory ownership
echo "Fixing log directory permissions..."
sudo mkdir -p /var/log/audio-recorder
sudo chown -R $CURRENT_USER:$CURRENT_USER /var/log/audio-recorder
echo "✓ Log directory ownership fixed"
echo ""

# Reload systemd
echo "Reloading systemd daemon..."
sudo systemctl daemon-reload
echo "✓ Systemd reloaded"
echo ""

# Restart service
echo "Restarting audio-recorder service..."
sudo systemctl restart audio-recorder
echo ""

# Wait a moment for service to start
sleep 3

# Check status
echo "=========================================="
echo "Service Status:"
echo "=========================================="
sudo systemctl status audio-recorder --no-pager
echo ""

# Check if service is running
if sudo systemctl is-active --quiet audio-recorder; then
    echo "✓ Service is running!"
    echo ""
    
    # Get IP address
    IP_ADDR=$(hostname -I | awk '{print $1}')
    
    echo "=========================================="
    echo "✓ Configuration Complete!"
    echo "=========================================="
    echo ""
    echo "Access web UI at:"
    echo "  http://$IP_ADDR:5000"
    echo "  or"
    echo "  http://$(hostname).local:5000"
    echo ""
else
    echo "❌ Service failed to start"
    echo ""
    echo "Check logs for errors:"
    echo "  sudo journalctl -u audio-recorder -n 50"
    echo "  cat /var/log/audio-recorder/error.log"
    echo ""
    echo "Or try running manually to see errors:"
    echo "  cd ~/audio-recorder"
    echo "  python3 app.py"
    echo ""
fi
