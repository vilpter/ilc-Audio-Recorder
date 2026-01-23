# ILC Audio Recorder

**Headless Dual-Mono Audio Recording System for Raspberry Pi**

[![Version](https://img.shields.io/badge/version-1.2.0-blue.svg)](https://github.com/vilpter/ilc-Audio-Recorder/releases)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Raspberry%20Pi-red.svg)](https://www.raspberrypi.org/)

> Professional-grade dual-channel audio recording with web-based scheduling and management

---

## 🎯 Features

### Recording
- **Dual-Mono Capture:** Independent left/right channel recording (48kHz, 16-bit WAV)
- **USB Audio Interface:** Behringer UCA202/UCA222 support
- **Smart Duration Limits:** 4-hour default with override option
- **Disk Space Protection:** Pre-flight checks prevent failed recordings
- **Configurable Filenames:** Customize channel suffixes and format

### Scheduling
- **One-Time & Recurring:** Daily, weekly, monthly patterns
- **Recording Templates:** Save and reuse configurations
- **Visual Calendar:** Multi-week view with color-coded events
- **Click to Schedule:** Create schedules directly from calendar

### Web Interface
- **Dashboard:** Real-time recording status and quick controls
- **Live Clock:** Current date/time display on all pages
- **Settings Page:** Device configuration, filename customization
- **Backup/Restore:** Export/import schedules and configuration
- **File Browser:** Download or delete recordings

### System
- **Auto-Start Service:** Systemd integration, runs on boot
- **Automated Installer:** One-command setup
- **Auto-Detection:** Finds USB audio device automatically
- **Persistent Schedules:** Survive reboots and power cycles

---

## 🚀 Quick Start

### Requirements
- Raspberry Pi 3/4 (2GB+ RAM recommended)
- Behringer UCA202 or UCA222 USB audio interface
- Raspberry Pi OS Lite (64-bit) - Trixie or Bookworm
- 32GB+ microSD card

### Installation

```bash
# Download latest release
wget https://github.com/vilpter/ilc-Audio-Recorder/releases/download/v1.2.0/audio-recorder-v1.2.0.tar.gz

# Extract
tar -xzf audio-recorder-v1.2.0.tar.gz
cd audio-recorder

# Install dependencies
sudo apt update
sudo apt install -y python3-pip ffmpeg alsa-utils sqlite3

# Run automated installer
./install.sh

# Access web interface
# Open browser: http://<raspberry-pi-ip>:5000
```

---

## 📖 Documentation

- **[Installation Guide](README.md)** - Complete setup instructions
- **[Release Notes](RELEASE_NOTES_v1.2.0.md)** - What's new in v1.2.0
- **[Deployment Checklist](DEPLOYMENT_CHECKLIST.md)** - Step-by-step deployment guide
- **[Development Summary](DEVELOPMENT_SUMMARY.md)** - Technical architecture

---

## 🎨 Screenshots

### Dashboard
Real-time recording status with manual controls and quick record presets.

### Calendar View
Multi-week visual schedule with color-coded events - click any day to create a new schedule.

### Settings Page
Configure audio device, customize filename format, backup/restore schedules.

---

## 🔧 Configuration

### Audio Device
Web interface auto-detects USB audio devices. Manual selection available in Settings.

### Recording Filenames
Default format: `YYYY_MMM_DD_HH:MM_L.wav` (e.g., `2026_Jan_17_14:30_L.wav`)

Customize channel suffixes in Settings:
- Left channel: `L` (default) → Change to anything
- Right channel: `R` (default) → Change to anything

### Backup/Restore
Export schedules (`.sched`) and configuration (`.conf`) separately.  
Import with automatic backup and one-click revert.

---

## 📊 System Performance

| Resource | Usage | Notes |
|----------|-------|-------|
| **CPU** | <5% | During recording on Pi 3/4 |
| **RAM** | ~100 MB | Application memory |
| **Disk I/O** | 384 KB/s | Sustained write rate |
| **File Size** | ~345 MB/hour | Per channel (WAV format) |
| **Network** | <1 Mbps | Web UI access |

---

## 🛠️ Development

### Project Structure
```
audio-recorder/
├── app.py              # Flask web server
├── recorder.py         # Audio capture engine
├── scheduler.py        # Job scheduling
├── templates_manager.py # Recording templates
├── templates/          # HTML templates
├── configs/            # ALSA & udev configs
├── install.sh          # Automated installer
└── requirements.txt    # Python dependencies
```

### Built With
- **Backend:** Python 3.11+, Flask, APScheduler
- **Frontend:** HTML5, Tailwind CSS, Vanilla JavaScript
- **Audio:** FFmpeg, ALSA
- **Database:** SQLite3

### Contributing
Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

---

## 📋 Changelog

### v1.2.0 (2026-01-17) - Current
- **Fixed:** Recording stop button error
- **Added:** Live date/time clock in navigation
- **Added:** Configurable recording filenames
- **Added:** Calendar day click to create schedules
- **Added:** Complete backup/restore system

### v1.1.0 (2026-01-17)
- **Added:** Automated installation script
- **Fixed:** Username detection for systemd service

### v1.0.0 (2026-01-17)
- Initial release with core recording and scheduling features

See [RELEASE_NOTES_v1.2.0.md](RELEASE_NOTES_v1.2.0.md) for detailed changes.

---

## 🐛 Known Issues

None currently reported for v1.2.0.

Report issues: [GitHub Issues](https://github.com/vilpter/ilc-Audio-Recorder/issues)

---

## 📝 License

[Specify your license here - e.g., MIT, GPL-3.0, etc.]

---

## 🙏 Acknowledgments

- **Testing:** User feedback and field testing
- **Platform:** Raspberry Pi Foundation
- **Audio Processing:** FFmpeg project

---

## 📞 Support

- **Issues:** [GitHub Issues](https://github.com/vilpter/ilc-Audio-Recorder/issues)
- **Documentation:** See README.md and wiki
- **Quick Fixes:** Run `./fix_service.sh` or `./configure_audio.sh`

---

## 🗺️ Roadmap

### Planned Features (v1.3.0+)
- Real-time status polling
- Disk space monitoring dashboard
- Audio level meter
- Optional post-processing (WAV → MP3/FLAC)
- Email/webhook notifications

### Feedback Wanted
Have ideas? [Open an issue](https://github.com/vilpter/ilc-Audio-Recorder/issues/new) with the `enhancement` label.

---

**Made with ❤️ for archivists, broadcasters, and audio enthusiasts**
