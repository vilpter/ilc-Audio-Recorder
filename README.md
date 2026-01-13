# ILC Audio Recorder

A headless dual-mono audio archiving system for Raspberry Pi with Behringer UCA202 USB audio interface. Features a web-based interface for scheduling recordings, managing files, and monitoring status.

## Features

### Phase 1 (Current Implementation)
- ✅ Web UI accessible via local network
- ✅ Manual recording start/stop with configurable duration
- ✅ Scheduled recordings (one-time and recurring)
- ✅ Recurring patterns: daily, weekly, monthly, weekdays, weekends
- ✅ Recording templates for preset configurations
- ✅ Multi-week calendar view of scheduled recordings
- ✅ File browser with download and delete capabilities
- ✅ Pre-flight disk space checks
- ✅ 4-hour default duration limit with override option
- ✅ Automatic service restart on reboot (systemd)
- ✅ Schedule persistence across reboots (SQLite)

### Phase 2 (Future)
- ⏳ Basic authentication for web UI
- ⏳ Auto-cleanup of old files (retention policy)
- ⏳ Export schedule as iCal
- ⏳ Log viewer in web UI
- ⏳ Dark mode UI

### Phase 3 (Future)
- ⏳ Real-time status display with polling
- ⏳ Disk space monitoring with warnings
- ⏳ Audio level meter preview
- ⏳ Optional post-recording conversion (WAV → MP3/FLAC)

## Hardware Requirements

- **Raspberry Pi:** Pi 3B/3B+ or Pi 4 (2GB+ RAM recommended)
- **Audio Interface:** Behringer UCA202 USB
- **Storage:** 32GB+ SD card (Class 10 or better)
- **Power Supply:** 5V/2.5A (Pi 3) or 5V/3A (Pi 4)
- **Network:** Ethernet or WiFi connection

## Software Requirements

- **OS:** Raspberry Pi OS Lite (64-bit) - Trixie (Debian 13) **RECOMMENDED**
  - Alternative: Bookworm (Debian 12) also supported
- **Download:** https://www.raspberrypi.com/software/operating-systems/
- **Image:** "Raspberry Pi OS Lite (64-bit)" - No desktop environment

## Installation

### Step 0: Prepare Raspberry Pi

1. **Flash OS to SD Card** using Raspberry Pi Imager
   - Select "Raspberry Pi OS Lite (64-bit)"
   - Click the gear icon for advanced settings

2. **Configure Headless Access** in Raspberry Pi Imager:
   - ✅ Enable SSH
   - ✅ Set hostname (e.g., `ilc-recorder`)
   - ✅ Configure username/password (default: `pi`)
   - ✅ Set WiFi credentials (if not using Ethernet)
   - ✅ Set locale and timezone

3. **First Boot:**
   - Insert SD card and power on
   - Wait 2-3 minutes for initial boot
   - Connect via SSH: `ssh pi@ilc-recorder.local`

4. **Verify Installation:**
   ```bash
   cat /etc/os-release  # Should show Debian 13 (trixie) or 12 (bookworm)
   uname -m             # Should show: aarch64 (64-bit ARM)
   ```

### Step 1: System Updates

**IMPORTANT: Always update first!**

```bash
sudo apt update && sudo apt upgrade -y
```

### Step 2: Install Dependencies

```bash
# Install system packages
sudo apt install -y python3-pip ffmpeg alsa-utils sqlite3 git

# Verify installations
ffmpeg -version
python3 --version  # Should be Python 3.11+
```

### Step 3: Install ILC Audio Recorder

```bash
# Clone or copy the project
cd ~
# If using git:
# git clone <repository-url> ilc-audio-recorder

# If copying files manually, upload to ~/ilc-audio-recorder

cd ~/ilc-audio-recorder

# Install Python dependencies
pip3 install -r requirements.txt --break-system-packages
```

**Note:** The `--break-system-packages` flag is required on newer Raspberry Pi OS versions that use externally-managed Python environments.

### Step 4: Configure ALSA

```bash
# Copy ALSA configuration
sudo cp configs/asound.conf /etc/asound.conf

# Reload ALSA
sudo alsactl kill rescan

# Verify UCA202 is detected
arecord -l
# Should show: card 1: CODEC [USB Audio CODEC]

# Test audio capture (5 second test)
arecord -D hw:1 -f S16_LE -r 48000 -c 2 -d 5 test.wav
aplay test.wav  # Play back to verify (if speakers connected)
rm test.wav
```

### Step 5: Create Recordings Directory

```bash
# Create recordings directory
mkdir -p ~/recordings

# Verify write permissions
touch ~/recordings/test.txt && rm ~/recordings/test.txt
```

### Step 6: Install Systemd Service

```bash
# Create log directory
sudo mkdir -p /var/log/ilc-audio-recorder
sudo chown pi:pi /var/log/ilc-audio-recorder

# Copy service file
sudo cp ilc-audio-recorder.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable auto-start on boot
sudo systemctl enable ilc-audio-recorder

# Start the service
sudo systemctl start ilc-audio-recorder

# Check status
sudo systemctl status ilc-audio-recorder
```

### Step 7: Access Web Interface

Open a browser and navigate to:
- **By hostname:** http://ilc-recorder.local:5000
- **By IP address:** http://YOUR_PI_IP:5000

To find your Pi's IP address:
```bash
hostname -I
```

## Usage

### Dashboard (/)
- View current recording status
- Start/stop manual recordings
- Configure recording duration
- Monitor disk space

### Schedule (/schedule)
- Create one-time scheduled recordings
- Create recurring schedules (daily, weekly, monthly)
- Load presets from templates
- View and delete scheduled jobs

### Calendar (/calendar)
- Visual multi-week calendar view
- See all upcoming recordings
- Distinguish one-time vs recurring events
- Click dates to see event details

### Recordings (/recordings)
- Browse all recorded files
- Download recordings
- Delete old files
- Search and filter by source (A/B)

### Templates (/templates)
- Create reusable recording presets
- Save common recording configurations
- Edit existing templates
- Quick-load templates when scheduling

## File Structure

```
ilc-audio-recorder/
├── app.py                      # Flask web server
├── recorder.py                 # Audio capture logic
├── scheduler.py                # Job scheduling (APScheduler)
├── templates_manager.py        # Recording templates manager
├── requirements.txt            # Python dependencies
├── ilc-audio-recorder.service  # Systemd service file
├── README.md                   # This file
├── PROJECT_SCOPE.md            # Detailed project scope
├── configs/
│   └── asound.conf            # ALSA configuration
├── templates/                  # HTML templates
│   ├── index.html             # Dashboard
│   ├── schedule.html          # Schedule manager
│   ├── calendar.html          # Calendar view
│   ├── recordings.html        # File browser
│   └── templates_mgmt.html    # Template manager
├── static/                     # Static assets (if any)
└── data/                       # SQLite databases (auto-created)
    ├── scheduler.db           # Scheduled jobs
    ├── scheduler.db.meta      # Job metadata
    └── templates.db           # Recording templates
```

## Recording File Format

Files are saved as dual-mono WAV files:
- **Format:** PCM 16-bit
- **Sample Rate:** 48kHz
- **Channels:** 2 (split into separate files)
- **Naming:** `source_[A|B]_YYYYMMDD_HHMMSS.wav`

**Example:**
```
source_A_20260112_143022.wav  # Left channel (Source A)
source_B_20260112_143022.wav  # Right channel (Source B)
```

**File Size Estimates:**
- ~10 MB/minute/channel
- ~1.2 GB/hour for both channels
- 4-hour recording ≈ 4.8 GB total

## Troubleshooting

### Service Won't Start

```bash
# Check service status
sudo systemctl status ilc-audio-recorder

# View logs
sudo journalctl -u ilc-audio-recorder -n 50

# Check application logs
tail -f /var/log/ilc-audio-recorder/app.log
tail -f /var/log/ilc-audio-recorder/error.log
```

### UCA202 Not Detected

```bash
# List USB devices
lsusb
# Should show: "Burr-Brown from TI USB Audio CODEC"

# List ALSA cards
arecord -l
# Should show card 1: CODEC [USB Audio CODEC]

# If missing, try:
sudo reboot
```

### Cannot Access Web UI

```bash
# Check if service is running
sudo systemctl status ilc-audio-recorder

# Check if port 5000 is open
sudo netstat -tlnp | grep 5000

# Test from Pi itself
curl http://localhost:5000

# Check firewall (if enabled)
sudo ufw status
```

### Recording Fails to Start

1. **Check disk space:**
   ```bash
   df -h ~/recordings
   ```

2. **Test FFmpeg manually:**
   ```bash
   ffmpeg -f alsa -i hw:1 -t 10 \
     -filter_complex "[0:a]channelsplit=channel_layout=stereo[left][right]" \
     -map "[left]" -acodec pcm_s16le -ar 48000 test_A.wav \
     -map "[right]" -acodec pcm_s16le -ar 48000 test_B.wav
   ```

3. **Check ALSA permissions:**
   ```bash
   groups pi  # Should include "audio"
   ```

### Scheduled Jobs Not Running

```bash
# Check scheduler database
sqlite3 ~/ilc-audio-recorder/data/scheduler.db "SELECT * FROM apscheduler_jobs;"

# Check job metadata
sqlite3 ~/ilc-audio-recorder/data/scheduler.db.meta "SELECT * FROM job_metadata;"

# Restart service
sudo systemctl restart ilc-audio-recorder
```

## Configuration

### Change Recordings Directory

Edit the service file:
```bash
sudo nano /etc/systemd/system/ilc-audio-recorder.service
```

Change this line:
```ini
Environment="RECORDINGS_DIR=/home/pi/recordings"
```

Then reload and restart:
```bash
sudo systemctl daemon-reload
sudo systemctl restart ilc-audio-recorder
```

### Change Web Port

Edit `app.py` and change the port in the last line:
```python
app.run(host='0.0.0.0', port=5000, debug=False)
```

Then restart the service.

## Maintenance

### View Logs

```bash
# Application logs
tail -f /var/log/ilc-audio-recorder/app.log

# Error logs
tail -f /var/log/ilc-audio-recorder/error.log

# System journal
sudo journalctl -u ilc-audio-recorder -f
```

### Backup Configuration

```bash
# Backup databases
cp ~/ilc-audio-recorder/data/*.db ~/backups/

# Backup recordings
rsync -av ~/recordings/ ~/backups/recordings/
```

### Update Software

```bash
cd ~/ilc-audio-recorder
git pull  # If using git

# Restart service
sudo systemctl restart ilc-audio-recorder
```

## Security Notes

- This system is designed for **local network use only**
- No authentication is implemented in Phase 1
- Do not expose port 5000 to the internet
- For remote access, use SSH tunneling or VPN
- Phase 2 will add basic HTTP authentication

## Performance

- **Pi 3:** Handles dual-mono 48kHz recording effortlessly
- **Pi 4:** Identical performance for this workload
- **CPU Usage:** <5% during recording
- **RAM Usage:** ~100-150MB for web service
- **Network:** Minimal bandwidth (web UI only)

## Technical Details

### Audio Capture Pipeline

```
Behringer UCA202 (USB)
    ↓
ALSA hw:1 (stereo input)
    ↓
FFmpeg channelsplit filter
    ↓
Two mono WAV files (Source A + Source B)
```

### Scheduling System

- **Engine:** APScheduler with SQLite persistence
- **Triggers:** CronTrigger for recurring, DateTrigger for one-time
- **Persistence:** Jobs survive service restarts and reboots
- **Execution:** Python threading for concurrent recording management

## Support

For issues, questions, or contributions:
- Check the `PROJECT_SCOPE.md` for detailed architectural information
- Review logs in `/var/log/ilc-audio-recorder/`
- Test components individually (FFmpeg, ALSA, Python modules)

## License

This project is provided as-is for educational and archival purposes.

## Credits

Built with:
- **Flask** - Web framework
- **APScheduler** - Job scheduling
- **FFmpeg** - Audio processing
- **Tailwind CSS** - UI styling
- **Raspberry Pi OS** - Operating system

---

**Version:** 1.0.0 (Phase 1)
**Last Updated:** 2026-01-12
**Status:** Production Ready
