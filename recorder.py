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
import db_utils
import config
import logging_setup

# Log file paths (exported for Settings page)
config.ensure_dirs()
LOG_DIR = config.LOG_DIR
RECORDER_LOG_PATH = config.RECORDER_LOG_PATH
FFMPEG_LOG_PATH = config.FFMPEG_LOG_PATH

# Handlers are installed by logging_setup.configure_logging() (called from app.py)
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


FFMPEG_LOG_MAX_BYTES = logging_setup.MAX_BYTES
FFMPEG_PROGRESS_INTERVAL = 60  # seconds between logged progress lines


def _is_ffmpeg_progress(line):
    return line.lstrip().startswith('size=') and 'time=' in line


def _log_ffmpeg_output(process, paths, job_timestamp):
    """Log FFmpeg stderr to dedicated log file.

    FFmpeg prints a progress line twice a second; only one per
    FFMPEG_PROGRESS_INTERVAL is kept, plus the last one before any other
    message (such as an error or the exit summary).
    """
    ffmpeg_log_file = FFMPEG_LOG_PATH
    logging_setup.rotate_if_oversized(ffmpeg_log_file, FFMPEG_LOG_MAX_BYTES)

    try:
        with open(ffmpeg_log_file, 'a') as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"Recording: {job_timestamp}\n")
            f.write(f"Started: {datetime.now().isoformat()}\n")
            f.write(f"Output files: {paths['source_a']}, {paths['source_b']}\n")
            f.write(f"{'='*60}\n")

            # Read stderr in real-time
            last_progress_logged = 0.0
            pending_progress = None
            for line in process.stderr:
                timestamp = datetime.now().strftime('%H:%M:%S')
                if _is_ffmpeg_progress(line):
                    now = time.monotonic()
                    if now - last_progress_logged < FFMPEG_PROGRESS_INTERVAL:
                        pending_progress = f"[{timestamp}] {line}"
                        continue
                    last_progress_logged = now
                elif pending_progress:
                    # Progress just before a message (exit, error) gives it context
                    f.write(pending_progress)
                pending_progress = None
                f.write(f"[{timestamp}] {line}")
                f.flush()
            if pending_progress:
                f.write(pending_progress)

            # stderr closes as FFmpeg exits; collect its exit status for the log
            try:
                returncode = process.wait(timeout=10)
            except Exception:
                returncode = process.returncode
            f.write(f"\nProcess ended: {datetime.now().isoformat()}\n")
            f.write(f"Return code: {returncode}\n")
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
_stop_requested = False  # set by stop_capture() so the monitor knows the stop was intended

# Recordings (by base name) being analyzed, so one recording is never analyzed twice at once
_analysis_in_progress = set()
_analysis_lock = threading.Lock()

# Shared audio recording status. Lives here (not in app.py) so the Flask routes
# and the scheduler thread mutate the same dict regardless of how app.py is run.
recording_status = {
    'is_recording': False,
    'current_job': None,
    'start_time': None
}


def load_channel_suffixes():
    """Load channel suffix configuration from database"""
    try:
        db_path = config.SCHEDULE_DB_PATH

        if not db_path.exists():
            return 'L', 'R'  # Defaults if DB doesn't exist yet

        left_row = db_utils.fetch_one(db_path,
            "SELECT value FROM system_config WHERE key = 'channel_left_suffix'")
        left_suffix = left_row[0] if left_row else 'L'

        right_row = db_utils.fetch_one(db_path,
            "SELECT value FROM system_config WHERE key = 'channel_right_suffix'")
        right_suffix = right_row[0] if right_row else 'R'

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
    global current_process, _stop_requested
    
    # Load device from config if not specified
    if device is None:
        # Import here to avoid circular dependency
        import scheduler
        device_config = scheduler.get_system_config('audio_device', 'auto')
        logger.info(f"Device config from database: '{device_config}'")
        if device_config == 'auto':
            logger.info("Auto-detecting audio device...")
            device = auto_detect_audio_device(verbose=True)
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
        _stop_requested = False
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
    global current_process, _stop_requested

    with process_lock:
        if not current_process or current_process.poll() is not None:
            raise RuntimeError("No recording in progress")

        # Send SIGTERM for graceful shutdown
        _stop_requested = True
        current_process.terminate()
        
        # Wait up to 5 seconds for graceful exit
        try:
            current_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            # Force kill if necessary
            current_process.kill()
            current_process.wait()

        current_process = None
    # The monitor thread sees the process exit and schedules analysis of this
    # recording (and of any older recordings still missing analysis).


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
    stopped_by_user = _stop_requested
    if stopped_by_user:
        logger.info(f"Recording {job_timestamp} stopped by user after {elapsed_total:.1f}s "
                    f"(scheduled for {duration}s)")
    else:
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

        # Warn if files are much smaller than the time actually recorded implies
        # (a stopped-early recording is expected to be shorter than scheduled)
        recorded_seconds = min(duration, elapsed_total)
        expected_size_mb = (recorded_seconds * SAMPLE_RATE * BYTES_PER_SAMPLE) / (1024 * 1024)
        # (skipped for very short recordings, where FFmpeg's startup time dominates)
        if recorded_seconds >= 10 and (size_a_mb < expected_size_mb * 0.5 or size_b_mb < expected_size_mb * 0.5):
            logger.warning(f"WARNING: File sizes are smaller than expected for {recorded_seconds:.0f}s "
                          f"of audio ({expected_size_mb:.1f} MB). Recording may be truncated!")
        if not stopped_by_user and elapsed_total < duration * 0.95:
            logger.warning(f"WARNING: Recording {job_timestamp} ended after {elapsed_total:.0f}s "
                           f"of {duration}s without being stopped (FFmpeg return code "
                           f"{process.returncode})")

        # Schedule analysis after 20-second delay
        threading.Timer(
            20.0,  # 20 second delay
            _analyze_recording_delayed,
            args=(paths['source_a'], paths['source_b'], job_timestamp)
        ).start()

        # Catch up on older recordings that never got analyzed
        threading.Thread(
            target=analyze_unanalyzed_recordings,
            kwargs={'exclude': {paths['source_a'].name, paths['source_b'].name}},
            daemon=True
        ).start()

    else:
        logger.error(f"Recording FAILED: {job_timestamp} - output files not created")
        logger.error(f"  Expected: {paths['source_a']}")
        logger.error(f"  Expected: {paths['source_b']}")


def _analyze_recording_delayed(source_a, source_b, job_timestamp):
    """
    Analyze recording files and store results in database.
    Called 20 seconds after recording completes.

    Args:
        source_a: Path to left channel WAV file
        source_b: Path to right channel WAV file
        job_timestamp: Recording timestamp identifier
    """
    with _analysis_lock:
        if job_timestamp in _analysis_in_progress:
            logger.info(f"Analysis already running for {job_timestamp}; skipping duplicate")
            return
        _analysis_in_progress.add(job_timestamp)
    try:
        _analyze_recording(source_a, source_b, job_timestamp)
    finally:
        with _analysis_lock:
            _analysis_in_progress.discard(job_timestamp)


def _analyze_recording(source_a, source_b, job_timestamp):
    """Analyze both channels of one recording and store the results."""
    import audio_analyzer
    import db_utils
    from datetime import datetime

    logger.info(f"Starting analysis for recording: {job_timestamp}")

    def analyze_and_store(filepath, channel_name):
        """Analyze single channel and store results"""
        try:
            # Verify file still exists and has content
            if not filepath.exists() or filepath.stat().st_size == 0:
                logger.warning(f"File not found or empty: {filepath}")
                return

            # Run analysis
            result = audio_analyzer.analyze_audio_file(
                str(filepath),
                silence_threshold_db=-60.0,
                silence_duration_sec=2.0
            )

            # Extract channel 0 stats (mono file)
            channel_stats = result['channels'][0] if result['channels'] else None

            if not channel_stats:
                logger.error(f"No channel data in analysis for {filepath}")
                return

            # Run artifact detection (clipping + discontinuities)
            artifact_result = None
            try:
                import artifact_detector
                artifact_result = artifact_detector.detect_artifacts(str(filepath))
                if artifact_result.error_message:
                    logger.warning(f"Artifact detection warning for {filepath.name}: "
                                  f"{artifact_result.error_message}")
                    artifact_result = None
                else:
                    logger.info(f"Artifact detection for {filepath.name}: "
                               f"{artifact_result.digital_clip_count} digital clips, "
                               f"{artifact_result.flatline_clip_count} flatline clips, "
                               f"{artifact_result.discontinuity_count} discontinuities, "
                               f"quality={artifact_result.quality_score}")
            except Exception as ae:
                logger.error(f"Artifact detection failed for {filepath}: {ae}")

            # Store in database
            from scheduler import DB_PATH
            db_utils.execute_query(DB_PATH, '''
                INSERT OR REPLACE INTO audio_analysis
                (filename, channel, analyzed_at, total_duration, non_silent_percentage,
                 mean_db, max_db, max_db_time, status,
                 digital_clip_count, flatline_clip_count, discontinuity_count,
                 quality_score, artifact_details, artifact_version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                filepath.name,
                channel_name,
                datetime.now().isoformat(),
                channel_stats['total_duration'],
                channel_stats['non_silent_percentage'],
                channel_stats['mean_db'],
                channel_stats['max_db'],
                channel_stats['max_db_time'],
                'completed',
                artifact_result.digital_clip_count if artifact_result else None,
                artifact_result.flatline_clip_count if artifact_result else None,
                artifact_result.discontinuity_count if artifact_result else None,
                artifact_result.quality_score if artifact_result else None,
                artifact_result.to_artifact_json() if artifact_result else None,
                1 if artifact_result else None,
            ), commit=True)

            logger.info(f"Analysis completed for {filepath.name}: "
                       f"{channel_stats['non_silent_percentage']:.1f}% non-silent, "
                       f"max {channel_stats['max_db']:.1f} dB")

        except Exception as e:
            logger.error(f"Analysis failed for {filepath}: {e}")
            # Store failure status
            try:
                from scheduler import DB_PATH
                db_utils.execute_query(DB_PATH, '''
                    INSERT OR REPLACE INTO audio_analysis
                    (filename, channel, analyzed_at, status, error_message)
                    VALUES (?, ?, ?, ?, ?)
                ''', (filepath.name, channel_name, datetime.now().isoformat(),
                     'failed', str(e)), commit=True)
            except:
                pass

    # Analyze both channels
    analyze_and_store(source_a, 'left')
    analyze_and_store(source_b, 'right')

    logger.info(f"Analysis batch complete for: {job_timestamp}")


def analyze_unanalyzed_recordings(exclude=()):
    """
    Check for WAV files without a successful analysis and analyze them.
    Called on app startup and after each recording (with that recording's
    files in exclude, since they are analyzed separately).
    """
    from pathlib import Path
    from scheduler import get_system_config, DB_PATH
    import db_utils

    storage_path = get_system_config('storage_path', '/mnt/usb_recorder')
    recordings_dir = Path(storage_path)

    if not recordings_dir.exists():
        return

    # Get all analyzed filenames (failed analyses are retried)
    analyzed_files = set()
    try:
        results = db_utils.fetch_all(DB_PATH,
            "SELECT DISTINCT filename FROM audio_analysis WHERE status != 'failed'")
        analyzed_files = {row[0] for row in results}
    except:
        pass  # Table might not exist yet

    # Find unanalyzed WAV files
    wav_files = list(recordings_dir.glob('*.wav'))
    unanalyzed = [f for f in wav_files if f.name not in analyzed_files and f.name not in exclude]

    if unanalyzed:
        logger.info(f"Found {len(unanalyzed)} unanalyzed recordings")

        # Load configured channel suffixes
        left_suffix, right_suffix = load_channel_suffixes()
        left_pattern = f'_{left_suffix}'
        right_pattern = f'_{right_suffix}'

        # Group by pairs (left/right)
        pairs = {}
        for filepath in unanalyzed:
            # Extract base timestamp (remove configured suffix)
            name = filepath.stem
            if name.endswith(left_pattern):
                base = name[:-len(left_pattern)]
                pairs.setdefault(base, {})['left'] = filepath
            elif name.endswith(right_pattern):
                base = name[:-len(right_pattern)]
                pairs.setdefault(base, {})['right'] = filepath

        # Analyze pairs in background
        for base_name, files in pairs.items():
            if 'left' in files and 'right' in files:
                threading.Thread(
                    target=_analyze_recording_delayed,
                    args=(files['left'], files['right'], base_name),
                    daemon=True
                ).start()


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


def auto_detect_audio_device(verbose=False):
    """
    Automatically select the best audio device

    Priority:
    1. First USB audio device (UCA202)
    2. First capture-capable device
    3. hw:1,0 as fallback

    verbose=True logs the selection at INFO (used when starting a recording);
    otherwise it is DEBUG, since the Settings page asks several times per load.
    """
    log = logger.info if verbose else logger.debug
    log(f"auto_detect_audio_device() called from thread: {threading.current_thread().name}")
    devices = get_available_audio_devices()
    log(f"Found {len(devices)} audio device(s): {[d['alsa_id'] for d in devices]}")

    # Try to find recommended device (UCA202)
    for dev in devices:
        if dev.get('is_recommended'):
            log(f"Selected recommended device: {dev['alsa_id']} ({dev['name']})")
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
        print(f"Recording should be complete. Check {get_recording_path()['directory']}")
    except Exception as e:
        print(f"Error: {e}")
