# Phase 2 Enhancement: Audio Device Configuration GUI

## Priority: HIGH
**Reason:** Critical for easy deployment and avoiding manual configuration issues

---

## Feature Requirement

### User Story
As a user deploying the audio recorder, I need to select which audio device to use through the web interface, so I don't have to manually edit configuration files or know which card number my UCA202 is assigned to.

---

## Implementation Plan

### 1. Backend API Endpoints

#### A. List Available Audio Devices
**Endpoint:** `GET /api/audio/devices`

**Response:**
```json
{
  "devices": [
    {
      "card": 0,
      "device": 0,
      "name": "bcm2835 Headphones",
      "description": "Raspberry Pi onboard audio",
      "type": "playback_only",
      "alsa_id": "hw:0,0",
      "is_capture_capable": false
    },
    {
      "card": 1,
      "device": 0,
      "name": "USB Audio CODEC",
      "description": "Behringer UCA202 (PCM2902)",
      "type": "full_duplex",
      "alsa_id": "hw:1,0",
      "is_capture_capable": true,
      "is_recommended": true
    }
  ],
  "current_device": "hw:1,0",
  "auto_detected": "hw:1,0"
}
```

**Implementation:**
```python
# New function in recorder.py
def get_available_audio_devices():
    """
    Parse arecord -l output to list all capture-capable devices
    
    Returns list of dictionaries with device info
    """
    import subprocess
    import re
    
    result = subprocess.run(['arecord', '-l'], capture_output=True, text=True)
    devices = []
    
    # Parse output format:
    # card 1: CODEC [USB Audio CODEC], device 0: USB Audio [USB Audio]
    pattern = r'card (\d+): (\w+) \[([^\]]+)\], device (\d+): ([^\[]+)'
    
    for match in re.finditer(pattern, result.stdout):
        card, short_name, full_name, device, desc = match.groups()
        
        alsa_id = f"hw:{card},{device}"
        
        # Detect UCA202 specifically
        is_uca202 = 'USB Audio' in full_name or 'PCM290' in full_name
        
        devices.append({
            'card': int(card),
            'device': int(device),
            'name': full_name.strip(),
            'description': desc.strip(),
            'alsa_id': alsa_id,
            'is_capture_capable': True,
            'is_recommended': is_uca202
        })
    
    return devices


def auto_detect_audio_device():
    """
    Automatically select the best audio device
    
    Priority:
    1. First USB audio device (UCA202)
    2. First capture-capable device
    3. hw:1,0 as fallback
    """
    devices = get_available_audio_devices()
    
    # Try to find recommended device (UCA202)
    for dev in devices:
        if dev.get('is_recommended'):
            return dev['alsa_id']
    
    # Fallback to first capture device
    if devices:
        return devices[0]['alsa_id']
    
    # Ultimate fallback
    return 'hw:1,0'
```

---

#### B. Get Current Audio Device
**Endpoint:** `GET /api/audio/config`

**Response:**
```json
{
  "current_device": "hw:1,0",
  "device_info": {
    "name": "USB Audio CODEC",
    "description": "Behringer UCA202",
    "is_connected": true
  },
  "auto_detect_available": true
}
```

---

#### C. Set Audio Device
**Endpoint:** `POST /api/audio/config`

**Request:**
```json
{
  "device": "hw:1,0",
  "auto_detect": false
}
```

**Response:**
```json
{
  "success": true,
  "device": "hw:1,0",
  "message": "Audio device updated successfully. Restart required for active recordings."
}
```

**Implementation:**
- Store selected device in SQLite config table
- Reload configuration without service restart
- Validate device exists before saving

---

### 2. Configuration Storage

#### Database Schema Addition
```sql
CREATE TABLE IF NOT EXISTS system_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Default values
INSERT OR IGNORE INTO system_config (key, value, updated_at) 
VALUES ('audio_device', 'auto', datetime('now'));

INSERT OR IGNORE INTO system_config (key, value, updated_at) 
VALUES ('auto_detect_audio', 'true', datetime('now'));
```

---

### 3. Frontend Implementation

#### A. Settings Page (New)
**Route:** `/settings`

**UI Components:**

```html
<!-- Audio Device Configuration Section -->
<div class="bg-white rounded-lg shadow-md p-6">
    <h2 class="text-xl font-semibold mb-4">Audio Device Settings</h2>
    
    <!-- Auto-detect option -->
    <div class="mb-4">
        <label class="flex items-center">
            <input type="checkbox" id="auto-detect" checked class="mr-2">
            <span class="text-gray-700">Automatically detect audio device</span>
        </label>
        <p class="text-sm text-gray-500 mt-1">
            Recommended: Automatically selects USB audio device (UCA202)
        </p>
    </div>
    
    <!-- Manual device selection -->
    <div id="manual-device-select" class="hidden">
        <label class="block text-gray-700 mb-2">Select Audio Device</label>
        <select id="device-select" class="w-full border rounded px-3 py-2">
            <!-- Populated by JavaScript -->
        </select>
        
        <!-- Device info display -->
        <div id="device-info" class="mt-3 p-3 bg-blue-50 border border-blue-200 rounded">
            <!-- Shows selected device details -->
        </div>
    </div>
    
    <!-- Test recording button -->
    <button onclick="testAudioDevice()" class="mt-4 bg-green-500 text-white px-4 py-2 rounded">
        Test Selected Device (5 sec)
    </button>
    
    <!-- Save button -->
    <button onclick="saveAudioConfig()" class="mt-4 bg-blue-500 text-white px-4 py-2 rounded">
        Save Configuration
    </button>
</div>

<!-- Currently Active Device Display -->
<div class="mt-6 p-4 bg-green-50 border border-green-200 rounded">
    <h3 class="font-semibold text-green-900 mb-2">Currently Active Device</h3>
    <p class="text-sm text-green-800">
        <strong>Device:</strong> <span id="current-device">hw:1,0</span><br>
        <strong>Name:</strong> <span id="current-device-name">USB Audio CODEC</span><br>
        <strong>Status:</strong> 
        <span id="device-status" class="text-green-600">● Connected</span>
    </p>
</div>
```

#### B. Navigation Update
Add "Settings" link to all page navigation bars:
```html
<a href="/settings" class="hover:underline">Settings</a>
```

---

### 4. JavaScript Implementation

```javascript
// Load available devices on page load
async function loadAudioDevices() {
    const response = await fetch('/api/audio/devices');
    const data = await response.json();
    
    const select = document.getElementById('device-select');
    select.innerHTML = '';
    
    data.devices.forEach(device => {
        const option = document.createElement('option');
        option.value = device.alsa_id;
        option.textContent = `${device.name} (${device.alsa_id})`;
        if (device.is_recommended) {
            option.textContent += ' ⭐ Recommended';
        }
        if (device.alsa_id === data.current_device) {
            option.selected = true;
        }
        select.appendChild(option);
    });
    
    // Update current device display
    document.getElementById('current-device').textContent = data.current_device;
}

// Toggle auto-detect
document.getElementById('auto-detect').addEventListener('change', (e) => {
    const manualSelect = document.getElementById('manual-device-select');
    manualSelect.classList.toggle('hidden', e.target.checked);
});

// Test audio device
async function testAudioDevice() {
    const device = document.getElementById('auto-detect').checked 
        ? 'auto' 
        : document.getElementById('device-select').value;
    
    try {
        const response = await fetch('/api/audio/test', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ device })
        });
        
        const result = await response.json();
        if (result.success) {
            alert('✓ Audio test successful! Device is working correctly.');
        } else {
            alert('✗ Audio test failed: ' + result.error);
        }
    } catch (error) {
        alert('Error testing device: ' + error);
    }
}

// Save configuration
async function saveAudioConfig() {
    const autoDetect = document.getElementById('auto-detect').checked;
    const device = autoDetect ? 'auto' : document.getElementById('device-select').value;
    
    try {
        const response = await fetch('/api/audio/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                device,
                auto_detect: autoDetect
            })
        });
        
        const result = await response.json();
        if (result.success) {
            alert('✓ Configuration saved! Changes will take effect for new recordings.');
            location.reload();
        } else {
            alert('✗ Error: ' + result.error);
        }
    } catch (error) {
        alert('Error saving configuration: ' + error);
    }
}
```

---

### 5. Recorder Module Updates

```python
# In recorder.py

# Add configuration loading
def load_audio_device_config():
    """Load audio device configuration from database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT value FROM system_config WHERE key = 'audio_device'")
    row = cursor.fetchone()
    conn.close()
    
    if row and row[0] != 'auto':
        return row[0]
    
    # Auto-detect
    return auto_detect_audio_device()


# Update start_capture to use configured device
def start_capture(duration_seconds=3600, device=None, allow_override=False):
    """
    Start FFmpeg capture process with validation
    
    Args:
        duration_seconds: Recording duration in seconds
        device: ALSA device identifier (None = use config)
        allow_override: Allow recordings longer than default limit
    """
    if device is None:
        device = load_audio_device_config()
    
    # ... rest of existing code
```

---

### 6. Testing Endpoints

#### Test Audio Device
**Endpoint:** `POST /api/audio/test`

**Request:**
```json
{
  "device": "hw:1,0",
  "duration": 5
}
```

**Implementation:**
```python
@app.route('/api/audio/test', methods=['POST'])
def test_audio_device():
    """Test audio device with short recording"""
    data = request.json
    device = data.get('device', 'auto')
    duration = data.get('duration', 5)
    
    if device == 'auto':
        device = recorder.auto_detect_audio_device()
    
    # Test recording to /tmp
    test_file = f'/tmp/audio_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.wav'
    
    cmd = [
        'arecord',
        '-D', device,
        '-f', 'S16_LE',
        '-r', '48000',
        '-c', '2',
        '-d', str(duration),
        test_file
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=duration+2)
        
        if result.returncode == 0 and Path(test_file).exists():
            file_size = Path(test_file).stat().st_size
            Path(test_file).unlink()  # Clean up
            
            return jsonify({
                'success': True,
                'device': device,
                'duration': duration,
                'file_size': file_size
            })
        else:
            return jsonify({
                'success': False,
                'error': result.stderr.decode()
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
```

---

## User Experience Flow

### First-Time Setup
1. User accesses web UI after installation
2. System auto-detects UCA202 (if connected)
3. Dashboard shows device status indicator
4. If device not auto-detected, banner prompts: "Configure audio device in Settings"

### Settings Page
1. User navigates to Settings
2. Sees current device and status
3. Can choose:
   - **Auto-detect** (default, recommended)
   - **Manual selection** from dropdown of available devices
4. **Test** button runs 5-second recording to verify
5. **Save** button persists configuration

### During Recording
- If configured device disconnects, show error
- Suggest checking Settings page
- Don't allow recording to start if device unavailable

---

## Deployment Notes

### Default Behavior (No Configuration)
- System uses `auto_detect_audio_device()`
- Prioritizes USB audio devices
- Falls back to hw:1,0 if no USB audio found
- User never sees errors on first deployment (unless no device at all)

### Migration from Phase 1
- Existing deployments default to 'auto' mode
- No manual configuration required
- Seamless upgrade

---

## Priority Justification

**Why HIGH priority for Phase 2:**
1. ✅ User just encountered this exact issue
2. ✅ Eliminates need for SSH/manual configuration
3. ✅ Makes system truly "headless" and user-friendly
4. ✅ Prevents deployment failures
5. ✅ Allows dynamic device switching without code edits

**Estimated Development Time:** 2-3 hours
- Backend API: 1 hour
- Frontend UI: 1 hour
- Testing: 0.5-1 hour

---

## Future Enhancements (Phase 3)

- **Multi-device support:** Record from multiple USB devices simultaneously
- **Device monitoring:** Alert if configured device disconnects
- **Advanced settings:** Sample rate selection, bit depth options
- **Audio level meters:** Show real-time input levels for device testing

---

## Notes for Development

- **Database migration:** Add system_config table in scheduler.py init
- **Config caching:** Load device config once at startup, reload on save
- **Error handling:** Graceful fallback if configured device unavailable
- **Validation:** Verify device exists before allowing save
- **Testing:** Include in deployment checklist for Phase 2

---

**Status:** DOCUMENTED FOR PHASE 2  
**Assigned Priority:** HIGH  
**Blocked By:** None  
**Blocks:** None (enhancement)

