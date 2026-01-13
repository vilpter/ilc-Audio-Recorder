#!/usr/bin/env python3
"""
Audio Recorder Module
Handles FFmpeg-based dual-mono audio capture from Behringer UCA202
"""

import subprocess
import threading
import os
import shutil
from datetime import datetime
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AudioRecorder:
    """Manages audio recording from ALSA device hw:1 (Behringer UCA202)"""

    # Constants
    DEFAULT_MAX_DURATION = 14400  # 4 hours in seconds
    SAMPLE_RATE = 48000
    BITS_PER_SAMPLE = 16
    CHANNELS = 2
    BYTES_PER_SAMPLE = 2  # 16-bit = 2 bytes
    SAFETY_MARGIN = 1.1  # 10% safety margin for disk space

    def __init__(self, recordings_dir="/home/pi/recordings"):
        """
        Initialize the audio recorder

        Args:
            recordings_dir: Directory to save recordings (default: /home/pi/recordings)
        """
        self.recordings_dir = Path(recordings_dir)
        self.recordings_dir.mkdir(parents=True, exist_ok=True)

        self.process = None
        self.is_recording = False
        self.current_session = None
        self._lock = threading.Lock()

    def estimate_file_size(self, duration_seconds):
        """
        Estimate the total size of both WAV files for a given duration

        Args:
            duration_seconds: Recording duration in seconds

        Returns:
            Estimated size in bytes
        """
        # Formula: duration * sample_rate * bytes_per_sample * channels * safety_margin
        size_per_channel = (
            duration_seconds *
            self.SAMPLE_RATE *
            self.BYTES_PER_SAMPLE *
            self.SAFETY_MARGIN
        )
        # Two files (source_A and source_B)
        total_size = size_per_channel * self.CHANNELS
        return int(total_size)

    def check_disk_space(self, required_bytes):
        """
        Check if sufficient disk space is available

        Args:
            required_bytes: Required space in bytes

        Returns:
            tuple: (bool, available_bytes, required_bytes)
        """
        stat = shutil.disk_usage(self.recordings_dir)
        available = stat.free

        # Require 2x the estimated size for safety
        required_with_margin = required_bytes * 2

        return (available >= required_with_margin, available, required_with_margin)

    def preflight_check(self, duration_seconds, allow_long_recording=False):
        """
        Perform pre-flight checks before starting recording

        Args:
            duration_seconds: Requested recording duration
            allow_long_recording: Override the 4-hour default limit

        Returns:
            tuple: (success: bool, error_message: str or None)
        """
        # Check duration limit
        if not allow_long_recording and duration_seconds > self.DEFAULT_MAX_DURATION:
            return (
                False,
                f"Recording duration ({duration_seconds}s) exceeds 4-hour limit. "
                f"Enable 'Allow longer recording' to override."
            )

        # Check disk space
        estimated_size = self.estimate_file_size(duration_seconds)
        has_space, available, required = self.check_disk_space(estimated_size)

        if not has_space:
            return (
                False,
                f"Insufficient disk space. Available: {self._format_bytes(available)}, "
                f"Required: {self._format_bytes(required)} "
                f"(estimated {self._format_bytes(estimated_size)} + 100% safety margin)"
            )

        return (True, None)

    def start_recording(self, duration_seconds, name_prefix="recording", allow_long_recording=False):
        """
        Start a new recording session

        Args:
            duration_seconds: Duration of recording in seconds
            name_prefix: Prefix for the filename (default: "recording")
            allow_long_recording: Override the 4-hour limit

        Returns:
            tuple: (success: bool, message: str, session_info: dict or None)
        """
        with self._lock:
            # Check if already recording
            if self.is_recording:
                return (False, "Recording already in progress", None)

            # Pre-flight checks
            success, error_msg = self.preflight_check(duration_seconds, allow_long_recording)
            if not success:
                logger.error(f"Pre-flight check failed: {error_msg}")
                return (False, error_msg, None)

            # Generate filenames with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            source_a_file = self.recordings_dir / f"source_A_{timestamp}.wav"
            source_b_file = self.recordings_dir / f"source_B_{timestamp}.wav"

            # Build FFmpeg command
            cmd = [
                'ffmpeg',
                '-f', 'alsa',
                '-i', 'hw:1',  # Behringer UCA202
                '-t', str(duration_seconds),
                '-filter_complex', '[0:a]channelsplit=channel_layout=stereo[left][right]',
                '-map', '[left]',
                '-acodec', 'pcm_s16le',
                '-ar', str(self.SAMPLE_RATE),
                str(source_a_file),
                '-map', '[right]',
                '-acodec', 'pcm_s16le',
                '-ar', str(self.SAMPLE_RATE),
                str(source_b_file)
            ]

            try:
                # Start FFmpeg process
                self.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )

                self.is_recording = True
                self.current_session = {
                    'start_time': datetime.now().isoformat(),
                    'duration': duration_seconds,
                    'source_a': str(source_a_file),
                    'source_b': str(source_b_file),
                    'name_prefix': name_prefix,
                    'pid': self.process.pid
                }

                # Start monitoring thread
                monitor_thread = threading.Thread(
                    target=self._monitor_recording,
                    daemon=True
                )
                monitor_thread.start()

                logger.info(
                    f"Recording started: {duration_seconds}s, "
                    f"PID: {self.process.pid}, "
                    f"Files: {source_a_file.name}, {source_b_file.name}"
                )

                return (True, "Recording started successfully", self.current_session)

            except FileNotFoundError:
                logger.error("FFmpeg not found. Is it installed?")
                return (False, "FFmpeg not found on system", None)
            except Exception as e:
                logger.error(f"Failed to start recording: {e}")
                return (False, f"Error starting recording: {str(e)}", None)

    def stop_recording(self):
        """
        Stop the current recording session

        Returns:
            tuple: (success: bool, message: str)
        """
        with self._lock:
            if not self.is_recording or self.process is None:
                return (False, "No active recording to stop")

            try:
                # Terminate FFmpeg gracefully
                self.process.terminate()
                self.process.wait(timeout=10)

                logger.info(f"Recording stopped: PID {self.process.pid}")

                self.is_recording = False
                session_info = self.current_session
                self.current_session = None
                self.process = None

                return (True, f"Recording stopped successfully")

            except subprocess.TimeoutExpired:
                # Force kill if graceful termination fails
                self.process.kill()
                self.is_recording = False
                self.current_session = None
                logger.warning("Recording process killed (timeout)")
                return (True, "Recording forcefully stopped")
            except Exception as e:
                logger.error(f"Error stopping recording: {e}")
                return (False, f"Error stopping recording: {str(e)}")

    def get_status(self):
        """
        Get current recording status

        Returns:
            dict: Status information
        """
        with self._lock:
            return {
                'is_recording': self.is_recording,
                'current_session': self.current_session,
                'recordings_dir': str(self.recordings_dir)
            }

    def _monitor_recording(self):
        """Internal method to monitor recording process completion"""
        if self.process:
            returncode = self.process.wait()

            with self._lock:
                self.is_recording = False

                if returncode == 0:
                    logger.info("Recording completed successfully")
                else:
                    stderr_output = self.process.stderr.read() if self.process.stderr else ""
                    logger.error(f"Recording ended with error code {returncode}: {stderr_output}")

                self.current_session = None
                self.process = None

    def _format_bytes(self, bytes_val):
        """Format bytes to human-readable string"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_val < 1024.0:
                return f"{bytes_val:.2f} {unit}"
            bytes_val /= 1024.0
        return f"{bytes_val:.2f} PB"

    def list_recordings(self):
        """
        List all recordings in the recordings directory

        Returns:
            list: List of recording file info dictionaries
        """
        recordings = []

        try:
            for file_path in sorted(self.recordings_dir.glob("*.wav"), key=lambda x: x.stat().st_mtime, reverse=True):
                stat = file_path.stat()
                recordings.append({
                    'filename': file_path.name,
                    'path': str(file_path),
                    'size': stat.st_size,
                    'size_formatted': self._format_bytes(stat.st_size),
                    'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    'modified_formatted': datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                })
        except Exception as e:
            logger.error(f"Error listing recordings: {e}")

        return recordings

    def delete_recording(self, filename):
        """
        Delete a recording file

        Args:
            filename: Name of the file to delete

        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            file_path = self.recordings_dir / filename

            # Security check: ensure file is within recordings directory
            if not file_path.resolve().parent == self.recordings_dir.resolve():
                return (False, "Invalid file path")

            if not file_path.exists():
                return (False, "File not found")

            file_path.unlink()
            logger.info(f"Deleted recording: {filename}")
            return (True, f"Deleted {filename}")

        except Exception as e:
            logger.error(f"Error deleting {filename}: {e}")
            return (False, f"Error deleting file: {str(e)}")


# Singleton instance
_recorder_instance = None

def get_recorder(recordings_dir="/home/pi/recordings"):
    """Get or create the singleton recorder instance"""
    global _recorder_instance
    if _recorder_instance is None:
        _recorder_instance = AudioRecorder(recordings_dir)
    return _recorder_instance
