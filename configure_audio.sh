#!/bin/bash
# Quick Audio Device Configuration Script
# Run this after installation to auto-detect and configure the correct audio device

echo "=========================================="
echo "Audio Recorder - Device Configuration"
echo "=========================================="
echo ""

# Detect which card the UCA202 is on
echo "Detecting audio devices..."
echo ""

arecord -l

echo ""
echo "=========================================="
echo ""

# Try to find USB audio device
CARD=$(arecord -l | grep -i "USB Audio\|PCM290\|CODEC" | head -1 | sed -n 's/card \([0-9]\).*/\1/p')

if [ -z "$CARD" ]; then
    echo "❌ No USB audio device detected!"
    echo ""
    echo "Please verify:"
    echo "  1. UCA202 is plugged into USB port"
    echo "  2. UCA202 power LED is on"
    echo "  3. Try different USB port"
    echo ""
    echo "Manual device selection:"
    echo "Look at the output above and note your card number."
    echo "Then edit ~/audio-recorder/recorder.py line 109:"
    echo "  Change: device='hw:1'"
    echo "  To:     device='hw:X'  (where X is your card number)"
    echo ""
    exit 1
fi

echo "✓ Found USB audio device on card $CARD"
echo ""

# Test the device
echo "Testing audio device hw:$CARD with 3-second recording..."
arecord -D hw:$CARD -f S16_LE -r 48000 -c 2 -d 3 /tmp/test_audio.wav 2>&1

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ Audio device test PASSED!"
    echo ""
    
    # Check file size
    SIZE=$(stat -f%z /tmp/test_audio.wav 2>/dev/null || stat -c%s /tmp/test_audio.wav 2>/dev/null)
    SIZE_MB=$(echo "scale=2; $SIZE / 1048576" | bc)
    echo "  Test file size: $SIZE_MB MB"
    
    # Clean up
    rm -f /tmp/test_audio.wav
    
    # Update recorder.py if needed
    if [ "$CARD" != "1" ]; then
        echo ""
        echo "⚠️  Device is on card $CARD (not the default card 1)"
        echo ""
        echo "Updating recorder.py configuration..."
        
        RECORDER_FILE="$HOME/audio-recorder/recorder.py"
        
        if [ -f "$RECORDER_FILE" ]; then
            # Backup original
            cp "$RECORDER_FILE" "$RECORDER_FILE.backup"
            
            # Update default device
            sed -i "s/device='hw:1'/device='hw:$CARD'/" "$RECORDER_FILE"
            
            echo "✓ Updated recorder.py to use hw:$CARD"
            echo "  (Backup saved as recorder.py.backup)"
        else
            echo "❌ recorder.py not found at $RECORDER_FILE"
            echo "   Please manually edit the file and change:"
            echo "   device='hw:1' to device='hw:$CARD'"
        fi
    else
        echo ""
        echo "✓ Device is on card 1 (default) - no configuration changes needed"
    fi
    
    echo ""
    echo "=========================================="
    echo "✓ Configuration Complete!"
    echo "=========================================="
    echo ""
    echo "Next steps:"
    echo "  1. If service is running, restart it:"
    echo "     sudo systemctl restart audio-recorder"
    echo ""
    echo "  2. Access web UI at: http://$(hostname -I | awk '{print $1}'):5000"
    echo ""
    echo "  3. Test a recording from the Dashboard"
    echo ""
    
else
    echo ""
    echo "❌ Audio device test FAILED"
    echo ""
    echo "Please check:"
    echo "  1. UCA202 connections"
    echo "  2. Audio input source is connected"
    echo "  3. Try unplugging and replugging UCA202"
    echo ""
    exit 1
fi
