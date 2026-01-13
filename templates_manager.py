#!/usr/bin/env python3
"""
Recording Templates Manager
Handles CRUD operations for recording templates (preset configurations)
"""

import sqlite3
from datetime import datetime
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TemplateManager:
    """Manages recording templates for reusable configurations"""

    def __init__(self, db_path="templates.db"):
        """
        Initialize the template manager

        Args:
            db_path: Path to SQLite database for template storage
        """
        self.db_path = Path(db_path)
        self._init_db()

    def _init_db(self):
        """Initialize the templates database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                duration INTEGER NOT NULL,
                recurrence_type TEXT,
                recurrence_time TEXT,
                recurrence_days TEXT,
                recurrence_day_of_month INTEGER,
                description TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        conn.commit()
        conn.close()
        logger.info(f"Template database initialized: {self.db_path}")

    def create_template(self, name, duration, recurrence_type=None, recurrence_time=None,
                       recurrence_days=None, recurrence_day_of_month=None, description=""):
        """
        Create a new recording template

        Args:
            name: Template name (must be unique)
            duration: Recording duration in seconds
            recurrence_type: 'one_time', 'daily', 'weekly', 'monthly', 'weekdays', 'weekends'
            recurrence_time: Time string (HH:MM) for recurring templates
            recurrence_days: Comma-separated day numbers (0-6) for weekly recurrence
            recurrence_day_of_month: Day number (1-31) for monthly recurrence
            description: Optional description

        Returns:
            tuple: (success: bool, template_id: int or None, message: str)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            now = datetime.now().isoformat()

            cursor.execute("""
                INSERT INTO templates
                (name, duration, recurrence_type, recurrence_time, recurrence_days,
                 recurrence_day_of_month, description, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                name, duration, recurrence_type, recurrence_time, recurrence_days,
                recurrence_day_of_month, description, now, now
            ))

            template_id = cursor.lastrowid
            conn.commit()
            conn.close()

            logger.info(f"Template created: {name} (ID: {template_id})")
            return (True, template_id, "Template created successfully")

        except sqlite3.IntegrityError:
            logger.error(f"Template name already exists: {name}")
            return (False, None, "Template name already exists")
        except Exception as e:
            logger.error(f"Error creating template: {e}")
            return (False, None, str(e))

    def get_template(self, template_id):
        """
        Get a template by ID

        Args:
            template_id: Template ID

        Returns:
            dict or None: Template data
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM templates WHERE id = ?", (template_id,))
            row = cursor.fetchone()
            conn.close()

            if row:
                return dict(row)
            return None

        except Exception as e:
            logger.error(f"Error getting template {template_id}: {e}")
            return None

    def get_all_templates(self):
        """
        Get all templates

        Returns:
            list: List of template dictionaries
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM templates ORDER BY name")
            rows = cursor.fetchall()
            conn.close()

            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Error getting templates: {e}")
            return []

    def update_template(self, template_id, name=None, duration=None, recurrence_type=None,
                       recurrence_time=None, recurrence_days=None,
                       recurrence_day_of_month=None, description=None):
        """
        Update an existing template

        Args:
            template_id: Template ID
            name: New name (optional)
            duration: New duration (optional)
            recurrence_type: New recurrence type (optional)
            recurrence_time: New recurrence time (optional)
            recurrence_days: New recurrence days (optional)
            recurrence_day_of_month: New day of month (optional)
            description: New description (optional)

        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            # Get existing template
            template = self.get_template(template_id)
            if not template:
                return (False, "Template not found")

            # Build update query dynamically
            updates = []
            params = []

            if name is not None:
                updates.append("name = ?")
                params.append(name)
            if duration is not None:
                updates.append("duration = ?")
                params.append(duration)
            if recurrence_type is not None:
                updates.append("recurrence_type = ?")
                params.append(recurrence_type)
            if recurrence_time is not None:
                updates.append("recurrence_time = ?")
                params.append(recurrence_time)
            if recurrence_days is not None:
                updates.append("recurrence_days = ?")
                params.append(recurrence_days)
            if recurrence_day_of_month is not None:
                updates.append("recurrence_day_of_month = ?")
                params.append(recurrence_day_of_month)
            if description is not None:
                updates.append("description = ?")
                params.append(description)

            if not updates:
                return (False, "No updates provided")

            # Add updated_at timestamp
            updates.append("updated_at = ?")
            params.append(datetime.now().isoformat())

            # Add template_id for WHERE clause
            params.append(template_id)

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            query = f"UPDATE templates SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(query, params)

            conn.commit()
            conn.close()

            logger.info(f"Template updated: ID {template_id}")
            return (True, "Template updated successfully")

        except sqlite3.IntegrityError:
            return (False, "Template name already exists")
        except Exception as e:
            logger.error(f"Error updating template {template_id}: {e}")
            return (False, str(e))

    def delete_template(self, template_id):
        """
        Delete a template

        Args:
            template_id: Template ID

        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("DELETE FROM templates WHERE id = ?", (template_id,))
            rows_affected = cursor.rowcount

            conn.commit()
            conn.close()

            if rows_affected > 0:
                logger.info(f"Template deleted: ID {template_id}")
                return (True, "Template deleted successfully")
            else:
                return (False, "Template not found")

        except Exception as e:
            logger.error(f"Error deleting template {template_id}: {e}")
            return (False, str(e))

    def get_template_summary(self, template_id):
        """
        Get a human-readable summary of a template

        Args:
            template_id: Template ID

        Returns:
            str: Template summary
        """
        template = self.get_template(template_id)
        if not template:
            return "Template not found"

        duration_mins = template['duration'] // 60
        duration_hours = duration_mins // 60
        duration_mins_remainder = duration_mins % 60

        duration_str = ""
        if duration_hours > 0:
            duration_str = f"{duration_hours}h {duration_mins_remainder}m"
        else:
            duration_str = f"{duration_mins}m"

        recurrence = template.get('recurrence_type', 'one_time')

        if recurrence == 'one_time':
            recurrence_str = "One-time recording"
        elif recurrence == 'daily':
            recurrence_str = f"Daily at {template.get('recurrence_time', 'N/A')}"
        elif recurrence == 'weekdays':
            recurrence_str = f"Weekdays at {template.get('recurrence_time', 'N/A')}"
        elif recurrence == 'weekends':
            recurrence_str = f"Weekends at {template.get('recurrence_time', 'N/A')}"
        elif recurrence == 'weekly':
            days = template.get('recurrence_days', '')
            recurrence_str = f"Weekly on days {days} at {template.get('recurrence_time', 'N/A')}"
        elif recurrence == 'monthly':
            day = template.get('recurrence_day_of_month', 'N/A')
            recurrence_str = f"Monthly on day {day} at {template.get('recurrence_time', 'N/A')}"
        else:
            recurrence_str = "Custom schedule"

        return f"{template['name']}: {duration_str}, {recurrence_str}"


# Singleton instance
_template_manager_instance = None

def get_template_manager(db_path="templates.db"):
    """Get or create the singleton template manager instance"""
    global _template_manager_instance
    if _template_manager_instance is None:
        _template_manager_instance = TemplateManager(db_path)
    return _template_manager_instance
