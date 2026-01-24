# Quick Start Guide

## For Impatient People Who Want to Get Recording ASAP

### Prerequisites Checklist

**Required (Audio):**
- [ ] Raspberry Pi 3B+ or 4 with Raspberry Pi OS Lite (64-bit) installed
- [ ] Behringer UCA202 connected via USB
- [ ] Network connection (Ethernet or WiFi)
- [ ] SSH access configured

**Optional (Video):**
- [ ] PTZOptics camera on same network
- [ ] USB drive for video storage (mounted at `/mnt/usb_recorder`)

### Installation (New Install)

```bash
cd ~
git clone https://github.com/vilpter/ilc-Audio-Recorder.git audio-recorder
cd audio-recorder
./install.sh
```

### Upgrading (Existing Install)

```bash
cd ~/audio-recorder
git pull
./install.sh
# Select "Upgrade" when prompted
```

The installer handles:
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

### First Audio Recording

1. Go to **Schedule** (/) - the calendar view
2. Click on a day to create a schedule
3. Set duration (default: 1 hour)
4. Click **Create Recording**
5. Audio files will be saved to `~/recordings/`

### Immediate Recording

1. Go to **New/In Progress** page
2. Set duration (minutes)
3. Click **Audio Only**, **Video Only**, or **Audio + Video**
4. Audio files save to `~/recordings/`, video to USB storage

### First Video Recording (Optional)

1. Go to **Settings** and configure camera:
   - Enter camera IP address
   - Enter credentials (if required)
   - Set USB storage path
   - Click **Test Connection**
2. Go to **New/In Progress** page
3. Select a PTZ preset (if desired)
4. Click **Video Only** or **Audio + Video**
5. Video files will be saved to USB storage

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
- Configure PTZ camera (IP, credentials, presets)
- Set USB storage path for video files
- Export/import schedules and configuration
- Backup and restore settings

### USB Storage Setup (for Video)

```bash
# Create mount point
sudo mkdir -p /mnt/usb_recorder

# Find your USB drive
lsblk

# Mount the drive (replace sda1 with your device)
sudo mount /dev/sda1 /mnt/usb_recorder

# For permanent mount, add to /etc/fstab:
echo '/dev/sda1 /mnt/usb_recorder auto defaults,nofail 0 2' | sudo tee -a /etc/fstab
```

For detailed documentation, see [README.md](README.md).
