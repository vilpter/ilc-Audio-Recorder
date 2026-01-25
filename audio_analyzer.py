"""
Audio Analysis Module

Analyzes WAV and MP3 files to determine:
- Percentage of non-silent audio
- Mean and max dB levels per channel
- Timestamp where max dB occurs per channel

Uses FFmpeg for analysis via subprocess calls.
"""

import subprocess
import json
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class ChannelStats:
    """Statistics for a single audio channel"""
    channel_number: int
    non_silent_percentage: float
    mean_db: float
    max_db: float
    max_db_time: float  # Time in seconds where max_db occurs
    total_duration: float


@dataclass
class AudioAnalysisResult:
    """Complete analysis results for an audio file"""
    filename: str
    total_duration: float
    channels: List[ChannelStats]
    overall_non_silent_percentage: float
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'filename': self.filename,
            'total_duration': self.total_duration,
            'channels': [
                {
                    'channel': c.channel_number,
                    'non_silent_percentage': c.non_silent_percentage,
                    'mean_db': c.mean_db,
                    'max_db': c.max_db,
                    'max_db_time': c.max_db_time,
                    'total_duration': c.total_duration
                }
                for c in self.channels
            ],
            'overall_non_silent_percentage': self.overall_non_silent_percentage
        }


class AudioAnalyzer:
    """
    Analyzes audio files using FFmpeg to detect silence and measure dB levels.
    """
    
    def __init__(self, silence_threshold_db: float = -60.0, 
                 silence_duration_sec: float = 2.0):
        """
        Initialize the audio analyzer.
        
        Args:
            silence_threshold_db: dB level below which audio is considered silent (default: -60.0)
            silence_duration_sec: Minimum duration in seconds for sustained silence (default: 2.0)
        """
        self.silence_threshold_db = silence_threshold_db
        self.silence_duration_sec = silence_duration_sec
    
    def analyze_file(self, filepath: str) -> AudioAnalysisResult:
        """
        Analyze an audio file for silence and dB levels.
        
        Args:
            filepath: Path to WAV or MP3 file
            
        Returns:
            AudioAnalysisResult with complete statistics
            
        Raises:
            FileNotFoundError: If file doesn't exist
            subprocess.CalledProcessError: If FFmpeg fails
            ValueError: If file format is not supported
        """
        # Get basic file info
        duration, num_channels = self._get_file_info(filepath)
        
        # Analyze each channel independently
        channel_stats = []
        for channel_num in range(num_channels):
            stats = self._analyze_channel(filepath, channel_num, duration)
            channel_stats.append(stats)
        
        # Calculate overall non-silent percentage (aggregate across all channels)
        # A section is non-silent if ANY channel is non-silent
        overall_non_silent_pct = self._calculate_overall_non_silent_percentage(
            filepath, duration, num_channels
        )
        
        return AudioAnalysisResult(
            filename=filepath,
            total_duration=duration,
            channels=channel_stats,
            overall_non_silent_percentage=overall_non_silent_pct
        )
    
    def _get_file_info(self, filepath: str) -> Tuple[float, int]:
        """
        Get duration and number of channels from audio file.
        
        Returns:
            Tuple of (duration_seconds, num_channels)
        """
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'stream=duration,channels',
            '-of', 'json',
            filepath
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        
        if not data.get('streams'):
            raise ValueError(f"No audio streams found in {filepath}")
        
        stream = data['streams'][0]
        duration = float(stream['duration'])
        channels = int(stream['channels'])
        
        return duration, channels
    
    def _analyze_channel(self, filepath: str, channel_num: int, 
                        duration: float) -> ChannelStats:
        """
        Analyze a single channel for silence and dB levels.
        
        Args:
            filepath: Path to audio file
            channel_num: Channel number (0-indexed)
            duration: Total duration of file in seconds
            
        Returns:
            ChannelStats for the channel
        """
        # Detect silence periods for this channel
        silence_periods = self._detect_silence(filepath, channel_num)
        
        # Calculate non-silent percentage
        total_silence = sum(end - start for start, end in silence_periods)
        non_silent_duration = duration - total_silence
        non_silent_pct = (non_silent_duration / duration) * 100.0 if duration > 0 else 0.0
        
        # Get dB statistics for non-silent portions
        mean_db, max_db, max_db_time = self._get_db_stats(
            filepath, channel_num, silence_periods, duration
        )
        
        return ChannelStats(
            channel_number=channel_num,
            non_silent_percentage=non_silent_pct,
            mean_db=mean_db,
            max_db=max_db,
            max_db_time=max_db_time,
            total_duration=duration
        )
    
    def _detect_silence(self, filepath: str, channel_num: int) -> List[Tuple[float, float]]:
        """
        Detect silence periods in a specific channel.
        
        Args:
            filepath: Path to audio file
            channel_num: Channel number (0-indexed)
            
        Returns:
            List of (start_time, end_time) tuples for silent periods
        """
        # Extract single channel and detect silence
        cmd = [
            'ffmpeg',
            '-i', filepath,
            '-af', f'pan=mono|c0=c{channel_num},'
                   f'silencedetect=noise={self.silence_threshold_db}dB:'
                   f'd={self.silence_duration_sec}',
            '-f', 'null',
            '-'
        ]
        
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        
        # Parse silence detection output from stderr
        silence_periods = []
        silence_start = None
        
        for line in result.stdout.split('\n'):
            if 'silence_start' in line:
                match = re.search(r'silence_start: ([\d.]+)', line)
                if match:
                    silence_start = float(match.group(1))
            elif 'silence_end' in line and silence_start is not None:
                match = re.search(r'silence_end: ([\d.]+)', line)
                if match:
                    silence_end = float(match.group(1))
                    silence_periods.append((silence_start, silence_end))
                    silence_start = None
        
        return silence_periods
    
    def _get_db_stats(self, filepath: str, channel_num: int,
                     silence_periods: List[Tuple[float, float]],
                     duration: float) -> Tuple[float, float, float]:
        """
        Calculate mean and max dB levels for non-silent portions.
        
        Args:
            filepath: Path to audio file
            channel_num: Channel number (0-indexed)
            silence_periods: List of silent time periods to exclude
            duration: Total duration
            
        Returns:
            Tuple of (mean_db, max_db, max_db_time)
        """
        # Build filter to exclude silence periods and get stats
        # We'll use astats filter to get RMS (mean) and peak (max) levels
        cmd = [
            'ffmpeg',
            '-i', filepath,
            '-af', f'pan=mono|c0=c{channel_num},astats=metadata=1:reset=1,ametadata=print:file=-',
            '-f', 'null',
            '-'
        ]
        
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        
        # Parse astats output to collect dB values over time
        rms_values = []
        peak_values = []
        max_peak = -float('inf')
        max_peak_time = 0.0
        current_time = 0.0
        
        for line in result.stdout.split('\n'):
            # Extract timestamp (pts_time)
            pts_match = re.search(r'pts_time:([\d.]+)', line)
            if pts_match:
                current_time = float(pts_match.group(1))
            
            # Extract RMS level (mean)
            rms_match = re.search(r'lavfi\.astats\.Overall\.RMS_level=([-\d.]+)', line)
            if rms_match:
                rms_db = float(rms_match.group(1))
                # Check if this time is in a non-silent period
                if not self._is_in_silence(current_time, silence_periods):
                    rms_values.append(rms_db)
            
            # Extract Peak level (max)
            peak_match = re.search(r'lavfi\.astats\.Overall\.Peak_level=([-\d.]+)', line)
            if peak_match:
                peak_db = float(peak_match.group(1))
                # Check if this time is in a non-silent period
                if not self._is_in_silence(current_time, silence_periods):
                    peak_values.append(peak_db)
                    if peak_db > max_peak:
                        max_peak = peak_db
                        max_peak_time = current_time
        
        # Calculate mean RMS (which represents mean dB)
        mean_db = sum(rms_values) / len(rms_values) if rms_values else -float('inf')
        max_db = max_peak if peak_values else -float('inf')
        
        return mean_db, max_db, max_peak_time
    
    def _is_in_silence(self, time: float, silence_periods: List[Tuple[float, float]]) -> bool:
        """Check if a given time falls within any silence period"""
        for start, end in silence_periods:
            if start <= time <= end:
                return True
        return False
    
    def _calculate_overall_non_silent_percentage(self, filepath: str, 
                                                 duration: float,
                                                 num_channels: int) -> float:
        """
        Calculate overall non-silent percentage considering all channels together.
        A moment is non-silent if ANY channel is non-silent.
        
        Args:
            filepath: Path to audio file
            duration: Total duration
            num_channels: Number of channels
            
        Returns:
            Overall non-silent percentage
        """
        # Run silencedetect on the full stereo/multi-channel file
        # This will detect silence only when ALL channels are silent
        cmd = [
            'ffmpeg',
            '-i', filepath,
            '-af', f'silencedetect=noise={self.silence_threshold_db}dB:'
                   f'd={self.silence_duration_sec}',
            '-f', 'null',
            '-'
        ]
        
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        
        # Parse silence periods
        silence_periods = []
        silence_start = None
        
        for line in result.stdout.split('\n'):
            if 'silence_start' in line:
                match = re.search(r'silence_start: ([\d.]+)', line)
                if match:
                    silence_start = float(match.group(1))
            elif 'silence_end' in line and silence_start is not None:
                match = re.search(r'silence_end: ([\d.]+)', line)
                if match:
                    silence_end = float(match.group(1))
                    silence_periods.append((silence_start, silence_end))
                    silence_start = None
        
        # Calculate non-silent percentage
        total_silence = sum(end - start for start, end in silence_periods)
        non_silent_duration = duration - total_silence
        non_silent_pct = (non_silent_duration / duration) * 100.0 if duration > 0 else 0.0
        
        return non_silent_pct


def analyze_audio_file(filepath: str, 
                      silence_threshold_db: float = -60.0,
                      silence_duration_sec: float = 2.0) -> Dict:
    """
    Convenience function to analyze an audio file.
    
    Args:
        filepath: Path to WAV or MP3 file
        silence_threshold_db: dB threshold for silence (default: -60.0)
        silence_duration_sec: Minimum silence duration in seconds (default: 2.0)
        
    Returns:
        Dictionary containing analysis results
        
    Example:
        >>> result = analyze_audio_file('recording.wav', silence_threshold_db=-50.0)
        >>> print(f"Non-silent: {result['overall_non_silent_percentage']:.1f}%")
        >>> for channel in result['channels']:
        ...     print(f"Channel {channel['channel']}: Max {channel['max_db']:.1f} dB "
        ...           f"at {channel['max_db_time']:.1f}s")
    """
    analyzer = AudioAnalyzer(silence_threshold_db, silence_duration_sec)
    result = analyzer.analyze_file(filepath)
    return result.to_dict()


if __name__ == '__main__':
    # Example usage
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python audio_analyzer.py <audio_file> [silence_threshold_db] [silence_duration_sec]")
        print("\nExample: python audio_analyzer.py recording.wav -50 1.5")
        sys.exit(1)
    
    filepath = sys.argv[1]
    silence_threshold = float(sys.argv[2]) if len(sys.argv) > 2 else -60.0
    silence_duration = float(sys.argv[3]) if len(sys.argv) > 3 else 2.0
    
    print(f"Analyzing: {filepath}")
    print(f"Silence threshold: {silence_threshold} dB")
    print(f"Silence duration: {silence_duration} seconds")
    print("-" * 60)
    
    result = analyze_audio_file(filepath, silence_threshold, silence_duration)
    
    print(f"\nFile: {result['filename']}")
    print(f"Duration: {result['total_duration']:.2f} seconds")
    print(f"Overall non-silent: {result['overall_non_silent_percentage']:.1f}%")
    print("\nPer-Channel Analysis:")
    print("-" * 60)
    
    for channel in result['channels']:
        print(f"\nChannel {channel['channel']}:")
        print(f"  Non-silent: {channel['non_silent_percentage']:.1f}%")
        print(f"  Mean dB: {channel['mean_db']:.1f}")
        print(f"  Max dB: {channel['max_db']:.1f} (at {channel['max_db_time']:.2f}s)")
