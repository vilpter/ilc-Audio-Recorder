# Church Recording - Technical Architecture

This document provides technical details for developers and system administrators.

---

## Technology Stack

### Backend
- **Python 3.11+** (ARM64 optimized)
- **Flask 3.0.0** - Lightweight web framework
- **Flask-Login** - Session authentication
- **APScheduler 3.10.4** - Background job scheduling
- **SQLite3** - Database for schedules, config, and users
- **FFmpeg** - Audio/video processing (system package)
- **ALSA** - Audio hardware interface (system package)
- **Requests** - HTTP client for camera control

### Frontend
- **HTML5** - Semantic markup
- **Tailwind CSS** (CDN) - Utility-first styling
- **Vanilla JavaScript** - No frameworks, lightweight
- **Fetch API** - REST communication

### System Integration
- **systemd** - Service management
- **ALSA** - Audio device configuration
- **udev** - Device rule management
- **h264_v4l2m2m** - Hardware-accelerated video encoding (Raspberry Pi)

---

## Hardware Compatibility

### Confirmed Compatible
- Raspberry Pi 4 (all RAM variants)
- Raspberry Pi 3 Model B/B+
- Behringer UCA202/UCA222 USB audio interface
- PTZOptics cameras (RTSP/HTTP CGI control)
- Pi OS Lite 64-bit (Trixie/Bookworm)

### Performance Metrics (Pi 3/4)

| Resource | Usage | Notes |
|----------|-------|-------|
| **CPU** | <5% | During audio recording |
| **RAM** | ~100 MB | Application memory |
| **Disk I/O** | 384 KB/s | Audio sustained write rate |
| **Audio File Size** | ~345 MB/hour | Per channel (WAV format) |
| **Video File Size** | ~2 GB/hour | Raw RTSP stream at 1080p |
| **Network** | <1 Mbps | Web UI access |

---

## Database Schema

### Schedule Database (`~/.audio-recorder/schedule.db`)

#### `scheduled_jobs` Table
```sql
CREATE TABLE scheduled_jobs (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    start_time TEXT NOT NULL,
    duration INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    completed_at TEXT,
    notes TEXT,
    is_recurring INTEGER DEFAULT 0,
    recurrence_pattern TEXT,
    parent_template_id TEXT,
    allow_override INTEGER DEFAULT 0,
    capture_video INTEGER DEFAULT 0
)
```

#### `recording_instances` Table
```sql
CREATE TABLE recording_instances (
    id TEXT PRIMARY KEY,
    parent_job_id TEXT NOT NULL,
    occurrence_date TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    started_at TEXT,
    completed_at TEXT,
    notes TEXT,
    FOREIGN KEY (parent_job_id) REFERENCES scheduled_jobs(id) ON DELETE CASCADE
)

CREATE INDEX idx_instances_parent ON recording_instances(parent_job_id)
CREATE INDEX idx_instances_date ON recording_instances(occurrence_date)
```

Tracks individual occurrences of recurring jobs. Created automatically when recordings execute or on-demand when past occurrences are viewed in the calendar.

#### `system_config` Table
```sql
CREATE TABLE system_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
```

Default configuration keys:
- `audio_device` - ALSA device ID or 'auto'
- `channel_left_suffix` - Left channel filename suffix (default: 'L')
- `channel_right_suffix` - Right channel filename suffix (default: 'R')
- `camera_ip` - PTZOptics camera IP address
- `camera_username` - Camera HTTP auth username
- `camera_password` - Camera HTTP auth password
- `usb_storage_path` - Video recording storage path

### Authentication Database (`~/.audio-recorder/auth.db`)

#### `users` Table
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL
)
```

---

## API Reference

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET/POST | `/login` | Login page and authentication |
| GET | `/logout` | Logout current user |
| GET/POST | `/setup` | Initial admin user setup |
| GET/POST | `/change-password` | Change user password |

### Pages (require login)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Dashboard (index) |
| GET | `/recordings` | Recordings file browser |
| GET | `/calendar` | Calendar view |
| GET | `/settings` | Settings page |
| GET | `/camera` | Camera control page |

### Audio Recording API
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/status` | Get current recording status |
| POST | `/api/record/start` | Start manual recording |
| POST | `/api/record/stop` | Stop current recording |

### Schedule API
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/schedule` | Create scheduled recording |
| DELETE | `/api/schedule/<job_id>` | Delete scheduled recording |
| PUT | `/api/schedule/<job_id>` | Update scheduled recording |
| GET | `/api/schedule/<job_id>/occurrence/<occurrence_date>` | Get/create instance for recurring job occurrence |

### Recordings API
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/recordings/<filename>` | Download recording file |
| DELETE | `/api/recordings/<filename>` | Delete recording file |
| POST | `/api/recordings/batch/delete` | Batch delete recordings |
| POST | `/api/recordings/batch/download` | Batch download as ZIP |

### Configuration API
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/config/filename` | Get filename config |
| POST | `/api/config/filename` | Update filename config |
| GET | `/api/audio/devices` | List available audio devices |
| GET | `/api/audio/config` | Get audio device config |
| POST | `/api/audio/config` | Set audio device config |
| POST | `/api/audio/test` | Test audio device (5 sec) |

### System API
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/logs` | Get application logs (supports type param: app, recorder, scheduler, ffmpeg, error) |
| GET | `/api/logs/paths` | Get all log file paths |
| GET | `/api/system/disk` | Get disk space info |

### Backup/Restore API
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/export/<type>` | Export schedules or config |
| POST | `/api/import/<type>` | Import schedules or config |
| POST | `/api/revert/<type>` | Revert to backup |
| GET | `/api/revert/available` | Check available backups |

### Camera/Video API
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET/POST | `/api/camera/preset/<id>` | Get/move to camera preset |
| GET | `/api/camera/config` | Get camera config |
| POST | `/api/camera/config` | Save camera config |
| POST | `/api/camera/test` | Test camera connection |
| GET | `/api/camera/stream` | Get RTSP stream URL |
| GET | `/api/video/status` | Get video recording status |
| POST | `/api/video/start` | Start video recording |
| POST | `/api/video/stop` | Stop video recording |
| GET | `/api/video/storage` | Get video storage info |
| GET | `/api/video/files` | List video files |
| POST | `/api/video/transcode/cancel` | Cancel transcoding |

---

## Design Decisions

### Audio Format
- **WAV format only** - No automatic compression (preserves quality)
- **48kHz sample rate** - Professional standard, fixed
- **16-bit depth** - CD quality, minimal CPU usage
- **Dual-mono output** - Separate L/R files for independent sources

### Video Capture
- **Raw RTSP recording** - Direct stream capture, no re-encoding during record
- **Background transcoding** - Hardware-accelerated MP4 conversion after recording
- **h264_v4l2m2m** - Raspberry Pi GPU encoder for efficient transcoding
- **USB storage default** - `/mnt/usb_recorder` for large video files

### Duration Limits
- **4-hour default limit** - Prevents accidental very long recordings
- **Override option** - Allow longer recordings with explicit checkbox
- **Disk space pre-flight** - Check 2x estimated size before starting

### Storage Strategy
- **Audio files** - `~/recordings/` (on SD card)
- **Video files** - USB storage (configurable path)
- **Databases** - `~/.audio-recorder/` (hidden directory)

### Security
- **Session-based authentication** - Flask-Login with secure sessions
- **Password hashing** - Werkzeug security (bcrypt-based)
- **Local network only** - No external authentication (Phase 1)

---

## File Structure

```
church-recording/
├── app.py                    # Flask web server, all routes
├── recorder.py               # Audio capture engine (FFmpeg)
├── video_recorder.py         # Video capture and camera control
├── scheduler.py              # Job scheduling (APScheduler)
├── auth.py                   # User authentication
├── requirements.txt          # Python dependencies
├── audio-recorder.service    # systemd service file
├── install.sh                # Automated installer
├── fix_service.sh            # Service repair script
├── configure_audio.sh        # Audio device setup script
├── troubleshoot_audio.sh     # Scheduled recording diagnostics
├── audio_analyzer.py         # Audio analysis utilities (future)
├── templates/
│   ├── index.html            # Dashboard
│   ├── login.html            # Login page
│   ├── setup.html            # Initial setup
│   ├── change_password.html  # Password change
│   ├── recordings.html       # File browser
│   ├── calendar.html         # Calendar view
│   ├── settings.html         # Settings page
│   ├── camera.html           # Camera control
│   └── templates_mgmt.html   # (deprecated, may be removed)
└── configs/
    ├── asound.conf           # ALSA configuration
    └── 85-usb-audio.rules    # udev rule for USB audio
```

---

## Storage Locations

| Data | Location | Notes |
|------|----------|-------|
| Audio recordings | `~/recordings/` | WAV files with timestamp names |
| Video recordings | `/mnt/usb_recorder/` | Configurable in Settings |
| Schedule database | `~/.audio-recorder/schedule.db` | SQLite |
| Auth database | `~/.audio-recorder/auth.db` | SQLite |
| Application logs | `/var/log/audio-recorder/app.log` | General application log |
| Error logs | `/var/log/audio-recorder/error.log` | Error-level messages |
| Recorder logs | `~/.audio-recorder/recorder.log` | Audio capture operations |
| Scheduler logs | `~/.audio-recorder/scheduler.log` | Scheduled job execution |
| FFmpeg logs | `~/.audio-recorder/ffmpeg.log` | FFmpeg stderr output |
| Service file | `/etc/systemd/system/audio-recorder.service` | Installed by install.sh |

---

## Backup Files

### Export Formats

**Schedule Export** (`.sched`)
- JSON format containing all scheduled recordings
- Includes recurring patterns and status

**Configuration Export** (`.conf`)
- JSON format containing system_config table
- Audio device, channel suffixes, camera settings

### Backup Location
Pre-import backups are stored in `~/.audio-recorder/`:
- `schedule_backup.sched` - Auto-created before schedule import
- `config_backup.conf` - Auto-created before config import

### One-Click Revert
If import causes issues, use Settings → Revert to restore from automatic backup.

---

*Last updated: 2026-01-25*
