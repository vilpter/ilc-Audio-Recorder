#!/usr/bin/env python3
"""
Audio Recorder Module
Handles dual-mono capture via FFmpeg
"""

import subprocess
import signal
import shutil
import sqlite3
import sys
import os
import logging
from pathlib import Path
from datetime import datetime
import threading
import time
import scheduler

# Log file paths (exported for Settings page)
LOG_DIR = Path.home() / '.audio-recorder'
LOG_DIR.mkdir(exist_ok=True)
RECORDER_LOG_PATH = LOG_DIR / 'recorder.log'
FFMPEG_LOG_PATH = LOG_DIR / 'ffmpeg.log'

# Configure logging for device detection troubleshooting
# Use local time for timestamps (not UTC)
class LocalTimeFormatter(logging.Formatter):
    converter = time.localtime  # Use local time instead of UTC

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stderr),
        logging.FileHandler(RECORDER_LOG_PATH)
    ]
)
# Apply local time formatter to all handlers
for handler in logging.root.handlers:
    handler.setFormatter(LocalTimeFormatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s',
                                            datefmt='%Y-%m-%d %H:%M:%S'))
logger = logging.getLogger('recorder')


def get_log_paths():
    """Return dict of log file paths for Settings page"""
    return {
        'recorder': str(RECORDER_LOG_PATH),
        'ffmpeg': str(FFMPEG_LOG_PATH),
        'scheduler': str(LOG_DIR / 'scheduler.log')
    }


def _log_system_state():
    """Log system state for troubleshooting - called at recording start"""
    logger.info("=" * 40)
    logger.info("SYSTEM STATE SNAPSHOT")
    logger.info("=" * 40)
    logger.info(f"Timestamp: {datetime.now().isoformat()}")
    logger.info(f"Thread: {threading.current_thread().name}")

    # Log environment variables relevant to audio
    env_vars = ['PATH', 'HOME', 'USER', 'DISPLAY', 'XDG_RUNTIME_DIR', 'PULSE_SERVER', 'ALSA_CARD']
    logger.info("Environment variables:")
    for var in env_vars:
        value = os.environ.get(var, '(not set)')
        logger.info(f"  {var}={value}")

    # Log ALSA mixer state
    try:
        result = subprocess.run(['amixer', '-c', '1'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            logger.info("ALSA mixer state (card 1):")
            for line in result.stdout.split('\n')[:20]:  # First 20 lines
                if line.strip():
                    logger.info(f"  {line}")
        else:
            logger.warning(f"amixer failed: {result.stderr}")
    except Exception as e:
        logger.warning(f"Could not get ALSA mixer state: {e}")

    # Log running audio processes
    try:
        result = subprocess.run(['pgrep', '-a', 'ffmpeg|arecord|pulseaudio|pipewire'],
                              capture_output=True, text=True, shell=False, timeout=5)
        # pgrep returns non-zero if no matches, that's OK
        if result.stdout.strip():
            logger.info("Running audio-related processes:")
            for line in result.stdout.strip().split('\n'):
                logger.info(f"  {line}")
        else:
            logger.info("No other audio processes running")
    except Exception as e:
        logger.debug(f"Could not check running processes: {e}")

    logger.info("=" * 40)


def _log_ffmpeg_output(process, paths, job_timestamp):
    """Log FFmpeg stderr to dedicated log file"""
    ffmpeg_log_file = FFMPEG_LOG_PATH

    try:
        with open(ffmpeg_log_file, 'a') as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"Recording: {job_timestamp}\n")
            f.write(f"Started: {datetime.now().isoformat()}\n")
            f.write(f"Output files: {paths['source_a']}, {paths['source_b']}\n")
            f.write(f"{'='*60}\n")

            # Read stderr in real-time
            for line in process.stderr:
                timestamp = datetime.now().strftime('%H:%M:%S')
                f.write(f"[{timestamp}] {line}")
                f.flush()

            f.write(f"\nProcess ended: {datetime.now().isoformat()}\n")
            f.write(f"Return code: {process.returncode}\n")
    except Exception as e:
        logger.error(f"Error writing FFmpeg log: {e}")

# Configuration constants
DEFAULT_MAX_DURATION = 14400  # 4 hours in seconds
SAMPLE_RATE = 48000
BYTES_PER_SAMPLE = 2  # 16-bit = 2 bytes
CHANNELS = 2  # Stereo (split into 2 mono files)
SAFETY_MARGIN = 1.1  # 10% overhead for filesystem
DISK_SPACE_MULTIPLIER = 2  # Require 2x estimated size

# Global process tracker
current_process = None
process_lock = threading.Lock()


def load_channel_suffixes():
    """Load channel suffix configuration from database"""
    try:
        from pathlib import Path as PPath
        db_path = PPath.home() / '.audio-recorder' / 'schedule.db'
        
        if not db_path.exists():
            return 'L', 'R'  # Defaults if DB doesn't exist yet
        
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        cursor.execute("SELECT value FROM system_config WHERE key = 'channel_left_suffix'")
        left_row = cursor.fetchone()
        left_suffix = left_row[0] if left_row else 'L'
        
        cursor.execute("SELECT value FROM system_config WHERE key = 'channel_right_suffix'")
        right_row = cursor.fetchone()
        right_suffix = right_row[0] if right_row else 'R'
        
        conn.close()
        return left_suffix, right_suffix
    except:
        return 'L', 'R'  # Fallback to defaults on any error


def get_recording_path():
    """Generate timestamped recording filenames with configured suffixes"""
    now = datetime.now()

    # New format: YYYY_MMM_DD_HH:MM_L.wav
    timestamp = now.strftime('%Y_%b_%d_%H:%M')

    # Get storage path from config
    storage_path = scheduler.get_system_config('storage_path', '/mnt/usb_recorder')
    recordings_dir = Path(storage_path)
    recordings_dir.mkdir(parents=True, exist_ok=True)

    # Load configured channel suffixes
    left_suffix, right_suffix = load_channel_suffixes()

    return {
        'source_a': recordings_dir / f'{timestamp}_{left_suffix}.wav',
        'source_b': recordings_dir / f'{timestamp}_{right_suffix}.wav',
        'timestamp': timestamp,
        'directory': recordings_dir
    }


def calculate_estimated_size(duration_seconds):
    """
    Calculate estimated file size for recording
    
    Args:
        duration_seconds: Recording duration in seconds
    
    Returns:
        Estimated total size in bytes (both channels)
    """
    # Size per channel: duration * sample_rate * bytes_per_sample
    size_per_channel = duration_seconds * SAMPLE_RATE * BYTES_PER_SAMPLE
    
    # Total for both channels with safety margin
    total_size = size_per_channel * CHANNELS * SAFETY_MARGIN
    
    return int(total_size)


def check_disk_space(duration_seconds, recording_dir):
    """
    Check if sufficient disk space is available
    
    Args:
        duration_seconds: Planned recording duration
        recording_dir: Path to recordings directory
    
    Returns:
        Tuple of (sufficient: bool, message: str, available_gb: float, required_gb: float)
    """
    estimated_size = calculate_estimated_size(duration_seconds)
    required_size = estimated_size * DISK_SPACE_MULTIPLIER
    
    # Check available disk space
    stat = shutil.disk_usage(recording_dir)
    available = stat.free
    
    available_gb = available / (1024**3)
    required_gb = required_size / (1024**3)
    
    if available < required_size:
        message = (f"Insufficient disk space. Required: {required_gb:.2f} GB "
                  f"(2x {estimated_size / (1024**3):.2f} GB estimate), "
                  f"Available: {available_gb:.2f} GB")
        return False, message, available_gb, required_gb
    
    message = f"Disk space OK. Required: {required_gb:.2f} GB, Available: {available_gb:.2f} GB"
    return True, message, available_gb, required_gb


def validate_duration(duration_seconds, allow_override=False):
    """
    Validate recording duration against limits
    
    Args:
        duration_seconds: Requested duration
        allow_override: If True, skip duration limit check
    
    Returns:
        Tuple of (valid: bool, message: str)
    """
    if duration_seconds <= 0:
        return False, "Duration must be positive"
    
    if not allow_override and duration_seconds > DEFAULT_MAX_DURATION:
        return False, (f"Duration exceeds {DEFAULT_MAX_DURATION/3600:.1f} hour limit. "
                      f"Use override option to allow longer recordings.")
    
    return True, "Duration valid"


def start_capture(duration_seconds=3600, device=None, allow_override=False):
    """
    Start FFmpeg capture process with validation
    
    Args:
        duration_seconds: Recording duration in seconds
        device: ALSA device identifier (None = use config)
        allow_override: Allow recordings longer than default limit
    
    Returns:
        Job ID (timestamp) for tracking
    
    Raises:
        RuntimeError: If recording already in progress or validation fails
    """
    global current_process
    
    # Load device from config if not specified
    if device is None:
        # Import here to avoid circular dependency
        import scheduler
        device_config = scheduler.get_system_config('audio_device', 'auto')
        logger.info(f"Device config from database: '{device_config}'")
        if device_config == 'auto':
            logger.info("Auto-detecting audio device...")
            device = auto_detect_audio_device()
        else:
            device = device_config
            logger.info(f"Using configured device: {device}")

    logger.info(f"FINAL DEVICE FOR RECORDING: {device}")
    
    with process_lock:
        if current_process and current_process.poll() is None:
            raise RuntimeError("Recording already in progress")
        
        # Validate duration
        valid, msg = validate_duration(duration_seconds, allow_override)
        if not valid:
            raise RuntimeError(msg)
        
        paths = get_recording_path()
        
        # Check disk space
        sufficient, msg, avail_gb, req_gb = check_disk_space(duration_seconds, paths['directory'])
        if not sufficient:
            raise RuntimeError(msg)
        
        logger.info(f"Starting recording: {duration_seconds}s on {device}, ~{req_gb/2:.2f} GB estimated per channel")
        print(f"Starting recording: {duration_seconds}s on {device}, ~{req_gb/2:.2f} GB estimated per channel")

        # Log system state for troubleshooting
        _log_system_state()

        # FFmpeg command for dual-mono capture
        cmd = [
            'ffmpeg',
            '-f', 'alsa',
            '-i', device,
            '-t', str(duration_seconds),
            '-filter_complex', '[0:a]channelsplit=channel_layout=stereo[left][right]',
            '-map', '[left]',
            '-acodec', 'pcm_s16le',
            '-ar', str(SAMPLE_RATE),
            str(paths['source_a']),
            '-map', '[right]',
            '-acodec', 'pcm_s16le',
            '-ar', str(SAMPLE_RATE),
            str(paths['source_b'])
        ]

        # Log the exact FFmpeg command for reproduction/debugging
        cmd_str = ' '.join(str(c) for c in cmd)
        logger.info(f"FFmpeg command: {cmd_str}")

        # Start FFmpeg process
        current_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=lambda: signal.signal(signal.SIGINT, signal.SIG_IGN),
            text=True  # Enable text mode for easier log reading
        )
        
        # Start monitoring thread
        monitor_thread = threading.Thread(
            target=_monitor_process,
            args=(current_process, paths, duration_seconds),
            daemon=True
        )
        monitor_thread.start()
        
        return paths['timestamp']


def is_recording():
    """
    Check if a recording is currently in progress
    
    Returns:
        bool: True if recording is active, False otherwise
    """
    global current_process
    with process_lock:
        return current_process is not None and current_process.poll() is None


def stop_capture():
    """
    Gracefully stop current recording
    """
    global current_process
    
    with process_lock:
        if not current_process or current_process.poll() is not None:
            raise RuntimeError("No recording in progress")
        
        # Send SIGTERM for graceful shutdown
        current_process.terminate()
        
        # Wait up to 5 seconds for graceful exit
        try:
            current_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            # Force kill if necessary
            current_process.kill()
            current_process.wait()
        
        current_process = None


def _monitor_process(process, paths, duration):
    """
    Monitor FFmpeg process and handle post-processing
    """
    job_timestamp = paths['timestamp']
    logger.info(f"Monitor thread started for recording: {job_timestamp}")

    # Start FFmpeg stderr logging in separate thread
    ffmpeg_log_thread = threading.Thread(
        target=_log_ffmpeg_output,
        args=(process, paths, job_timestamp),
        daemon=True
    )
    ffmpeg_log_thread.start()

    # Heartbeat logging - log every 60 seconds while recording
    heartbeat_interval = 60
    start_time = time.time()
    heartbeat_count = 0

    while process.poll() is None:
        time.sleep(5)  # Check every 5 seconds
        elapsed = time.time() - start_time

        # Log heartbeat every 60 seconds
        if elapsed >= (heartbeat_count + 1) * heartbeat_interval:
            heartbeat_count += 1
            minutes_elapsed = int(elapsed / 60)
            minutes_remaining = int((duration - elapsed) / 60)
            logger.info(f"HEARTBEAT [{job_timestamp}]: Recording in progress - "
                       f"{minutes_elapsed} min elapsed, ~{minutes_remaining} min remaining")

    # Process completed
    elapsed_total = time.time() - start_time
    logger.info(f"FFmpeg process ended for {job_timestamp} after {elapsed_total:.1f}s (expected {duration}s)")
    logger.info(f"FFmpeg return code: {process.returncode}")

    # Check if files were created successfully
    if paths['source_a'].exists() and paths['source_b'].exists():
        size_a = paths['source_a'].stat().st_size
        size_b = paths['source_b'].stat().st_size
        size_a_mb = size_a / (1024 * 1024)
        size_b_mb = size_b / (1024 * 1024)

        logger.info(f"Recording completed: {job_timestamp}")
        logger.info(f"  Left channel: {paths['source_a']} ({size_a_mb:.1f} MB)")
        logger.info(f"  Right channel: {paths['source_b']} ({size_b_mb:.1f} MB)")

        # Warn if files are suspiciously small (might be silent)
        expected_size_mb = (duration * SAMPLE_RATE * BYTES_PER_SAMPLE) / (1024 * 1024)
        if size_a_mb < expected_size_mb * 0.5 or size_b_mb < expected_size_mb * 0.5:
            logger.warning(f"WARNING: File sizes are smaller than expected ({expected_size_mb:.1f} MB). "
                          f"Recording may be truncated or silent!")

        print(f"Recording completed: {paths['timestamp']}")
    else:
        logger.error(f"Recording FAILED: {job_timestamp} - output files not created")
        logger.error(f"  Expected: {paths['source_a']}")
        logger.error(f"  Expected: {paths['source_b']}")
        print(f"Recording failed: {paths['timestamp']}")


def is_recording():
    """Check if a recording is currently in progress"""
    global current_process
    return current_process is not None and current_process.poll() is None


def get_available_devices():
    """
    List available ALSA audio devices
    
    Returns:
        List of device identifiers
    """
    try:
        result = subprocess.run(
            ['arecord', '-l'],
            capture_output=True,
            text=True
        )
        # Parse output to extract device list
        # This is a simplified version - can be enhanced
        return result.stdout
    except Exception as e:
        return f"Error listing devices: {e}"


def get_available_audio_devices():
    """
    Parse arecord -l output to list all capture-capable devices

    Returns list of dictionaries with device info
    """
    import re

    logger.debug(f"get_available_audio_devices() called from thread: {threading.current_thread().name}")

    try:
        result = subprocess.run(['arecord', '-l'], capture_output=True, text=True)
        logger.debug(f"arecord -l return code: {result.returncode}")
        logger.debug(f"arecord -l stdout: {result.stdout[:500] if result.stdout else '(empty)'}")
        if result.stderr:
            logger.debug(f"arecord -l stderr: {result.stderr[:500]}")
    except Exception as e:
        logger.error(f"arecord -l failed with exception: {e}")
        return []
    
    devices = []
    
    # Parse output format:
    # card 1: CODEC [USB Audio CODEC], device 0: USB Audio [USB Audio]
    pattern = r'card (\d+): (\w+) \[([^\]]+)\], device (\d+): ([^\[]+)'
    
    for match in re.finditer(pattern, result.stdout):
        card, short_name, full_name, device, desc = match.groups()
        
        alsa_id = f"hw:{card},{device}"
        
        # Detect UCA202 specifically
        is_uca202 = ('USB Audio' in full_name or 'PCM290' in full_name or 
                     'CODEC' in full_name or 'Burr-Brown' in result.stdout)
        
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
    logger.info(f"auto_detect_audio_device() called from thread: {threading.current_thread().name}")
    devices = get_available_audio_devices()
    logger.info(f"Found {len(devices)} audio device(s): {[d['alsa_id'] for d in devices]}")

    # Try to find recommended device (UCA202)
    for dev in devices:
        if dev.get('is_recommended'):
            logger.info(f"Selected recommended device: {dev['alsa_id']} ({dev['name']})")
            return dev['alsa_id']

    # Fallback to first capture device
    if devices:
        logger.warning(f"No recommended device found, using first device: {devices[0]['alsa_id']}")
        return devices[0]['alsa_id']

    # Ultimate fallback
    logger.error("NO AUDIO DEVICES DETECTED! Falling back to hw:1,0 - THIS MAY CAUSE SILENT RECORDINGS")
    return 'hw:1,0'


# Utility function for testing
if __name__ == '__main__':
    print("Available Audio Devices:")
    print(get_available_devices())
    print("\nStarting 10-second test recording...")
    
    try:
        job_id = start_capture(duration_seconds=10)
        print(f"Recording started: {job_id}")
        time.sleep(11)  # Wait for completion
        print("Recording should be complete. Check ~/recordings/")
    except Exception as e:
        print(f"Error: {e}")
