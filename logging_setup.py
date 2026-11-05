"""
Logging configuration for the service.

configure_logging() is called once at startup (app.py). It sends each part of the
application to its own size-limited, rotating file in config.LOG_DIR /
config.SERVICE_LOG_DIR:

    recorder.log    recorder, artifact_detector, audio_analyzer, db_utils
    (ffmpeg.log     FFmpeg output, written by recorder.py; rotated the same way)
    scheduler.log   scheduler, apscheduler
    app.log         everything else at INFO and above (web app, auth, ...)
    error.log       warnings and errors from every logger

Web request lines (werkzeug access log) are not logged: the pages poll the
server every few seconds and would bury everything else.

Set AUDIO_RECORDER_LOG_LEVEL=DEBUG (e.g. with `systemctl edit audio-recorder`)
for verbose troubleshooting output in all files except error.log.
"""
import logging
import logging.handlers
import os
import sys
import time

import config

MAX_BYTES = 5 * 1024 * 1024   # per file
BACKUP_COUNT = 3              # app.log.1 ... app.log.3

FORMAT = '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
DATEFMT = '%Y-%m-%d %H:%M:%S'

# Logger name prefixes routed to the component logs
RECORDER_LOGGERS = ('recorder', 'artifact_detector', 'audio_analyzer', 'db_utils')
SCHEDULER_LOGGERS = ('scheduler', 'apscheduler')

_configured = False


class LocalTimeFormatter(logging.Formatter):
    converter = time.localtime  # local time, not UTC


class _NameFilter(logging.Filter):
    """Pass (or, with exclude=True, block) records from the given logger names."""

    def __init__(self, prefixes, exclude=False):
        super().__init__()
        self.prefixes = prefixes
        self.exclude = exclude

    def filter(self, record):
        match = any(record.name == p or record.name.startswith(p + '.') for p in self.prefixes)
        return not match if self.exclude else match


def _log_level():
    name = os.environ.get('AUDIO_RECORDER_LOG_LEVEL', 'INFO').upper()
    level = logging.getLevelName(name)
    return level if isinstance(level, int) else logging.INFO


def rotate_if_oversized(path, max_bytes=None, backups=BACKUP_COUNT):
    """Rename path to path.1 (shifting .1 -> .2 ...) if it is at least max_bytes long.

    For files not written through a logging handler, such as ffmpeg.log.
    """
    max_bytes = MAX_BYTES if max_bytes is None else max_bytes
    try:
        if not path.exists() or path.stat().st_size < max_bytes:
            return
        for i in range(backups - 1, 0, -1):
            older = path.with_name(f'{path.name}.{i}')
            if older.exists():
                older.replace(path.with_name(f'{path.name}.{i + 1}'))
        path.replace(path.with_name(f'{path.name}.1'))
    except OSError as e:
        logging.getLogger(__name__).warning(f"Could not rotate {path}: {e}")


def _file_handler(path, level, log_filter=None):
    """Rotating file handler, or None if the file can't be opened (e.g. in development)."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(
            path, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding='utf-8')
    except OSError as e:
        print(f"Logging: cannot write {path}: {e}", file=sys.stderr)
        return None
    handler.setLevel(level)
    if log_filter:
        handler.addFilter(log_filter)
    # Rotation normally happens on the next write; rotate an oversized file now
    # (e.g. one that grew without limits under an older version)
    try:
        if path.stat().st_size >= MAX_BYTES:
            handler.doRollover()
    except OSError:
        pass
    return handler


def configure_logging():
    """Install the handlers described in the module docstring. Safe to call more than once."""
    global _configured
    if _configured:
        return
    _configured = True

    level = _log_level()
    formatter = LocalTimeFormatter(FORMAT, datefmt=DATEFMT)
    routed = RECORDER_LOGGERS + SCHEDULER_LOGGERS

    handlers = [
        _file_handler(config.RECORDER_LOG_PATH, level, _NameFilter(RECORDER_LOGGERS)),
        _file_handler(config.SCHEDULER_LOG_PATH, level, _NameFilter(SCHEDULER_LOGGERS)),
        _file_handler(config.APP_LOG_PATH, level, _NameFilter(routed, exclude=True)),
        _file_handler(config.ERROR_LOG_PATH, logging.WARNING),
    ]
    # Console output (the systemd journal, or the terminal in development)
    console = logging.StreamHandler(sys.stderr)
    console.setLevel(logging.WARNING)
    handlers.append(console)

    root = logging.getLogger()
    for handler in root.handlers[:]:
        root.removeHandler(handler)
    root.setLevel(min(level, logging.WARNING))
    for handler in handlers:
        if handler:
            handler.setFormatter(formatter)
            root.addHandler(handler)

    # ffmpeg.log is written by the recorder, one block per recording
    rotate_if_oversized(config.FFMPEG_LOG_PATH)

    # Request lines from the development server: one per poll, every few seconds
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    # APScheduler's "Looking for jobs to run" chatter is DEBUG; keep it out unless asked
    logging.getLogger('apscheduler').setLevel(level)
