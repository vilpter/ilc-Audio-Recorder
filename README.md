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
- Automatic post-recording analysis (silence detection, dB levels)
- Audio artifact detection (digital clipping, upstream/analog flat-top clipping, discontinuities)¹
- Traffic-light quality badges on Recordings page (green/yellow/red)
- Interactive analysis modal showing per-channel metrics and quality details
- Section tagging during recording (mark beginning/ending of segments for post-processing)

¹ Requires numpy, see [Audio artifact detection support](#audio-artifact-detection-support).

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
- Visual directory browser for storage path selection with folder creation
- Visual calendar with color-coded events
- Live date/time display on all pages
- Disk space monitoring in navigation ribbon
- Complete backup/restore system
- User authentication with login/logout
- Role-based permissions (Viewer, Operator, Admin)

### System
- Auto-start service (systemd)
- Automated installation script with upgrade support
- Automatic audio device detection
- Schedule persistence across reboots
- Export/import configuration and schedules

### Diagnostic Logging
- Dedicated log files for recorder, scheduler, and FFmpeg
- Log viewer in Settings with selectable log type and file path display
- System state logging at recording start (environment, ALSA state)
- 60-second heartbeat during recordings
- FFmpeg stderr capture for debugging
- Troubleshooting script for diagnosing scheduled recording issues

## Hardware Requirements

### Required (Audio)
- **Raspberry Pi:** Pi 3B/3B+ or Pi 4 (2GB+ RAM recommended)
- **OS:** 64-bit Linux with systemd, e.g. Raspberry Pi OS (64-bit); Python 3.9+
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
sudo apt install -y git python3 python3-venv ffmpeg alsa-utils
cd ~
git clone https://github.com/vilpter/ilc-Audio-Recorder.git audio-recorder
cd audio-recorder
./install.sh
```

### Upgrading
```bash
cd ~/audio-recorder
git pull
./install.sh --upgrade
```

Access web interface at: `http://<raspberry-pi-ip>:5000`

Run the installer as your normal user; it uses `sudo` where needed. It is safe to
re-run and never deletes recordings or application data. Options:
`--upgrade` (keep ALSA/udev configuration), `--fresh` (reinstall it and re-detect the
audio device), `--yes` (no prompts).

### What the installer sets up

| Item | Location |
|------|----------|
| Application code (copied from your checkout) | `/opt/audio-recorder/app` |
| Python virtual environment | `/opt/audio-recorder/.venv` |
| Users, schedules, settings, secret key, backups | `/var/lib/audio-recorder` |
| Logs | `/var/log/audio-recorder` |
| Service | `audio-recorder.service`, running as the `audio-recorder` system account |

- **Python dependencies** are installed into the virtual environment from
  `requirements.lock`, with every package pinned to an exact version and checked
  against its hash. Nothing is installed into the system Python, so OS upgrades
  and the app can't break each other.
- **64-bit OS required.** The installer stops on a 32-bit system (including
  32-bit Raspberry Pi OS on a Pi 4/5, whose kernel reports `aarch64`). If the
  hash-verified install fails, it restores the previous version and stops.
- <a id="audio-artifact-detection-support"></a>**Audio artifact detection support.**
  Clipping and discontinuity detection uses numpy, installed from prebuilt
  packages only. These exist for 64-bit ARM (Raspberry Pi OS 64-bit) and x86-64
  with the Python versions in current Debian / Raspberry Pi OS releases. On other
  combinations (other CPU types, or a Python release newer than numpy's prebuilt
  packages) the installer installs everything else and ends with a
  **NOTICE** that artifact detection is unavailable. Recording, scheduling and
  level/silence analysis are unaffected. Re-running `./install.sh --upgrade`
  retries the numpy install.
- **Recordings directory:** the installer checks that the service account can write
  to the configured storage path. On ext4 and similar drives it offers to grant the
  `audio-recorder` group access. FAT/exFAT drives get their permissions from mount
  options, so the installer prints the `/etc/fstab` change to make. If the path is
  somewhere the service can't reach (such as inside your home directory), the
  installer offers to move the recordings to a directory you choose (default
  `/mnt/usb_recorder`). It checks the destination has room, never overwrites a file
  already there, sets permissions and updates Settings → Storage Location.
- **Your user** is added to the `audio-recorder` group so you can read logs and
  manage recordings (log out and back in once for this to apply).
- **Upgrading from before 1.12.0:** data in `~/.audio-recorder` is copied to
  `/var/lib/audio-recorder` (the original is left in place for you to remove) and the
  old service file is saved to `/opt/audio-recorder/backup/`.
- **Rollback:** the previous code and virtual environment are kept as
  `/opt/audio-recorder/app.prev` and `.venv.prev`.
- **Service customizations** belong in a drop-in, which upgrades keep:
  `sudo systemctl edit audio-recorder`. The main unit file is replaced on every install.

## Manual Installation

The installer is the supported path. To see what it does, read `install.sh`; the
steps are: create the `audio-recorder` system account (in the `audio` group), copy
the code to `/opt/audio-recorder/app`, create the virtual environment with
`python3 -m venv /opt/audio-recorder/.venv` and
`/opt/audio-recorder/.venv/bin/python -m pip install --require-hashes -r requirements.lock`,
make the recordings directory writable by the account, copy
`configs/asound.conf` to `/etc/asound.conf`, and install `audio-recorder.service`.

## Development

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements-dev.lock
.venv/bin/python -m pytest
```

Runtime dependencies are declared in `pyproject.toml`. After changing them, regenerate
both lock files with the `uv pip compile` commands listed there.

When run from a checkout, the app keeps its data in `~/.audio-recorder`. Set
`AUDIO_RECORDER_STATE_DIR` (and optionally `AUDIO_RECORDER_LOG_DIR`) to use another
location; see `config.py`.

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
- Section tagging: mark beginning/ending of segments during recording
- Control PTZ camera presets (10 customizable positions)
- View video transcode progress
- Access live stream URLs for external players

### Recordings (/recordings)
- Browse all recorded audio files
- Browse raw and processed video files
- Batch select for bulk download or delete
- Download recordings as ZIP archive
- Click filenames to view audio analysis (duration, silence percentage, dB levels, clipping, discontinuities)
- Section tags displayed in analysis modal for post-processing reference
- Traffic-light quality badges for at-a-glance audio health overview

### Settings (/settings)
- Configure audio device (auto-detect or manual)
- Configure PTZ camera (IP, credentials, RTSP port)
- Set PTZ preset names (e.g., "Podium", "Wide Angle")
- Configure USB storage path for video files
- Test camera connection
- Customize recording filename format
- Export/import schedules and configuration
- Database clean-up tool to remove old recording entries

## File Structure

```
audio-recorder/
├── app.py                    # Flask web server
├── recorder.py               # Audio capture logic
├── video_recorder.py         # Video capture and transcoding
├── scheduler.py              # Job scheduling (APScheduler)
├── auth.py                   # Authentication module
├── config.py                 # State, log and backup paths
├── pyproject.toml            # Project metadata and top-level dependencies
├── requirements.lock         # Pinned, hashed runtime dependencies
├── requirements-dev.lock     # Same, plus test dependencies
├── audio-recorder.service    # Systemd service file
├── install.sh                # Installer / upgrader
├── configure_audio.sh        # Audio configuration helper
├── troubleshoot_audio.sh     # Diagnostic script for scheduled recordings
├── audio_analyzer.py         # Audio analysis module (silence detection, dB levels)
├── artifact_detector.py      # Audio artifact detection (clipping, discontinuities)
├── configs/
│   ├── asound.conf           # ALSA configuration
│   └── 85-usb-audio.rules    # udev rules for USB audio
├── tests/                    # pytest suite
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
sudo systemctl status audio-recorder
sudo journalctl -u audio-recorder -n 50
sudo tail -50 /var/log/audio-recorder/error.log

# Re-running the installer repairs the service, account and permissions
cd ~/audio-recorder && ./install.sh --upgrade
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
   df -h /mnt/usb_recorder    # or your Settings → Storage Location
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
- Role-based access control:
  - **Viewer**: Schedule, Control, Recordings access only
  - **Operator**: Limited Settings (Audio/Camera config)
  - **Admin**: Full access including user management

### Security Notes
- Designed for **local network use**
- For remote access, use SSH tunneling or VPN
- Credentials stored with secure password hashing (Werkzeug)
- Session secret key auto-generated and stored (mode 600) in `/var/lib/audio-recorder/`
- The service runs as an unprivileged `audio-recorder` account with a read-only `/usr`, `/boot` and `/etc`

## Roadmap

### Planned Features
- Add configurable audio post-processing (WAV → MP3/FLAC/AAC-LC) with adjustable bitrate
- Note the last date of download for files

## Built With

- **Backend:** Python 3.9+, Flask, Flask-Login, APScheduler
- **Frontend:** HTML5, Tailwind CSS, Vanilla JavaScript
- **Audio:** FFmpeg, ALSA
- **Database:** SQLite3

## Development Notes

### Post-Work Checklist
After completing development work, ensure the following are updated:

1. **Version Numbers**
   - Update `__version__` in `app.py` and `version` in `pyproject.toml` (a test checks they match)
   - Update version at bottom of `README.md`
   - Add entry to `CHANGELOG.md`

2. **Documentation**
   - Update `CHANGELOG.md` with detailed changes
   - Update `README.md` features if applicable
   - Update `ARCHITECTURE.md` if API or schema changed

3. **Testing**
   - Run the test suite: `.venv/bin/python -m pytest`
   - Test affected functionality in browser
   - Check for console errors in browser dev tools

## Support

- **Issues:** [GitHub Issues](https://github.com/vilpter/ilc-Audio-Recorder/issues)
- **Quick Fixes:** Re-run `./install.sh --upgrade`, or run `./configure_audio.sh` / `./troubleshoot_audio.sh`

---

**Version:** 1.12.2
**Last Updated:** 2026-11-04
