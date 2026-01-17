#!/usr/bin/env python3
"""
Recording Templates Manager
Handles saving and loading recording presets
"""

import sqlite3
from pathlib import Path
from datetime import datetime
import json

# Database setup
DB_PATH = Path.home() / '.audio-recorder' / 'schedule.db'


def init_templates_table():
    """Initialize templates table in database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS recording_templates (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            duration INTEGER NOT NULL,
            recurrence_pattern TEXT,
            notes TEXT,
            created_at TEXT NOT NULL,
            last_used TEXT
        )
    ''')
    
    conn.commit()
    conn.close()


def create_template(name, duration, recurrence_pattern=None, notes=''):
    """
    Create a new recording template
    
    Args:
        name: Template name (must be unique)
        duration: Recording duration in seconds
        recurrence_pattern: JSON string of recurrence settings (optional)
        notes: Optional notes
    
    Returns:
        Template ID
    """
    template_id = f"tpl_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO recording_templates (id, name, duration, recurrence_pattern, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (template_id, name, duration, recurrence_pattern, notes, datetime.now().isoformat()))
        
        conn.commit()
        return template_id
    except sqlite3.IntegrityError:
        raise ValueError(f"Template with name '{name}' already exists")
    finally:
        conn.close()


def get_template(template_id):
    """
    Retrieve a template by ID
    
    Returns:
        Template dictionary or None
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM recording_templates WHERE id = ?', (template_id,))
    row = cursor.fetchone()
    conn.close()
    
    return dict(row) if row else None


def get_template_by_name(name):
    """
    Retrieve a template by name
    
    Returns:
        Template dictionary or None
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM recording_templates WHERE name = ?', (name,))
    row = cursor.fetchone()
    conn.close()
    
    return dict(row) if row else None


def get_all_templates():
    """
    Get all recording templates
    
    Returns:
        List of template dictionaries
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM recording_templates ORDER BY name')
    templates = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return templates


def update_template(template_id, name=None, duration=None, recurrence_pattern=None, notes=None):
    """
    Update an existing template
    
    Args:
        template_id: Template to update
        name: New name (optional)
        duration: New duration (optional)
        recurrence_pattern: New recurrence pattern (optional)
        notes: New notes (optional)
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    updates = []
    params = []
    
    if name is not None:
        updates.append('name = ?')
        params.append(name)
    if duration is not None:
        updates.append('duration = ?')
        params.append(duration)
    if recurrence_pattern is not None:
        updates.append('recurrence_pattern = ?')
        params.append(recurrence_pattern)
    if notes is not None:
        updates.append('notes = ?')
        params.append(notes)
    
    if not updates:
        conn.close()
        return
    
    params.append(template_id)
    query = f"UPDATE recording_templates SET {', '.join(updates)} WHERE id = ?"
    
    try:
        cursor.execute(query, params)
        conn.commit()
    except sqlite3.IntegrityError:
        raise ValueError(f"Template name must be unique")
    finally:
        conn.close()


def delete_template(template_id):
    """Delete a template"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM recording_templates WHERE id = ?', (template_id,))
    conn.commit()
    conn.close()


def mark_template_used(template_id):
    """Update last_used timestamp when template is used"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE recording_templates 
        SET last_used = ?
        WHERE id = ?
    ''', (datetime.now().isoformat(), template_id))
    conn.commit()
    conn.close()


# Initialize table on module import
init_templates_table()


if __name__ == '__main__':
    # Test template system
    print("Testing template system...")
    
    # Create test templates
    tpl1 = create_template(
        name="Morning News (2hr)",
        duration=7200,
        recurrence_pattern=json.dumps({"type": "weekly", "days": [1, 2, 3, 4, 5], "time": "09:00"}),
        notes="Weekday morning news recording"
    )
    print(f"Created template: {tpl1}")
    
    tpl2 = create_template(
        name="Quick 30min",
        duration=1800,
        notes="Standard 30-minute recording"
    )
    print(f"Created template: {tpl2}")
    
    # List all templates
    print("\nAll templates:")
    for tpl in get_all_templates():
        print(f"  {tpl['name']}: {tpl['duration']}s - {tpl['notes']}")
