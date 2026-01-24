#!/usr/bin/env python3
"""
Scheduler Module
Manages scheduled recordings using SQLite and APScheduler
"""

import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
import json
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.cron import CronTrigger
import recorder
import atexit

# Database setup
DB_PATH = Path.home() / '.audio-recorder' / 'schedule.db'
DB_PATH.parent.mkdir(exist_ok=True)

# Initialize scheduler
scheduler = BackgroundScheduler()
scheduler.start()

# Ensure scheduler shuts down cleanly
atexit.register(lambda: scheduler.shutdown())


def init_database():
    """Initialize SQLite database for schedule storage"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scheduled_jobs (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            start_time TEXT NOT NULL,
            duration INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            completed_at TEXT,
            notes TEXT,
            is_recurring INTEGER DEFAULT 0,
            recurrence_pattern TEXT,
            parent_template_id TEXT,
            allow_override INTEGER DEFAULT 0,
            capture_video INTEGER DEFAULT 0
        )
    ''')

    # Add capture_video column if it doesn't exist (for upgrades)
    try:
        cursor.execute('ALTER TABLE scheduled_jobs ADD COLUMN capture_video INTEGER DEFAULT 0')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # System configuration table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS system_config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    ''')
    
    # Set default audio device to auto-detect
    cursor.execute('''
        INSERT OR IGNORE INTO system_config (key, value, updated_at) 
        VALUES ('audio_device', 'auto', datetime('now'))
    ''')
    
    # Set default channel suffixes
    cursor.execute('''
        INSERT OR IGNORE INTO system_config (key, value, updated_at) 
        VALUES ('channel_left_suffix', 'L', datetime('now'))
    ''')
    
    cursor.execute('''
        INSERT OR IGNORE INTO system_config (key, value, updated_at) 
        VALUES ('channel_right_suffix', 'R', datetime('now'))
    ''')
    
    conn.commit()
    conn.close()


def create_job(start_time, duration, name='Unnamed Recording', notes='',
               is_recurring=False, recurrence_pattern=None, template_id=None,
               allow_override=False, capture_video=False):
    """
    Create a new scheduled recording job

    Args:
        start_time: ISO format datetime string (e.g., '2024-01-15T14:30:00')
        duration: Recording duration in seconds
        name: Human-readable job name
        notes: Optional notes about the recording
        is_recurring: Whether this is a recurring schedule
        recurrence_pattern: JSON string with recurrence settings
        template_id: ID of template this job was created from (optional)
        allow_override: Allow duration longer than default limit
        capture_video: Also capture video from PTZ camera

    Returns:
        Job ID
    """
    # Parse start time
    dt = datetime.fromisoformat(start_time)
    job_id = f"job_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # Store in database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO scheduled_jobs
        (id, name, start_time, duration, created_at, notes, is_recurring,
         recurrence_pattern, parent_template_id, allow_override, capture_video)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (job_id, name, start_time, duration, datetime.now().isoformat(),
          notes, 1 if is_recurring else 0, recurrence_pattern, template_id,
          1 if allow_override else 0, 1 if capture_video else 0))

    conn.commit()
    conn.close()

    # Schedule with APScheduler
    if is_recurring and recurrence_pattern:
        # Parse recurrence pattern and create cron trigger
        pattern = json.loads(recurrence_pattern)
        trigger = _create_cron_trigger(pattern, dt.time())
    else:
        # One-time job
        trigger = DateTrigger(run_date=dt)

    scheduler.add_job(
        func=_execute_scheduled_recording,
        trigger=trigger,
        id=job_id,
        args=[job_id, duration, allow_override, capture_video],
        replace_existing=True
    )

    return job_id


def _create_cron_trigger(pattern, time_of_day):
    """
    Create a CronTrigger from recurrence pattern
    
    Pattern examples:
    - {"type": "daily", "time": "09:00"}
    - {"type": "weekly", "days": [1,2,3,4,5], "time": "09:00"}  # Mon-Fri
    - {"type": "monthly", "day": 1, "time": "09:00"}  # 1st of month
    
    Args:
        pattern: Dictionary with recurrence settings
        time_of_day: datetime.time object for scheduled time
    
    Returns:
        CronTrigger object
    """
    hour = time_of_day.hour
    minute = time_of_day.minute
    
    if pattern['type'] == 'daily':
        return CronTrigger(hour=hour, minute=minute)
    
    elif pattern['type'] == 'weekly':
        # days: list of 0-6 (Monday=0, Sunday=6)
        days_str = ','.join(str(d) for d in pattern.get('days', [0]))
        return CronTrigger(day_of_week=days_str, hour=hour, minute=minute)
    
    elif pattern['type'] == 'monthly':
        # day: 1-31
        return CronTrigger(day=pattern.get('day', 1), hour=hour, minute=minute)
    
    else:
        # Default to one-time (shouldn't reach here)
        return DateTrigger(run_date=datetime.now())


def delete_job(job_id):
    """
    Delete a scheduled job
    
    Args:
        job_id: Job identifier
    """
    # Remove from scheduler
    try:
        scheduler.remove_job(job_id)
    except:
        pass  # Job may have already completed
    
    # Remove from database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM scheduled_jobs WHERE id = ?', (job_id,))
    conn.commit()
    conn.close()


def get_all_jobs():
    """
    Retrieve all scheduled jobs
    
    Returns:
        List of job dictionaries
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM scheduled_jobs 
        ORDER BY start_time DESC
    ''')
    
    jobs = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return jobs


def get_pending_jobs():
    """Get only pending (not yet executed) jobs"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM scheduled_jobs 
        WHERE status = 'pending' AND start_time > ?
        ORDER BY start_time
    ''', (datetime.now().isoformat(),))
    
    jobs = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return jobs


def _execute_scheduled_recording(job_id, duration, allow_override=False, capture_video=False):
    """
    Internal function executed by APScheduler to start recording

    Args:
        job_id: Job identifier
        duration: Recording duration in seconds
        allow_override: Allow duration longer than default limit
        capture_video: Also capture video from PTZ camera
    """
    print(f"Executing scheduled job: {job_id}")

    video_error = None

    try:
        # Start audio recording with override flag
        recorder.start_capture(duration, allow_override=allow_override)

        # Start video recording if requested
        if capture_video:
            try:
                import video_recorder
                video_recorder.start_video_recording(duration)
                print(f"Job {job_id}: Video recording started")
            except Exception as ve:
                video_error = str(ve)
                print(f"Job {job_id}: Video recording failed: {ve}")
                # Audio continues even if video fails

        # Update database status
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        status_note = ""
        if capture_video and video_error:
            status_note = f"Audio OK, Video failed: {video_error}"

        cursor.execute('''
            UPDATE scheduled_jobs
            SET status = 'completed', completed_at = ?, notes = COALESCE(notes || ' ', '') || ?
            WHERE id = ?
        ''', (datetime.now().isoformat(), status_note, job_id))
        conn.commit()
        conn.close()

        print(f"Job {job_id} completed successfully")

    except Exception as e:
        print(f"Job {job_id} failed: {e}")

        # Update database with error status
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE scheduled_jobs
            SET status = 'failed', completed_at = ?, notes = ?
            WHERE id = ?
        ''', (datetime.now().isoformat(), str(e), job_id))
        conn.commit()
        conn.close()


def restore_jobs_on_startup():
    """
    Restore pending jobs from database after system restart
    Should be called when the application starts
    """
    jobs = get_pending_jobs()

    for job in jobs:
        start_time = datetime.fromisoformat(job['start_time'])
        allow_override = bool(job.get('allow_override', 0))
        capture_video = bool(job.get('capture_video', 0))

        # Handle recurring jobs
        if job.get('is_recurring') and job.get('recurrence_pattern'):
            pattern = json.loads(job['recurrence_pattern'])
            trigger = _create_cron_trigger(pattern, start_time.time())

            scheduler.add_job(
                func=_execute_scheduled_recording,
                trigger=trigger,
                id=job['id'],
                args=[job['id'], job['duration'], allow_override, capture_video],
                replace_existing=True
            )
            print(f"Restored recurring job: {job['id']} - {pattern['type']}")

        # Handle one-time jobs
        elif start_time > datetime.now():
            scheduler.add_job(
                func=_execute_scheduled_recording,
                trigger=DateTrigger(run_date=start_time),
                id=job['id'],
                args=[job['id'], job['duration'], allow_override, capture_video],
                replace_existing=True
            )
            print(f"Restored scheduled job: {job['id']} at {start_time}")
        else:
            # Mark one-time jobs as missed if past due
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE scheduled_jobs
                SET status = 'missed'
                WHERE id = ?
            ''', (job['id'],))
            conn.commit()
            conn.close()
            print(f"Marked job as missed: {job['id']}")


def get_system_config(key, default=None):
    """Get system configuration value"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT value FROM system_config WHERE key = ?', (key,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else default


def set_system_config(key, value):
    """Set system configuration value"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO system_config (key, value, updated_at)
        VALUES (?, ?, datetime('now'))
    ''', (key, value))
    conn.commit()
    conn.close()


# Initialize database on module import
init_database()

# Restore jobs on module import (for application startup)
restore_jobs_on_startup()


if __name__ == '__main__':
    # Test scheduling
    from datetime import timedelta
    
    print("Testing scheduler...")
    
    # Schedule a job 30 seconds from now
    future_time = (datetime.now() + timedelta(seconds=30)).isoformat()
    job_id = create_job(
        start_time=future_time,
        duration=10,
        name='Test Recording',
        notes='Automated test'
    )
    
    print(f"Created test job: {job_id}")
    print("Pending jobs:")
    for job in get_pending_jobs():
        print(f"  {job['name']} - {job['start_time']}")
