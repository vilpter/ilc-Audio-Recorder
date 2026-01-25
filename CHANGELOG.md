# Changelog

All notable changes to the Church Recording project are documented in this file.

## [1.5.3] - 2026-01-25

### Added
- **Enhanced Diagnostic Logging** - Comprehensive logging for troubleshooting scheduled recordings
  - Dedicated `recorder.log` for audio capture operations
  - Dedicated `scheduler.log` for job scheduling events
  - Dedicated `ffmpeg.log` for FFmpeg stderr output
  - System state logging at recording start (environment variables, ALSA mixer state)
  - 60-second heartbeat logging during active recordings
  - File size verification on recording completion
- **Log Viewer Improvements** (Settings page)
  - New log types: Recorder, Scheduler, FFmpeg
  - Displays log file path for each log type
  - New `/api/logs/paths` endpoint for log file locations
- **Troubleshooting Script** (`troubleshoot_audio.sh`)
  - Diagnoses scheduled recording issues on Raspberry Pi
  - Tests device detection in main thread vs background thread
  - Validates FFmpeg and arecord capture
  - Checks audio device configuration
- **Audio Analyzer** (`audio_analyzer.py`)
  - Utility module for audio file analysis (future feature)
  - Silence detection using FFmpeg silencedetect filter
  - Average dB level analysis
  - Functions: `analyze_file()`, `analyze_multiple_files()`, `detect_silence()`

### Changed
- All log timestamps now use local timezone (previously UTC)
- Log viewer dropdown includes all available log types

### Technical
- New `LocalTimeFormatter` class for timezone-aware logging
- Added `_log_system_state()` function in recorder.py
- Added `_log_scheduler_environment()` function in scheduler.py
- Added `_log_ffmpeg_output()` function for FFmpeg stderr capture

---

## [1.5.2] - 2026-01-25

### Changed
- **Storage Consolidation** - Unified storage location for audio and video recordings

---

## [1.5.1] - 2026-01-24

### Changed
- **Navigation** - Renamed "New/In Progress" to "Control" across all pages
- **Settings** - Renamed "Recording Filename Configuration" to "Audio Filename Nomenclature"
- **Calendar** - Simplified "Also capture video" label (removed "from PTZ camera")
- **Calendar Events** - Added [A] or [A&V] indicator to show recording type
- **Event Details** - Shows "Audio only" or "Audio & Video" type in popup

### Added
- **ARCHITECTURE.md** - New consolidated technical documentation with API reference, database schema, and design decisions

### Removed
- **docs/ folder** - Removed obsolete planning documents (content migrated to ARCHITECTURE.md)

---

## [1.5.0] - 2026-01-24

### Changed
- **Rebranded** from "Audio Recorder" to "Church Recording"
- **Schedule page (/)** - Calendar renamed to Schedule, now the only way to create scheduled recordings
- **New/In Progress page (/camera)** - Camera page renamed, now includes unified recording controls
- **Unified Recording Controls** - Start Audio Only, Video Only, or Both from one page
- **Combined Status Panel** - View audio and video recording status together
- **Mobile Page Indicator** - Shows current page name on mobile devices
- **Simplified Navigation** - Removed standalone Schedule page, consolidated workflow

### Removed
- Standalone Schedule page (`/schedule`) - functionality moved to calendar modal
- Quick Record from Settings page - moved to New/In Progress page
- Recording Status from Settings page - moved to New/In Progress page

### Technical
- Deleted `schedule.html` template
- Removed `/schedule` route from `app.py`
- Updated navigation across all templates

---

## [1.4.0] - 2026-01-24

### Added
- **Video Capture System** - PTZOptics camera integration for synchronized A/V recording
  - New Camera tab for PTZ preset control and video recording
  - RTSP stream capture using ffmpeg with `-c copy` (zero CPU re-encoding)
  - Hardware-accelerated transcoding using `h264_v4l2m2m` (Raspberry Pi GPU)
  - Automatic post-processing: raw files saved to `/raw/`, transcoded to `/processed/`
  - Real-time transcode progress tracking with percentage display
  - USB storage validation with mount point checking

- **PTZ Camera Control**
  - 10 customizable preset buttons with user-defined labels
  - HTTP CGI proxy for PTZOptics camera commands
  - Optional HTTP Basic authentication support
  - Connection testing from Settings page

- **Camera Configuration** (Settings page)
  - Camera IP address and credentials
  - USB storage path configuration
  - Preset naming for intuitive camera positions (e.g., "Podium", "Wide Angle")

- **Scheduled Video Recording**
  - "Also capture video" checkbox in Calendar and Schedule pages
  - Video recording triggered automatically with audio schedules
  - Independent failure handling (audio continues if video fails)

- **Live Stream Viewing**
  - Copyable ffplay command for terminal playback
  - Copyable RTSP URL for VLC and other players

- **New API Endpoints**
  - `GET/POST /api/camera/preset/<id>` - PTZ preset control
  - `GET/POST /api/camera/config` - Camera settings
  - `POST /api/camera/test` - Connection testing
  - `GET /api/camera/stream` - Stream URL info
  - `GET /api/video/status` - Recording & transcode status
  - `POST /api/video/start` - Start video recording
  - `POST /api/video/stop` - Stop video recording (graceful MP4 finalization)
  - `GET /api/video/storage` - USB storage disk space
  - `GET /api/video/files` - List raw and processed videos
  - `POST /api/video/transcode/cancel` - Cancel transcoding

### Changed
- Navigation bar updated with Camera link on all pages
- `/api/record/start` now accepts `capture_video` parameter
- `/api/record/stop` now stops both audio and video if running
- Scheduled jobs now include `capture_video` field

### Technical
- New `video_recorder.py` module for all video functionality
- Database schema extended with `capture_video` column (auto-migrated)
- Added `requests` library dependency for camera HTTP API

---

## [1.3.0] - 2026-01-20

### Added
- **User Authentication** - Full login/logout system with Flask-Login
  - Initial setup wizard for admin account creation
  - Change password functionality
  - "Remember me" persistent sessions
  - All routes now require authentication
- **Batch File Operations** - Multi-select recordings for bulk actions
  - Checkboxes on file rows with "Select All"
  - Batch delete multiple files at once
  - Batch download as ZIP archive
  - New endpoints: `/api/recordings/batch/delete`, `/api/recordings/batch/download`
- **Disk Space Monitoring** - Real-time storage tracking in navigation ribbon
  - Shows "X.X / Y.Y GB" usage on all pages
  - Color-coded warnings: blue (normal), yellow (<24 hours), red pulsing (<10 hours)
  - Hover tooltip with detailed info
  - Auto-refreshes every 30 seconds
  - New endpoint: `/api/system/disk`
- **Calendar Enhancements**
  - Delete button in event details panel
  - Event name as heading (instead of generic "Event Details")
  - End times displayed as time ranges [start - end]
- **Navigation Improvements**
  - Calendar is now the root URL (/)
  - Dashboard content migrated to Settings page
  - Reordered navigation: Calendar | Schedule | Recordings | Settings

### Changed
- 4-hour recording checkbox replaced with dynamic red warning text
- Live date/time clock added to Settings ribbon

### Removed
- **Templates feature** - Eliminated from all files (nav, routes, APIs, export/import)
  - Templates were deemed unnecessary for the workflow
  - Simplifies the application significantly

---

## [1.2.0] - 2026-01-17

### Added
- **Live Date/Time Display** - Real-time clock in navigation bar on all pages
  - Format: `Friday, January 17, 2026 14:30:45`
  - Updates every second
- **Configurable Recording Filenames**
  - New format: `YYYY_MMM_DD_HH:MM_L.wav` (e.g., `2026_Jan_17_14:30_L.wav`)
  - User-customizable channel suffixes (default L/R)
  - Configure in Settings page with live preview
- **Calendar Day Click** - Click any day to create schedule instantly
  - Modal popup with date pre-filled
  - Time defaults to 09:00
  - Full access to all scheduling options
- **Complete Backup/Restore System**
  - Export schedules (.sched) and config (.conf) separately
  - Import with auto-backup and two-step confirmation
  - Quick revert (one-click undo) to restore previous state
  - Automatic backup protection before every import

### Fixed
- Recording stop button error when recording already finished
- Now properly syncs between web UI state and actual recorder process

### Changed
- Settings page now has three major sections: Audio, Filename, Backup/Restore
- Better state management between frontend and backend

---

## [1.1.1] - 2026-01-17

### Added
- **Settings Page** (`/settings`) with audio device configuration and log viewer
- **Audio Device Configuration GUI**
  - Auto-detect mode (recommended) - automatically selects USB audio device
  - Manual selection from dropdown of available devices
  - Device testing with 3-second test recording
  - Live device list with card number, name, description
  - Configuration persistence to database
- **Log Viewer** in Settings page
  - View application logs and error logs
  - Selectable line count (50, 100, 200, 500)
  - Auto-refresh every 5 seconds
  - Terminal-style monospace display
- **Calendar Click-to-Create** - Click any calendar day to create new recording

### Fixed
- Critical recording state synchronization bug
- Status not updating when recordings finish naturally
- Hardcoded audio device in recorder.py

### Changed
- Real-time status polling now works correctly
- Settings navigation link added to all pages

### Removed
- iCal export removed from roadmap

---

## [1.1.0] - 2026-01-17

### Added
- **Automated Installer** (`install.sh`) - One-command setup
  - Automatically detects username (no more hardcoded `pi`)
  - Auto-detects audio device card number
  - Generates customized systemd service file
  - Tests everything and shows web UI URL

### Fixed
- Hardcoded `pi` username in systemd service (now auto-detected)
- Audio device card number assumptions (now auto-detected)

### Changed
- Installation time reduced from ~15 minutes to ~2 minutes
- Clearer documentation structure

---

## [1.0.0] - 2026-01-17

### Added
- **Core Recording Features**
  - Dual-mono capture (48kHz, 16-bit WAV, independent L/R channels)
  - Manual start/stop from web UI
  - 4-hour duration limit with override option
  - Pre-flight disk space checking (requires 2x estimated size)
- **Scheduling System**
  - One-time scheduled recordings
  - Recurring schedules (daily, weekly, monthly patterns)
  - Multi-week calendar view with color-coded events
  - Schedule persistence across reboots (APScheduler + SQLite)
- **Web Interface**
  - Dashboard with real-time recording status
  - Schedule management page
  - Visual calendar view
  - File browser with download/delete
- **System Integration**
  - Auto-start service (systemd)
  - ALSA configuration for Behringer UCA202
  - udev rules for consistent device numbering

---

## System Requirements

### Hardware
- Raspberry Pi 3B/3B+ or Pi 4 (2GB+ RAM recommended)
- Behringer UCA202 or UCA222 USB audio interface
- 32GB+ microSD card (Class 10 or better)
- Network connection (Ethernet or WiFi)

### Software
- Raspberry Pi OS Lite (64-bit) - Trixie (Debian 13) recommended
- Alternative: Bookworm (Debian 12) also supported
- Python 3.11+
- FFmpeg, ALSA, SQLite3
