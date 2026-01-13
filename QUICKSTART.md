# Quick Start Guide

## For Impatient People Who Want to Get Recording ASAP

### Prerequisites Checklist
- [ ] Raspberry Pi 3B+ or 4 with Raspberry Pi OS Lite (64-bit) installed
- [ ] Behringer UCA202 connected via USB
- [ ] Network connection (Ethernet or WiFi)
- [ ] SSH access configured

### Installation (5 Minutes)

```bash
# 1. Update system
sudo apt update && sudo apt upgrade -y

# 2. Install dependencies
sudo apt install -y python3-pip ffmpeg alsa-utils sqlite3

# 3. Go to home directory and upload/clone project
cd ~
# [Upload the ilc-audio-recorder folder here]

# 4. Install Python packages
cd ~/ilc-audio-recorder
pip3 install -r requirements.txt --break-system-packages

# 5. Configure ALSA
sudo cp configs/asound.conf /etc/asound.conf
sudo alsactl kill rescan

# 6. Create recordings directory
mkdir -p ~/recordings

# 7. Install systemd service
sudo mkdir -p /var/log/ilc-audio-recorder
sudo chown pi:pi /var/log/ilc-audio-recorder
sudo cp ilc-audio-recorder.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ilc-audio-recorder
sudo systemctl start ilc-audio-recorder

# 8. Check status
sudo systemctl status ilc-audio-recorder
```

### Access the Web UI

Find your Pi's IP address:
```bash
hostname -I
```

Open in browser:
```
http://YOUR_PI_IP:5000
```

Or use hostname:
```
http://ilc-recorder.local:5000
```

### First Recording

1. Go to **Dashboard** (/)
2. Enter a recording name (optional)
3. Select duration (default: 1 hour)
4. Click **Start Recording**
5. Files will be saved to `~/recordings/`

### Verify Audio is Working

```bash
# Test UCA202 detection
arecord -l
# Should show: card 1: CODEC [USB Audio CODEC]

# Quick 5-second test recording
arecord -D hw:1 -f S16_LE -r 48000 -c 2 -d 5 test.wav

# Check file was created
ls -lh test.wav
# Should be ~1.8 MB

# Clean up
rm test.wav
```

### Troubleshooting

**Web UI not accessible?**
```bash
# Check service
sudo systemctl status ilc-audio-recorder

# Check logs
tail -f /var/log/ilc-audio-recorder/app.log
```

**UCA202 not found?**
```bash
lsusb | grep Audio
sudo reboot
```

**Recording fails?**
```bash
# Check disk space
df -h ~/recordings

# Test FFmpeg manually
ffmpeg -f alsa -i hw:1 -t 5 \
  -filter_complex "[0:a]channelsplit=channel_layout=stereo[left][right]" \
  -map "[left]" -acodec pcm_s16le -ar 48000 test_A.wav \
  -map "[right]" -acodec pcm_s16le -ar 48000 test_B.wav
```

### Common Tasks

**Stop service:**
```bash
sudo systemctl stop ilc-audio-recorder
```

**Restart service:**
```bash
sudo systemctl restart ilc-audio-recorder
```

**View logs:**
```bash
tail -f /var/log/ilc-audio-recorder/app.log
```

**Find recordings:**
```bash
ls -lh ~/recordings/
```

That's it! You're recording. For detailed documentation, see [README.md](README.md).
