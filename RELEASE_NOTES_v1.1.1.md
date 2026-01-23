# Audio Recorder v1.1.1 Release Notes

**Release Date:** 2026-01-17  
**Status:** Production Ready

---

## What's New in v1.1.1

### 🐛 Critical Bug Fix
**Fixed recording state synchronization bug**
- Resolved issue where "Stop Recording" button would error after recording completed naturally
- Fixed state desynchronization between web UI and backend recorder
- Status now automatically updates when recordings finish (via existing 2-second polling)
- **This also implements real-time status polling** (previously listed as Phase 3)

**Details:**
- `/api/status` endpoint now syncs with actual `recorder.is_recording()` state
- `/api/record/stop` checks actual recorder state instead of cached status
- No more "No recording in progress" errors when stopping completed recordings

---

### 🎛️ Audio Device Configuration GUI (Phase 2 → v1.1.1)
**NEW: Settings Page** with complete audio device management

**Features:**
- ✅ **Auto-detect mode** (recommended) - automatically selects USB audio device
- ✅ **Manual selection** - choose specific device from dropdown
- ✅ **Device testing** - 3-second test recording to verify device works
- ✅ **Live device list** - shows all available ALSA capture devices
- ✅ **Device information** - displays card number, name, description
- ✅ **Configuration persistence** - settings saved to database
- ✅ **Visual status indicators** - shows connected/not found status

**Benefits:**
- No more SSH required to configure audio device
- No more manual editing of recorder.py
- Dynamic device switching without code changes
- Handles multiple USB audio devices gracefully

---

### 📊 Log Viewer (Phase 2 → v1.1.1)
**NEW: Built-in log viewer** in Settings page

**Features:**
- ✅ View application logs (app.log) and error logs (error.log)
- ✅ Selectable line count (50, 100, 200, 500 lines)
- ✅ Auto-refresh every 5 seconds
- ✅ Terminal-style display (monospace, syntax highlighting)
- ✅ Scroll to bottom on load
- ✅ Manual refresh button

**Benefits:**
- No more SSH required to check logs
- Real-time troubleshooting from web UI
- Easy debugging of recording issues

---

### 📅 Calendar Click-to-Create (Improvement)
**Enhanced calendar interaction**

**Features:**
- ✅ Click any calendar day to create new recording
- ✅ Modal popup with full scheduling form
- ✅ Date pre-filled with clicked day
- ✅ Time defaults to 09:00 (customizable)
- ✅ All scheduling options available (recurring, templates, override)
- ✅ Create button saves and refreshes calendar
- ✅ Clicking existing events still shows event details

**Benefits:**
- Faster workflow for creating schedules
- Visual, intuitive schedule creation
- No need to type dates manually

---

## Changes from v1.1.0

### Added
- ✨ **Settings page** (`/settings`) with audio device config and log viewer
- 🎛️ Auto-detect audio device system with manual override
- 🧪 Audio device testing (3-second test recording)
- 📊 Log viewer with auto-refresh
- 📅 Click-to-create modal on calendar days
- 🔧 System configuration storage (database)
- 🎯 Real-time status synchronization

### Fixed
- 🐛 **Critical:** Recording state desync causing "Stop Recording" errors
- 🐛 Status not updating when recordings finish naturally
- 🐛 Hardcoded audio device in recorder.py

### Improved
- 📈 Real-time status polling now works correctly (moved from Phase 3)
- 🎨 Settings navigation link added to all pages
- 📝 Better error messages in audio device configuration
- 🔄 Automatic state sync every 2 seconds

### Removed
- ❌ iCal export removed from roadmap (as requested)

---

## Upgrade from v1.1.0

### Quick Upgrade
```bash
cd ~/audio-recorder

# Backup database
cp ~/.audio-recorder/schedule.db ~/schedule-backup.db

# Stop service
sudo systemctl stop audio-recorder

# Extract new version
tar -xzf ~/audio-recorder-v1.1.1.tar.gz --strip-components=1

# Restart service
sudo systemctl restart audio-recorder

# Check status
sudo systemctl status audio-recorder
```

The database will auto-upgrade with the new `system_config` table on first run.

---

## New System Requirements

No changes - same as v1.1.0:
- Python 3.11+
- FFmpeg, ALSA, SQLite3
- Raspberry Pi OS Lite (64-bit) Trixie or Bookworm
- Raspberry Pi 3B/3B+ or Pi 4

---

## Feature Comparison

| Feature | v1.0.x | v1.1.0 | v1.1.1 |
|---------|--------|--------|--------|
| Automated installer | ❌ | ✅ | ✅ |
| Audio device auto-detect | ❌ | ❌ | ✅ |
| Audio device GUI config | ❌ | ❌ | ✅ |
| Log viewer in UI | ❌ | ❌ | ✅ |
| Recording state sync | ❌ | ❌ | ✅ |
| Real-time status polling | ❌ | ❌ | ✅ |
| Calendar click-to-create | ❌ | ❌ | ✅ |
| Settings page | ❌ | ❌ | ✅ |

---

## Known Issues

None reported for v1.1.1.

### From Earlier Versions (Now Fixed)
- ~~Recording stop button errors~~ → Fixed in v1.1.1
- ~~Status not updating~~ → Fixed in v1.1.1
- ~~Audio device hardcoded~~ → Fixed with GUI config
- ~~Service user hardcoded as 'pi'~~ → Fixed in v1.1.0
- ~~Audio device card number assumed~~ → Fixed in v1.1.0

---

## Roadmap

### Completed (v1.1.1)
- ✅ Recording state synchronization
- ✅ Real-time status polling
- ✅ Audio device configuration GUI
- ✅ Log viewer in web UI
- ✅ Calendar click-to-create

### Future Enhancements (Post-Testing Phase)
Consolidated from Phase 2 & Phase 3:

**User Management & Security:**
- 🔐 Basic HTTP authentication
- 👤 User preferences/settings

**File Management:**
- 🗑️ Automatic cleanup with retention policy
- 💾 Disk space monitoring dashboard
- 🔄 Optional post-processing (WAV → MP3/FLAC)
- 📦 Batch operations (delete multiple files)

**UI Improvements:**
- 🌙 Dark mode
- 📱 Mobile-responsive improvements
- 🎨 Customizable themes

**Recording Features:**
- 🎵 Audio level meter (preview without recording)
- 🔊 Pre-recording level check
- ⏯️ Pause/resume recording

**Advanced Scheduling:**
- 📅 Drag-and-drop calendar rescheduling
- 🔔 Email/webhook notifications
- 📤 Schedule import/export
- 🔁 Template-based bulk scheduling

**System Features:**
- 📊 Recording statistics/analytics
- 📈 Storage usage graphs
- 🔍 Search recordings by date/name
- 🏷️ Tagging system for recordings

---

## Testing Status

### ✅ Tested
- Recording state synchronization fix
- Audio device auto-detection
- Audio device configuration persistence
- Log viewer functionality
- Calendar modal creation
- Settings page navigation

### ⏳ Requires Live Testing
- Long-duration recording (4+ hours) with new state sync
- Multiple device switching scenarios
- Heavy concurrent schedule load

---

## Migration Notes

### Database Changes
v1.1.1 adds a new `system_config` table:
```sql
CREATE TABLE IF NOT EXISTS system_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

This is created automatically on first run. No manual migration needed.

### Configuration Files
- No changes to `asound.conf` or systemd service
- New audio device config is stored in database, not files

---

## Documentation Updates

### Updated Files
- `README.md` - Added Settings page documentation
- `DEPLOYMENT_CHECKLIST.md` - Updated testing procedures
- `PROJECT_SCOPE.md` - Consolidated roadmap

### New Files
- `RELEASE_NOTES_v1.1.1.md` - This file
- `ROADMAP.md` - Consolidated future enhancements

---

## Support

### Quick Troubleshooting
```bash
# View logs from web UI
# Navigate to Settings → Log Viewer

# Or via command line:
tail -f /var/log/audio-recorder/app.log
tail -f /var/log/audio-recorder/error.log

# Test audio device from Settings page
# Or via command line:
cd ~/audio-recorder
./configure_audio.sh

# Check service status
sudo systemctl status audio-recorder
```

### Common Questions

**Q: How do I change my audio device?**  
A: Go to Settings → Audio Device Configuration → Select your device → Test → Save

**Q: Why doesn't my recording stop?**  
A: This was a bug in v1.1.0, fixed in v1.1.1. Upgrade to resolve.

**Q: How do I quickly create a recording for tomorrow?**  
A: Go to Calendar → Click tomorrow's date → Fill in details → Create

**Q: Where are my logs?**  
A: Settings → Log Viewer (or `/var/log/audio-recorder/`)

---

## Credits

**Testing & Feedback:** User community
**Platform:** Raspberry Pi Foundation

---

**Questions or Issues?**  
Check the Settings page for device configuration and logs before reporting issues!
