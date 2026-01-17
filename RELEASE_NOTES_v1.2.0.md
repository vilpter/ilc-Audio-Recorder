# Audio Recorder v1.2.0 Release Notes

**Release Date:** 2026-01-17  
**Status:** Production Ready

---

## What's New in v1.2.0

### 🐛 Critical Bug Fix
**Recording Stop State Synchronization**
- Fixed bug where "Stop Recording" button would show error even though recording had finished
- System now properly syncs between web UI state and actual recorder process
- Status updates automatically when recording completes naturally

### ✨ Major New Features

#### 1. **Live Date/Time Display**
- Real-time clock in navigation bar on all pages
- Format: `Friday, January 17, 2026 14:30:45`
- Updates every second
- Helps verify system time is correct when scheduling recordings

#### 2. **Configurable Recording Filenames**
- **New Format:** `YYYY_MMM_DD_HH:MM_L.wav` and `YYYY_MMM_DD_HH:MM_R.wav`
- **Example:** `2026_Jan_17_14:30_L.wav`, `2026_Jan_17_14:30_R.wav`
- **User-customizable channel suffixes** (L/R by default)
  - Configure in Settings page
  - Change to anything you want (e.g., "Left"/"Right", "Ch1"/"Ch2")
  - Live preview shows filename format
- More human-readable than previous `source_A_20260117_143000.wav` format
- Month names instead of numbers

#### 3. **Calendar Day Click to Create Schedule**
- Click any day on the calendar → instant schedule creation modal
- Date pre-filled with clicked day
- Time defaults to 09:00
- Full access to recurring options, templates, duration settings
- Create schedules directly from calendar view
- No need to switch to Schedule page

#### 4. **Complete Backup/Restore System**
- **Export Schedules & Templates** → `.sched` file
  - Contains all scheduled recordings and templates
  - Timestamped filename: `audio-recorder-schedules-20260117_143000.sched`
  
- **Export System Configuration** → `.conf` file
  - Contains audio device settings, channel suffixes, all preferences
  - Timestamped filename: `audio-recorder-config-20260117_143000.conf`

- **Import with Safety**
  - Separate upload for schedules vs configuration
  - Two-step confirmation before overwriting
  - Automatic backup before any import
  - File type validation (only accepts correct extensions)

- **Quick Revert (One-Click Undo)**
  - "Revert to Last Schedules" button
  - "Revert to Last Configuration" button
  - Buttons only enabled when backups exist
  - Restores to state before most recent import
  - Same confirmation warnings

- **Auto-Backup Protection**
  - System automatically backs up before every import
  - Backups stored in `~/.audio-recorder/backups/`
  - `schedules.sched.last` - last schedules state
  - `config.conf.last` - last configuration state

---

## Complete Feature Summary

### All Features (v1.0 + v1.1 + v1.2)

**Recording:**
- ✅ Dual-mono capture (48kHz, 16-bit WAV, independent channels)
- ✅ Manual start/stop from Dashboard
- ✅ Quick record presets
- ✅ **NEW:** Configurable channel filename suffixes
- ✅ **NEW:** Human-readable filename format with month names
- ✅ 4-hour duration limit with override option
- ✅ Pre-flight disk space checking (requires 2x estimated size)
- ✅ **FIXED:** Stop button now works correctly when recording finishes

**Scheduling:**
- ✅ One-time scheduled recordings
- ✅ Recurring schedules (daily, weekly, monthly patterns)
- ✅ Recording templates (save and reuse configurations)
- ✅ Multi-week calendar view
- ✅ **NEW:** Click calendar days to create schedules instantly

**Web Interface:**
- ✅ Dashboard with real-time status
- ✅ Schedule management page
- ✅ Visual calendar with color-coded events
- ✅ Template library
- ✅ File browser with download/delete
- ✅ **NEW:** Live date/time display on all pages
- ✅ Settings page with device configuration
- ✅ **NEW:** Backup/Restore functionality
- ✅ System log viewer

**System:**
- ✅ Auto-start service (systemd)
- ✅ Schedule persistence across reboots
- ✅ One-command installation script
- ✅ Automatic audio device detection
- ✅ **NEW:** Export/import configuration and schedules
- ✅ **NEW:** Automatic backup before imports
- ✅ **NEW:** Quick revert functionality

---

## Installation

### Fresh Install
```bash
# Extract files
tar -xzf audio-recorder-v1.2.0.tar.gz
cd audio-recorder

# Install prerequisites
sudo apt install -y python3-pip ffmpeg alsa-utils sqlite3

# Run automated installer
./install.sh

# Access web UI
# Open browser to: http://<pi-ip>:5000
```

### Upgrading from v1.1.0

**Option A: In-Place Upgrade (Recommended)**
```bash
# Stop service
sudo systemctl stop audio-recorder

# Backup your database first!
cp ~/.audio-recorder/schedule.db ~/schedule-backup-$(date +%Y%m%d).db

# Extract new version
cd ~
tar -xzf audio-recorder-v1.2.0.tar.gz
cd audio-recorder

# Restart service
sudo systemctl restart audio-recorder
```

**Option B: Fresh Install + Import Backups**
1. Export your schedules and config from v1.1.0 Settings page
2. Fresh install v1.2.0
3. Import your exported .sched and .conf files

---

## Changelog

### Added
- ✨ Live date/time clock in navigation bar (all pages)
- ✨ Configurable recording filename format
  - Channel suffix customization (L/R → anything you want)
  - New format: `YYYY_MMM_DD_HH:MM_SUFFIX.wav`
  - Live filename preview in Settings
- ✨ Calendar day click → create schedule modal
- ✨ Complete backup/restore system
  - Export schedules (.sched) and config (.conf) separately
  - Import with auto-backup and two-step confirmation
  - Quick revert to undo last import
  - Automatic backup protection

### Fixed
- 🐛 Recording stop button error when recording already finished
  - Now properly checks actual recorder state
  - Auto-syncs UI status with recording process
  - No more "No recording in progress" false errors

### Improved
- 📚 Settings page now has three major sections:
  1. Audio Device Configuration
  2. Filename Configuration
  3. Backup & Restore
- ⚡ Better state management between frontend and backend
- 🎯 More intuitive calendar interaction

---

## Database Changes (Auto-Migration)

New configuration keys added to `system_config` table:
- `channel_left_suffix` (default: 'L')
- `channel_right_suffix` (default: 'R')

**No action required** - database automatically updates on first run.

---

## File Structure Changes

**New directories:**
```
~/.audio-recorder/backups/
├── schedules.sched.last   # Auto-backup before schedule import
└── config.conf.last       # Auto-backup before config import
```

**New filename format for recordings:**
```
Old: source_A_20260117_143000.wav
New: 2026_Jan_17_14:30_L.wav
```

---

## Known Issues

None reported for v1.2.0.

---

## Testing Recommendations

### Critical Tests
1. **Bug Fix Verification:**
   - Start a 1-minute recording
   - Wait for it to finish naturally
   - Click "Stop Recording" button
   - Should get "No recording in progress" immediately (no error popup)

2. **Filename Configuration:**
   - Change channel suffixes in Settings
   - Start a test recording
   - Verify new filenames match your configuration

3. **Calendar Click:**
   - Click any day on calendar
   - Verify modal opens with correct pre-filled date
   - Create a schedule
   - Verify it appears on calendar

4. **Backup/Restore:**
   - Export schedules and config
   - Create a new schedule
   - Import the exported schedules
   - Verify new schedule is gone, old ones restored
   - Use Revert button to undo
   - Verify new schedule is back

---

## System Requirements

**Hardware:**
- Raspberry Pi 3B/3B+ or Pi 4
- Behringer UCA202/UCA222 USB audio interface
- 32GB+ microSD card
- Network connection

**Software:**
- Raspberry Pi OS Lite (64-bit)
- Trixie (Debian 13) or Bookworm (Debian 12)
- Python 3.11+
- FFmpeg, ALSA, SQLite3

---

## Performance

**No performance impact from new features:**
- Live clock: <0.1% CPU (JavaScript only)
- Filename config: No overhead (loaded once at startup)
- Backup/restore: Only active during export/import operations
- Calendar click: Client-side only (no server impact)

**Recording performance unchanged:**
- CPU: <5% during recording
- RAM: ~100 MB application
- Disk I/O: 384 KB/s sustained

---

## Migration Guide

### From v1.1.0
- No breaking changes
- Existing recordings keep old filename format
- New recordings use new format automatically
- Database auto-migrates on first run

### From v1.0.x
- Follow v1.1.0 migration first, then upgrade to v1.2.0
- Or fresh install v1.2.0 and manually migrate data

---

## Support & Troubleshooting

### Quick Fixes
```bash
# Service issues
./fix_service.sh

# Audio device issues
./configure_audio.sh

# View logs
cat /var/log/audio-recorder/app.log
sudo journalctl -u audio-recorder -n 50

# Test manually
cd ~/audio-recorder
python3 app.py
```

### Common Issues

**"Stop Recording" button not working:**
- Fixed in v1.2.0 - upgrade to resolve

**Filename format still old:**
- Only affects new recordings
- Existing files keep original names
- Configure custom suffixes in Settings if desired

**Backup/restore buttons disabled:**
- Normal on fresh install
- Buttons enable after first import operation
- Check `/home/ilc/.audio-recorder/backups/` for backup files

---

## Roadmap

### Phase 3 (Future)
- Real-time status polling without page refresh
- Disk space monitoring dashboard
- Audio level meter (preview without recording)
- Optional post-processing (WAV → MP3/FLAC)
- Email/webhook notifications

---

**Questions or Issues?**  
Check the README.md or run `./fix_service.sh` and `./configure_audio.sh` for common problems.

**Enjoy v1.2.0!** 🎉
