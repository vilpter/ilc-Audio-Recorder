"""Scheduler regressions."""
import json
import sqlite3
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import app as app_module
import recorder
import scheduler


def test_scheduler_does_not_import_app():
    # When the service runs `python3 app.py`, the routes live in __main__;
    # `import app` would load a second copy with its own state.
    source = Path(scheduler.__file__).read_text()
    assert 'from app import' not in source
    assert 'import app\n' not in source


def test_recording_status_is_shared():
    assert app_module.recording_status is recorder.recording_status


def _make_job(is_recurring=False):
    start = (datetime.now() + timedelta(days=1)).replace(microsecond=0).isoformat()
    pattern = json.dumps({'type': 'daily'}) if is_recurring else None
    # Job IDs have one-second resolution; retry if a previous test used this second.
    for _ in range(3):
        try:
            return scheduler.create_job(start, 60, name='test job', is_recurring=is_recurring,
                                        recurrence_pattern=pattern)
        except sqlite3.IntegrityError:
            time.sleep(1.05)
    raise RuntimeError('could not create a uniquely-named job')


def test_scheduled_recording_enables_section_marking(logged_in, monkeypatch):
    monkeypatch.setattr(recorder, 'start_capture', lambda *a, **kw: None)
    job_id = _make_job()

    scheduler._execute_scheduled_recording(job_id, 60)

    assert recorder.recording_status['is_recording'] is True
    assert recorder.recording_status['current_job'] == job_id

    resp = logged_in.post('/api/recording/section', json={'type': 'start'})
    assert resp.status_code == 200, resp.get_json()
    resp = logged_in.post('/api/recording/section', json={'type': 'end'})
    assert resp.status_code == 200, resp.get_json()
    assert len(scheduler.get_sections_for_recording(job_id)) == 1


def test_recurring_execution_records_completed_instance(monkeypatch):
    monkeypatch.setattr(recorder, 'start_capture', lambda *a, **kw: None)
    job_id = _make_job(is_recurring=True)

    scheduler._execute_scheduled_recording(job_id, 60)

    instance = scheduler.get_instance_for_occurrence(job_id, date.today().isoformat())
    assert instance is not None
    assert instance['status'] == 'completed', instance


def test_past_occurrence_lookup(logged_in):
    job_id = _make_job(is_recurring=True)
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    resp = logged_in.get(f'/api/schedule/{job_id}/occurrence/{yesterday}')
    assert resp.status_code == 200, resp.get_json()
