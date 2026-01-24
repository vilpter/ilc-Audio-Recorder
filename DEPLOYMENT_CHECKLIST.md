# Deployment Checklist

Use this checklist when deploying Audio/Video Recorder to a new Raspberry Pi.

## Pre-Deployment

### Hardware Setup (Audio - Required)
- [ ] Raspberry Pi 3B+ or 4 with adequate power supply
- [ ] 32GB+ SD card (Class 10 or better)
- [ ] Behringer UCA202 USB audio interface
- [ ] Network cable (or WiFi configured)
- [ ] Audio sources connected to UCA202 inputs

### Hardware Setup (Video - Optional)
- [ ] PTZOptics camera with HTTP CGI and RTSP support
- [ ] Camera connected to same network as Pi
- [ ] USB external drive for video storage
- [ ] Camera IP address documented: _______________
- [ ] Camera credentials (if authentication enabled): _______________

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
- [ ] Test Calendar (/) - loads without errors
- [ ] Test Schedule (/schedule) - loads without errors
- [ ] Test Camera (/camera) - loads without errors
- [ ] Test Recordings (/recordings) - loads without errors
- [ ] Test Settings (/settings) - loads without errors

### Functional Testing

#### Manual Audio Recording Test
- [ ] Go to Schedule page
- [ ] Create a quick one-time recording (1 minute)
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
- [ ] Verify "Also capture video" checkbox is present
- [ ] Close modal without saving

#### Schedule Test
- [ ] Go to Schedule page
- [ ] Create a test schedule
- [ ] Verify job appears in list
- [ ] Go to Calendar page
- [ ] Verify event shows up
- [ ] Return to Schedule page
- [ ] Delete test schedule

#### Video Recording Test (if camera configured)
- [ ] Go to Settings page
- [ ] Configure camera IP and credentials
- [ ] Click "Test Connection" - verify success
- [ ] Go to Camera page
- [ ] Click a PTZ preset button - verify camera moves
- [ ] Start a short video recording (1 minute)
- [ ] Verify recording status shows active
- [ ] Stop recording
- [ ] Verify raw file appears in file list
- [ ] Wait for transcoding to complete
- [ ] Verify processed file appears

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

### Video/Camera Setup
- [ ] Mount USB drive for video storage:
  ```bash
  sudo mkdir -p /mnt/usb_recorder
  sudo mount /dev/sda1 /mnt/usb_recorder
  ```
- [ ] Add to /etc/fstab for permanent mount:
  ```bash
  echo '/dev/sda1 /mnt/usb_recorder auto defaults,nofail 0 2' | sudo tee -a /etc/fstab
  ```
- [ ] Create raw and processed directories:
  ```bash
  mkdir -p /mnt/usb_recorder/raw /mnt/usb_recorder/processed
  ```
- [ ] Go to Settings page
- [ ] Configure camera IP address
- [ ] Enter camera credentials (if required)
- [ ] Set USB storage path: `/mnt/usb_recorder`
- [ ] Name PTZ presets (e.g., "Podium", "Wide", "Audience")
- [ ] Test camera connection

### Performance Monitoring
- [ ] Check CPU temperature: `vcgencmd measure_temp`
- [ ] Ensure adequate cooling (add heatsink/fan if needed)
- [ ] Monitor during first few recordings
- [ ] Monitor during video transcoding (higher CPU usage)

## Sign-Off

### Deployment Information
- **Date:** _______________
- **Deployed By:** _______________
- **Pi Model:** _______________
- **OS Version:** _______________
- **Network Info:** _______________
- **Location:** _______________

### Video Configuration (if applicable)
- **Camera Model:** _______________
- **Camera IP:** _______________
- **USB Storage Path:** _______________
- **USB Drive Capacity:** _______________

### Test Results
- [ ] All audio tests passed
- [ ] All video tests passed (if configured)
- [ ] Known issues documented: _______________
- [ ] User training completed: _______________
- [ ] Backup exported: _______________

### Notes
```
[Add any deployment-specific notes here]
```

---

**Deployment Complete!**

The Audio/Video Recorder is now ready for production use.
