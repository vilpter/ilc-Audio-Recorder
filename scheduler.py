#!/usr/bin/env python3
"""
Scheduler Module
Handles scheduled recordings using APScheduler with SQLite persistence
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from datetime import datetime, timedelta
import logging
import sqlite3
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RecordingScheduler:
    """Manages scheduled recording jobs using APScheduler"""

    def __init__(self, db_path="scheduler.db", recorder=None):
        """
        Initialize the scheduler

        Args:
            db_path: Path to SQLite database for job persistence
            recorder: AudioRecorder instance for executing recordings
        """
        self.db_path = Path(db_path)
        self.recorder = recorder

        # Configure job store
        jobstores = {
            'default': SQLAlchemyJobStore(url=f'sqlite:///{self.db_path}')
        }

        # Create scheduler
        self.scheduler = BackgroundScheduler(
            jobstores=jobstores,
            job_defaults={'coalesce': False, 'max_instances': 1}
        )

        # Initialize metadata database
        self._init_metadata_db()

    def _init_metadata_db(self):
        """Initialize metadata database for job information"""
        conn = sqlite3.connect(f"{self.db_path}.meta")
        cursor = conn.cursor()

        # Create jobs metadata table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS job_metadata (
                job_id TEXT PRIMARY KEY,
                name TEXT,
                duration INTEGER,
                recurrence_type TEXT,
                recurrence_pattern TEXT,
                template_id TEXT,
                created_at TEXT,
                notes TEXT
            )
        """)

        conn.commit()
        conn.close()

    def start(self):
        """Start the scheduler"""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Scheduler started")

    def shutdown(self):
        """Shutdown the scheduler"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler stopped")

    def _execute_recording(self, job_id, duration, name):
        """
        Internal method to execute a scheduled recording

        Args:
            job_id: Job identifier
            duration: Recording duration in seconds
            name: Recording name/prefix
        """
        logger.info(f"Executing scheduled job: {job_id} - {name} ({duration}s)")

        if self.recorder:
            success, message, session = self.recorder.start_recording(
                duration_seconds=duration,
                name_prefix=name,
                allow_long_recording=True  # Scheduled jobs can override limit
            )

            if success:
                logger.info(f"Scheduled recording started: {name}")
            else:
                logger.error(f"Failed to start scheduled recording: {message}")
        else:
            logger.error("No recorder instance available")

    def add_one_time_job(self, start_datetime, duration, name, notes=""):
        """
        Schedule a one-time recording

        Args:
            start_datetime: datetime object for when to start
            duration: Recording duration in seconds
            name: Recording name/prefix
            notes: Optional notes

        Returns:
            tuple: (success: bool, job_id: str or None, message: str)
        """
        try:
            # Create job
            job = self.scheduler.add_job(
                func=self._execute_recording,
                trigger=DateTrigger(run_date=start_datetime),
                args=[None, duration, name],  # job_id will be set after creation
                name=name,
                id=None  # Let APScheduler generate ID
            )

            # Update job_id in args
            job.modify(args=[job.id, duration, name])

            # Save metadata
            self._save_job_metadata(
                job_id=job.id,
                name=name,
                duration=duration,
                recurrence_type='one_time',
                recurrence_pattern=start_datetime.isoformat(),
                notes=notes
            )

            logger.info(f"One-time job scheduled: {job.id} at {start_datetime}")
            return (True, job.id, "Job scheduled successfully")

        except Exception as e:
            logger.error(f"Failed to schedule job: {e}")
            return (False, None, str(e))

    def add_recurring_job(self, recurrence_type, start_time, duration, name,
                         days_of_week=None, day_of_month=None, notes=""):
        """
        Schedule a recurring recording

        Args:
            recurrence_type: 'daily', 'weekly', 'monthly', 'weekdays', 'weekends'
            start_time: Time string (HH:MM format)
            duration: Recording duration in seconds
            name: Recording name/prefix
            days_of_week: List of day numbers (0=Monday, 6=Sunday) for weekly
            day_of_month: Day number (1-31) for monthly
            notes: Optional notes

        Returns:
            tuple: (success: bool, job_id: str or None, message: str)
        """
        try:
            hour, minute = map(int, start_time.split(':'))

            # Build cron trigger based on recurrence type
            if recurrence_type == 'daily':
                trigger = CronTrigger(hour=hour, minute=minute)
                pattern = f"Daily at {start_time}"

            elif recurrence_type == 'weekdays':
                trigger = CronTrigger(day_of_week='mon-fri', hour=hour, minute=minute)
                pattern = f"Weekdays at {start_time}"

            elif recurrence_type == 'weekends':
                trigger = CronTrigger(day_of_week='sat,sun', hour=hour, minute=minute)
                pattern = f"Weekends at {start_time}"

            elif recurrence_type == 'weekly' and days_of_week:
                # Convert list [0, 2, 4] to 'mon,wed,fri'
                day_names = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
                days_str = ','.join([day_names[d] for d in days_of_week])
                trigger = CronTrigger(day_of_week=days_str, hour=hour, minute=minute)
                pattern = f"Weekly on {days_str} at {start_time}"

            elif recurrence_type == 'monthly' and day_of_month:
                trigger = CronTrigger(day=day_of_month, hour=hour, minute=minute)
                pattern = f"Monthly on day {day_of_month} at {start_time}"

            else:
                return (False, None, "Invalid recurrence type or missing parameters")

            # Create job
            job = self.scheduler.add_job(
                func=self._execute_recording,
                trigger=trigger,
                args=[None, duration, name],
                name=name,
                id=None
            )

            # Update job_id in args
            job.modify(args=[job.id, duration, name])

            # Save metadata
            self._save_job_metadata(
                job_id=job.id,
                name=name,
                duration=duration,
                recurrence_type=recurrence_type,
                recurrence_pattern=pattern,
                notes=notes
            )

            logger.info(f"Recurring job scheduled: {job.id} - {pattern}")
            return (True, job.id, f"Recurring job scheduled: {pattern}")

        except Exception as e:
            logger.error(f"Failed to schedule recurring job: {e}")
            return (False, None, str(e))

    def remove_job(self, job_id):
        """
        Remove a scheduled job

        Args:
            job_id: Job identifier

        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            self.scheduler.remove_job(job_id)
            self._delete_job_metadata(job_id)
            logger.info(f"Job removed: {job_id}")
            return (True, "Job removed successfully")
        except Exception as e:
            logger.error(f"Failed to remove job {job_id}: {e}")
            return (False, str(e))

    def get_all_jobs(self):
        """
        Get all scheduled jobs with metadata

        Returns:
            list: List of job dictionaries
        """
        jobs = []

        try:
            # Get jobs from scheduler
            scheduled_jobs = self.scheduler.get_jobs()

            # Get metadata
            conn = sqlite3.connect(f"{self.db_path}.meta")
            cursor = conn.cursor()

            for job in scheduled_jobs:
                cursor.execute(
                    "SELECT * FROM job_metadata WHERE job_id = ?",
                    (job.id,)
                )
                metadata = cursor.fetchone()

                next_run = job.next_run_time.isoformat() if job.next_run_time else None

                job_info = {
                    'id': job.id,
                    'name': job.name,
                    'next_run': next_run,
                    'next_run_formatted': job.next_run_time.strftime("%Y-%m-%d %H:%M:%S") if job.next_run_time else "N/A"
                }

                # Add metadata if available
                if metadata:
                    job_info.update({
                        'duration': metadata[2],
                        'recurrence_type': metadata[3],
                        'recurrence_pattern': metadata[4],
                        'template_id': metadata[5],
                        'created_at': metadata[6],
                        'notes': metadata[7]
                    })

                jobs.append(job_info)

            conn.close()

        except Exception as e:
            logger.error(f"Error getting jobs: {e}")

        return jobs

    def get_jobs_for_calendar(self, start_date, end_date):
        """
        Get all job occurrences within a date range for calendar display

        Args:
            start_date: Start date (datetime)
            end_date: End date (datetime)

        Returns:
            list: List of job occurrence dictionaries
        """
        occurrences = []

        try:
            jobs = self.get_all_jobs()

            for job in jobs:
                apscheduler_job = self.scheduler.get_job(job['id'])
                if not apscheduler_job:
                    continue

                # For one-time jobs
                if job.get('recurrence_type') == 'one_time':
                    next_run = apscheduler_job.next_run_time
                    if next_run and start_date <= next_run <= end_date:
                        occurrences.append({
                            'job_id': job['id'],
                            'name': job['name'],
                            'start': next_run.isoformat(),
                            'duration': job.get('duration', 0),
                            'type': 'one_time',
                            'pattern': job.get('recurrence_pattern', '')
                        })

                # For recurring jobs, calculate occurrences
                else:
                    trigger = apscheduler_job.trigger
                    current = start_date

                    # Generate up to 100 occurrences within range
                    count = 0
                    while current <= end_date and count < 100:
                        next_fire = trigger.get_next_fire_time(None, current)
                        if next_fire and next_fire <= end_date:
                            occurrences.append({
                                'job_id': job['id'],
                                'name': job['name'],
                                'start': next_fire.isoformat(),
                                'duration': job.get('duration', 0),
                                'type': job.get('recurrence_type', 'recurring'),
                                'pattern': job.get('recurrence_pattern', '')
                            })
                            current = next_fire + timedelta(seconds=1)
                            count += 1
                        else:
                            break

        except Exception as e:
            logger.error(f"Error generating calendar occurrences: {e}")

        return occurrences

    def _save_job_metadata(self, job_id, name, duration, recurrence_type,
                          recurrence_pattern, template_id=None, notes=""):
        """Save job metadata to database"""
        try:
            conn = sqlite3.connect(f"{self.db_path}.meta")
            cursor = conn.cursor()

            cursor.execute("""
                INSERT OR REPLACE INTO job_metadata
                (job_id, name, duration, recurrence_type, recurrence_pattern,
                 template_id, created_at, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job_id, name, duration, recurrence_type, recurrence_pattern,
                template_id, datetime.now().isoformat(), notes
            ))

            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error saving job metadata: {e}")

    def _delete_job_metadata(self, job_id):
        """Delete job metadata from database"""
        try:
            conn = sqlite3.connect(f"{self.db_path}.meta")
            cursor = conn.cursor()
            cursor.execute("DELETE FROM job_metadata WHERE job_id = ?", (job_id,))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error deleting job metadata: {e}")


# Singleton instance
_scheduler_instance = None

def get_scheduler(db_path="scheduler.db", recorder=None):
    """Get or create the singleton scheduler instance"""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = RecordingScheduler(db_path, recorder)
        _scheduler_instance.start()
    return _scheduler_instance
