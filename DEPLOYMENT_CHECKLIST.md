# Deployment Checklist

Use this checklist when deploying ILC Audio Recorder to a new Raspberry Pi.

## Pre-Deployment

### Hardware Setup
- [ ] Raspberry Pi 3B+ or 4 with adequate power supply
- [ ] 32GB+ SD card (Class 10 or better)
- [ ] Behringer UCA202 USB audio interface
- [ ] Network cable (or WiFi configured)
- [ ] Audio sources connected to UCA202 inputs

### Software Preparation
- [ ] Raspberry Pi OS Lite (64-bit) image downloaded
- [ ] Raspberry Pi Imager installed on computer
- [ ] Project files ready to transfer

## Initial Pi Setup

### OS Installation
- [ ] Flash Raspberry Pi OS Lite to SD card
- [ ] Configure SSH in Raspberry Pi Imager settings
- [ ] Set hostname (e.g., `ilc-recorder`)
- [ ] Configure WiFi credentials (if applicable)
- [ ] Set username to `pi` and secure password
- [ ] Set correct timezone

### First Boot
- [ ] Insert SD card and power on
- [ ] Wait 2-3 minutes for initialization
- [ ] Connect via SSH: `ssh pi@ilc-recorder.local`
- [ ] Verify OS version: `cat /etc/os-release`
- [ ] Verify 64-bit: `uname -m` (should show `aarch64`)

## System Configuration

### Updates
- [ ] Run: `sudo apt update`
- [ ] Run: `sudo apt upgrade -y`
- [ ] Reboot: `sudo reboot`

### Dependencies
- [ ] Install: `sudo apt install -y python3-pip ffmpeg alsa-utils sqlite3`
- [ ] Verify FFmpeg: `ffmpeg -version`
- [ ] Verify Python: `python3 --version` (should be 3.11+)

### Hardware Verification
- [ ] Plug in UCA202 USB cable
- [ ] Run: `lsusb | grep Audio` (should show "Burr-Brown")
- [ ] Run: `arecord -l` (should show card 1: CODEC)

## Application Installation

### File Transfer
- [ ] Upload project to `/home/pi/ilc-audio-recorder`
- [ ] Verify all files present: `ls -la ~/ilc-audio-recorder`
- [ ] Set execute permissions: `chmod +x ~/ilc-audio-recorder/*.py`

### Python Dependencies
- [ ] Navigate: `cd ~/ilc-audio-recorder`
- [ ] Install: `pip3 install -r requirements.txt --break-system-packages`
- [ ] Verify: `pip3 list | grep Flask`

### ALSA Configuration
- [ ] Copy config: `sudo cp configs/asound.conf /etc/asound.conf`
- [ ] Reload ALSA: `sudo alsactl kill rescan`
- [ ] Test recording (5 sec): `arecord -D hw:1 -f S16_LE -r 48000 -c 2 -d 5 test.wav`
- [ ] Check file size: `ls -lh test.wav` (should be ~1.8MB)
- [ ] Delete test: `rm test.wav`

### Recordings Directory
- [ ] Create: `mkdir -p ~/recordings`
- [ ] Test write: `touch ~/recordings/test.txt && rm ~/recordings/test.txt`

### Systemd Service
- [ ] Create log dir: `sudo mkdir -p /var/log/ilc-audio-recorder`
- [ ] Set ownership: `sudo chown pi:pi /var/log/ilc-audio-recorder`
- [ ] Copy service: `sudo cp ilc-audio-recorder.service /etc/systemd/system/`
- [ ] Reload daemon: `sudo systemctl daemon-reload`
- [ ] Enable service: `sudo systemctl enable ilc-audio-recorder`
- [ ] Start service: `sudo systemctl start ilc-audio-recorder`
- [ ] Check status: `sudo systemctl status ilc-audio-recorder`
- [ ] Verify "active (running)" status

## Post-Installation Testing

### Web UI Access
- [ ] Get Pi IP: `hostname -I`
- [ ] Open browser: `http://PI_IP_ADDRESS:5000`
- [ ] Verify dashboard loads
- [ ] Check disk space indicator shows
- [ ] Status shows "IDLE"

### Page Verification
- [ ] Test Dashboard (/) - loads without errors
- [ ] Test Schedule (/schedule) - loads without errors
- [ ] Test Calendar (/calendar) - loads without errors
- [ ] Test Recordings (/recordings) - loads without errors
- [ ] Test Templates (/templates) - loads without errors

### Functional Testing

#### Manual Recording Test
- [ ] Go to Dashboard
- [ ] Set name: "test_recording"
- [ ] Set duration: 5 minutes (300 seconds)
- [ ] Click "Start Recording"
- [ ] Verify status changes to "RECORDING"
- [ ] See recording details displayed
- [ ] Wait 10 seconds
- [ ] Click "Stop Recording"
- [ ] Go to Recordings page
- [ ] Verify `source_A_*.wav` and `source_B_*.wav` files exist
- [ ] Download both files
- [ ] Verify files play correctly
- [ ] Delete test files

#### Template Test
- [ ] Go to Templates page
- [ ] Create template: "Daily 1-Hour Recording"
- [ ] Set duration: 1 hour
- [ ] Set recurrence: Daily at 09:00
- [ ] Save template
- [ ] Verify template appears in list

#### Schedule Test
- [ ] Go to Schedule page
- [ ] Load "Daily 1-Hour Recording" template
- [ ] Verify fields populate
- [ ] Create schedule
- [ ] Verify job appears in list
- [ ] Go to Calendar page
- [ ] Verify recurring events show up
- [ ] Return to Schedule page
- [ ] Delete test schedule

### Log Verification
- [ ] Check app log: `tail -20 /var/log/ilc-audio-recorder/app.log`
- [ ] Check error log: `tail -20 /var/log/ilc-audio-recorder/error.log`
- [ ] Verify no critical errors

### Reboot Test
- [ ] Reboot Pi: `sudo reboot`
- [ ] Wait for boot
- [ ] Reconnect SSH
- [ ] Check service auto-started: `sudo systemctl status ilc-audio-recorder`
- [ ] Verify web UI accessible
- [ ] Check schedules persisted (go to Schedule page)

## Production Readiness

### Security
- [ ] Change default `pi` password: `passwd`
- [ ] Consider disabling SSH password auth (use keys only)
- [ ] Verify web UI only accessible on local network
- [ ] Document static IP or hostname for access

### Documentation
- [ ] Note Pi's IP address or hostname
- [ ] Document audio source connections (what's A, what's B)
- [ ] Create backup of initial configuration
- [ ] Print quick reference card for non-technical users

### Backup Strategy
- [ ] Document recordings location: `/home/pi/recordings`
- [ ] Set up external backup destination (if applicable)
- [ ] Consider automated backup script
- [ ] Document database locations: `~/ilc-audio-recorder/data/`

### Monitoring Setup
- [ ] Add Pi to network monitoring (if available)
- [ ] Document how to check service status
- [ ] Create user guide for accessing web UI
- [ ] Establish maintenance schedule

## Optional Configuration

### Static IP (if using DHCP reservation)
- [ ] Note Pi's MAC address: `ip link show`
- [ ] Configure DHCP reservation on router
- [ ] Document assigned IP address

### Performance Tuning
- [ ] Check CPU temperature: `vcgencmd measure_temp`
- [ ] Ensure adequate cooling (add heatsink/fan if needed)
- [ ] Monitor during first few recordings

### Future Enhancements
- [ ] Plan retention policy (auto-delete old files)
- [ ] Consider external USB storage for recordings
- [ ] Plan authentication implementation (Phase 2)

## Sign-Off

### Deployment Information
- **Date:** _______________
- **Deployed By:** _______________
- **Pi Model:** _______________
- **Pi Serial:** _______________
- **OS Version:** _______________
- **Network Info:** _______________
- **Location:** _______________

### Test Results
- [ ] All tests passed
- [ ] Known issues documented: _______________
- [ ] User training completed: _______________
- [ ] Backup plan in place: _______________

### Notes
```
[Add any deployment-specific notes here]
```

---

**Deployment Complete!** 🎉

The ILC Audio Recorder is now ready for production use.
