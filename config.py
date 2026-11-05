"""
Filesystem locations for runtime state and logs.

Every module that needs a state, log or backup path imports it from here, so
deployments can relocate them without code changes.

Environment variables (all optional):
    AUDIO_RECORDER_STATE_DIR    Databases, secret key, backups.
                                Default: ~/.audio-recorder
    AUDIO_RECORDER_LOG_DIR      recorder.log, scheduler.log, ffmpeg.log.
                                Default: same as the state directory
    AUDIO_RECORDER_SERVICE_LOG_DIR
                                Where systemd writes app.log / error.log
                                (shown on the Settings page).
                                Default: /var/log/audio-recorder

The recordings directory is not configured here; it is a user setting stored in
the schedule database (system_config 'storage_path').
"""
import os
from pathlib import Path


def _dir_from_env(name, default):
    value = os.environ.get(name)
    return Path(value).expanduser() if value else Path(default)


STATE_DIR = _dir_from_env('AUDIO_RECORDER_STATE_DIR', Path.home() / '.audio-recorder')
LOG_DIR = _dir_from_env('AUDIO_RECORDER_LOG_DIR', STATE_DIR)
SERVICE_LOG_DIR = _dir_from_env('AUDIO_RECORDER_SERVICE_LOG_DIR', '/var/log/audio-recorder')

BACKUP_DIR = STATE_DIR / 'backups'

AUTH_DB_PATH = STATE_DIR / 'auth.db'
SCHEDULE_DB_PATH = STATE_DIR / 'schedule.db'
SECRET_KEY_PATH = STATE_DIR / 'secret_key'

RECORDER_LOG_PATH = LOG_DIR / 'recorder.log'
SCHEDULER_LOG_PATH = LOG_DIR / 'scheduler.log'
FFMPEG_LOG_PATH = LOG_DIR / 'ffmpeg.log'
APP_LOG_PATH = SERVICE_LOG_DIR / 'app.log'
ERROR_LOG_PATH = SERVICE_LOG_DIR / 'error.log'

LOG_PATHS = {
    'app': APP_LOG_PATH,
    'error': ERROR_LOG_PATH,
    'recorder': RECORDER_LOG_PATH,
    'scheduler': SCHEDULER_LOG_PATH,
    'ffmpeg': FFMPEG_LOG_PATH,
}


def ensure_dirs():
    """Create the state and log directories if missing."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
