# Church Recording

**Headless Dual-Mono Audio + PTZ Video Recording System for Raspberry Pi**

A professional-grade dual-channel audio and video recording system with web-based scheduling and management for Raspberry Pi. Supports Behringer UCA202 USB audio interface and PTZOptics cameras for synchronized A/V capture. Designed for church services and similar recurring event recording.

## Features

### Audio Recording
- Dual-mono capture (48kHz, 16-bit WAV, independent channels)
- Manual start/stop from Dashboard
- Configurable recording filenames with customizable channel suffixes
- Human-readable filename format: `YYYY_MMM_DD_HH:MM_L.wav`
- 4-hour duration limit with override option
- Pre-flight disk space checking

### Video Recording
- PTZOptics camera integration for synchronized A/V capture
- RTSP stream capture using FFmpeg with `-c copy` (zero CPU re-encoding)
- Hardware-accelerated transcoding using `h264_v4l2m2m` (Raspberry Pi GPU)
- 10 customizable PTZ preset buttons with user-defined labels
- Automatic post-processing: raw files saved to `/raw/`, transcoded to `/processed/`
- Real-time transcode progress tracking with percentage display
- USB storage validation with mount point checking
- Live stream viewing with copyable ffplay/VLC commands

### Scheduling
- One-time scheduled recordings
- Recurring schedules (daily, weekly, monthly patterns)
- Multi-week calendar view
- Click calendar days to create schedules instantly
- Optional video capture with audio schedules

### Web Interface
- Schedule page with calendar view and instant scheduling
- New/In Progress page for unified recording controls
- Recordings page with audio and video file browser
- Settings page with audio and camera configuration
- Visual calendar with color-coded events
- Live date/time display on all pages
- Disk space monitoring in navigation ribbon
- Complete backup/restore system
- User authentication with login/logout

### System
- Auto-start service (systemd)
- Automated installation script with upgrade support
- Automatic audio device detection
- Schedule persistence across reboots
- Export/import configuration and schedules

## Hardware Requirements

### Required (Audio)
- **Raspberry Pi:** Pi 3B/3B+ or Pi 4 (2GB+ RAM recommended)
- **Audio Interface:** Behringer UCA202 or UCA222 USB
- **Storage:** 32GB+ SD card (Class 10 or better)
- **Power Supply:** 5V/2.5A (Pi 3) or 5V/3A (Pi 4)
- **Network:** Ethernet or WiFi connection

### Optional (Video)
- **PTZ Camera:** PTZOptics camera with HTTP CGI support and RTSP streaming
- **USB Storage:** External USB drive for video files (mounted at `/mnt/usb_recorder`)
- **Network:** Camera and Pi must be on same network for RTSP access

## Software Requirements

- **OS:** Raspberry Pi OS Lite (64-bit) - Trixie (Debian 13) recommended
  - Alternative: Bookworm (Debian 12) also supported
- **Download:** https://www.raspberrypi.com/software/operating-systems/
- **Image:** "Raspberry Pi OS Lite (64-bit)" - No desktop environment

## Quick Start

### New Installation
```bash
cd ~
git clone https://github.com/vilpter/ilc-Audio-Recorder.git audio-recorder
cd audio-recorder
./install.sh
```

### Upgrading Existing Installation
```bash
cd ~/audio-recorder
git pull
./install.sh
# Select "Upgrade" when prompted
```

Access web interface at: `http://<raspberry-pi-ip>:5000`

The installer handles:
- System dependencies (Python, FFmpeg, ALSA, SQLite)
- Python packages
- ALSA configuration
- Recordings directory
- Systemd service setup
- Log directories

**Upgrade Mode** preserves your ALSA config, udev rules, and service customizations.

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

### Schedule (/)
- Visual multi-week calendar view
- See all upcoming recordings
- Click any day to create or edit schedules
- Option to capture video with audio schedules
- One-time and recurring recording support

### New/In Progress (/camera)
- Unified recording controls: Audio Only, Video Only, or Both
- Combined audio/video status display
- Control PTZ camera presets (10 customizable positions)
- View video transcode progress
- Access live stream URLs for external players

### Recordings (/recordings)
- Browse all recorded audio files
- Browse raw and processed video files
- Batch select for bulk download or delete
- Download recordings as ZIP archive

### Settings (/settings)
- Configure audio device (auto-detect or manual)
- Configure PTZ camera (IP, credentials, RTSP port)
- Set PTZ preset names (e.g., "Podium", "Wide Angle")
- Configure USB storage path for video files
- Test camera connection
- Customize recording filename format
- Export/import schedules and configuration

## File Structure

```
audio-recorder/
├── app.py                    # Flask web server
├── recorder.py               # Audio capture logic
├── video_recorder.py         # Video capture and transcoding
├── scheduler.py              # Job scheduling (APScheduler)
├── auth.py                   # Authentication module
├── requirements.txt          # Python dependencies
├── audio-recorder.service    # Systemd service file
├── install.sh                # Automated installer
├── configure_audio.sh        # Audio configuration helper
├── fix_service.sh            # Service troubleshooting script
├── configs/
│   ├── asound.conf           # ALSA configuration
│   └── 85-usb-audio.rules    # udev rules for USB audio
└── templates/                # HTML templates
    ├── calendar.html         # Schedule page (home page with calendar)
    ├── camera.html           # New/In Progress (recording controls)
    ├── recordings.html       # Audio and video file browser
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

## Video Recording

### Storage Structure
Video files are saved to USB storage (default: `/mnt/usb_recorder`):
```
/mnt/usb_recorder/
├── raw/                      # Original RTSP captures (large files)
│   └── video_2026-01-24_14-30-00.mp4
└── processed/                # Transcoded files (smaller, Pi-optimized)
    └── video_2026-01-24_14-30-00.mp4
```

### Video Format
- **Raw Files:** Direct RTSP stream copy (no re-encoding, zero CPU usage)
- **Processed Files:** H.264 transcoded using Raspberry Pi GPU (`h264_v4l2m2m`)
- **Default Bitrate:** 2 Mbps (configurable)

### PTZ Camera Setup
1. Go to **Settings** page
2. Enter camera IP address (e.g., `192.168.1.100`)
3. Enter credentials if authentication is enabled
4. Configure USB storage path
5. Name your PTZ presets (e.g., "Podium", "Wide Angle", "Audience")
6. Click **Test Connection** to verify

### Live Stream Viewing
From the **Camera** page, copy the stream URL for external players:
- **ffplay:** `ffplay rtsp://192.168.1.100:554/1`
- **VLC:** Open Network Stream with the RTSP URL

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

### Camera Configuration
Configure in Settings page:
- **Camera IP:** Network address of PTZOptics camera
- **Username/Password:** Optional HTTP Basic authentication
- **RTSP Port:** Default 554
- **USB Storage Path:** Mount point for video files (default `/mnt/usb_recorder`)
- **Preset Names:** Custom labels for PTZ positions 1-10

### Backup/Restore
Export from Settings page:
- **Schedules (.sched):** All scheduled recordings
- **Configuration (.conf):** Audio device settings, channel suffixes, camera config

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

### Video Recording Issues

**Camera not connecting?**
1. Verify camera IP in Settings
2. Test camera ping: `ping 192.168.1.100`
3. Check camera is on same network as Pi
4. Verify credentials if authentication enabled

**USB storage not detected?**
```bash
# Check mount point exists
ls -la /mnt/usb_recorder

# Verify USB drive is mounted
df -h /mnt/usb_recorder

# Mount manually if needed
sudo mount /dev/sda1 /mnt/usb_recorder
```

**Transcoding slow or failing?**
```bash
# Check hardware encoder availability
ffmpeg -encoders | grep v4l2

# Monitor transcode progress in logs
tail -f /var/log/audio-recorder/app.log
```

**RTSP stream not working?**
```bash
# Test stream directly
ffplay rtsp://CAMERA_IP:554/1

# Check port is accessible
nc -zv CAMERA_IP 554
```

## Performance

### Audio Recording
| Resource | Usage | Notes |
|----------|-------|-------|
| **CPU** | <5% | During recording on Pi 3/4 |
| **RAM** | ~100 MB | Application memory |
| **Disk I/O** | 384 KB/s | Sustained write rate |
| **File Size** | ~345 MB/hour | Per channel (WAV format) |

### Video Recording
| Resource | Usage | Notes |
|----------|-------|-------|
| **CPU (capture)** | <5% | RTSP passthrough with `-c copy` |
| **CPU (transcode)** | 10-30% | Hardware-accelerated `h264_v4l2m2m` |
| **File Size (raw)** | Varies | Depends on camera bitrate |
| **File Size (processed)** | ~900 MB/hour | At 2 Mbps default bitrate |

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

### v1.5.0 (Current)
- Rebranded from "Audio Recorder" to "Church Recording"
- Renamed Calendar page to "Schedule" - calendar-based scheduling
- Renamed Camera page to "New/In Progress" - unified recording controls
- Added Audio Only, Video Only, and Both recording buttons
- Added combined audio/video status panel
- Added mobile page indicator
- Removed standalone Schedule page (consolidated into calendar modal)
- Moved Quick Record from Settings to New/In Progress page

### v1.4.0
- Added PTZOptics camera integration for synchronized A/V recording
- RTSP stream capture with zero CPU re-encoding (`-c copy`)
- Hardware-accelerated transcoding using Raspberry Pi GPU
- USB storage support for video files
- Video capture checkbox in Schedule page
- Real-time transcode progress tracking
- Live stream viewing with copyable URLs

### v1.3.0
- Added user authentication (login/logout)
- Added batch file operations (multi-select, bulk download/delete)
- Added disk space monitoring in navigation ribbon

See [CHANGELOG.md](CHANGELOG.md) for detailed changes.

## Roadmap

### Planned Features
- Audio post-processing (WAV → MP3/FLAC/AAC-LC) with adjustable bitrate
- Note the last date of download for files

### Recently Completed (v1.5.0)
- Unified recording controls (Audio/Video/Both)
- Combined status panel for audio and video
- Simplified navigation and workflow
- Mobile-friendly page indicators

### Previously Completed (v1.4.0)
- PTZOptics camera integration with video recording
- RTSP stream capture with hardware-accelerated transcoding
- Video capture option for scheduled recordings
- Camera settings page with preset naming
- Live stream URLs for external players

## Built With

- **Backend:** Python 3.11+, Flask, Flask-Login, APScheduler
- **Frontend:** HTML5, Tailwind CSS, Vanilla JavaScript
- **Audio:** FFmpeg, ALSA
- **Database:** SQLite3

## Support

- **Issues:** [GitHub Issues](https://github.com/vilpter/ilc-Audio-Recorder/issues)
- **Quick Fixes:** Run `./fix_service.sh` or `./configure_audio.sh`

---

**Version:** 1.5.0
**Last Updated:** 2026-01-24
