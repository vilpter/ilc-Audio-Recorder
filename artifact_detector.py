"""
Audio Artifact Detection Module

Detects clipping (digital and analog flat-top) and discontinuities
in 16-bit PCM WAV files using FFmpeg piped to NumPy.

Designed for Raspberry Pi: processes audio in chunks to minimize memory usage.
Peak memory ~1 MB regardless of file duration.

Detection types:
  - Digital clipping: samples at/near 16-bit max (±32760+)
  - Upstream/analog clipping (flat-top): runs of consecutive near-identical
    samples in high-amplitude regions (catches clipping at any level)
  - Discontinuities: sudden jumps flagged via adaptive statistical threshold
"""

import subprocess
import json
import logging
from dataclasses import dataclass, field
from typing import List, Optional

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

logger = logging.getLogger(__name__)

# --- Detection Thresholds ---
# Digital clipping: samples at or near 16-bit signed max
DIGITAL_CLIP_THRESHOLD = 32760       # |sample| >= this is "clipping" (within 8 of max)
SAMPLE_MAX_16BIT = 32768             # absolute max for signed 16-bit

# Flat-top detection (upstream/analog clipping)
FLATLINE_MIN_RUN = 5                 # consecutive near-identical samples to flag
FLATLINE_AMPLITUDE_FLOOR = 0.7       # only check above 70% of max amplitude range
FLATLINE_TOLERANCE = 2               # samples within ±2 count as "same value"

# Discontinuity detection
DISCONTINUITY_STD_MULTIPLIER = 6.0   # flag diffs > 6 std devs above local mean
DISCONTINUITY_MIN_MAGNITUDE = 5000   # absolute minimum diff to consider

# Chunk processing
CHUNK_DURATION_SECONDS = 10          # process in 10-second windows
BOUNDARY_TAIL_SAMPLES = 50           # samples carried between chunks

# Quality score thresholds
QUALITY_YELLOW_CLIPS = 5             # total clips >= this = yellow
QUALITY_RED_CLIPS = 50               # total clips >= this = red
QUALITY_YELLOW_DISCONTINUITIES = 1   # discontinuities >= this = yellow
QUALITY_RED_DISCONTINUITIES = 5      # discontinuities >= this = red

# Event storage cap (prevents unbounded JSON growth for heavily damaged files)
MAX_STORED_EVENTS = 100

# Current artifact detection schema version (bump when algorithm changes)
ARTIFACT_VERSION = 1


@dataclass
class ClippingEvent:
    timestamp: float        # seconds into recording
    duration_samples: int   # how many consecutive clipped samples
    peak_value: int         # the sample value (e.g., 32767 or -32768)
    event_type: str         # 'digital' or 'flatline'


@dataclass
class DiscontinuityEvent:
    timestamp: float        # seconds into recording
    magnitude: int          # size of the jump in sample values
    direction: str          # 'positive' or 'negative'


@dataclass
class ArtifactDetectionResult:
    digital_clip_count: int = 0
    flatline_clip_count: int = 0
    discontinuity_count: int = 0
    quality_score: str = 'green'
    clipping_events: List[ClippingEvent] = field(default_factory=list)
    discontinuity_events: List[DiscontinuityEvent] = field(default_factory=list)
    error_message: Optional[str] = None

    def to_artifact_json(self) -> str:
        """Serialize events to JSON string for database storage."""
        clip_events = self.clipping_events
        disc_events = self.discontinuity_events
        truncated = False

        # Cap stored events to prevent unbounded JSON
        if len(clip_events) + len(disc_events) > MAX_STORED_EVENTS:
            truncated = True
            half = MAX_STORED_EVENTS // 2
            if len(clip_events) > half:
                clip_events = clip_events[:half // 2] + clip_events[-(half // 2):]
            if len(disc_events) > half:
                disc_events = disc_events[:half // 2] + disc_events[-(half // 2):]

        return json.dumps({
            'version': ARTIFACT_VERSION,
            'clipping_events': [
                {'t': round(e.timestamp, 3), 'dur': e.duration_samples,
                 'val': e.peak_value, 'type': e.event_type}
                for e in clip_events
            ],
            'discontinuity_events': [
                {'t': round(e.timestamp, 3), 'mag': e.magnitude, 'dir': e.direction}
                for e in disc_events
            ],
            'truncated': truncated
        })

    @classmethod
    def error(cls, message: str) -> 'ArtifactDetectionResult':
        return cls(error_message=message)


class ArtifactDetector:
    """
    Detects audio artifacts by piping FFmpeg PCM output to NumPy.
    Processes in chunks to maintain low memory footprint on Raspberry Pi.
    """

    def __init__(self, sample_rate: int = 48000):
        self.sample_rate = sample_rate
        self.chunk_samples = sample_rate * CHUNK_DURATION_SECONDS
        self.bytes_per_sample = 2  # 16-bit

    def analyze_file(self, filepath: str) -> ArtifactDetectionResult:
        """
        Analyze a WAV file for clipping and discontinuities.

        Args:
            filepath: Path to a mono 16-bit WAV file

        Returns:
            ArtifactDetectionResult with counts, quality score, and event details
        """
        if not NUMPY_AVAILABLE:
            return ArtifactDetectionResult.error("NumPy not installed")

        all_clip_events: List[ClippingEvent] = []
        all_disc_events: List[DiscontinuityEvent] = []
        tail_buffer = None
        chunk_offset_samples = 0

        try:
            proc = self._start_ffmpeg_pipe(filepath)
        except Exception as e:
            return ArtifactDetectionResult.error(f"FFmpeg failed to start: {e}")

        try:
            bytes_per_chunk = self.chunk_samples * self.bytes_per_sample

            while True:
                raw_data = proc.stdout.read(bytes_per_chunk)
                if not raw_data:
                    break

                samples = np.frombuffer(raw_data, dtype=np.int16)
                if len(samples) == 0:
                    break

                # Prepend tail buffer for boundary detection
                if tail_buffer is not None:
                    analysis_samples = np.concatenate([tail_buffer, samples])
                    analysis_offset = chunk_offset_samples - len(tail_buffer)
                else:
                    analysis_samples = samples
                    analysis_offset = chunk_offset_samples

                # Detect artifacts in this chunk
                clip_events = self._detect_digital_clipping(
                    analysis_samples, analysis_offset)
                flatline_events = self._detect_flatline_clipping(
                    analysis_samples, analysis_offset)
                disc_events = self._detect_discontinuities(
                    analysis_samples, analysis_offset)

                all_clip_events.extend(clip_events)
                all_clip_events.extend(flatline_events)
                all_disc_events.extend(disc_events)

                # Save tail for next chunk's boundary check
                tail_buffer = samples[-BOUNDARY_TAIL_SAMPLES:].copy()
                chunk_offset_samples += len(samples)

        except Exception as e:
            logger.error(f"Error processing audio chunks: {e}")
            return ArtifactDetectionResult.error(f"Chunk processing error: {e}")
        finally:
            proc.stdout.close()
            proc.wait()

        # Separate counts by type
        digital_clips = [e for e in all_clip_events if e.event_type == 'digital']
        flatline_clips = [e for e in all_clip_events if e.event_type == 'flatline']

        # Calculate quality score
        quality = _calculate_quality_score(
            len(digital_clips), len(flatline_clips), len(all_disc_events))

        result = ArtifactDetectionResult(
            digital_clip_count=len(digital_clips),
            flatline_clip_count=len(flatline_clips),
            discontinuity_count=len(all_disc_events),
            quality_score=quality,
            clipping_events=all_clip_events,
            discontinuity_events=all_disc_events,
        )

        return result

    def _start_ffmpeg_pipe(self, filepath: str) -> subprocess.Popen:
        """Start FFmpeg decoding WAV to raw PCM via stdout pipe."""
        cmd = [
            'ffmpeg',
            '-i', filepath,
            '-f', 's16le',
            '-acodec', 'pcm_s16le',
            '-ar', str(self.sample_rate),
            '-ac', '1',
            'pipe:1'
        ]
        return subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL
        )

    def _detect_digital_clipping(self, samples: np.ndarray,
                                  offset_samples: int) -> List[ClippingEvent]:
        """
        Find samples at or near the 16-bit max/min.
        Groups consecutive clipped samples into single events.
        """
        clipped = np.abs(samples.astype(np.int32)) >= DIGITAL_CLIP_THRESHOLD
        return self._group_runs(samples, clipped, offset_samples, 'digital')

    def _detect_flatline_clipping(self, samples: np.ndarray,
                                   offset_samples: int) -> List[ClippingEvent]:
        """
        Find runs of consecutive near-identical samples in high-amplitude
        regions. Catches upstream/analog clipping at any level.
        """
        amplitude_floor = int(FLATLINE_AMPLITUDE_FLOOR * SAMPLE_MAX_16BIT)
        high_amplitude = np.abs(samples.astype(np.int32)) >= amplitude_floor

        if not np.any(high_amplitude):
            return []

        # Find where consecutive samples differ by more than tolerance
        diffs = np.abs(np.diff(samples.astype(np.int32)))
        is_flat = diffs <= FLATLINE_TOLERANCE

        # Both conditions: high amplitude AND flat (same as previous sample)
        # is_flat[i] means samples[i] and samples[i+1] are near-identical
        # high_amplitude[i] means samples[i] is in the high-amplitude zone
        # A flat run requires all samples in the run to be high-amplitude AND flat
        flat_and_high = is_flat & high_amplitude[:-1] & high_amplitude[1:]

        events = []
        i = 0
        n = len(flat_and_high)

        while i < n:
            if flat_and_high[i]:
                run_start = i
                while i < n and flat_and_high[i]:
                    i += 1
                run_length = i - run_start + 1  # +1 because diff is between pairs

                if run_length >= FLATLINE_MIN_RUN:
                    # Don't double-count events also caught by digital clipping
                    peak = int(np.max(np.abs(samples[run_start:run_start + run_length].astype(np.int32))))
                    if peak < DIGITAL_CLIP_THRESHOLD:
                        timestamp = float((offset_samples + run_start) / self.sample_rate)
                        events.append(ClippingEvent(
                            timestamp=timestamp,
                            duration_samples=run_length,
                            peak_value=int(samples[run_start]),
                            event_type='flatline'
                        ))
            else:
                i += 1

        return events

    def _detect_discontinuities(self, samples: np.ndarray,
                                 offset_samples: int) -> List[DiscontinuityEvent]:
        """
        Find sudden jumps using adaptive thresholding.
        Flags diffs exceeding N standard deviations above the local mean,
        with a minimum magnitude floor.
        """
        if len(samples) < 2:
            return []

        # Cast to int32 to prevent int16 overflow on diff
        diffs = np.diff(samples.astype(np.int32))
        abs_diffs = np.abs(diffs)

        local_mean = np.mean(abs_diffs)
        local_std = np.std(abs_diffs)

        threshold = max(
            local_mean + DISCONTINUITY_STD_MULTIPLIER * local_std,
            DISCONTINUITY_MIN_MAGNITUDE
        )

        anomalies = np.where(abs_diffs > threshold)[0]

        events = []
        for idx in anomalies:
            timestamp = float((offset_samples + idx) / self.sample_rate)
            diff_val = int(diffs[idx])
            events.append(DiscontinuityEvent(
                timestamp=timestamp,
                magnitude=int(abs(diff_val)),
                direction='positive' if diff_val > 0 else 'negative'
            ))

        return events

    def _group_runs(self, samples: np.ndarray, mask: np.ndarray,
                    offset_samples: int, event_type: str) -> List[ClippingEvent]:
        """
        Group consecutive True values in mask into single ClippingEvents.
        """
        if not np.any(mask):
            return []

        events = []
        # Find run starts and ends using diff on the boolean mask
        padded = np.concatenate([[False], mask, [False]])
        changes = np.diff(padded.astype(np.int8))
        starts = np.where(changes == 1)[0]
        ends = np.where(changes == -1)[0]

        for start, end in zip(starts, ends):
            run_length = int(end - start)
            peak = int(samples[start])  # representative value
            timestamp = float((offset_samples + start) / self.sample_rate)
            events.append(ClippingEvent(
                timestamp=timestamp,
                duration_samples=run_length,
                peak_value=peak,
                event_type=event_type
            ))

        return events


def _calculate_quality_score(digital_clips: int, flatline_clips: int,
                             discontinuities: int) -> str:
    """Determine traffic-light quality score from artifact counts."""
    total_clips = digital_clips + flatline_clips

    if total_clips >= QUALITY_RED_CLIPS or discontinuities >= QUALITY_RED_DISCONTINUITIES:
        return 'red'
    elif total_clips >= QUALITY_YELLOW_CLIPS or discontinuities >= QUALITY_YELLOW_DISCONTINUITIES:
        return 'yellow'
    else:
        return 'green'


def detect_artifacts(filepath: str, sample_rate: int = 48000) -> ArtifactDetectionResult:
    """
    Convenience function to detect audio artifacts in a file.

    Args:
        filepath: Path to a mono WAV file
        sample_rate: Sample rate in Hz (default: 48000)

    Returns:
        ArtifactDetectionResult with counts, quality score, and event details
    """
    detector = ArtifactDetector(sample_rate)
    return detector.analyze_file(filepath)


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage: python artifact_detector.py <audio_file>")
        print("\nAnalyzes a WAV file for clipping and discontinuities.")
        sys.exit(1)

    logging.basicConfig(level=logging.INFO)
    filepath = sys.argv[1]

    print(f"Analyzing: {filepath}")
    print("-" * 60)

    result = detect_artifacts(filepath)

    if result.error_message:
        print(f"Error: {result.error_message}")
        sys.exit(1)

    print(f"Quality Score: {result.quality_score.upper()}")
    print(f"Digital Clipping Events: {result.digital_clip_count}")
    print(f"Flat-top Clipping Events: {result.flatline_clip_count}")
    print(f"Discontinuities: {result.discontinuity_count}")

    if result.clipping_events:
        print(f"\nClipping Timestamps (first 20):")
        for e in result.clipping_events[:20]:
            mins = int(e.timestamp // 60)
            secs = e.timestamp % 60
            print(f"  {mins}m {secs:.1f}s - {e.event_type}, "
                  f"{e.duration_samples} samples, peak={e.peak_value}")

    if result.discontinuity_events:
        print(f"\nDiscontinuity Timestamps (first 20):")
        for e in result.discontinuity_events[:20]:
            mins = int(e.timestamp // 60)
            secs = e.timestamp % 60
            print(f"  {mins}m {secs:.1f}s - magnitude={e.magnitude}, "
                  f"direction={e.direction}")

    print(f"\nJSON artifact details ({len(result.to_artifact_json())} bytes)")
