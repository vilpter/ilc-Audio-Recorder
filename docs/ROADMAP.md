# Audio Recorder - Future Enhancements Roadmap

**Current Version:** v1.1.1  
**Last Updated:** 2026-01-17

---

## Completed Features ✅

### Phase 1 (v1.0.x - v1.1.0)
- ✅ Dual-mono audio capture (48kHz, 16-bit WAV)
- ✅ Web UI (Dashboard, Schedule, Calendar, Templates, Recordings)
- ✅ Recurring schedules (daily, weekly, monthly)
- ✅ Recording templates
- ✅ Multi-week calendar view
- ✅ 4-hour duration limit with override
- ✅ Pre-flight disk space checking
- ✅ Systemd auto-start service
- ✅ Automated installation script
- ✅ Username auto-detection
- ✅ Audio device auto-detection (command-line)

### Phase 2 Priority Items (v1.1.1)
- ✅ **Recording state synchronization fix**
- ✅ **Real-time status polling**
- ✅ **Audio device configuration GUI**
- ✅ **Log viewer in web UI**
- ✅ **Calendar click-to-create modal**

---

## Future Enhancements (Post-Testing Phase)

These features are consolidated from the original Phase 2 and Phase 3 plans. They will be prioritized based on live testing feedback and user needs.

---

### 🔐 Security & User Management

#### Basic Authentication (HIGH)
- HTTP basic auth for web UI
- Single admin username/password
- Session management
- Remember me functionality
- **Benefit:** Secure deployment on shared networks

#### User Preferences (MEDIUM)
- Customizable default duration
- Preferred time format (12h/24h)
- Email for notifications (if implemented)
- UI preferences (theme, layout)
- **Benefit:** Personalized experience

**Estimated Time:** 2-3 hours

---

### 💾 File & Storage Management

#### Retention Policy & Auto-Cleanup (MEDIUM)
- Configure automatic file deletion after N days
- Separate retention for recurring vs one-time recordings
- Manual retention overrides (keep forever)
- Warning before deletion
- Deletion logs
- **Benefit:** Prevent disk from filling up

#### Disk Space Monitoring Dashboard (HIGH)
- Real-time disk usage gauge
- Projected days until full
- Per-recording space usage breakdown
- Warning thresholds (< 10%, < 5%, < 1GB)
- Auto-disable new recordings when critically low
- **Benefit:** Proactive storage management

#### Optional Post-Processing (LOW)
- WAV → MP3 conversion (configurable bitrate)
- WAV → FLAC conversion (lossless compression)
- Keep original + compressed option
- Automatic post-recording conversion
- Manual batch conversion tool
- **Benefit:** Save disk space (optional)

#### Batch File Operations (MEDIUM)
- Select multiple recordings
- Bulk delete
- Bulk download (ZIP archive)
- Bulk tag/categorize
- **Benefit:** Easier file management

**Estimated Time:** 4-6 hours total

---

### 🎵 Recording Features

#### Audio Level Meter (MEDIUM)
- Real-time input level display (dBFS)
- Peak hold indicators
- Stereo L/R separate meters
- Visual clipping warnings
- No-recording preview mode
- **Benefit:** Set proper input levels before recording

#### Pre-Recording Level Check (MEDIUM)
- Quick 5-second level test before scheduled recording
- Auto-adjust if levels too low/high (if supported by device)
- Warning notification if levels are problematic
- **Benefit:** Prevent silent or clipped recordings

#### Pause/Resume Recording (LOW)
- Pause button during active recording
- Creates separate files or gap markers
- Resume from same recording session
- **Benefit:** Handle interruptions without stopping recording
- **Challenge:** Complex implementation, may fragment files

**Estimated Time:** 3-5 hours total

---

### 📅 Advanced Scheduling

#### Drag-and-Drop Calendar Rescheduling (HIGH)
- Drag events to different days/times
- Visual feedback during drag
- Confirmation before moving
- Update database immediately
- **Benefit:** Quick schedule adjustments

#### Notifications (MEDIUM)
- Email notifications on recording completion
- Webhook support for integration
- Discord/Slack notifications (optional)
- Error notifications (recording failed)
- **Benefit:** Remote monitoring
- **Requirement:** SMTP configuration or webhook setup

#### Schedule Import/Export (LOW)
- Export schedules as CSV
- Import schedules from CSV
- Bulk schedule creation from file
- **Benefit:** Backup and template sharing
- **Note:** iCal export removed from scope

#### Template-Based Bulk Scheduling (MEDIUM)
- Apply template to date range
- "Record every weekday for next month" wizard
- Skip holidays/exceptions
- Preview before creation
- **Benefit:** Rapid schedule creation

**Estimated Time:** 4-6 hours total

---

### 🎨 UI/UX Improvements

#### Dark Mode (LOW)
- Toggle in Settings
- Persistent preference
- Tailwind dark: classes
- **Benefit:** Easier on eyes, modern UI

#### Mobile Responsive Improvements (MEDIUM)
- Better touch targets
- Hamburger menu for navigation
- Optimized calendar for mobile
- Swipe gestures
- **Benefit:** Usable on phones/tablets

#### Customizable Themes (LOW)
- Color scheme presets
- Custom brand colors
- Logo upload
- **Benefit:** Personalization

**Estimated Time:** 2-4 hours total

---

### 📊 Analytics & Reporting

#### Recording Statistics Dashboard (MEDIUM)
- Total recordings count
- Total hours recorded
- Total storage used
- Most active days/times
- Average recording duration
- Recurring vs one-time breakdown
- **Benefit:** Usage insights

#### Storage Usage Graphs (MEDIUM)
- Historical storage growth chart
- Per-month breakdown
- Projection graph
- **Benefit:** Capacity planning

#### Search & Filter Recordings (HIGH)
- Search by filename, date, or notes
- Filter by date range
- Filter by source (left/right channel)
- Sort by size, date, duration
- **Benefit:** Find recordings quickly

#### Tagging System (MEDIUM)
- Add custom tags to recordings
- Filter by tags
- Tag-based auto-cleanup rules
- **Benefit:** Organization

**Estimated Time:** 4-6 hours total

---

### 🔧 System Improvements

#### Health Check Dashboard (MEDIUM)
- System uptime
- Last successful recording
- Failed recordings count
- Service restart count
- Database integrity check
- **Benefit:** System reliability monitoring

#### Backup & Restore (HIGH)
- Backup database + recordings to external drive
- Restore from backup
- Automatic backup scheduling
- **Benefit:** Disaster recovery

#### Multi-Device Recording (FUTURE)
- Support multiple USB audio devices
- Record from multiple sources simultaneously
- Device grouping
- **Benefit:** Stereo studio setups
- **Challenge:** Significant complexity, low priority

#### Sample Rate Configuration (LOW)
- Choose 44.1kHz or 48kHz
- Per-recording or global setting
- **Benefit:** Flexibility for different workflows

**Estimated Time:** 3-5 hours total

---

## Prioritization Criteria

Features will be prioritized based on:
1. **User Feedback:** Features requested by actual users
2. **Pain Points:** Issues discovered during live testing
3. **Impact vs Effort:** High-impact, low-effort features first
4. **Dependencies:** Features that unlock other features
5. **Stability:** Features that improve reliability

---

## Development Process

For each new feature:
1. **Specification:** Detailed design document
2. **Prototyping:** Proof-of-concept implementation
3. **Review:** User feedback on prototype
4. **Implementation:** Production-quality code
5. **Testing:** Automated and manual testing
6. **Documentation:** Update README and guides
7. **Release:** Version bump and release notes

---

## Version Planning

### Tentative Future Releases

**v1.2.0 - "Management"** (After Testing)
- Disk space monitoring dashboard
- Retention policy & auto-cleanup
- Search & filter recordings
- Backup & restore

**v1.3.0 - "Professional"** (TBD)
- Audio level meter
- Pre-recording level check
- Advanced scheduling features
- Notifications

**v1.4.0 - "Polish"** (TBD)
- Dark mode
- Mobile improvements
- Statistics dashboard
- Health check

**v2.0.0 - "Next Generation"** (Future)
- Complete UI redesign
- Multi-device support
- Advanced analytics
- API for external integration

---

## Feature Requests

Users can request features by:
1. Documenting use case and rationale
2. Estimating priority (Nice-to-have vs Critical)
3. Describing expected behavior
4. Providing examples if applicable

---

## Notes

- **iCal export:** Removed from roadmap per user request
- **Real-time status:** Completed ahead of schedule in v1.1.1
- **Audio config GUI:** Completed ahead of schedule in v1.1.1
- **Recurring schedules:** Completed in Phase 1

All estimates are rough and will be refined during implementation planning.

---

**Status:** Living document, updated with each release  
**Last Review:** v1.1.1 release
