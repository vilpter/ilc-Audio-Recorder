"""Log routing, rotation and the Settings log viewer."""
import logging
import logging.handlers
import re
import uuid
from pathlib import Path

import app as app_module
import config
import logging_setup

ROOT = Path(__file__).resolve().parent.parent


def _flush():
    for handler in logging.getLogger().handlers:
        handler.flush()


def _read(path):
    return path.read_text() if path.exists() else ''


def test_records_go_to_their_component_logs():
    tag = uuid.uuid4().hex
    logging.getLogger('recorder').info(f'rec {tag}')
    logging.getLogger('scheduler').info(f'sch {tag}')
    logging.getLogger('apscheduler.scheduler').info(f'aps {tag}')
    logging.getLogger('app').info(f'web {tag}')
    logging.getLogger('recorder').warning(f'warn {tag}')
    logging.getLogger('werkzeug').info(f'GET /api/status {tag}')
    logging.getLogger('recorder').debug(f'debug {tag}')
    _flush()

    rec, sch = _read(config.RECORDER_LOG_PATH), _read(config.SCHEDULER_LOG_PATH)
    app_log, err = _read(config.APP_LOG_PATH), _read(config.ERROR_LOG_PATH)

    assert f'rec {tag}' in rec and f'rec {tag}' not in sch + app_log + err
    assert f'sch {tag}' in sch and f'aps {tag}' in sch
    assert f'sch {tag}' not in rec + app_log
    assert f'web {tag}' in app_log and f'web {tag}' not in rec + sch + err
    # error.log gets warnings from everything, and the component log keeps them too
    assert f'warn {tag}' in err and f'warn {tag}' in rec
    # request lines and DEBUG output are not logged at the default level
    assert tag not in ''.join(l for l in (rec + sch + app_log + err).splitlines(True) if 'GET /api/status' in l)
    assert f'debug {tag}' not in rec


def test_log_files_rotate():
    files = {Path(h.baseFilename): h for h in logging.getLogger().handlers
             if isinstance(h, logging.FileHandler)}
    expected = {config.RECORDER_LOG_PATH, config.SCHEDULER_LOG_PATH,
                config.APP_LOG_PATH, config.ERROR_LOG_PATH}
    assert expected <= set(files)
    for path in expected:
        handler = files[path]
        assert isinstance(handler, logging.handlers.RotatingFileHandler)
        assert handler.maxBytes == logging_setup.MAX_BYTES and handler.backupCount >= 1


def test_configure_logging_is_idempotent():
    before = list(logging.getLogger().handlers)
    logging_setup.configure_logging()
    assert logging.getLogger().handlers == before


def test_no_module_configures_logging_itself():
    # Two basicConfig() calls once sent every log to whichever module was imported first
    for path in ROOT.glob('*.py'):
        text = path.read_text()
        body = text.split("if __name__ == '__main__':")[0]
        assert 'basicConfig(' not in body, path.name
        if path.name != 'logging_setup.py':
            assert 'FileHandler(' not in body, path.name


def test_log_level_from_environment(monkeypatch):
    monkeypatch.setenv('AUDIO_RECORDER_LOG_LEVEL', 'debug')
    assert logging_setup._log_level() == logging.DEBUG
    monkeypatch.setenv('AUDIO_RECORDER_LOG_LEVEL', 'nonsense')
    assert logging_setup._log_level() == logging.INFO


def test_service_unit_leaves_log_files_to_the_app():
    unit = (ROOT / 'audio-recorder.service').read_text()
    assert not re.search(r'^Standard(Output|Error)=append:', unit, re.M)


def test_tail_lines(tmp_path):
    log = tmp_path / 'big.log'
    log.write_text(''.join(f'line {i}\n' for i in range(50000)))
    tail, total = app_module._tail_lines(log, 3)
    assert tail == ['line 49997\n', 'line 49998\n', 'line 49999\n']
    assert total == 50000

    log.write_text('a\nb\npartial')
    tail, total = app_module._tail_lines(log, 2)
    assert tail == ['b\n', 'partial'] and total == 3

    log.write_text('')
    assert app_module._tail_lines(log, 5) == ([], 0)

    log.write_text('only\n')
    assert app_module._tail_lines(log, 5) == (['only\n'], 1)


def test_logs_api_tail(logged_in):
    tag = uuid.uuid4().hex
    logging.getLogger('recorder').info(f'tail-me {tag}')
    _flush()
    data = logged_in.get('/api/logs?type=recorder&lines=1').get_json()
    assert data['showing_lines'] == 1 and tag in data['logs'][0]
    assert data['total_lines'] >= 1
    assert logged_in.get('/api/logs?type=recorder&lines=abc').status_code == 200


def test_oversized_log_rotated_at_startup(tmp_path, monkeypatch):
    path = tmp_path / 'error.log'
    path.write_text('x' * 200)
    monkeypatch.setattr(logging_setup, 'MAX_BYTES', 100)
    handler = logging_setup._file_handler(path, logging.WARNING)
    try:
        assert path.with_name('error.log.1').read_text() == 'x' * 200
        assert path.stat().st_size == 0
    finally:
        handler.close()


def test_rotate_if_oversized(tmp_path):
    path = tmp_path / 'ffmpeg.log'
    for content in ('first' * 30, 'second' * 30, 'third' * 30, 'fourth' * 30):
        path.write_text(content)
        logging_setup.rotate_if_oversized(path, max_bytes=100, backups=3)
    assert not path.exists()
    assert path.with_name('ffmpeg.log.1').read_text().startswith('fourth')
    assert path.with_name('ffmpeg.log.3').read_text().startswith('second')
    assert not path.with_name('ffmpeg.log.4').exists()
    path.write_text('small')
    logging_setup.rotate_if_oversized(path, max_bytes=100)
    assert path.read_text() == 'small'
