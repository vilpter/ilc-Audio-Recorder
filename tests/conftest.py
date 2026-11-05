"""
Test fixtures.

The app modules create state under Path.home()/.audio-recorder and start the
APScheduler at import time, so HOME is redirected to a temp directory before
anything is imported.
"""
import logging
import os
import sys
import tempfile
from pathlib import Path

_TEST_HOME = tempfile.mkdtemp(prefix='audio-recorder-test-home-')
os.environ['HOME'] = _TEST_HOME

# The app logs to sys.stderr from the scheduler thread; once pytest closes its
# captured stream those writes fail noisily at teardown. Silence that noise.
logging.raiseExceptions = False

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

import app as app_module  # noqa: E402
import auth  # noqa: E402
import recorder  # noqa: E402
import scheduler  # noqa: E402

PASSWORD = 'test-password-123'


@pytest.fixture(scope='session', autouse=True)
def _storage_dir():
    storage = Path(_TEST_HOME) / 'recordings'
    storage.mkdir(exist_ok=True)
    scheduler.set_system_config('storage_path', str(storage))
    return storage


@pytest.fixture(scope='session')
def admin_user():
    user = auth.User.get_by_username('admin')
    if user is None:
        user = auth.User.create('admin', PASSWORD, role='admin', is_primary_admin=True)
    return user


@pytest.fixture
def flask_app():
    app_module.app.config.update(TESTING=True)
    return app_module.app


@pytest.fixture
def client(flask_app, admin_user):
    """Unauthenticated client (an admin user exists, so no setup redirect)."""
    return flask_app.test_client()


@pytest.fixture
def logged_in(client):
    resp = client.post('/login', data={'username': 'admin', 'password': PASSWORD})
    assert resp.status_code == 302, resp.data
    return client


@pytest.fixture(autouse=True)
def _reset_recording_status():
    recorder.recording_status.update(is_recording=False, current_job=None, start_time=None)
    yield
    recorder.recording_status.update(is_recording=False, current_job=None, start_time=None)
