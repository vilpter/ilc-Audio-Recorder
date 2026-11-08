"""audio_analyzer must cope with the values ffmpeg prints for digital silence."""
import shutil
import subprocess
from types import SimpleNamespace

import pytest

import audio_analyzer
from audio_analyzer import AudioAnalyzer, _parse_db


def test_parse_db():
    assert _parse_db('-18.06') == pytest.approx(-18.06)
    assert _parse_db('0.000000') == 0.0
    assert _parse_db('-inf') is None
    assert _parse_db('inf') is None
    assert _parse_db('nan') is None
    assert _parse_db('-') is None


def _fake_run(output):
    def run(cmd, **kwargs):
        return SimpleNamespace(stdout=output, returncode=0)
    return run


def test_db_stats_skip_inf_frames(monkeypatch):
    # astats output for a recording that starts in digital silence
    output = '\n'.join([
        'frame:0    pts:0       pts_time:0',
        'lavfi.astats.Overall.RMS_level=-inf',
        'lavfi.astats.Overall.Peak_level=-inf',
        'frame:1    pts:1024    pts_time:0.021333',
        'lavfi.astats.Overall.RMS_level=-21.0',
        'lavfi.astats.Overall.Peak_level=-18.0',
        'frame:2    pts:2048    pts_time:0.042667',
        'lavfi.astats.Overall.RMS_level=-23.0',
        'lavfi.astats.Overall.Peak_level=-12.5',
    ])
    monkeypatch.setattr(audio_analyzer.subprocess, 'run', _fake_run(output))
    mean_db, max_db, max_time = AudioAnalyzer()._get_db_stats('x.wav', 0, [], 1.0)
    assert mean_db == pytest.approx(-22.0)
    assert max_db == pytest.approx(-12.5)
    assert max_time == pytest.approx(0.042667)


def test_db_stats_all_silent(monkeypatch):
    output = 'lavfi.astats.Overall.RMS_level=-inf\nlavfi.astats.Overall.Peak_level=-inf\n'
    monkeypatch.setattr(audio_analyzer.subprocess, 'run', _fake_run(output))
    mean_db, max_db, _ = AudioAnalyzer()._get_db_stats('x.wav', 0, [], 1.0)
    assert mean_db == float('-inf') and max_db == float('-inf')


def test_negative_silence_start(monkeypatch):
    output = ('[silencedetect @ 0x1] silence_start: -0.0213\n'
              '[silencedetect @ 0x1] silence_end: 3.5 | silence_duration: 3.52\n')
    monkeypatch.setattr(audio_analyzer.subprocess, 'run', _fake_run(output))
    assert AudioAnalyzer()._detect_silence('x.wav', 0) == [(0.0, 3.5)]


@pytest.mark.skipif(not shutil.which('ffmpeg'), reason='ffmpeg not installed')
def test_real_file_with_digital_silence(tmp_path):
    """2 s of exact zeros followed by 2 s of tone: the case that failed in production."""
    wav = tmp_path / 'mixed.wav'
    subprocess.run([
        'ffmpeg', '-v', 'error', '-y',
        '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=mono',
        '-f', 'lavfi', '-i', 'sine=f=440:r=48000',
        '-filter_complex', '[0:a]atrim=0:2[a];[1:a]atrim=0:2[b];[a][b]concat=n=2:v=0:a=1',
        '-c:a', 'pcm_s16le', str(wav)], check=True)
    result = audio_analyzer.analyze_audio_file(str(wav))
    ch = result['channels'][0]
    assert -30 < ch['max_db'] < 0
    assert -30 < ch['mean_db'] < 0
    assert 40 < ch['non_silent_percentage'] < 60


def test_db_stats_keep_ffmpeg_log_out_of_levels(monkeypatch):
    """FFmpeg's log on stderr must not be merged into the metadata it prints on stdout.

    Merged, a progress line could split a value, e.g. "Peak_level=-" followed by
    "size=N/A time=...", which failed with "could not convert string to float: '-'".
    """
    seen = {}

    def run(cmd, **kwargs):
        seen.update(kwargs, cmd=cmd)
        return SimpleNamespace(stdout='', returncode=0)

    monkeypatch.setattr(audio_analyzer.subprocess, 'run', run)
    AudioAnalyzer()._get_db_stats('x.wav', 0, [], 1.0)
    assert seen.get('stderr') is not subprocess.STDOUT
    assert '-nostats' in seen['cmd']


def test_db_stats_skip_split_values(monkeypatch):
    output = ('lavfi.astats.Overall.Peak_level=-\n'
              'lavfi.astats.Overall.Peak_level=-9.5\n'
              'lavfi.astats.Overall.RMS_level=-29.38size=N/A time=01:31:44.85\n'
              'lavfi.astats.Overall.RMS_level=-20.0\n')
    monkeypatch.setattr(audio_analyzer.subprocess, 'run', _fake_run(output))
    mean_db, max_db, _ = AudioAnalyzer()._get_db_stats('x.wav', 0, [], 1.0)
    assert max_db == pytest.approx(-9.5)
    assert mean_db == pytest.approx(-20.0)
