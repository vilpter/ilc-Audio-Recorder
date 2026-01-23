# Audio Recorder v1.1.0 Release Notes

**Release Date:** 2026-01-17  
**Status:** Production Ready

---

## What's New in v1.1.0

### 🚀 One-Command Installation
**NEW: `install.sh`** - Fully automated installation script that:
- ✅ Automatically detects your username (no more hardcoded `pi` user)
- ✅ Auto-detects audio device card number
- ✅ Generates customized systemd service file
- ✅ Configures all permissions correctly
- ✅ Tests everything and shows you the web UI URL

**Before (v1.0.x):** 10 manual steps, potential for user errors  
**Now (v1.1.0):** One command: `./install.sh`

---

## Installation (Fresh Setup)

### Quick Start
```bash
# 1. Transfer files to Pi
scp audio-recorder-v1.1.0.tar.gz pi@raspberrypi.local:~/

# 2. SSH into Pi
ssh pi@raspberrypi.local

# 3. Extract
tar -xzf audio-recorder-v1.1.0.tar.gz
cd audio-recorder

# 4. Install prerequisites (one-time)
sudo apt update
sudo apt install -y python3-pip ffmpeg alsa-utils sqlite3

# 5. Run installer
./install.sh

# Done! Access web UI at http://<pi-ip>:5000
```

---

## Upgrading from v1.0.x

If you already have v1.0.x installed and running:

### Option A: Fresh Install (Recommended)
```bash
# Stop old service
sudo systemctl stop audio-recorder

# Backup your database (if you have schedules/templates)
cp ~/.audio-recorder/schedule.db ~/schedule-backup.db

# Backup your recordings
# (They're in ~/recordings - leave them there)

# Remove old installation
rm -rf ~/audio-recorder

# Install v1.1.0 fresh (see Quick Start above)

# Restore database if needed
cp ~/schedule-backup.db ~/.audio-recorder/schedule.db
sudo systemctl restart audio-recorder
```

### Option B: In-Place Upgrade
```bash
cd ~/audio-recorder

# Backup
cp -r ~/audio-recorder ~/audio-recorder.backup

# Extract new version over old
tar -xzf ~/audio-recorder-v1.1.0.tar.gz --strip-components=1

# Re-run service fix to ensure correct username
./fix_service.sh

# Done
```

---

## Changes from v1.0.2

### Added
- ✨ **Automated installer** (`install.sh`) with zero-config setup
- 📝 Updated README with quick install instructions
- 🔧 Service file now auto-generated with detected username
- ✅ Prerequisites checking before installation
- 📊 Better error messages and status reporting

### Fixed
- 🐛 Hardcoded `pi` username in systemd service (now auto-detected)
- 🐛 Audio device card number assumptions (now auto-detected)
- 📄 Installation documentation now matches actual Pi OS behavior

### Improved
- 📚 Clearer documentation structure (Quick vs Manual install)
- 🎯 Streamlined deployment process
- ⚡ Faster time-to-running (2 minutes vs 15 minutes)

---

## What Hasn't Changed

All Phase 1 features remain the same:
- ✅ Dual-mono audio capture (48kHz, 16-bit WAV)
- ✅ Web UI (Dashboard, Schedule, Calendar, Templates, Recordings)
- ✅ Recurring schedules (daily, weekly, monthly)
- ✅ Recording templates
- ✅ 4-hour duration limit with override
- ✅ Pre-flight disk space checking
- ✅ Multi-week calendar view

---

## Known Issues

None reported yet for v1.1.0.

### From v1.0.x (now fixed)
- ~~Service fails with 217/USER error~~ → Fixed with auto-detection
- ~~Audio device not found on hw:1~~ → Fixed with configure_audio.sh

---

## System Requirements

**Hardware:**
- Raspberry Pi 3B/3B+ or Pi 4
- Behringer UCA202/UCA222 USB audio interface
- 32GB+ microSD card (Class 10 or better)
- Network connection (Ethernet or WiFi)

**Software:**
- Raspberry Pi OS Lite (64-bit)
- Trixie (Debian 13) or Bookworm (Debian 12)
- Python 3.11+
- FFmpeg, ALSA, SQLite3

---

## File Listing

```
audio-recorder/
├── install.sh              # NEW: Automated installer
├── configure_audio.sh      # Audio device detection
├── fix_service.sh          # Service configuration fixer
├── app.py                  # Flask web server
├── recorder.py             # Audio capture module
├── scheduler.py            # Job scheduler
├── templates_manager.py    # Template manager
├── requirements.txt        # Python dependencies
├── audio-recorder.service  # Systemd service template
├── README.md               # Complete documentation
├── DEPLOYMENT_CHECKLIST.md # Deployment guide
├── DEVELOPMENT_SUMMARY.md  # Technical details
├── PROJECT_SCOPE.md        # Project specification
├── PHASE2_AUDIO_CONFIG_GUI.md  # Future feature specs
├── templates/
│   ├── index.html
│   ├── schedule.html
│   ├── calendar.html
│   ├── templates_mgmt.html
│   └── recordings.html
└── configs/
    ├── asound.conf
    └── 85-usb-audio.rules
```

---

## Testing Status

### ✅ Tested On
- Raspberry Pi 4 (2GB, 4GB) - Trixie
- Raspberry Pi 3B+ - Bookworm
- Behringer UCA202 (USB Audio)

### ✅ Installation Scenarios
- Fresh Pi OS install with custom username
- Fresh Pi OS install with `pi` username
- Upgrade from v1.0.2

### ⏳ Pending Testing
- Long-duration recording (>4 hours with override)
- Heavy load (multiple recurring schedules)

---

## Support

### Quick Troubleshooting
```bash
# Service won't start
./fix_service.sh

# Audio device not found
./configure_audio.sh

# Check logs
sudo journalctl -u audio-recorder -n 50
cat /var/log/audio-recorder/error.log

# Run manually to see errors
cd ~/audio-recorder
python3 app.py
```

### Documentation
- **README.md** - Complete installation and usage guide
- **DEPLOYMENT_CHECKLIST.md** - Step-by-step deployment guide
- **DEVELOPMENT_SUMMARY.md** - Technical architecture

---

## Roadmap

### Phase 2 (Planned)
- 🎛️ **Audio device configuration GUI** (HIGH PRIORITY)
  - Web-based device selector
  - Auto-detection with manual override
  - Test recording button
- 🔐 Basic HTTP authentication
- 📊 Log viewer in web UI
- 📅 iCal export for schedules
- 🗑️ Retention policy / auto-cleanup

### Phase 3 (Future)
- 📡 Real-time status polling
- 💾 Disk space monitoring dashboard
- 🎵 Audio level meter (preview without recording)
- 🔄 Optional post-processing (WAV → MP3/FLAC)

---

## Credits

**Testing:** User feedback and field testing
**Platform:** Raspberry Pi Foundation

---

## License

[Specify license here]

---

**Questions or Issues?**  
Check the README.md troubleshooting section or run `./fix_service.sh` and `./configure_audio.sh` to auto-fix common issues.
