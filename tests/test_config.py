"""Path configuration (config.py)."""
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

import config

ROOT = Path(__file__).resolve().parent.parent
APP_MODULES = ['app.py', 'auth.py', 'recorder.py', 'scheduler.py', 'video_recorder.py',
               'db_utils.py', 'validation.py', 'audio_analyzer.py', 'artifact_detector.py']


def _load_config(env):
    """Import config in a fresh interpreter with the given environment."""
    code = ('import config, json; print(json.dumps({k: str(getattr(config, k)) for k in '
            '["STATE_DIR", "LOG_DIR", "SERVICE_LOG_DIR", "AUTH_DB_PATH", "SCHEDULE_DB_PATH", '
            '"SECRET_KEY_PATH", "BACKUP_DIR", "SCHEDULER_LOG_PATH", "APP_LOG_PATH"]}))')
    out = subprocess.run([sys.executable, '-c', code], cwd=ROOT, env=env,
                         capture_output=True, text=True, check=True).stdout
    import json
    return json.loads(out)


def _base_env(tmp_path):
    env = {k: v for k, v in os.environ.items() if not k.startswith('AUDIO_RECORDER_')}
    env['HOME'] = str(tmp_path)
    return env


def test_defaults_match_previous_locations(tmp_path):
    paths = _load_config(_base_env(tmp_path))
    state = tmp_path / '.audio-recorder'
    assert paths['STATE_DIR'] == str(state)
    assert paths['LOG_DIR'] == str(state)
    assert paths['AUTH_DB_PATH'] == str(state / 'auth.db')
    assert paths['SCHEDULE_DB_PATH'] == str(state / 'schedule.db')
    assert paths['SECRET_KEY_PATH'] == str(state / 'secret_key')
    assert paths['BACKUP_DIR'] == str(state / 'backups')
    assert paths['SCHEDULER_LOG_PATH'] == str(state / 'scheduler.log')
    assert paths['APP_LOG_PATH'] == '/var/log/audio-recorder/app.log'


def test_environment_overrides(tmp_path):
    env = _base_env(tmp_path)
    env['AUDIO_RECORDER_STATE_DIR'] = '/var/lib/audio-recorder'
    env['AUDIO_RECORDER_LOG_DIR'] = '/var/log/audio-recorder'
    env['AUDIO_RECORDER_SERVICE_LOG_DIR'] = '/srv/logs'
    paths = _load_config(env)
    assert paths['AUTH_DB_PATH'] == '/var/lib/audio-recorder/auth.db'
    assert paths['BACKUP_DIR'] == '/var/lib/audio-recorder/backups'
    assert paths['SCHEDULER_LOG_PATH'] == '/var/log/audio-recorder/scheduler.log'
    assert paths['APP_LOG_PATH'] == '/srv/logs/app.log'


def test_empty_env_var_uses_default(tmp_path):
    env = _base_env(tmp_path)
    env['AUDIO_RECORDER_STATE_DIR'] = ''
    assert _load_config(env)['STATE_DIR'] == str(tmp_path / '.audio-recorder')


@pytest.mark.parametrize('module', APP_MODULES)
def test_no_hardcoded_state_paths(module):
    source = (ROOT / module).read_text()
    for needle in ('Path.home()', "'.audio-recorder'", '/var/log/audio-recorder'):
        assert needle not in source, f'{module} hard-codes {needle}; use config.py'


def test_modules_use_configured_paths():
    import auth
    import recorder
    import scheduler
    assert auth.AUTH_DB_PATH == config.AUTH_DB_PATH
    assert scheduler.DB_PATH == config.SCHEDULE_DB_PATH
    assert recorder.RECORDER_LOG_PATH == config.RECORDER_LOG_PATH
    assert config.STATE_DIR == Path(os.environ['AUDIO_RECORDER_STATE_DIR'])
    assert config.AUTH_DB_PATH.exists() and config.SCHEDULE_DB_PATH.exists()


def test_log_paths_api(logged_in):
    resp = logged_in.get('/api/logs/paths')
    assert resp.status_code == 200
    assert resp.get_json() == {k: str(v) for k, v in config.LOG_PATHS.items()}


def test_revert_status_uses_backup_dir(logged_in):
    config.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    marker = config.BACKUP_DIR / 'schedules.sched.last'
    marker.write_bytes(b'')
    try:
        resp = logged_in.get('/api/revert/available')
        assert resp.status_code == 200, resp.get_json()
        assert resp.get_json()['schedules_available'] is True
    finally:
        marker.unlink()


def test_pyproject_version_matches_app():
    import re
    import app as app_module
    text = (ROOT / 'pyproject.toml').read_text()
    assert re.search(r'^version = "([^"]+)"', text, re.M).group(1) == app_module.__version__


def test_lock_files_cover_pyproject_dependencies():
    import re
    deps = re.search(r'^dependencies = \[(.*?)\]', (ROOT / 'pyproject.toml').read_text(), re.M | re.S).group(1)
    names = {name.lower() for name in re.findall(r'^\s*"([A-Za-z0-9_.-]+)', deps, re.M)}
    assert len(names) == 6
    for lock in ('requirements.lock', 'requirements-dev.lock'):
        locked = set(re.findall(r'^([a-z0-9_.-]+)==', (ROOT / lock).read_text(), re.M))
        assert names <= locked, f'{lock} is stale; regenerate it (see pyproject.toml)'
    assert 'pytest' in (ROOT / 'requirements-dev.lock').read_text()


def test_service_unit_matches_config_env():
    unit = (ROOT / 'audio-recorder.service').read_text()
    assert 'ExecStart=/opt/audio-recorder/.venv/bin/python /opt/audio-recorder/app/app.py' in unit
    assert 'User=audio-recorder' in unit
    for var in ('AUDIO_RECORDER_STATE_DIR=/var/lib/audio-recorder',
                'AUDIO_RECORDER_LOG_DIR=/var/log/audio-recorder',
                'AUDIO_RECORDER_SERVICE_LOG_DIR=/var/log/audio-recorder'):
        assert f'Environment={var}' in unit


def test_installer_checks_service_paths_as_root():
    """The installing user cannot read the state, log or storage directories, so
    shell tests on them must use `sudo test`; a plain `[ -e ... ]` reports
    "missing" and once caused every upgrade to re-migrate old data over live data."""
    text = (ROOT / 'install.sh').read_text()
    unprivileged = re.findall(r'\[\[? +!? *-[a-z] +"\$(?:STATE_DIR|LOG_DIR|STORAGE)\b[^\]]*\]', text)
    globs = re.findall(r'"\$(?:STATE_DIR|LOG_DIR|STORAGE)"/\*', text)
    assert not unprivileged and not globs, unprivileged + globs
