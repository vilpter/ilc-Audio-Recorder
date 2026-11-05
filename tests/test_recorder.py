"""Recording post-processing: FFmpeg log, completion checks, analysis scheduling."""
import logging
import threading
import time

import pytest

import recorder


class FakeProcess:
    def __init__(self, stderr_lines=(), returncode=0):
        self.stderr = iter(stderr_lines)
        self.returncode = returncode

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        return self.returncode


@pytest.fixture
def ffmpeg_log(tmp_path, monkeypatch):
    path = tmp_path / 'ffmpeg.log'
    monkeypatch.setattr(recorder, 'FFMPEG_LOG_PATH', path)
    return path


def _paths(tmp_path, seconds=0):
    paths = {'timestamp': '2026_Jan_01_10:00',
             'source_a': tmp_path / 'a.wav', 'source_b': tmp_path / 'b.wav'}
    size = seconds * recorder.SAMPLE_RATE * recorder.BYTES_PER_SAMPLE
    for key in ('source_a', 'source_b'):
        paths[key].write_bytes(b'RIFF' + b'\0' * (40 + size))  # 44-byte WAV header + audio
    return paths


def test_ffmpeg_progress_lines_are_throttled(ffmpeg_log, tmp_path):
    lines = ['Input #0, alsa\n'] + [f'size=  {i}KiB time=00:00:{i:02d}.00 bitrate=768kbits/s\n' for i in range(40)] \
        + ['Exiting normally, received signal 15.\n']
    recorder._log_ffmpeg_output(FakeProcess(lines), _paths(tmp_path), 'job')
    text = ffmpeg_log.read_text()
    progress = [l for l in text.splitlines() if 'size=' in l]
    assert len(progress) == 2                      # first one, and the last before exit
    assert 'time=00:00:39.00' in progress[-1]
    assert 'Input #0' in text and 'Exiting normally' in text
    assert text.rstrip().endswith('Return code: 0')


def test_ffmpeg_log_rotates(ffmpeg_log, tmp_path, monkeypatch):
    monkeypatch.setattr(recorder, 'FFMPEG_LOG_MAX_BYTES', 100)
    ffmpeg_log.write_text('x' * 200)
    recorder._log_ffmpeg_output(FakeProcess(['hello\n']), _paths(tmp_path), 'job')
    assert ffmpeg_log.with_name('ffmpeg.log.1').read_text() == 'x' * 200
    assert 'x' * 200 not in ffmpeg_log.read_text()


@pytest.fixture
def no_followup(monkeypatch):
    """Run _monitor_process without the delayed analysis and catch-up scan."""
    started = []
    monkeypatch.setattr(recorder, '_log_ffmpeg_output', lambda *a: None)
    monkeypatch.setattr(threading, 'Timer', lambda *a, **k: type('T', (), {'start': lambda s: started.append(a)})())
    monkeypatch.setattr(recorder, 'analyze_unanalyzed_recordings', lambda **k: None)
    return started


def test_no_size_warning_when_stopped_early(tmp_path, monkeypatch, caplog, no_followup):
    monkeypatch.setattr(recorder, '_stop_requested', True)
    paths = _paths(tmp_path, seconds=0)  # stopped right away: tiny files are expected
    with caplog.at_level(logging.INFO, logger='recorder'):
        recorder._monitor_process(FakeProcess(returncode=255), paths, 3600)
    assert 'stopped by user' in caplog.text
    assert 'smaller than expected' not in caplog.text
    assert 'without being stopped' not in caplog.text
    assert no_followup  # analysis was still scheduled


def test_unexpected_early_end_is_reported(tmp_path, monkeypatch, caplog, no_followup):
    monkeypatch.setattr(recorder, '_stop_requested', False)
    with caplog.at_level(logging.INFO, logger='recorder'):
        recorder._monitor_process(FakeProcess(returncode=1), _paths(tmp_path), 3600)
    assert 'without being stopped' in caplog.text


def test_recording_is_not_analyzed_twice_at_once(monkeypatch, tmp_path):
    calls = []

    def slow_analysis(a, b, job):
        calls.append(job)
        time.sleep(0.3)

    monkeypatch.setattr(recorder, '_analyze_recording', slow_analysis)
    args = (tmp_path / 'a.wav', tmp_path / 'b.wav', '2026_Jan_01_10:00')
    threads = [threading.Thread(target=recorder._analyze_recording_delayed, args=args) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert calls == ['2026_Jan_01_10:00']

    recorder._analyze_recording_delayed(*args)  # finished, so it may run again
    assert len(calls) == 2


def test_catch_up_scan_skips_excluded_files(monkeypatch, _storage_dir):
    names = ['2026_Jan_02_10:00_L.wav', '2026_Jan_02_10:00_R.wav']
    for n in names:
        (_storage_dir / n).write_bytes(b'RIFF')
    started = []
    monkeypatch.setattr(recorder, 'load_channel_suffixes', lambda: ('L', 'R'))
    monkeypatch.setattr(recorder, '_analyze_recording_delayed', lambda *a: started.append(a[2]))
    real_thread = threading.Thread
    monkeypatch.setattr(threading, 'Thread', lambda target, args=(), kwargs=None, daemon=None:
                        real_thread(target=target, args=args, kwargs=kwargs or {}))
    try:
        recorder.analyze_unanalyzed_recordings(exclude=set(names))
        time.sleep(0.1)
        assert '2026_Jan_02_10:00' not in started
        recorder.analyze_unanalyzed_recordings()
        time.sleep(0.1)
        assert '2026_Jan_02_10:00' in started
    finally:
        for n in names:
            (_storage_dir / n).unlink()


def test_stop_capture_does_not_start_a_second_analysis(monkeypatch):
    scans = []
    monkeypatch.setattr(recorder, 'analyze_unanalyzed_recordings', lambda **k: scans.append(k))

    class Running(FakeProcess):
        def __init__(self):
            super().__init__(returncode=None)

        def terminate(self):
            self.returncode = 255

        def wait(self, timeout=None):
            return self.returncode

    monkeypatch.setattr(recorder, 'current_process', Running())
    recorder.stop_capture()
    time.sleep(0.05)
    assert recorder._stop_requested is True
    assert scans == []


def test_truncated_recording_still_warns(tmp_path, monkeypatch, caplog, no_followup):
    monkeypatch.setattr(recorder, '_stop_requested', False)
    real_time, fake = time.time, [1000.0, 1600.0]  # start, end: 600 s elapsed
    monkeypatch.setattr(recorder.time, 'time', lambda: fake.pop(0) if fake else real_time())
    with caplog.at_level(logging.INFO, logger='recorder'):
        recorder._monitor_process(FakeProcess(returncode=0), _paths(tmp_path, seconds=1), 600)
    assert 'smaller than expected for 600s' in caplog.text
