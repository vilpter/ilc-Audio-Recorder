# Changelog

All notable changes to the ILC Audio Recorder project are documented in this file.

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
