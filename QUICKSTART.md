# Quick Start Guide

## For Impatient People Who Want to Get Recording ASAP

### Prerequisites Checklist
- [ ] Raspberry Pi 3B+ or 4 with Raspberry Pi OS Lite (64-bit) installed
- [ ] Behringer UCA202 connected via USB
- [ ] Network connection (Ethernet or WiFi)
- [ ] SSH access configured

### Installation (Automated)

```bash
# 1. Clone or download the project
cd ~
git clone https://github.com/vilpter/ilc-Audio-Recorder.git audio-recorder
cd audio-recorder

# 2. Run the installer (handles everything)
./install.sh

# 3. Access web UI
# Open browser to: http://<pi-ip>:5000
```

That's it! The installer handles:
- System dependencies (Python, FFmpeg, ALSA)
- Python packages
- ALSA configuration
- Recordings directory
- Systemd service setup
- Log directories

### Access the Web UI

Find your Pi's IP address:
```bash
hostname -I
```

Open in browser:
```
http://YOUR_PI_IP:5000
```

### First Recording

1. Go to **Dashboard** (/)
2. Select duration (default: 1 hour)
3. Click **Start Recording**
4. Files will be saved to `~/recordings/`

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
# Run the fix script
./fix_service.sh

# Or manually check
sudo systemctl status audio-recorder
tail -f /var/log/audio-recorder/app.log
```

**UCA202 not found?**
```bash
# Run audio configuration helper
./configure_audio.sh

# Or manually check
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
  -map "[left]" -acodec pcm_s16le -ar 48000 test_L.wav \
  -map "[right]" -acodec pcm_s16le -ar 48000 test_R.wav
```

### Common Tasks

**Stop service:**
```bash
sudo systemctl stop audio-recorder
```

**Restart service:**
```bash
sudo systemctl restart audio-recorder
```

**View logs:**
```bash
tail -f /var/log/audio-recorder/app.log
```

**Find recordings:**
```bash
ls -lh ~/recordings/
```

### Configuration

Access **Settings** page in the web UI to:
- Configure audio device (auto-detect or manual)
- Customize recording filename format (channel suffixes)
- Export/import schedules and configuration
- Backup and restore settings

For detailed documentation, see [README.md](README.md).
