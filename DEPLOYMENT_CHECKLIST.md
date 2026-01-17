# Deployment Checklist

Use this checklist when deploying Audio Recorder to a new Raspberry Pi.

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

## Initial Pi Setup

### OS Installation
- [ ] Flash Raspberry Pi OS Lite to SD card
- [ ] Configure SSH in Raspberry Pi Imager settings
- [ ] Set hostname (e.g., `audio-recorder`)
- [ ] Configure WiFi credentials (if applicable)
- [ ] Set username to `pi` and secure password
- [ ] Set correct timezone

### First Boot
- [ ] Insert SD card and power on
- [ ] Wait 2-3 minutes for initialization
- [ ] Connect via SSH: `ssh pi@audio-recorder.local`
- [ ] Verify OS version: `cat /etc/os-release`
- [ ] Verify 64-bit: `uname -m` (should show `aarch64`)

## System Configuration

### Updates
- [ ] Run: `sudo apt update`
- [ ] Run: `sudo apt upgrade -y`
- [ ] Reboot: `sudo reboot`

## Application Installation (Automated)

The `install.sh` script handles most installation steps automatically.

### Clone and Install
```bash
cd ~
git clone https://github.com/vilpter/ilc-Audio-Recorder.git audio-recorder
cd audio-recorder
./install.sh
```

### Verify Installation
- [ ] Check service status: `sudo systemctl status audio-recorder`
- [ ] Verify "active (running)" status
- [ ] Check logs: `tail -20 /var/log/audio-recorder/app.log`

### Manual Steps (if needed)
If the installer encounters issues, use the helper scripts:
- [ ] Audio issues: `./configure_audio.sh`
- [ ] Service issues: `./fix_service.sh`

## Post-Installation Testing

### Web UI Access
- [ ] Get Pi IP: `hostname -I`
- [ ] Open browser: `http://PI_IP_ADDRESS:5000`
- [ ] Verify dashboard loads
- [ ] Status shows "Idle"

### Page Verification
- [ ] Test Dashboard (/) - loads without errors
- [ ] Test Schedule (/schedule) - loads without errors
- [ ] Test Calendar (/calendar) - loads without errors
- [ ] Test Templates (/templates) - loads without errors
- [ ] Test Recordings (/recordings) - loads without errors
- [ ] Test Settings (/settings) - loads without errors

### Functional Testing

#### Manual Recording Test
- [ ] Go to Dashboard
- [ ] Set duration: 1 minute
- [ ] Click "Start Recording"
- [ ] Verify status changes to recording state
- [ ] Wait for recording to complete (or click Stop)
- [ ] Go to Recordings page
- [ ] Verify `*_L.wav` and `*_R.wav` files exist
- [ ] Download both files
- [ ] Verify files play correctly
- [ ] Delete test files

#### Settings Test
- [ ] Go to Settings page
- [ ] Verify audio device detection works
- [ ] Test filename configuration preview
- [ ] Verify backup/restore buttons are present

#### Calendar Click Test
- [ ] Go to Calendar page
- [ ] Click on a future day
- [ ] Verify schedule creation modal appears
- [ ] Close modal without saving

#### Template Test
- [ ] Go to Templates page
- [ ] Create template: "Daily 1-Hour Recording"
- [ ] Set duration: 1 hour
- [ ] Set recurrence: Daily at 09:00
- [ ] Save template
- [ ] Verify template appears in list

#### Schedule Test
- [ ] Go to Schedule page
- [ ] Create a test schedule
- [ ] Verify job appears in list
- [ ] Go to Calendar page
- [ ] Verify event shows up
- [ ] Return to Schedule page
- [ ] Delete test schedule

### Reboot Test
- [ ] Reboot Pi: `sudo reboot`
- [ ] Wait for boot
- [ ] Reconnect SSH
- [ ] Check service auto-started: `sudo systemctl status audio-recorder`
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
- [ ] Document audio source connections (what's L, what's R)
- [ ] Export initial configuration from Settings page
- [ ] Store backup files safely

### Backup Strategy
- [ ] Document recordings location: `~/recordings`
- [ ] Document database location: `~/.audio-recorder/`
- [ ] Export schedules and config from Settings page
- [ ] Set up external backup destination (if applicable)

### Monitoring Setup
- [ ] Add Pi to network monitoring (if available)
- [ ] Document how to check service status
- [ ] Create user guide for accessing web UI

## Optional Configuration

### Static IP (if using DHCP reservation)
- [ ] Note Pi's MAC address: `ip link show`
- [ ] Configure DHCP reservation on router
- [ ] Document assigned IP address

### Custom Filename Configuration
- [ ] Go to Settings page
- [ ] Configure channel suffixes (L/R or custom)
- [ ] Verify filename preview shows expected format

### Performance Monitoring
- [ ] Check CPU temperature: `vcgencmd measure_temp`
- [ ] Ensure adequate cooling (add heatsink/fan if needed)
- [ ] Monitor during first few recordings

## Sign-Off

### Deployment Information
- **Date:** _______________
- **Deployed By:** _______________
- **Pi Model:** _______________
- **OS Version:** _______________
- **Network Info:** _______________
- **Location:** _______________

### Test Results
- [ ] All tests passed
- [ ] Known issues documented: _______________
- [ ] User training completed: _______________
- [ ] Backup exported: _______________

### Notes
```
[Add any deployment-specific notes here]
```

---

**Deployment Complete!**

The Audio Recorder is now ready for production use.
