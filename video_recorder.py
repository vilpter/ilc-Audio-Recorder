#!/usr/bin/env python3
"""
Video Recorder Module
Handles PTZOptics camera control, RTSP stream recording, and hardware-accelerated transcoding
"""

import subprocess
import signal
import shutil
import os
import re
import threading
import json
from pathlib import Path
from datetime import datetime
from urllib.parse import quote

import requests

# Import scheduler for config storage (reuses existing system_config table)
import scheduler

# Configuration constants
DEFAULT_VIDEO_BITRATE = '4M'  # For hardware transcoding
VIDEO_MB_PER_HOUR = 2000  # Estimated ~2GB/hour for raw RTSP stream at 1080p
SAFETY_MARGIN = 1.1

# Global process tracker for video recording
video_process = None
video_process_lock = threading.Lock()
current_video_file = None
video_start_time = None

# Global tracker for transcoding
transcode_process = None
transcode_progress = {
    'is_processing': False,
    'current_file': None,
    'progress_percent': 0,
    'status': 'idle'
}
transcode_lock = threading.Lock()


# ============================================================================
# Configuration Functions (uses existing scheduler.system_config table)
# ============================================================================

def get_camera_config():
    """
    Load camera configuration from database using existing system_config table

    Returns:
        Dictionary with camera settings
    """
    return {
        'camera_ip': scheduler.get_system_config('camera_ip', ''),
        'camera_username': scheduler.get_system_config('camera_username', ''),
        'camera_password': scheduler.get_system_config('camera_password', ''),
        'storage_path': scheduler.get_system_config('storage_path', '/mnt/usb_recorder'),
        'preset_names': json.loads(scheduler.get_system_config('preset_names', '{}'))
    }


def set_camera_config(key, value):
    """
    Save camera configuration to database

    Args:
        key: Configuration key
        value: Configuration value (will be JSON-encoded if dict)
    """
    if isinstance(value, dict):
        value = json.dumps(value)
    scheduler.set_system_config(key, value)


def get_preset_names():
    """Get preset ID to name mappings"""
    try:
        return json.loads(scheduler.get_system_config('preset_names', '{}'))
    except:
        return {}


def set_preset_names(preset_dict):
    """Save preset ID to name mappings"""
    scheduler.set_system_config('preset_names', json.dumps(preset_dict))


# ============================================================================
# Storage Validation Functions
# ============================================================================

def validate_storage_path(storage_path):
    """
    Validate that the storage path exists and is writable

    Args:
        storage_path: Path to the USB storage mount point

    Returns:
        Tuple of (valid: bool, message: str)
    """
    path = Path(storage_path)

    if not path.exists():
        return False, f"Storage path does not exist: {storage_path}"

    if not path.is_dir():
        return False, f"Storage path is not a directory: {storage_path}"

    # Check if path is a mount point (for USB drives)
    if not os.path.ismount(storage_path) and storage_path.startswith('/mnt/'):
        return False, f"USB drive not mounted at: {storage_path}"

    # Check write permissions by trying to create a test file
    test_file = path / '.write_test'
    try:
        test_file.touch()
        test_file.unlink()
    except (PermissionError, OSError) as e:
        return False, f"Cannot write to storage path: {e}"

    return True, "Storage path is valid and writable"


def check_video_disk_space(duration_seconds, storage_path):
    """
    Check if sufficient disk space is available for video recording

    Args:
        duration_seconds: Planned recording duration
        storage_path: Path to storage location

    Returns:
        Tuple of (sufficient: bool, message: str, available_gb: float, required_gb: float)
    """
    # Estimate size: ~2GB/hour for raw RTSP stream
    estimated_mb = (duration_seconds / 3600) * VIDEO_MB_PER_HOUR
    required_mb = estimated_mb * SAFETY_MARGIN * 2  # 2x safety multiplier

    try:
        stat = shutil.disk_usage(storage_path)
        available_mb = stat.free / (1024 * 1024)

        available_gb = available_mb / 1024
        required_gb = required_mb / 1024

        if available_mb < required_mb:
            message = (f"Insufficient disk space. Required: {required_gb:.2f} GB, "
                      f"Available: {available_gb:.2f} GB")
            return False, message, available_gb, required_gb

        message = f"Disk space OK. Required: {required_gb:.2f} GB, Available: {available_gb:.2f} GB"
        return True, message, available_gb, required_gb
    except Exception as e:
        return False, f"Error checking disk space: {e}", 0, 0


# ============================================================================
# Camera Proxy Functions (PTZ Control)
# ============================================================================

def call_camera_preset(preset_id):
    """
    Call a PTZ preset on the PTZOptics camera

    Args:
        preset_id: Preset number (1-255)

    Returns:
        Tuple of (success: bool, message: str)
    """
    config = get_camera_config()

    if not config['camera_ip']:
        return False, "Camera IP not configured"

    # Build the CGI URL for PTZOptics
    # Format: http://[IP]/cgi-bin/ptzctrl.cgi?ptzcmd&poscall&[preset_id]
    url = f"http://{config['camera_ip']}/cgi-bin/ptzctrl.cgi?ptzcmd&poscall&{preset_id}"

    try:
        # Build auth tuple if credentials provided
        auth = None
        if config['camera_username'] and config['camera_password']:
            auth = (config['camera_username'], config['camera_password'])

        response = requests.get(url, auth=auth, timeout=10)

        if response.status_code == 200:
            return True, f"Preset {preset_id} called successfully"
        else:
            return False, f"Camera returned status {response.status_code}: {response.text}"

    except requests.exceptions.ConnectionError:
        return False, f"Cannot connect to camera at {config['camera_ip']}"
    except requests.exceptions.Timeout:
        return False, "Camera request timed out"
    except Exception as e:
        return False, f"Error calling preset: {e}"


def get_rtsp_url(include_credentials=True):
    """
    Get the RTSP stream URL for the camera

    Args:
        include_credentials: Whether to include auth in URL

    Returns:
        RTSP URL string or None if not configured
    """
    config = get_camera_config()

    if not config['camera_ip']:
        return None

    # Build RTSP URL with optional authentication
    if include_credentials and config['camera_username'] and config['camera_password']:
        # URL-encode credentials for special characters
        username = quote(config['camera_username'], safe='')
        password = quote(config['camera_password'], safe='')
        return f"rtsp://{username}:{password}@{config['camera_ip']}/1"
    else:
        return f"rtsp://{config['camera_ip']}/1"


def get_live_stream_info():
    """
    Get live stream viewing information for the UI

    Returns:
        Dictionary with stream URLs and commands
    """
    config = get_camera_config()

    if not config['camera_ip']:
        return {
            'configured': False,
            'message': 'Camera IP not configured'
        }

    rtsp_url = f"rtsp://{config['camera_ip']}/1"

    return {
        'configured': True,
        'camera_ip': config['camera_ip'],
        'rtsp_url': rtsp_url,
        'ffplay_command': f"ffplay -i {rtsp_url}",
        'vlc_url': rtsp_url
    }


def test_camera_connection():
    """
    Test connection to the camera

    Returns:
        Tuple of (success: bool, message: str)
    """
    config = get_camera_config()

    if not config['camera_ip']:
        return False, "Camera IP not configured"

    try:
        auth = None
        if config['camera_username'] and config['camera_password']:
            auth = (config['camera_username'], config['camera_password'])

        # Try to reach the camera's web interface
        response = requests.get(
            f"http://{config['camera_ip']}/",
            auth=auth,
            timeout=5
        )

        if response.status_code == 200:
            return True, "Camera connection successful"
        elif response.status_code == 401:
            return False, "Authentication failed - check username/password"
        else:
            return False, f"Camera returned status {response.status_code}"

    except requests.exceptions.ConnectionError:
        return False, f"Cannot connect to camera at {config['camera_ip']}"
    except requests.exceptions.Timeout:
        return False, "Connection timed out"
    except Exception as e:
        return False, f"Connection error: {e}"


# ============================================================================
# Video Recording Functions
# ============================================================================

def get_video_path(storage_path):
    """
    Generate timestamped video filename in the raw directory

    Args:
        storage_path: Base storage path

    Returns:
        Dictionary with file paths
    """
    now = datetime.now()
    timestamp = now.strftime('%Y_%b_%d_%H-%M-%S')

    # Create raw directory for unprocessed recordings
    raw_dir = Path(storage_path) / 'raw'
    raw_dir.mkdir(parents=True, exist_ok=True)

    # Create processed directory for transcoded files
    processed_dir = Path(storage_path) / 'processed'
    processed_dir.mkdir(parents=True, exist_ok=True)

    return {
        'raw_file': raw_dir / f'video_{timestamp}.mp4',
        'processed_file': processed_dir / f'video_{timestamp}_compressed.mp4',
        'timestamp': timestamp,
        'raw_dir': raw_dir,
        'processed_dir': processed_dir
    }


def start_video_recording(duration_seconds=None):
    """
    Start video recording from RTSP stream

    Args:
        duration_seconds: Recording duration in seconds (None for indefinite)

    Returns:
        Dictionary with status and file info

    Raises:
        RuntimeError: If recording fails to start
    """
    global video_process, current_video_file, video_start_time

    config = get_camera_config()

    if not config['camera_ip']:
        raise RuntimeError("Camera IP not configured")

    storage_path = config['storage_path']

    # Validate storage path
    valid, msg = validate_storage_path(storage_path)
    if not valid:
        raise RuntimeError(msg)

    # Check disk space if duration specified
    if duration_seconds:
        sufficient, msg, _, _ = check_video_disk_space(duration_seconds, storage_path)
        if not sufficient:
            raise RuntimeError(msg)

    with video_process_lock:
        if video_process and video_process.poll() is None:
            raise RuntimeError("Video recording already in progress")

        rtsp_url = get_rtsp_url()
        paths = get_video_path(storage_path)
        current_video_file = paths['raw_file']
        video_start_time = datetime.now()

        # Build ffmpeg command
        # Using -c copy for zero CPU re-encoding (stream copy)
        cmd = [
            'ffmpeg',
            '-rtsp_transport', 'tcp',  # Use TCP for more reliable streaming
            '-i', rtsp_url,
            '-c', 'copy',              # Copy codec - no re-encoding
            '-map', '0',               # Map all streams
            '-movflags', '+faststart', # Enable fast start for MP4
        ]

        # Add duration if specified
        if duration_seconds:
            cmd.extend(['-t', str(duration_seconds)])

        # Output file
        cmd.append(str(paths['raw_file']))

        print(f"Starting video recording: {paths['raw_file']}")

        try:
            video_process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=lambda: signal.signal(signal.SIGINT, signal.SIG_IGN)
            )

            # Start monitoring thread
            monitor_thread = threading.Thread(
                target=_monitor_video_process,
                args=(video_process, paths, duration_seconds),
                daemon=True
            )
            monitor_thread.start()

            return {
                'success': True,
                'file': str(paths['raw_file']),
                'timestamp': paths['timestamp']
            }

        except Exception as e:
            raise RuntimeError(f"Failed to start ffmpeg: {e}")


def stop_video_recording():
    """
    Gracefully stop video recording

    Sends 'q' to ffmpeg stdin to properly finalize the MP4 file

    Returns:
        Dictionary with status
    """
    global video_process, current_video_file, video_start_time

    with video_process_lock:
        if not video_process or video_process.poll() is not None:
            raise RuntimeError("No video recording in progress")

        print("Stopping video recording...")

        # Send 'q' to ffmpeg stdin for graceful shutdown
        # This ensures the MP4 header is written correctly
        try:
            video_process.stdin.write(b'q')
            video_process.stdin.flush()
            video_process.wait(timeout=10)
        except (subprocess.TimeoutExpired, BrokenPipeError, OSError):
            # If stdin doesn't work, try SIGTERM
            if video_process.poll() is None:
                video_process.terminate()
                try:
                    video_process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    # Force kill if necessary
                    video_process.kill()
                    video_process.wait()

        stopped_file = current_video_file
        video_process = None
        current_video_file = None
        video_start_time = None

        return {
            'success': True,
            'file': str(stopped_file) if stopped_file else None
        }


def is_video_recording():
    """Check if video recording is currently in progress"""
    global video_process
    with video_process_lock:
        return video_process is not None and video_process.poll() is None


def get_video_recording_status():
    """
    Get current video recording status

    Returns:
        Dictionary with recording status
    """
    global video_process, current_video_file, video_start_time

    with video_process_lock:
        is_recording = video_process is not None and video_process.poll() is None

        return {
            'is_recording': is_recording,
            'current_file': str(current_video_file) if current_video_file else None,
            'start_time': video_start_time.isoformat() if video_start_time else None
        }


def _monitor_video_process(process, paths, duration):
    """
    Monitor video recording process and trigger post-processing
    """
    # Wait for process to complete
    process.wait()

    # Check if file was created successfully
    if paths['raw_file'].exists() and paths['raw_file'].stat().st_size > 0:
        print(f"Video recording completed: {paths['raw_file']}")

        # Trigger transcoding in background
        threading.Thread(
            target=transcode_video,
            args=(str(paths['raw_file']), str(paths['processed_file'])),
            daemon=True
        ).start()
    else:
        print(f"Video recording failed or empty: {paths['raw_file']}")


# ============================================================================
# Hardware-Accelerated Transcoding Functions
# ============================================================================

def transcode_video(input_file, output_file, delete_raw=True):
    """
    Transcode video using hardware-accelerated h264_v4l2m2m codec (Raspberry Pi)

    Args:
        input_file: Path to raw input file
        output_file: Path for compressed output
        delete_raw: Whether to delete raw file after successful transcode

    Returns:
        Tuple of (success: bool, message: str)
    """
    global transcode_process, transcode_progress

    with transcode_lock:
        if transcode_process and transcode_process.poll() is None:
            return False, "Transcoding already in progress"

        transcode_progress = {
            'is_processing': True,
            'current_file': Path(input_file).name,
            'progress_percent': 0,
            'status': 'starting'
        }

    try:
        # Get input file duration for progress calculation
        duration = get_video_duration(input_file)

        # Build ffmpeg transcode command with h264_v4l2m2m (RPi hardware encoder)
        cmd = [
            'ffmpeg',
            '-i', input_file,
            '-c:v', 'h264_v4l2m2m',    # Hardware-accelerated H.264 encoder
            '-b:v', DEFAULT_VIDEO_BITRATE,
            '-c:a', 'copy',             # Copy audio without re-encoding
            '-y',                       # Overwrite output
            output_file
        ]

        print(f"Starting transcode: {input_file} -> {output_file}")

        with transcode_lock:
            transcode_progress['status'] = 'transcoding'

        transcode_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )

        # Monitor progress from stderr in a separate thread
        if duration:
            progress_thread = threading.Thread(
                target=_read_transcode_progress,
                args=(transcode_process.stderr, duration),
                daemon=True
            )
            progress_thread.start()

        # Wait for completion
        return_code = transcode_process.wait()

        if return_code == 0 and Path(output_file).exists():
            with transcode_lock:
                transcode_progress['progress_percent'] = 100
                transcode_progress['status'] = 'verifying'

            # Verify output file is valid
            output_duration = get_video_duration(output_file)
            if output_duration and duration:
                duration_diff = abs(output_duration - duration)
                if duration_diff > 5:  # More than 5 seconds difference
                    with transcode_lock:
                        transcode_progress['status'] = 'error'
                        transcode_progress['is_processing'] = False
                    return False, f"Output duration mismatch: expected {duration}s, got {output_duration}s"

            # Delete raw file if requested and transcode successful
            if delete_raw:
                try:
                    Path(input_file).unlink()
                    print(f"Deleted raw file: {input_file}")
                except Exception as e:
                    print(f"Warning: Could not delete raw file: {e}")

            with transcode_lock:
                transcode_progress['status'] = 'completed'
                transcode_progress['is_processing'] = False

            return True, f"Transcode completed: {output_file}"
        else:
            with transcode_lock:
                transcode_progress['status'] = 'error'
                transcode_progress['is_processing'] = False
            return False, f"Transcode failed with return code {return_code}"

    except Exception as e:
        with transcode_lock:
            transcode_progress['status'] = 'error'
            transcode_progress['is_processing'] = False
        return False, f"Transcode error: {e}"

    finally:
        with transcode_lock:
            transcode_process = None


def _read_transcode_progress(stderr, total_duration):
    """
    Read ffmpeg stderr and update progress
    """
    global transcode_progress

    time_pattern = re.compile(r'time=(\d+):(\d+):(\d+)\.(\d+)')

    try:
        for line in stderr:
            match = time_pattern.search(line)
            if match:
                hours, mins, secs, _ = map(int, match.groups())
                current_time = hours * 3600 + mins * 60 + secs
                progress = min(99, int((current_time / total_duration) * 100))

                with transcode_lock:
                    transcode_progress['progress_percent'] = progress
    except:
        pass  # Ignore read errors


def get_video_duration(file_path):
    """
    Get video duration using ffprobe

    Args:
        file_path: Path to video file

    Returns:
        Duration in seconds or None
    """
    try:
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-show_entries', 'format=duration',
            '-of', 'csv=p=0',
            file_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except Exception as e:
        print(f"Error getting video duration: {e}")
    return None


def get_transcode_status():
    """
    Get current transcoding status

    Returns:
        Dictionary with transcode status
    """
    global transcode_progress

    with transcode_lock:
        return transcode_progress.copy()


def cancel_transcode():
    """Cancel ongoing transcoding"""
    global transcode_process, transcode_progress

    with transcode_lock:
        if transcode_process and transcode_process.poll() is None:
            transcode_process.terminate()
            try:
                transcode_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                transcode_process.kill()

            transcode_progress['status'] = 'cancelled'
            transcode_progress['is_processing'] = False
            return True
    return False


# ============================================================================
# File Management Functions
# ============================================================================

def list_video_files():
    """
    List all video files in the storage directory

    Returns:
        Dictionary with raw and processed file lists
    """
    config = get_camera_config()
    storage_path = Path(config['storage_path'])

    raw_files = []
    processed_files = []

    raw_dir = storage_path / 'raw'
    processed_dir = storage_path / 'processed'

    if raw_dir.exists():
        for f in sorted(raw_dir.glob('*.mp4'), reverse=True):
            stat = f.stat()
            raw_files.append({
                'name': f.name,
                'path': str(f),
                'size_mb': round(stat.st_size / (1024 * 1024), 2),
                'modified': datetime.fromtimestamp(stat.st_mtime).isoformat()
            })

    if processed_dir.exists():
        for f in sorted(processed_dir.glob('*.mp4'), reverse=True):
            stat = f.stat()
            processed_files.append({
                'name': f.name,
                'path': str(f),
                'size_mb': round(stat.st_size / (1024 * 1024), 2),
                'modified': datetime.fromtimestamp(stat.st_mtime).isoformat()
            })

    return {
        'raw': raw_files,
        'processed': processed_files
    }


def get_storage_info():
    """
    Get storage disk space information

    Returns:
        Dictionary with disk space info
    """
    config = get_camera_config()
    storage_path = config['storage_path']

    try:
        valid, msg = validate_storage_path(storage_path)

        if not valid:
            return {
                'mounted': False,
                'message': msg,
                'path': storage_path
            }

        stat = shutil.disk_usage(storage_path)

        total_gb = stat.total / (1024 ** 3)
        used_gb = stat.used / (1024 ** 3)
        free_gb = stat.free / (1024 ** 3)

        # Estimate recording hours remaining (~2GB/hour)
        hours_remaining = (stat.free / (1024 ** 2)) / VIDEO_MB_PER_HOUR

        return {
            'mounted': True,
            'path': storage_path,
            'total_gb': round(total_gb, 2),
            'used_gb': round(used_gb, 2),
            'free_gb': round(free_gb, 2),
            'percent_used': round((stat.used / stat.total) * 100, 1),
            'hours_remaining': round(hours_remaining, 1)
        }
    except Exception as e:
        return {
            'mounted': False,
            'path': storage_path,
            'message': str(e)
        }


# ============================================================================
# Test Functions
# ============================================================================

if __name__ == '__main__':
    print("Video Recorder Module Test")
    print("=" * 50)

    # Test storage validation
    print("\nTesting storage validation...")
    valid, msg = validate_storage_path('/tmp')
    print(f"  /tmp: {valid} - {msg}")

    # Test camera config
    print("\nCurrent camera config:")
    config = get_camera_config()
    for key, value in config.items():
        if key == 'camera_password' and value:
            print(f"  {key}: ****")
        else:
            print(f"  {key}: {value}")

    # Test storage info
    print("\nStorage info:")
    info = get_storage_info()
    for key, value in info.items():
        print(f"  {key}: {value}")

    # Test live stream info
    print("\nLive stream info:")
    stream_info = get_live_stream_info()
    for key, value in stream_info.items():
        print(f"  {key}: {value}")
