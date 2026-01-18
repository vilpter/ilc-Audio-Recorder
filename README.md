# Audio Recorder

**Headless Dual-Mono Audio Recording System for Raspberry Pi**

A professional-grade dual-channel audio recording system with web-based scheduling and management for Raspberry Pi with Behringer UCA202 USB audio interface.

## Features

### Recording
- Dual-mono capture (48kHz, 16-bit WAV, independent channels)
- Manual start/stop from Dashboard
- Configurable recording filenames with customizable channel suffixes
- Human-readable filename format: `YYYY_MMM_DD_HH:MM_L.wav`
- 4-hour duration limit with override option
- Pre-flight disk space checking

### Scheduling
- One-time scheduled recordings
- Recurring schedules (daily, weekly, monthly patterns)
- Recording templates (save and reuse configurations)
- Multi-week calendar view
- Click calendar days to create schedules instantly

### Web Interface
- Dashboard with real-time status
- Schedule management page
- Visual calendar with color-coded events
- Template library
- File browser with download/delete
- Live date/time display on all pages
- Settings page with device configuration
- Complete backup/restore system
- User authentication with login/logout

### System
- Auto-start service (systemd)
- Automated installation script
- Automatic audio device detection
- Schedule persistence across reboots
- Export/import configuration and schedules

## Hardware Requirements

- **Raspberry Pi:** Pi 3B/3B+ or Pi 4 (2GB+ RAM recommended)
- **Audio Interface:** Behringer UCA202 or UCA222 USB
- **Storage:** 32GB+ SD card (Class 10 or better)
- **Power Supply:** 5V/2.5A (Pi 3) or 5V/3A (Pi 4)
- **Network:** Ethernet or WiFi connection

## Software Requirements

- **OS:** Raspberry Pi OS Lite (64-bit) - Trixie (Debian 13) recommended
  - Alternative: Bookworm (Debian 12) also supported
- **Download:** https://www.raspberrypi.com/software/operating-systems/
- **Image:** "Raspberry Pi OS Lite (64-bit)" - No desktop environment

## Quick Start

```bash
# Clone the repository
cd ~
git clone https://github.com/vilpter/ilc-Audio-Recorder.git audio-recorder
cd audio-recorder

# Run the automated installer
./install.sh

# Access web interface
# Open browser: http://<raspberry-pi-ip>:5000
```

The installer handles:
- System dependencies (Python, FFmpeg, ALSA, SQLite)
- Python packages
- ALSA configuration
- Recordings directory
- Systemd service setup
- Log directories

## Installation (Manual)

If you prefer manual installation or the installer encounters issues:

### Step 1: System Updates

```bash
sudo apt update && sudo apt upgrade -y
```

### Step 2: Install Dependencies

```bash
sudo apt install -y python3-pip ffmpeg alsa-utils sqlite3 git
```

### Step 3: Install Python Dependencies

```bash
cd ~/audio-recorder
pip3 install -r requirements.txt --break-system-packages
```

### Step 4: Configure ALSA

```bash
sudo cp configs/asound.conf /etc/asound.conf
sudo alsactl kill rescan

# Verify UCA202 is detected
arecord -l
# Should show: card 1: CODEC [USB Audio CODEC]
```

### Step 5: Create Directories

```bash
mkdir -p ~/recordings
mkdir -p ~/.audio-recorder
```

### Step 6: Install Systemd Service

```bash
sudo mkdir -p /var/log/audio-recorder
sudo chown $USER:$USER /var/log/audio-recorder
sudo cp audio-recorder.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable audio-recorder
sudo systemctl start audio-recorder
```

## Usage

### Dashboard (/)
- View current recording status
- Start/stop manual recordings
- Quick record presets

### Schedule (/schedule)
- Create one-time scheduled recordings
- Create recurring schedules
- Load presets from templates
- View and delete scheduled jobs

### Calendar (/calendar)
- Visual multi-week calendar view
- See all upcoming recordings
- Click any day to create a new schedule

### Templates (/templates)
- Create reusable recording presets
- Save common recording configurations
- Quick-load templates when scheduling

### Recordings (/recordings)
- Browse all recorded files
- Download recordings
- Delete old files

### Settings (/settings)
- Configure audio device (auto-detect or manual)
- Customize recording filename format
- Set channel suffixes (L/R or custom)
- Export schedules and configuration
- Import backups with one-click revert

## File Structure

```
audio-recorder/
├── app.py                    # Flask web server
├── recorder.py               # Audio capture logic
├── scheduler.py              # Job scheduling (APScheduler)
├── templates_manager.py      # Recording templates manager
├── requirements.txt          # Python dependencies
├── audio-recorder.service    # Systemd service file
├── install.sh                # Automated installer
├── configure_audio.sh        # Audio configuration helper
├── fix_service.sh            # Service troubleshooting script
├── configs/
│   ├── asound.conf           # ALSA configuration
│   └── 85-usb-audio.rules    # udev rules for USB audio
├── auth.py                   # Authentication module
└── templates/                # HTML templates
    ├── index.html            # Dashboard
    ├── schedule.html         # Schedule manager
    ├── calendar.html         # Calendar view
    ├── recordings.html       # File browser
    ├── templates_mgmt.html   # Template manager
    ├── settings.html         # Settings page
    ├── login.html            # Login page
    ├── setup.html            # Initial setup
    └── change_password.html  # Password change
```

## Recording File Format

Files are saved as dual-mono WAV files:
- **Format:** PCM 16-bit
- **Sample Rate:** 48kHz
- **Channels:** 2 (split into separate files)
- **Naming:** `YYYY_MMM_DD_HH:MM_SUFFIX.wav`

**Example:**
```
2026_Jan_17_14:30_L.wav  # Left channel
2026_Jan_17_14:30_R.wav  # Right channel
```

**File Size Estimates:**
- ~345 MB/hour per channel
- ~690 MB/hour for both channels
- 4-hour recording ≈ 2.8 GB total

## Configuration

### Audio Device
The system auto-detects USB audio devices. Configure in Settings page:
- **Auto-detect:** Recommended, finds UCA202 automatically
- **Manual:** Select specific device if multiple audio interfaces present

### Recording Filenames
Configure channel suffixes in Settings:
- Default: `L` and `R`
- Change to anything (e.g., "Left"/"Right", "Ch1"/"Ch2")
- Live preview shows expected filename format

### Backup/Restore
Export from Settings page:
- **Schedules (.sched):** All scheduled recordings and templates
- **Configuration (.conf):** Audio device settings, channel suffixes

Import features:
- Two-step confirmation before overwriting
- Automatic backup before any import
- One-click revert to undo last import

## Troubleshooting

### Service Won't Start

```bash
# Run the fix script
./fix_service.sh

# Or manually check
sudo systemctl status audio-recorder
sudo journalctl -u audio-recorder -n 50
tail -f /var/log/audio-recorder/app.log
```

### UCA202 Not Detected

```bash
# Run audio configuration helper
./configure_audio.sh

# Or manually check
lsusb | grep Audio
arecord -l
sudo reboot
```

### Cannot Access Web UI

```bash
# Check if service is running
sudo systemctl status audio-recorder

# Check if port 5000 is open
sudo netstat -tlnp | grep 5000

# Test from Pi itself
curl http://localhost:5000
```

### Recording Fails to Start

1. **Check disk space:**
   ```bash
   df -h ~/recordings
   ```

2. **Test FFmpeg manually:**
   ```bash
   ffmpeg -f alsa -i hw:1 -t 5 \
     -filter_complex "[0:a]channelsplit=channel_layout=stereo[left][right]" \
     -map "[left]" -acodec pcm_s16le -ar 48000 test_L.wav \
     -map "[right]" -acodec pcm_s16le -ar 48000 test_R.wav
   ```

3. **Check ALSA permissions:**
   ```bash
   groups $USER  # Should include "audio"
   ```

## Performance

| Resource | Usage | Notes |
|----------|-------|-------|
| **CPU** | <5% | During recording on Pi 3/4 |
| **RAM** | ~100 MB | Application memory |
| **Disk I/O** | 384 KB/s | Sustained write rate |
| **File Size** | ~345 MB/hour | Per channel (WAV format) |

## Security & Authentication

### First-Time Setup
On first access, you'll be prompted to create an admin account:
1. Navigate to `http://<raspberry-pi-ip>:5000`
2. Create username (min 3 characters) and password (min 6 characters)
3. Log in with your new credentials

### Authentication Features
- Session-based authentication with Flask-Login
- "Remember me" option for persistent sessions
- Change password from Settings page
- All routes protected - login required

### Security Notes
- Designed for **local network use**
- For remote access, use SSH tunneling or VPN
- Credentials stored with secure password hashing (Werkzeug)
- Session secret key auto-generated and stored in `~/.audio-recorder/`

## Changelog

### v1.3.0 (Current)
- Added user authentication (login/logout)
- Added initial setup wizard for admin account creation
- Added change password functionality
- Added "Remember me" persistent sessions
- All routes now require authentication

### v1.2.0
- Fixed recording stop button error when recording already finished
- Added live date/time clock in navigation bar
- Added configurable recording filename format
- Added calendar day click to create schedules
- Added complete backup/restore system
- Refactored code for better maintainability

### v1.1.0
- Added automated installation script
- Fixed username detection for systemd service

### v1.0.0
- Initial release with core recording and scheduling features

See [RELEASE_NOTES_v1.2.0.md](RELEASE_NOTES_v1.2.0.md) for detailed changes.

## Roadmap

### Planned Features
- Disk space monitoring dashboard
- Audio level meter preview
- Optional post-processing (WAV → MP3/FLAC)
- Email/webhook notifications
- Search & filter recordings

## Built With

- **Backend:** Python 3.11+, Flask, Flask-Login, APScheduler
- **Frontend:** HTML5, Tailwind CSS, Vanilla JavaScript
- **Audio:** FFmpeg, ALSA
- **Database:** SQLite3

## Support

- **Issues:** [GitHub Issues](https://github.com/vilpter/ilc-Audio-Recorder/issues)
- **Quick Fixes:** Run `./fix_service.sh` or `./configure_audio.sh`

---

**Version:** 1.3.0
**Last Updated:** 2026-01-18
