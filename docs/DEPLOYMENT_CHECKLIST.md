# Audio Recorder - Deployment Checklist

## Pre-Deployment Preparation

### 1. Hardware Setup
- [ ] Raspberry Pi 3/4 with power supply
- [ ] 32GB+ microSD card (Class 10 or better)
- [ ] Behringer UCA202 USB audio interface
- [ ] Ethernet cable or WiFi configured
- [ ] Audio sources ready to connect to UCA202

### 2. SD Card Preparation
- [ ] Download Raspberry Pi OS Lite (64-bit) Trixie or Bookworm
- [ ] Write image using Raspberry Pi Imager
- [ ] Configure in Imager settings:
  - [ ] Enable SSH
  - [ ] Set hostname (e.g., audio-recorder)
  - [ ] Configure WiFi (if not using Ethernet)
  - [ ] Set username/password
  - [ ] Set timezone

### 3. Network Configuration
- [ ] Configure DHCP reservation on router for static IP
- [ ] Note the assigned IP address
- [ ] Verify network connectivity after boot

---

## Installation Steps

### Phase 1: System Setup
- [ ] Boot Pi and wait 2-3 minutes
- [ ] SSH into Pi: `ssh pi@raspberrypi.local`
- [ ] Verify OS version: `cat /etc/os-release`
- [ ] System update: `sudo apt update && sudo apt upgrade -y`
- [ ] Reboot if kernel updated: `sudo reboot`

### Phase 2: Dependencies
- [ ] Install packages: `sudo apt install -y python3-pip python3-venv ffmpeg alsa-utils sqlite3`
- [ ] Verify FFmpeg: `ffmpeg -version`
- [ ] Verify ALSA: `arecord --version`

### Phase 3: Project Files
- [ ] Transfer audio-recorder directory to `/home/pi/`
- [ ] Set ownership: `sudo chown -R pi:pi ~/audio-recorder`
- [ ] Set permissions: `chmod +x ~/audio-recorder/*.py`
- [ ] Verify all files present: `ls -la ~/audio-recorder/`

### Phase 4: Python Environment
- [ ] Install requirements: `pip3 install --break-system-packages -r ~/audio-recorder/requirements.txt`
- [ ] Verify Flask: `python3 -c "import flask; print(flask.__version__)"`
- [ ] Verify APScheduler: `python3 -c "import apscheduler; print(apscheduler.__version__)"`

### Phase 5: Audio Configuration
- [ ] Plug in Behringer UCA202
- [ ] Check detection: `lsusb | grep -i audio`
- [ ] List audio devices: `arecord -l`
- [ ] Confirm UCA202 is card 1
- [ ] Copy ALSA config: `sudo cp ~/audio-recorder/configs/asound.conf /etc/asound.conf`
- [ ] (Optional) Copy udev rule: `sudo cp ~/audio-recorder/configs/85-usb-audio.rules /etc/udev/rules.d/`
- [ ] Reload udev: `sudo udevadm control --reload-rules && sudo udevadm trigger`

### Phase 6: Audio Testing
- [ ] Test 5-second recording: `arecord -D hw:1 -f S16_LE -r 48000 -c 2 -d 5 /tmp/test.wav`
- [ ] Verify file created: `ls -lh /tmp/test.wav`
- [ ] Check file size (should be ~1.7 MB for 5 seconds stereo)
- [ ] Delete test file: `rm /tmp/test.wav`

### Phase 7: Service Setup
- [ ] Create log directory: `sudo mkdir -p /var/log/audio-recorder`
- [ ] Set ownership: `sudo chown pi:pi /var/log/audio-recorder`
- [ ] Copy service file: `sudo cp ~/audio-recorder/audio-recorder.service /etc/systemd/system/`
- [ ] Reload systemd: `sudo systemctl daemon-reload`
- [ ] Enable service: `sudo systemctl enable audio-recorder`
- [ ] Start service: `sudo systemctl start audio-recorder`
- [ ] Check status: `sudo systemctl status audio-recorder`

### Phase 8: Web Interface Verification
- [ ] Wait 10 seconds for service to start
- [ ] Check if port is open: `sudo netstat -tlnp | grep 5000`
- [ ] Access web UI from another computer: `http://<pi-ip>:5000`
- [ ] Verify dashboard loads
- [ ] Check all navigation links work

---

## Functional Testing

### Test 1: Manual Recording
- [ ] Navigate to Dashboard
- [ ] Set duration to 1 minute
- [ ] Click "Start Recording"
- [ ] Verify status shows "Recording"
- [ ] Wait for completion
- [ ] Check Recordings page for files
- [ ] Download and verify audio files

### Test 2: Scheduled Recording
- [ ] Navigate to Schedule page
- [ ] Create a recording 5 minutes in the future
- [ ] Verify it appears in schedule list
- [ ] Wait for scheduled time
- [ ] Check Recordings page for files
- [ ] Verify recording completed

### Test 3: Recurring Schedule
- [ ] Navigate to Schedule page
- [ ] Create daily recurring recording
- [ ] Check checkbox for "Recurring Schedule"
- [ ] Select "Daily"
- [ ] Schedule for tomorrow at specific time
- [ ] Verify it appears with "RECURRING" badge
- [ ] Navigate to Calendar
- [ ] Verify recurring event shows on multiple days

### Test 4: Template Creation
- [ ] Navigate to Templates page
- [ ] Create template: "Test 30min"
- [ ] Set duration to 30 minutes
- [ ] Add recurring pattern (optional)
- [ ] Save template
- [ ] Navigate to Schedule page
- [ ] Select template from dropdown
- [ ] Verify fields auto-populate
- [ ] Create schedule from template

### Test 5: Calendar View
- [ ] Navigate to Calendar
- [ ] Verify current week displays
- [ ] Check that all scheduled recordings appear
- [ ] Click on an event
- [ ] Verify event details display
- [ ] Use Previous/Next buttons
- [ ] Verify calendar updates

### Test 6: File Management
- [ ] Navigate to Recordings page
- [ ] Verify all recorded files listed
- [ ] Download a file
- [ ] Verify file plays correctly
- [ ] Delete a file
- [ ] Verify file removed from list

### Test 7: Duration Limits
- [ ] Try to create 5-hour recording without override
- [ ] Verify error message about 4-hour limit
- [ ] Enable "Allow longer than 4 hours" checkbox
- [ ] Try again
- [ ] Verify recording accepted (don't actually record 5 hours!)
- [ ] Stop recording after verification

### Test 8: Disk Space Check
- [ ] Attempt to create very long recording (e.g., 100 hours)
- [ ] Verify disk space error if insufficient
- [ ] Verify error message shows available vs required space

### Test 9: Service Persistence
- [ ] Create a scheduled recording for 10 minutes in future
- [ ] Reboot Pi: `sudo reboot`
- [ ] Wait for reboot (2-3 minutes)
- [ ] SSH back in
- [ ] Check service status: `sudo systemctl status audio-recorder`
- [ ] Access web UI
- [ ] Verify schedule still exists
- [ ] Wait for scheduled time
- [ ] Verify recording executes

### Test 10: Long-Duration Recording (4 hours)
- [ ] Start 4-hour test recording
- [ ] Monitor system resources: `htop`
- [ ] Verify CPU stays under 10%
- [ ] Check disk space periodically
- [ ] Verify recording completes successfully
- [ ] Check file sizes (~5.2 GB total for both channels)

---

## Performance Verification

### Resource Monitoring
- [ ] Check CPU usage during recording: `top` or `htop`
- [ ] Verify <5% CPU usage
- [ ] Check memory usage: `free -h`
- [ ] Verify ~100 MB used by application
- [ ] Check disk I/O: `iostat -x 1 10`
- [ ] Verify no I/O bottlenecks

### Audio Quality
- [ ] Record test tone or known source
- [ ] Download and analyze in audio editor
- [ ] Verify 48kHz sample rate
- [ ] Verify 16-bit depth
- [ ] Check for dropouts or glitches
- [ ] Verify channels are independent

### Network Responsiveness
- [ ] Access web UI while recording
- [ ] Verify pages load quickly (<2 seconds)
- [ ] Test all pages during active recording
- [ ] Verify no UI freezing

---

## Production Readiness

### Security
- [ ] Change default Pi password: `passwd`
- [ ] (Optional) Set up firewall: `sudo ufw enable && sudo ufw allow 5000/tcp`
- [ ] (Optional) Configure fail2ban for SSH
- [ ] Verify only necessary ports open: `sudo netstat -tlnp`

### Backup
- [ ] Backup database: `cp ~/.audio-recorder/schedule.db ~/schedule-backup.db`
- [ ] Document backup procedure
- [ ] Test database restore

### Documentation
- [ ] Document static IP address
- [ ] Note audio source connections
- [ ] Record any custom configurations
- [ ] Save copy of README.md locally

### Monitoring
- [ ] Set up log rotation for application logs
- [ ] Create cron job to check disk space
- [ ] Document maintenance procedures

---

## Post-Deployment

### Day 1
- [ ] Monitor logs: `tail -f /var/log/audio-recorder/app.log`
- [ ] Verify scheduled recordings execute
- [ ] Check for any errors in logs

### Week 1
- [ ] Review all recorded files for quality
- [ ] Monitor disk space usage
- [ ] Verify all recurring schedules working
- [ ] Document any issues

### Month 1
- [ ] Archive old recordings if needed
- [ ] Review system performance
- [ ] Check for software updates
- [ ] Backup database

---

## Troubleshooting Quick Reference

### Service Won't Start
```bash
sudo journalctl -u audio-recorder -n 50
cd ~/audio-recorder && python3 app.py
```

### Audio Not Recording
```bash
arecord -l
ffmpeg -f alsa -i hw:1 -t 5 test.wav
sudo dmesg | grep -i usb
```

### Web UI Not Accessible
```bash
sudo systemctl status audio-recorder
sudo netstat -tlnp | grep 5000
curl http://localhost:5000
```

### Disk Space Full
```bash
df -h
du -sh ~/recordings/*
# Delete old recordings or add external storage
```

---

## Sign-Off

### Completed By
- Name: ________________
- Date: ________________
- Signature: ________________

### Verified By
- Name: ________________
- Date: ________________
- Signature: ________________

### Production Deployment Date
- Date: ________________
- Time: ________________
- Location: ________________

### Notes
_________________________________________________________________
_________________________________________________________________
_________________________________________________________________
