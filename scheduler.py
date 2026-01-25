#!/usr/bin/env python3
"""
Scheduler Module
Manages scheduled recordings using SQLite and APScheduler
"""

import sqlite3
import sys
import os
import logging
import traceback
from pathlib import Path
from datetime import datetime, timedelta
import json
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.cron import CronTrigger
import recorder
import atexit

# Log file path
LOG_DIR = Path.home() / '.audio-recorder'
LOG_DIR.mkdir(exist_ok=True)
SCHEDULER_LOG_PATH = LOG_DIR / 'scheduler.log'

# Configure logging for scheduler troubleshooting
# Use local time for timestamps (not UTC)
import time as time_module

class LocalTimeFormatter(logging.Formatter):
    converter = time_module.localtime  # Use local time instead of UTC

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stderr),
        logging.FileHandler(SCHEDULER_LOG_PATH)
    ]
)
# Apply local time formatter to all handlers
for handler in logging.root.handlers:
    handler.setFormatter(LocalTimeFormatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s',
                                            datefmt='%Y-%m-%d %H:%M:%S'))
logger = logging.getLogger('scheduler')


def _log_scheduler_environment():
    """Log environment variables and system state for scheduler thread troubleshooting"""
    import threading

    logger.info("-" * 40)
    logger.info("SCHEDULER THREAD ENVIRONMENT")
    logger.info("-" * 40)
    logger.info(f"Thread: {threading.current_thread().name}")
    logger.info(f"Thread ID: {threading.current_thread().ident}")
    logger.info(f"Is daemon: {threading.current_thread().daemon}")
    logger.info(f"Process ID: {os.getpid()}")
    logger.info(f"Working directory: {os.getcwd()}")

    # Log key environment variables
    env_vars = ['PATH', 'HOME', 'USER', 'DISPLAY', 'XDG_RUNTIME_DIR',
                'PULSE_SERVER', 'ALSA_CARD', 'LANG', 'LC_ALL']
    logger.info("Environment variables:")
    for var in env_vars:
        value = os.environ.get(var, '(not set)')
        # Truncate PATH if too long
        if var == 'PATH' and len(value) > 100:
            value = value[:100] + '...'
        logger.info(f"  {var}={value}")

    logger.info("-" * 40)

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

    # Migrate usb_storage_path to unified storage_path
    cursor.execute("SELECT value FROM system_config WHERE key = 'usb_storage_path'")
    existing_usb = cursor.fetchone()

    if existing_usb:
        # Migrate existing value from usb_storage_path to storage_path
        cursor.execute('''
            INSERT OR IGNORE INTO system_config (key, value, updated_at)
            VALUES ('storage_path', ?, datetime('now'))
        ''', (existing_usb[0],))
    else:
        # Set default storage path
        cursor.execute('''
            INSERT OR IGNORE INTO system_config (key, value, updated_at)
            VALUES ('storage_path', '/mnt/usb_recorder', datetime('now'))
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


def update_job(job_id, start_time=None, duration=None, name=None, notes=None,
               is_recurring=None, recurrence_pattern=None, allow_override=None,
               capture_video=None):
    """
    Update an existing scheduled job

    Args:
        job_id: Job identifier
        start_time: ISO format datetime string (optional)
        duration: Recording duration in seconds (optional)
        name: Human-readable job name (optional)
        notes: Optional notes about the recording (optional)
        is_recurring: Whether this is a recurring schedule (optional)
        recurrence_pattern: JSON string with recurrence settings (optional)
        allow_override: Allow duration longer than default limit (optional)
        capture_video: Also capture video from PTZ camera (optional)

    Returns:
        True if successful
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get current job data
    cursor.execute('SELECT * FROM scheduled_jobs WHERE id = ?', (job_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise ValueError(f"Job {job_id} not found")

    current = dict(row)

    # Update only provided fields
    new_start_time = start_time if start_time is not None else current['start_time']
    new_duration = duration if duration is not None else current['duration']
    new_name = name if name is not None else current['name']
    new_notes = notes if notes is not None else current['notes']
    new_is_recurring = is_recurring if is_recurring is not None else bool(current['is_recurring'])
    new_recurrence_pattern = recurrence_pattern if recurrence_pattern is not None else current['recurrence_pattern']
    new_allow_override = allow_override if allow_override is not None else bool(current['allow_override'])
    new_capture_video = capture_video if capture_video is not None else bool(current['capture_video'])

    # Update database
    cursor.execute('''
        UPDATE scheduled_jobs
        SET start_time = ?, duration = ?, name = ?, notes = ?,
            is_recurring = ?, recurrence_pattern = ?, allow_override = ?, capture_video = ?
        WHERE id = ?
    ''', (new_start_time, new_duration, new_name, new_notes,
          1 if new_is_recurring else 0, new_recurrence_pattern,
          1 if new_allow_override else 0, 1 if new_capture_video else 0, job_id))

    conn.commit()
    conn.close()

    # Remove old scheduler job
    try:
        scheduler.remove_job(job_id)
    except:
        pass

    # Re-schedule with new parameters
    dt = datetime.fromisoformat(new_start_time)

    if new_is_recurring and new_recurrence_pattern:
        pattern = json.loads(new_recurrence_pattern)
        trigger = _create_cron_trigger(pattern, dt.time())
    else:
        trigger = DateTrigger(run_date=dt)

    scheduler.add_job(
        func=_execute_scheduled_recording,
        trigger=trigger,
        id=job_id,
        args=[job_id, new_duration, new_allow_override, new_capture_video],
        replace_existing=True
    )

    return True


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
    import threading
    logger.info(f"=" * 60)
    logger.info(f"SCHEDULED RECORDING START: {job_id}")
    logger.info(f"Thread: {threading.current_thread().name}")
    logger.info(f"Duration: {duration}s, allow_override: {allow_override}, capture_video: {capture_video}")
    logger.info(f"=" * 60)

    # Log scheduler thread environment for troubleshooting
    _log_scheduler_environment()

    video_error = None

    try:
        # Start audio recording with override flag
        logger.info(f"Job {job_id}: Calling recorder.start_capture()...")
        recorder.start_capture(duration, allow_override=allow_override)
        logger.info(f"Job {job_id}: recorder.start_capture() returned successfully")

        # Start video recording if requested
        if capture_video:
            try:
                import video_recorder
                video_recorder.start_video_recording(duration)
                logger.info(f"Job {job_id}: Video recording started")
            except Exception as ve:
                video_error = str(ve)
                logger.error(f"Job {job_id}: Video recording failed: {ve}")
                logger.error(traceback.format_exc())
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

        logger.info(f"Job {job_id} completed successfully")

    except Exception as e:
        logger.error(f"Job {job_id} FAILED: {e}")
        logger.error(f"Full traceback:\n{traceback.format_exc()}")

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
