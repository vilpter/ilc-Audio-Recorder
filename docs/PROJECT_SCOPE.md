# Project: Headless Dual-Mono Audio Recording System
**Hardware:** Raspberry Pi 4 + Behringer UCA202 USB Interface  
**Status:** Scope Definition Phase - REVISED  
**Created:** 2026-01-12  
**Last Updated:** 2026-01-12

---

## Revision Summary

**Key Decisions Made:**
- ✅ Scheduler: APScheduler confirmed (see alternatives analysis in Section 2)
- ✅ File format: Keep WAV only (no automatic conversion)
- ✅ Duration limit: 4-hour default with override + pre-flight disk check
- ✅ Sample rate: 48kHz (professional standard)
- ✅ Network: Static IP via DHCP reservation (out of scope for project)
- ✅ Authentication: Phase 2 (local network trusted initially)
- ✅ Notifications: Log file only (no email/webhooks)

**Phase 1 Scope Expanded:**
- Added: Recurring scheduled recordings (daily/weekly/monthly patterns)
- Added: Recording templates (save preset configurations)
- Added: Multi-week calendar view
- Moved to Phase 3: Real-time status display, disk monitoring

**Next Action:** ✅ ALL DECISIONS RESOLVED - READY FOR GREEN LIGHT

---

## Executive Summary
Build a headless Raspberry Pi system that captures two independent mono analog streams via the Behringer UCA202's stereo input, managed through a local web interface. The system will support scheduled recordings, manual triggers, and file management.

---

## 1. Hardware Configuration

### Target Hardware
- **SBC:** Raspberry Pi 4 (any RAM variant, 2GB+ recommended)
  - **Pi 3 Compatibility:** ✅ Fully compatible (see compatibility analysis document)
  - Pi 3 Model B/B+ will work identically with no code changes
  - Only minor differences: slightly slower web UI (< 1s), still excellent performance
- **Audio Interface:** Behringer UCA202
  - 16-bit stereo input
  - 48kHz max sample rate
  - USB 1.1 (class-compliant, no drivers needed)
  - Consistently mapped as ALSA device `hw:1`

### Operating System
- **Recommended:** Raspberry Pi OS Lite (64-bit) - Trixie (Debian 13)
- **Alternative:** Bookworm (Debian 12) also fully supported
- **Version:** Latest stable release (2024 or newer)
- **Download:** https://www.raspberrypi.com/software/operating-systems/
- **Image:** "Raspberry Pi OS Lite (64-bit)" - headless, no desktop environment
- **Why 64-bit:** Better performance, future-proofing, native ARM64 packages
- **Why Trixie:** Newer kernel, updated packages, better hardware support

### Storage Considerations
- **Estimated WAV file size:** ~10 MB/minute/channel (48kHz, 16-bit)
- **1-hour recording:** ~1.2 GB for both channels
- **Recommended:** 32GB+ SD card or external USB drive for `/home/pi/recordings`

---

## 2. Scheduler Options Analysis

### APScheduler (Current Choice)
- **Pros:** 
  - Python-native, integrates directly with Flask
  - Supports cron-like syntax, interval, and one-time jobs
  - Persistent job stores (SQLite, PostgreSQL, etc.)
  - Can reschedule jobs dynamically from code
  - Good documentation and active maintenance
- **Cons:** 
  - Adds Python dependency overhead
  - Requires application to stay running
  - Less battle-tested than system cron
- **Best for:** Applications needing dynamic scheduling via web UI

### Alternative 1: System Cron
- **Pros:**
  - Rock-solid reliability (been around since 1975)
  - Zero Python dependencies
  - Runs independently of application
  - Simple syntax, universal knowledge
- **Cons:**
  - Requires file I/O to modify schedules (parsing crontab)
  - No native "one-time job" support (must delete after execution)
  - Complex recurring patterns need manual calculation
  - Web UI would need to execute shell commands via subprocess
- **Best for:** Static, unchanging schedules

### Alternative 2: Celery + Redis/RabbitMQ
- **Pros:**
  - Industry-standard for distributed task queues
  - Extremely robust, handles failures gracefully
  - Supports advanced patterns (retries, chaining, etc.)
- **Cons:**
  - MASSIVE overkill for this project
  - Requires Redis or RabbitMQ message broker
  - Complex setup and configuration
  - High memory footprint on Pi
- **Best for:** Large-scale distributed systems

### Alternative 3: Schedule (schedule library)
- **Pros:**
  - Simpler than APScheduler
  - Human-readable syntax: `schedule.every().day.at("10:30").do(job)`
  - Minimal dependencies
- **Cons:**
  - No persistence - jobs lost on restart
  - No built-in job storage
  - Application must stay running
  - Would need custom SQLite layer for persistence
- **Best for:** Simple, ephemeral scheduling in long-running scripts

### Alternative 4: Huey
- **Pros:**
  - Lightweight alternative to Celery
  - Redis or SQLite backend
  - Built-in cron-like scheduling
  - Flask integration available
- **Cons:**
  - Less mature than APScheduler
  - Smaller community
  - Still requires separate worker process
- **Best for:** Medium-complexity projects wanting queue + scheduling

### Alternative 5: Python-crontab
- **Pros:**
  - Python wrapper around system cron
  - Can read/write crontab programmatically
  - Benefits from cron's reliability
- **Cons:**
  - Still has cron's limitations (no one-time jobs)
  - Requires careful permission handling
  - Must parse cron syntax for display in UI
- **Best for:** Projects wanting system cron with Python control

### Recommendation: Stick with APScheduler
**Rationale:** Given the requirement for:
- **Recurring schedules** (weekly recordings, etc.)
- **Dynamic job creation** via web UI
- **Job templates** (reusable configurations)
- **Multi-week calendar view** (requires querying scheduled jobs)

APScheduler is the best fit. System cron would require significant custom code to achieve the same functionality, and other options are either too complex or lack persistence.

---

## 3. System Architecture

### A. Operating System
- **Base:** Raspberry Pi OS Lite (64-bit, headless)
- **Rationale:** Minimal overhead, no GUI needed

### B. Audio Stack
- **Capture:** FFmpeg with ALSA backend
- **Format:** Dual mono WAV files (PCM 16-bit, 48kHz)
- **Split Logic:** `channelsplit` filter to separate L/R channels
- **Sample Command:**
  ```bash
  ffmpeg -f alsa -i hw:1 -t 3600 \
    -filter_complex "[0:a]channelsplit=channel_layout=stereo[left][right]" \
    -map "[left]" -acodec pcm_s16le -ar 48000 source_A_20260112.wav \
    -map "[right]" -acodec pcm_s16le -ar 48000 source_B_20260112.wav
  ```

### C. Backend Services
- **Web Framework:** Flask (lightweight, easy to debug)
  - Alternative considered: FastAPI (more modern, but overkill for this scope)
- **Scheduler:** APScheduler + SQLite database
  - Persists schedules across reboots
  - Supports future expansion (recurring jobs, etc.)
- **Process Management:** Python subprocess module with signal handling

### D. Frontend Interface
- **Tech:** HTML + Tailwind CSS (CDN-based, no build step)
- **Access:** Local network only (http://raspberrypi.local:5000 or static IP)
- **Features:**
  1. **Dashboard (/)** 
     - Real-time recording status indicator
     - Manual start/stop controls
     - Quick record button (preset duration)
  2. **Schedule (/schedule)**
     - Create future scheduled recordings
     - View pending/completed jobs
     - Delete scheduled jobs
  3. **Recordings (/recordings)**
     - Browse captured files
     - Download links
     - Delete files
     - Display file size and timestamps

### E. File Organization
```
/home/pi/recordings/
├── source_A_20260112_143022.wav
├── source_B_20260112_143022.wav
├── source_A_20260112_180000.wav
├── source_B_20260112_180000.wav
└── [optional: converted/ subdirectory for MP3/FLAC]
```

**Naming Convention:** `source_[A|B]_YYYYMMDD_HHMMSS.[ext]`

---

## 5. Core Features

### Must-Have (Phase 1)
- [ ] Web UI accessible via local network
- [ ] Manual recording start/stop with duration input
- [ ] Scheduled recording creation/deletion
- [ ] **Recurring scheduled recordings** (daily, weekly, monthly patterns)
- [ ] **Recording templates** (save preset durations/names for reuse)
- [ ] **Multi-week calendar view** of all scheduled recordings
- [ ] File browser with download capability
- [ ] File deletion from web UI
- [ ] Automatic service restart on Pi reboot (systemd)
- [ ] Schedule persistence across reboots

### Should-Have (Phase 2)
- [ ] Basic authentication for web UI
- [ ] Auto-cleanup of old files (retention policy)
- [ ] Export schedule as iCal
- [ ] Log viewer in web UI
- [ ] Dark mode UI

### Nice-to-Have (Phase 3)
- [ ] Real-time status display (Recording/Idle) with polling
- [ ] **Disk space monitoring with warnings**
- [ ] **Recording duration limits enforcement**
- [ ] Audio level meter preview (non-recording monitoring)
- [ ] Post-recording file conversion (WAV → MP3/FLAC)

---

## 4. Development Decisions Needed

### Decision 1: Post-Processing Strategy
**Question:** How should large WAV files be handled after recording?

**DECISION: Keep files as WAV - no automatic conversion**

**Rationale:** 
- Preserves maximum quality and flexibility
- User can convert offline if needed
- Simplifies system architecture (no post-processing pipeline)
- WAV files can be processed by any audio software later

**Implementation:** No post-processing module needed in Phase 1 or 2. Can be added as optional feature in Phase 3 if desired.

---

### Decision 2: Recording Duration Limits
**Question:** Should there be safeguards against runaway recordings?

**DECISION: 4-hour default limit with override + pre-flight disk check**

**Implementation:**
- Default max duration: 4 hours (14,400 seconds)
- UI provides override checkbox: "Allow longer recording"
- Pre-flight check: Verify at least 2x estimated file size is available before starting
- Estimated size calculation: `duration_seconds * 48000 * 2 bytes * 2 channels * 1.1 safety margin`

**Example:**
- 4-hour recording = ~3.3 GB (both channels)
- Require 6.6 GB free before allowing start

---

### Decision 3: Headless Network Access
**Question:** How should the Pi be accessed on the network?

**DECISION: Static IP handled externally via DHCP reservation**

**Implementation:**
- User will configure DHCP reservation on router
- Application assumes network connectivity is pre-configured
- Documentation will mention accessing via IP address
- No `raspi-config` network setup in project scope

**Out of scope:** Network configuration, WiFi setup, static IP assignment.

---

### Decision 4: Authentication
**Question:** Should the web UI require a password?

**Context:** System runs on local network only.

**Options:**
- **A.** No authentication (Phase 1)
  - Acceptable if network is trusted
- **B.** Basic HTTP auth (Phase 2)
  - Simple username/password
- **C.** Full user management
  - Overkill for single-user system

**Recommendation:** **Option A for Phase 1**, add Option B if deploying on shared networks.

---

### Decision 5: Sample Rate
**Question:** What sample rate should be used?

**DECISION: 48kHz (professional standard)**

**Rationale:**
- Professional video/broadcast standard
- Better future-proofing than 44.1kHz
- UCA202 supports it natively
- Minimal file size difference vs 44.1kHz

**Implementation:** Hard-coded to 48kHz in FFmpeg capture command.

---

## 6. Outstanding Technical Tasks

### Phase 1 Core Tasks

#### A. ALSA Configuration
- [ ] Create `/etc/asound.conf` to ensure UCA202 is always `hw:1`
- [ ] Add udev rule to prevent card number from changing
- [ ] Test with: `arecord -l` and `arecord -D hw:1 -f S16_LE -r 48000 -c 2 test.wav`

#### B. Systemd Service
- [ ] Create `audio-recorder.service` file
- [ ] Enable auto-start on boot
- [ ] Configure restart policy (always/on-failure)
- [ ] Set up logging to `/var/log/audio-recorder/app.log`
- [ ] Configure log rotation to prevent disk fill
- [ ] Log recording start/stop, errors, and schedule execution

#### C. Recurring Schedule Engine
- [ ] Implement cron-style patterns in scheduler.py (daily, weekly, monthly)
- [ ] Add recurrence rules to SQLite schema
- [ ] Create UI for recurring pattern selection
- [ ] Support "every weekday", "every weekend", "specific days" patterns

#### D. Recording Templates System
- [ ] Add templates table to SQLite database
- [ ] Create template CRUD operations (Create, Read, Update, Delete)
- [ ] Build template selection UI in schedule form
- [ ] Save/load template presets (duration, name, recurrence)

#### E. Multi-Week Calendar View
- [ ] Design calendar grid layout (week-by-week or month view)
- [ ] Color-code recurring vs one-time recordings
- [ ] Show recording duration visually
- [ ] Click-to-edit scheduled items
- [ ] Consider using FullCalendar.js library or custom implementation

#### F. Duration Limit & Pre-Flight Check
- [ ] Add 4-hour (14,400 sec) default limit to recorder.py
- [ ] Implement override checkbox in UI
- [ ] Calculate estimated file size: `duration * 48000 * 2 * 2 * 1.1`
- [ ] Check available disk space with `shutil.disk_usage()`
- [ ] Reject recording if insufficient space (need 2x estimate)

#### G. Frontend Completion
- [ ] Complete `schedule.html` template (currently truncated)
- [ ] Create `recordings.html` template
- [ ] Build calendar component for multi-week view
- [ ] Add template management interface
- [ ] Implement recurring schedule selector (dropdowns/radio buttons)

### Phase 2 Tasks (Authentication & Management)
- [ ] Implement basic HTTP auth (Flask-HTTPAuth)
- [ ] Create retention policy configuration
- [ ] Build iCal export functionality
- [ ] Add log viewer in web UI

### Phase 3 Tasks (Advanced Features)
- [ ] Real-time status polling with JavaScript
- [ ] Disk space monitoring dashboard
- [ ] Optional post-processing conversion
- [ ] Audio level meter (non-recording preview)

---

## 6. Installation Workflow (Draft)

### Prerequisites: Fresh Raspberry Pi OS Installation

**Required OS Version:**
- **Raspberry Pi OS Lite (64-bit)** - Trixie (Debian 13) [RECOMMENDED]
- **Alternative:** Bookworm (Debian 12) also works
- **Download:** https://www.raspberrypi.com/software/operating-systems/
- **Image Name:** "Raspberry Pi OS Lite (64-bit)" - No desktop environment

**Step 0: Prepare SD Card & Initial Setup**
1. Use Raspberry Pi Imager to write OS to SD card (32GB+ recommended)
2. **Configure headless access** (use Pi Imager "Settings" gear icon):
   - Enable SSH
   - Set hostname (e.g., `audio-recorder`)
   - Configure WiFi credentials (if not using Ethernet)
   - Set username/password (default: pi/raspberry)
   - Set locale/timezone
3. Insert SD card into Pi and power on
4. Wait 2-3 minutes for first boot
5. Connect via SSH: `ssh pi@audio-recorder.local` (or use IP address)

**Verify OS Version:**
```bash
cat /etc/os-release
# Should show: 
#   PRETTY_NAME="Debian GNU/Linux 13 (trixie)"
#   VERSION="13 (trixie)"
# OR for Bookworm:
#   PRETTY_NAME="Debian GNU/Linux 12 (bookworm)"

uname -m
# Should show: aarch64 (64-bit ARM)
```

### Step-by-Step Installation

**On Fresh Raspberry Pi OS Lite (64-bit):**
```bash
# 1. System updates (REQUIRED - do this first!)
sudo apt update && sudo apt upgrade -y

# 2. Install dependencies
sudo apt update && sudo apt upgrade -y

# 2. Install dependencies
sudo apt install -y python3-pip ffmpeg alsa-utils sqlite3

# 3. Clone/copy project files
cd ~
# [Transfer audio-recorder directory]

# 4. Install Python packages
cd ~/audio-recorder
pip3 install -r requirements.txt

# 5. Configure ALSA
sudo cp configs/asound.conf /etc/asound.conf

# 6. Test audio capture
arecord -D hw:1 -f S16_LE -r 48000 -c 2 -d 5 test.wav

# 7. Install systemd service
sudo cp audio-recorder.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable audio-recorder
sudo systemctl start audio-recorder

# 8. Access web UI
# Navigate to http://raspberrypi.local:5000
```

---

## 9. File Structure (Current Status)
```
audio-recorder/
├── app.py                    # ✅ Flask web server (needs calendar routes)
├── recorder.py               # ✅ Audio capture logic (needs duration limit)
├── scheduler.py              # ✅ Job scheduling (needs recurring patterns)
├── templates.py              # ❌ NEW: Recording templates manager
├── requirements.txt          # ✅ Python dependencies
├── templates/
│   ├── index.html           # ✅ Dashboard (basic version done)
│   ├── schedule.html        # ⚠️  Needs completion + recurring UI
│   ├── calendar.html        # ❌ NEW: Multi-week calendar view
│   ├── templates_mgmt.html  # ❌ NEW: Template management page
│   └── recordings.html      # ❌ File browser (not created yet)
├── configs/
│   ├── asound.conf          # ❌ ALSA config for UCA202
│   └── alsa-base.conf       # ❌ udev rule (optional)
├── audio-recorder.service   # ❌ Systemd service file
└── README.md                # ❌ Installation guide
```

**Legend:**
- ✅ Complete
- ⚠️  Partially complete, needs updates
- ❌ Not started

---

## 8. Estimated Development Timeline

| Phase | Tasks | Time Estimate |
|-------|-------|---------------|
| **Phase 1: Core Functionality** | Complete HTML templates (calendar view, recurring schedules, templates), ALSA config, systemd service, 4-hour limit logic, pre-flight disk check | 4-6 hours |
| **Phase 2: User Management** | Authentication, notifications, retention policy, iCal export | 2-3 hours |
| **Phase 3: Advanced Features** | Real-time status polling, disk monitoring, optional compression | 2-3 hours |
| **Testing & Documentation** | Hardware testing, README, troubleshooting guide | 1-2 hours |

**Total Phase 1:** 5-8 hours of active development + testing  
**Total All Phases:** 9-14 hours

---

## 11. Questions for You - ALL RESOLVED ✅

1. **Do you want automatic post-processing?** ✅ **NO - Keep WAV files only**
2. **Maximum recording duration:** ✅ **4-hour default with override capability**
3. **Disk space handling:** ✅ **Pre-flight check (2x estimated size required)**
4. **Network setup preference:** ✅ **Static IP via DHCP (out of scope for project)**
5. **Will you need recurring schedules?** ✅ **YES - Phase 1 requirement**
6. **Authentication required?** ✅ **Phase 2 (local network trusted initially)**
7. **Notification preference:** ✅ **Log file only - no email/webhooks needed**

---

## 12. Next Steps - READY TO PROCEED

Once you approve the scope:
1. Complete remaining HTML templates
2. Create ALSA and systemd configuration files
3. Write installation README
4. Package for deployment to Pi
5. Hardware testing protocol

**Ready to proceed?** Let me know any scope changes or architectural preferences!

---

## QUICK REFERENCE SUMMARY

### Hardware Requirements
- **Pi Model:** Raspberry Pi 3B/3B+ or Pi 4 (both fully compatible)
- **Audio Interface:** Behringer UCA202 USB
- **Storage:** 32GB+ SD card (Class 10 or better)
- **Power:** 5V/2.5A for Pi 3, 5V/3A for Pi 4

### Software Requirements
- **OS:** Raspberry Pi OS Lite (64-bit) - Trixie (Debian 13) [RECOMMENDED]
  - Alternative: Bookworm (Debian 12) also supported
- **Download:** https://www.raspberrypi.com/software/operating-systems/
- **Image:** "Raspberry Pi OS Lite (64-bit)" - No desktop
- **Network:** Configure static IP via DHCP reservation on router

### Phase 1 Development Status
- ✅ Core Flask app, recorder, scheduler modules written
- ⚠️  Needs: Recurring schedules, templates, calendar view, complete HTML templates
- ⚠️  Needs: ALSA config, systemd service, duration limits
- **Estimated Time:** 5-8 hours

### Ready to Start? ✅
All architectural decisions resolved. Awaiting green light for Phase 1 implementation.
