#!/usr/bin/env python3
"""
Flask Web Application
Main web interface for the ILC Audio Recorder
"""

from flask import Flask, render_template, request, jsonify, send_file
from datetime import datetime, timedelta
import os
from pathlib import Path

# Import our modules
from recorder import get_recorder
from scheduler import get_scheduler
from templates_manager import get_template_manager

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'ilc-audio-recorder-secret-key-change-in-production'

# Initialize components
RECORDINGS_DIR = os.getenv('RECORDINGS_DIR', '/home/pi/recordings')
DB_DIR = Path(__file__).parent / 'data'
DB_DIR.mkdir(exist_ok=True)

recorder = get_recorder(RECORDINGS_DIR)
scheduler = get_scheduler(str(DB_DIR / 'scheduler.db'), recorder)
template_manager = get_template_manager(str(DB_DIR / 'templates.db'))


# ============================================================================
# Dashboard Routes
# ============================================================================

@app.route('/')
def index():
    """Dashboard page"""
    status = recorder.get_status()
    return render_template('index.html', status=status)


@app.route('/api/status')
def api_status():
    """Get current recording status (for AJAX polling)"""
    return jsonify(recorder.get_status())


# ============================================================================
# Recording Control Routes
# ============================================================================

@app.route('/api/recording/start', methods=['POST'])
def api_start_recording():
    """Start a manual recording"""
    data = request.json

    duration = int(data.get('duration', 3600))
    name = data.get('name', 'manual_recording')
    allow_long = data.get('allow_long_recording', False)

    success, message, session = recorder.start_recording(
        duration_seconds=duration,
        name_prefix=name,
        allow_long_recording=allow_long
    )

    return jsonify({
        'success': success,
        'message': message,
        'session': session
    })


@app.route('/api/recording/stop', methods=['POST'])
def api_stop_recording():
    """Stop the current recording"""
    success, message = recorder.stop_recording()

    return jsonify({
        'success': success,
        'message': message
    })


# ============================================================================
# Schedule Routes
# ============================================================================

@app.route('/schedule')
def schedule():
    """Schedule management page"""
    jobs = scheduler.get_all_jobs()
    templates = template_manager.get_all_templates()
    return render_template('schedule.html', jobs=jobs, templates=templates)


@app.route('/api/schedule/add', methods=['POST'])
def api_add_schedule():
    """Add a new scheduled recording"""
    data = request.json

    schedule_type = data.get('type', 'one_time')  # 'one_time' or 'recurring'
    name = data.get('name', 'scheduled_recording')
    duration = int(data.get('duration', 3600))
    notes = data.get('notes', '')

    if schedule_type == 'one_time':
        # One-time schedule
        start_datetime_str = data.get('start_datetime')
        try:
            start_datetime = datetime.fromisoformat(start_datetime_str)
            success, job_id, message = scheduler.add_one_time_job(
                start_datetime=start_datetime,
                duration=duration,
                name=name,
                notes=notes
            )
        except ValueError as e:
            return jsonify({
                'success': False,
                'message': f'Invalid datetime format: {str(e)}'
            })

    elif schedule_type == 'recurring':
        # Recurring schedule
        recurrence_type = data.get('recurrence_type')  # daily, weekly, monthly, etc.
        start_time = data.get('start_time')  # HH:MM format
        days_of_week = data.get('days_of_week')  # List of day numbers for weekly
        day_of_month = data.get('day_of_month')  # Day number for monthly

        success, job_id, message = scheduler.add_recurring_job(
            recurrence_type=recurrence_type,
            start_time=start_time,
            duration=duration,
            name=name,
            days_of_week=days_of_week,
            day_of_month=day_of_month,
            notes=notes
        )

    else:
        return jsonify({
            'success': False,
            'message': 'Invalid schedule type'
        })

    return jsonify({
        'success': success,
        'job_id': job_id,
        'message': message
    })


@app.route('/api/schedule/delete/<job_id>', methods=['DELETE'])
def api_delete_schedule(job_id):
    """Delete a scheduled job"""
    success, message = scheduler.remove_job(job_id)

    return jsonify({
        'success': success,
        'message': message
    })


@app.route('/api/schedule/list')
def api_list_schedules():
    """Get all scheduled jobs"""
    jobs = scheduler.get_all_jobs()
    return jsonify({'jobs': jobs})


# ============================================================================
# Calendar Routes
# ============================================================================

@app.route('/calendar')
def calendar():
    """Multi-week calendar view"""
    return render_template('calendar.html')


@app.route('/api/calendar/events')
def api_calendar_events():
    """Get calendar events for a date range"""
    # Get date range from query parameters
    start_str = request.args.get('start')
    end_str = request.args.get('end')

    try:
        if start_str and end_str:
            start_date = datetime.fromisoformat(start_str)
            end_date = datetime.fromisoformat(end_str)
        else:
            # Default: 4 weeks from today
            start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = start_date + timedelta(weeks=4)

        events = scheduler.get_jobs_for_calendar(start_date, end_date)

        return jsonify({'events': events})

    except ValueError as e:
        return jsonify({
            'error': f'Invalid date format: {str(e)}'
        }), 400


# ============================================================================
# Recordings Routes
# ============================================================================

@app.route('/recordings')
def recordings():
    """File browser page"""
    files = recorder.list_recordings()
    return render_template('recordings.html', recordings=files)


@app.route('/api/recordings/list')
def api_list_recordings():
    """Get list of all recordings"""
    files = recorder.list_recordings()
    return jsonify({'recordings': files})


@app.route('/api/recordings/download/<filename>')
def api_download_recording(filename):
    """Download a recording file"""
    try:
        file_path = Path(RECORDINGS_DIR) / filename

        # Security check
        if not file_path.resolve().parent == Path(RECORDINGS_DIR).resolve():
            return jsonify({'error': 'Invalid file path'}), 403

        if not file_path.exists():
            return jsonify({'error': 'File not found'}), 404

        return send_file(
            file_path,
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/recordings/delete/<filename>', methods=['DELETE'])
def api_delete_recording(filename):
    """Delete a recording file"""
    success, message = recorder.delete_recording(filename)

    return jsonify({
        'success': success,
        'message': message
    })


# ============================================================================
# Template Routes
# ============================================================================

@app.route('/templates')
def templates():
    """Template management page"""
    all_templates = template_manager.get_all_templates()
    return render_template('templates_mgmt.html', templates=all_templates)


@app.route('/api/templates/list')
def api_list_templates():
    """Get all templates"""
    all_templates = template_manager.get_all_templates()
    return jsonify({'templates': all_templates})


@app.route('/api/templates/get/<int:template_id>')
def api_get_template(template_id):
    """Get a specific template"""
    template = template_manager.get_template(template_id)

    if template:
        return jsonify({'success': True, 'template': template})
    else:
        return jsonify({'success': False, 'message': 'Template not found'}), 404


@app.route('/api/templates/create', methods=['POST'])
def api_create_template():
    """Create a new template"""
    data = request.json

    name = data.get('name')
    duration = int(data.get('duration', 3600))
    recurrence_type = data.get('recurrence_type')
    recurrence_time = data.get('recurrence_time')
    recurrence_days = data.get('recurrence_days')
    recurrence_day_of_month = data.get('recurrence_day_of_month')
    description = data.get('description', '')

    success, template_id, message = template_manager.create_template(
        name=name,
        duration=duration,
        recurrence_type=recurrence_type,
        recurrence_time=recurrence_time,
        recurrence_days=recurrence_days,
        recurrence_day_of_month=recurrence_day_of_month,
        description=description
    )

    return jsonify({
        'success': success,
        'template_id': template_id,
        'message': message
    })


@app.route('/api/templates/update/<int:template_id>', methods=['PUT'])
def api_update_template(template_id):
    """Update an existing template"""
    data = request.json

    # Extract fields (all optional)
    name = data.get('name')
    duration = data.get('duration')
    if duration is not None:
        duration = int(duration)
    recurrence_type = data.get('recurrence_type')
    recurrence_time = data.get('recurrence_time')
    recurrence_days = data.get('recurrence_days')
    recurrence_day_of_month = data.get('recurrence_day_of_month')
    description = data.get('description')

    success, message = template_manager.update_template(
        template_id=template_id,
        name=name,
        duration=duration,
        recurrence_type=recurrence_type,
        recurrence_time=recurrence_time,
        recurrence_days=recurrence_days,
        recurrence_day_of_month=recurrence_day_of_month,
        description=description
    )

    return jsonify({
        'success': success,
        'message': message
    })


@app.route('/api/templates/delete/<int:template_id>', methods=['DELETE'])
def api_delete_template(template_id):
    """Delete a template"""
    success, message = template_manager.delete_template(template_id)

    return jsonify({
        'success': success,
        'message': message
    })


# ============================================================================
# System Info Routes
# ============================================================================

@app.route('/api/system/disk_space')
def api_disk_space():
    """Get disk space information"""
    import shutil
    stat = shutil.disk_usage(RECORDINGS_DIR)

    return jsonify({
        'total': stat.total,
        'used': stat.used,
        'free': stat.free,
        'percent_used': (stat.used / stat.total) * 100
    })


# ============================================================================
# Error Handlers
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == '__main__':
    # Run Flask app
    # In production, use a proper WSGI server (gunicorn, uwsgi, etc.)
    app.run(
        host='0.0.0.0',  # Listen on all interfaces
        port=5000,
        debug=False  # Set to False in production
    )
