#!/bin/bash
#
# Audio Recording Troubleshooting Script
# Run this on the Raspberry Pi to diagnose scheduled recording issues
#

echo "============================================================"
echo "Audio Recording Troubleshooting Script"
echo "Date: $(date)"
echo "============================================================"
echo

# Detect the script's directory (where the code lives)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
echo "Script location: $SCRIPT_DIR"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_section() {
    echo
    echo "------------------------------------------------------------"
    echo -e "${YELLOW}$1${NC}"
    echo "------------------------------------------------------------"
}

print_ok() {
    echo -e "${GREEN}[OK]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# ============================================================
# Step 1: List ALSA audio devices
# ============================================================
print_section "STEP 1: ALSA Audio Devices (arecord -l)"

arecord -l
if [ $? -eq 0 ]; then
    print_ok "arecord -l succeeded"
else
    print_error "arecord -l failed - check ALSA installation"
fi

# ============================================================
# Step 2: Check for UCA202/USB audio device
# ============================================================
print_section "STEP 2: USB Audio Devices"

lsusb | grep -i audio
if [ $? -eq 0 ]; then
    print_ok "USB audio device found"
else
    print_warn "No USB audio device found in lsusb"
fi

echo
echo "Looking for Burr-Brown/UCA202:"
lsusb | grep -i "burr-brown\|08bb"
if [ $? -eq 0 ]; then
    print_ok "UCA202/Burr-Brown device detected"
else
    print_warn "UCA202/Burr-Brown not found - using different audio device?"
fi

# ============================================================
# Step 3: Test device detection from Python (main thread)
# ============================================================
print_section "STEP 3: Python Device Detection (Main Thread)"

python3 -c "
import sys
sys.path.insert(0, '$SCRIPT_DIR')
try:
    from recorder import auto_detect_audio_device, get_available_audio_devices
    import threading

    print(f'Current thread: {threading.current_thread().name}')
    print()

    devices = get_available_audio_devices()
    print(f'Detected {len(devices)} device(s):')
    for d in devices:
        rec = ' [RECOMMENDED]' if d.get('is_recommended') else ''
        print(f'  - {d[\"alsa_id\"]}: {d[\"name\"]}{rec}')

    print()
    selected = auto_detect_audio_device()
    print(f'Auto-selected device: {selected}')
except ImportError as e:
    print(f'Import error: {e}')
    print('Make sure you are running from the project directory')
" 2>&1 | grep -v "^\[" | head -20  # Filter out logging noise

# ============================================================
# Step 4: Test device detection from background thread
# ============================================================
print_section "STEP 4: Python Device Detection (Background Thread - Simulates Scheduler)"

python3 -c "
import sys
sys.path.insert(0, '$SCRIPT_DIR')
try:
    from recorder import auto_detect_audio_device, get_available_audio_devices
    import threading

    results = {}

    def detect_in_thread():
        results['thread_name'] = threading.current_thread().name
        results['devices'] = get_available_audio_devices()
        results['selected'] = auto_detect_audio_device()

    # Run in a daemon thread (like APScheduler does)
    t = threading.Thread(target=detect_in_thread, daemon=True)
    t.start()
    t.join(timeout=10)

    print(f'Thread name: {results.get(\"thread_name\", \"FAILED\")}')
    devices = results.get('devices', [])
    print(f'Detected {len(devices)} device(s):')
    for d in devices:
        rec = ' [RECOMMENDED]' if d.get('is_recommended') else ''
        print(f'  - {d[\"alsa_id\"]}: {d[\"name\"]}{rec}')

    print()
    print(f'Auto-selected device: {results.get(\"selected\", \"FAILED\")}')

    if len(devices) == 0:
        print()
        print('*** WARNING: No devices detected in background thread! ***')
        print('*** This is likely the cause of silent scheduled recordings ***')
except ImportError as e:
    print(f'Import error: {e}')
" 2>&1 | grep -v "^\[" | head -25

# ============================================================
# Step 5: Check current audio device configuration
# ============================================================
print_section "STEP 5: Current Audio Configuration"

python3 -c "
import sys
sys.path.insert(0, '$SCRIPT_DIR')
try:
    import scheduler

    device = scheduler.get_system_config('audio_device', 'auto')
    storage = scheduler.get_system_config('storage_path', '/mnt/usb_recorder')
    left = scheduler.get_system_config('channel_left_suffix', 'L')
    right = scheduler.get_system_config('channel_right_suffix', 'R')

    print(f'Audio device setting: {device}')
    print(f'Storage path: {storage}')
    print(f'Channel suffixes: {left} / {right}')

    if device == 'auto':
        print()
        print('NOTE: Device is set to \"auto\" - detection runs at each recording start')
        print('RECOMMENDATION: Set a specific device to avoid detection issues')
except ImportError as e:
    print(f'Import error: {e}')
" 2>&1 | grep -v "^\[" | head -15

# ============================================================
# Step 6: Check if hw:1,0 exists
# ============================================================
print_section "STEP 6: Check Fallback Device (hw:1,0)"

arecord -D hw:1,0 --dump-hw-params 2>&1 | head -20
if [ $? -eq 0 ]; then
    print_ok "hw:1,0 exists and is accessible"
else
    print_error "hw:1,0 does NOT exist or is not accessible"
    echo "If device detection fails, recordings will try to use hw:1,0 which doesn't work!"
fi

# ============================================================
# Step 7: Quick arecord test (5 seconds)
# ============================================================
print_section "STEP 7: Quick arecord Test (5 seconds with hw:1,0)"

echo "Recording 5 seconds with arecord..."
TEST_FILE="/tmp/test_arecord_$$.wav"
timeout 6 arecord -D hw:1,0 -f S16_LE -r 48000 -c 2 -d 5 "$TEST_FILE" 2>&1

if [ -f "$TEST_FILE" ]; then
    SIZE=$(stat -c%s "$TEST_FILE")
    echo "Test file created: $TEST_FILE ($SIZE bytes)"

    if [ "$SIZE" -gt 100000 ]; then
        print_ok "arecord test PASSED - file has expected size"
    else
        print_error "arecord test file is too small - may be silent!"
    fi

    # Check if file has actual audio content using sox if available
    if command -v sox &> /dev/null; then
        echo
        echo "Audio stats (via sox):"
        sox "$TEST_FILE" -n stat 2>&1 | grep -E "Maximum amplitude|Mean.*amplitude|RMS"
    fi

    rm -f "$TEST_FILE"
else
    print_error "arecord test failed - no file created"
fi

# ============================================================
# Step 8: Quick FFmpeg test (THIS IS THE KEY TEST)
# ============================================================
print_section "STEP 8: Quick FFmpeg Test (5 seconds with hw:1,0) - CRITICAL"

echo "Recording 5 seconds with FFmpeg (same method as app)..."
TEST_LEFT="/tmp/test_ffmpeg_L_$$.wav"
TEST_RIGHT="/tmp/test_ffmpeg_R_$$.wav"

ffmpeg -y -f alsa -i hw:1,0 -t 5 \
    -filter_complex '[0:a]channelsplit=channel_layout=stereo[left][right]' \
    -map '[left]' -acodec pcm_s16le -ar 48000 "$TEST_LEFT" \
    -map '[right]' -acodec pcm_s16le -ar 48000 "$TEST_RIGHT" 2>&1 | tail -10

echo

if [ -f "$TEST_LEFT" ] && [ -f "$TEST_RIGHT" ]; then
    SIZE_L=$(stat -c%s "$TEST_LEFT")
    SIZE_R=$(stat -c%s "$TEST_RIGHT")
    echo "Left channel: $TEST_LEFT ($SIZE_L bytes)"
    echo "Right channel: $TEST_RIGHT ($SIZE_R bytes)"

    if [ "$SIZE_L" -gt 100000 ] && [ "$SIZE_R" -gt 100000 ]; then
        print_ok "FFmpeg test PASSED - both channels have expected size"
    else
        print_error "FFmpeg test files are too small - SILENT RECORDINGS!"
        echo "This confirms the issue is with FFmpeg capture, not device detection"
    fi

    # Check audio content
    if command -v sox &> /dev/null; then
        echo
        echo "Left channel stats:"
        sox "$TEST_LEFT" -n stat 2>&1 | grep -E "Maximum amplitude|Mean.*amplitude|RMS"
        echo
        echo "Right channel stats:"
        sox "$TEST_RIGHT" -n stat 2>&1 | grep -E "Maximum amplitude|Mean.*amplitude|RMS"
    fi

    rm -f "$TEST_LEFT" "$TEST_RIGHT"
else
    print_error "FFmpeg test failed - files not created"
fi

# ============================================================
# Step 9: Check log files
# ============================================================
print_section "STEP 9: Recent Log Entries"

LOG_DIR="$HOME/.audio-recorder"

if [ -f "$LOG_DIR/recorder.log" ]; then
    echo "=== Last 20 lines of recorder.log ==="
    tail -20 "$LOG_DIR/recorder.log"
else
    print_warn "No recorder.log found (will be created after first recording with new code)"
fi

echo
if [ -f "$LOG_DIR/scheduler.log" ]; then
    echo "=== Last 20 lines of scheduler.log ==="
    tail -20 "$LOG_DIR/scheduler.log"
else
    print_warn "No scheduler.log found (will be created after first scheduled recording)"
fi

# ============================================================
# Step 10: Check scheduled jobs
# ============================================================
print_section "STEP 10: Scheduled Jobs Status"

python3 -c "
import sys
sys.path.insert(0, '$SCRIPT_DIR')
try:
    import scheduler

    jobs = scheduler.get_all_jobs()
    if not jobs:
        print('No scheduled jobs found')
    else:
        print(f'Found {len(jobs)} job(s):')
        for j in jobs[-10:]:
            print(f'  {j[\"id\"]}: {j[\"name\"]} - {j[\"status\"]} at {j[\"start_time\"]}')
            if j.get('notes'):
                print(f'    Notes: {j[\"notes\"]}')
except ImportError as e:
    print(f'Import error: {e}')
" 2>&1 | grep -v "^\[" | head -20

# ============================================================
# Summary and Recommendations
# ============================================================
print_section "SUMMARY AND RECOMMENDATIONS"

echo "KEY TESTS TO CHECK:"
echo "  - Step 7 (arecord): Tests basic ALSA capture"
echo "  - Step 8 (FFmpeg): Tests the exact method used by the app"
echo
echo "If arecord works but FFmpeg produces silent files:"
echo "  -> Issue is with FFmpeg ALSA capture configuration"
echo
echo "If both work in this test but scheduled recordings are silent:"
echo "  -> Issue is timing/environment when scheduler runs"
echo
echo "QUICK FIX - Set explicit device:"
echo "  cd $SCRIPT_DIR"
echo "  python3 -c \"import scheduler; scheduler.set_system_config('audio_device', 'hw:1,0')\""
echo
echo "Check logs after next scheduled recording:"
echo "  tail -f ~/.audio-recorder/recorder.log"
echo "  tail -f ~/.audio-recorder/scheduler.log"
echo
echo "============================================================"
echo "Troubleshooting complete"
echo "============================================================"
