#!/usr/bin/env python3
"""
Headless Dual-Mono Audio Recording System
Main Flask Application
"""

from flask import Flask, render_template, jsonify, request, send_file, redirect, url_for, flash
from flask_login import login_required, login_user, logout_user, current_user
from pathlib import Path
import json
import os
import subprocess
import sqlite3
from datetime import datetime
import recorder
import video_recorder
import scheduler
import auth
import db_utils
import validation

app = Flask(__name__)

# Session configuration
app.secret_key = auth.generate_secret_key()

# Initialize Flask-Login
auth.login_manager.init_app(app)

# Initialize auth database
auth.init_auth_db()


def get_recordings_dir():
    """Get the configured recordings directory path"""
    storage_path = scheduler.get_system_config('storage_path', '/mnt/usb_recorder')
    recordings_dir = Path(storage_path)
    recordings_dir.mkdir(parents=True, exist_ok=True)
    return recordings_dir


# Global status tracker for audio
recording_status = {
    'is_recording': False,
    'current_job': None,
    'start_time': None
}

# Global status tracker for video
video_recording_status = {
    'is_recording': False,
    'current_file': None,
    'start_time': None
}


# ============================================================================
# Authentication Routes
# ============================================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page and authentication"""
    # Redirect to setup if no users exist
    if auth.needs_setup():
        return redirect(url_for('setup'))

    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember', False)

        user = auth.User.get_by_username(username)

        if user and user.check_password(password):
            login_user(user, remember=bool(remember))
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        else:
            flash('Invalid username or password', 'error')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    """Logout current user"""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


@app.route('/setup', methods=['GET', 'POST'])
def setup():
    """Initial setup - create admin user"""
    # Only allow setup if no users exist
    if not auth.needs_setup():
        return redirect(url_for('login'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        # Validation
        errors = []
        if not username or len(username) < 3:
            errors.append('Username must be at least 3 characters')
        if not password or len(password) < 6:
            errors.append('Password must be at least 6 characters')
        if password != confirm_password:
            errors.append('Passwords do not match')

        if errors:
            for error in errors:
                flash(error, 'error')
        else:
            user = auth.User.create(username, password)
            if user:
                flash('Admin account created successfully. Please log in.', 'success')
                return redirect(url_for('login'))
            else:
                flash('Failed to create account', 'error')

    return render_template('setup.html')


@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Change current user's password"""
    if request.method == 'POST':
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not current_user.check_password(current_password):
            flash('Current password is incorrect', 'error')
        elif len(new_password) < 6:
            flash('New password must be at least 6 characters', 'error')
        elif new_password != confirm_password:
            flash('New passwords do not match', 'error')
        else:
            auth.User.update_password(current_user.username, new_password)
            flash('Password changed successfully', 'success')
            return redirect(url_for('settings_page'))

    return render_template('change_password.html')


# ============================================================================
# Protected Routes
# ============================================================================

@app.route('/')
@login_required
def index():
    """Calendar view - main landing page"""
    from datetime import datetime, timedelta

    jobs = scheduler.get_all_jobs()

    # Fetch instances for calendar view (past 90 days and next 30 days)
    start_date = (datetime.now() - timedelta(days=90)).date()
    end_date = (datetime.now() + timedelta(days=30)).date()
    instances = scheduler.get_instances_for_date_range(start_date, end_date)

    return render_template('calendar.html', jobs=jobs, instances=instances)


@app.route('/api/status')
@login_required
def get_status():
    """API endpoint for real-time status polling"""
    # Sync with actual recorder state to prevent desync
    actual_recording = recorder.is_recording()
    
    if recording_status['is_recording'] != actual_recording:
        # State mismatch - sync to actual recorder state
        recording_status['is_recording'] = actual_recording
        if not actual_recording:
            # Recording finished - clear job info
            recording_status['current_job'] = None
            recording_status['start_time'] = None
    
    return jsonify(recording_status)


@app.route('/api/record/start', methods=['POST'])
@login_required
def start_recording():
    """Manual recording start (audio, optionally with video)"""
    data = request.json or {}

    # Validate input parameters
    schema = {
        'duration': {
            'type': 'duration',
            'required': False,
            'default': 3600,
            'allow_override': data.get('allow_override', False)
        },
        'allow_override': {
            'type': 'boolean',
            'required': False,
            'default': False
        },
        'capture_video': {
            'type': 'boolean',
            'required': False,
            'default': False
        }
    }

    valid, error_msg, validated = validation.validate_request_data(data, schema)
    if not valid:
        return jsonify({'error': error_msg}), 400

    duration = validated['duration']
    allow_override = validated['allow_override']
    capture_video = validated['capture_video']

    if recording_status['is_recording']:
        return jsonify({'error': 'Recording already in progress'}), 400

    try:
        job_id = recorder.start_capture(duration, allow_override=allow_override)
        recording_status['is_recording'] = True
        recording_status['current_job'] = job_id
        recording_status['start_time'] = datetime.now().isoformat()

        video_started = False
        video_error = None

        # Also start video recording if requested
        if capture_video:
            try:
                video_recorder.start_video_recording(duration)
                video_recording_status['is_recording'] = True
                video_recording_status['start_time'] = datetime.now().isoformat()
                video_started = True
            except Exception as ve:
                video_error = str(ve)
                # Audio recording continues even if video fails

        return jsonify({
            'success': True,
            'job_id': job_id,
            'video_started': video_started,
            'video_error': video_error
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/record/stop', methods=['POST'])
@login_required
def stop_recording():
    """Manual recording stop (stops both audio and video if running)"""
    audio_was_recording = recorder.is_recording()
    video_was_recording = video_recorder.is_video_recording()

    if not audio_was_recording and not video_was_recording:
        return jsonify({'error': 'No recording in progress'}), 400

    audio_stopped = False
    video_stopped = False
    errors = []

    # Stop audio recording
    if audio_was_recording:
        try:
            recorder.stop_capture()
            recording_status['is_recording'] = False
            recording_status['current_job'] = None
            recording_status['start_time'] = None
            audio_stopped = True
        except Exception as e:
            errors.append(f"Audio: {str(e)}")

    # Stop video recording
    if video_was_recording:
        try:
            video_recorder.stop_video_recording()
            video_recording_status['is_recording'] = False
            video_recording_status['current_file'] = None
            video_recording_status['start_time'] = None
            video_stopped = True
        except Exception as e:
            errors.append(f"Video: {str(e)}")

    if errors:
        return jsonify({
            'success': False,
            'audio_stopped': audio_stopped,
            'video_stopped': video_stopped,
            'errors': errors
        }), 500

    return jsonify({
        'success': True,
        'audio_stopped': audio_stopped,
        'video_stopped': video_stopped
    })


@app.route('/api/schedule', methods=['POST'])
@login_required
def create_schedule():
    """Create new scheduled recording"""
    data = request.json or {}

    # Validate input parameters
    schema = {
        'start_time': {
            'type': 'datetime',
            'required': True
        },
        'duration': {
            'type': 'duration',
            'required': True,
            'allow_override': data.get('allow_override', False)
        },
        'name': {
            'type': 'string',
            'required': False,
            'default': 'Unnamed Recording',
            'max_length': 255,
            'allow_empty': False
        },
        'notes': {
            'type': 'string',
            'required': False,
            'default': '',
            'max_length': 1000,
            'allow_empty': True
        },
        'is_recurring': {
            'type': 'boolean',
            'required': False,
            'default': False
        },
        'recurrence_pattern': {
            'type': 'json',
            'required': False,
            'default': None
        },
        'allow_override': {
            'type': 'boolean',
            'required': False,
            'default': False
        },
        'capture_video': {
            'type': 'boolean',
            'required': False,
            'default': False
        }
    }

    valid, error_msg, validated = validation.validate_request_data(data, schema)
    if not valid:
        return jsonify({'error': error_msg}), 400

    try:
        # Convert recurrence_pattern back to JSON string if it's a dict
        recurrence_pattern = validated['recurrence_pattern']
        if recurrence_pattern is not None and isinstance(recurrence_pattern, dict):
            import json
            recurrence_pattern = json.dumps(recurrence_pattern)

        job_id = scheduler.create_job(
            start_time=validated['start_time'],
            duration=validated['duration'],
            name=validated['name'],
            notes=validated['notes'],
            is_recurring=validated['is_recurring'],
            recurrence_pattern=recurrence_pattern,
            allow_override=validated['allow_override'],
            capture_video=validated['capture_video']
        )
        return jsonify({'success': True, 'job_id': job_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/schedule/<job_id>', methods=['DELETE'])
@login_required
def delete_schedule(job_id):
    """Delete scheduled recording"""
    try:
        scheduler.delete_job(job_id)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/schedule/<job_id>', methods=['PUT'])
@login_required
def update_schedule(job_id):
    """Update existing scheduled recording"""
    data = request.json or {}

    # Validate input parameters (all optional for updates)
    schema = {
        'start_time': {
            'type': 'datetime',
            'required': False,
            'default': None
        },
        'duration': {
            'type': 'duration',
            'required': False,
            'default': None,
            'allow_none': True,  # None means don't update
            'allow_override': data.get('allow_override', False) if data.get('duration') is not None else False
        },
        'name': {
            'type': 'string',
            'required': False,
            'default': None,
            'max_length': 255
        },
        'notes': {
            'type': 'string',
            'required': False,
            'default': None,
            'max_length': 1000,
            'allow_empty': True
        },
        'is_recurring': {
            'type': 'boolean',
            'required': False,
            'default': None
        },
        'recurrence_pattern': {
            'type': 'json',
            'required': False,
            'default': None
        },
        'allow_override': {
            'type': 'boolean',
            'required': False,
            'default': None
        },
        'capture_video': {
            'type': 'boolean',
            'required': False,
            'default': None
        }
    }

    valid, error_msg, validated = validation.validate_request_data(data, schema)
    if not valid:
        return jsonify({'error': error_msg}), 400

    try:
        # Convert recurrence_pattern back to JSON string if it's a dict
        recurrence_pattern = validated['recurrence_pattern']
        if recurrence_pattern is not None and isinstance(recurrence_pattern, dict):
            import json
            recurrence_pattern = json.dumps(recurrence_pattern)

        scheduler.update_job(
            job_id=job_id,
            start_time=validated['start_time'],
            duration=validated['duration'],
            name=validated['name'],
            notes=validated['notes'],
            is_recurring=validated['is_recurring'],
            recurrence_pattern=recurrence_pattern,
            allow_override=validated['allow_override'],
            capture_video=validated['capture_video']
        )
        return jsonify({'success': True})
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/schedule/<job_id>/occurrence/<occurrence_date>', methods=['GET'])
@login_required
def get_occurrence_instance(job_id, occurrence_date):
    """
    Get or create instance for a specific occurrence of a recurring job.
    Automatically repairs missing instances for past occurrences.
    """
    try:
        # Ensure instance exists (will create if missing for past occurrence)
        instance, was_created = scheduler.ensure_instance_exists(job_id, occurrence_date)

        if instance is None:
            # Instance doesn't exist and shouldn't (future occurrence or invalid pattern)
            return jsonify({'instance': None, 'was_created': False}), 200

        return jsonify({
            'instance': instance,
            'was_created': was_created
        }), 200

    except Exception as e:
        logger.error(f"Error fetching/creating instance for {job_id} on {occurrence_date}: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/recordings')
@login_required
def recordings_page():
    """File browser interface"""
    recordings_dir = get_recordings_dir()
    files = []
    
    for file_path in sorted(recordings_dir.glob('*'), reverse=True):
        if file_path.is_file():
            stat = file_path.stat()
            files.append({
                'name': file_path.name,
                'size': stat.st_size,
                'size_mb': round(stat.st_size / (1024 * 1024), 2),
                'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'type': file_path.suffix
            })
    
    return render_template('recordings.html', files=files)


@app.route('/api/recordings/<filename>')
@login_required
def download_file(filename):
    """Download a recording file"""
    file_path = get_recordings_dir() / filename
    if not file_path.exists() or not file_path.is_file():
        return jsonify({'error': 'File not found'}), 404
    
    return send_file(file_path, as_attachment=True)


@app.route('/api/recordings/<filename>', methods=['DELETE'])
@login_required
def delete_file(filename):
    """Delete a recording file"""
    file_path = get_recordings_dir() / filename
    if not file_path.exists():
        return jsonify({'error': 'File not found'}), 404

    try:
        file_path.unlink()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/recordings/<filename>/analysis')
@login_required
def get_file_analysis(filename):
    """Get audio analysis results for a recording file"""
    try:
        # Fetch analysis for both channels
        results = db_utils.fetch_all(scheduler.DB_PATH, '''
            SELECT channel, analyzed_at, total_duration, non_silent_percentage,
                   mean_db, max_db, max_db_time, status, error_message
            FROM audio_analysis
            WHERE filename = ?
            ORDER BY channel
        ''', (filename,))

        if not results:
            return jsonify({'analyzed': False, 'message': 'No analysis available'})

        # Format response
        analysis_data = {
            'analyzed': True,
            'filename': filename,
            'channels': []
        }

        for row in results:
            channel_data = {
                'channel': row[0],  # 'left' or 'right'
                'analyzed_at': row[1],
                'total_duration': row[2],
                'non_silent_percentage': row[3],
                'mean_db': row[4],
                'max_db': row[5],
                'max_db_time': row[6],
                'status': row[7],
                'error_message': row[8]
            }
            analysis_data['channels'].append(channel_data)

        return jsonify(analysis_data)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/recordings/batch/delete', methods=['POST'])
@login_required
def batch_delete_files():
    """Delete multiple recording files"""
    data = request.json
    files = data.get('files', [])

    if not files:
        return jsonify({'error': 'No files specified'}), 400

    deleted = []
    errors = []

    for filename in files:
        file_path = get_recordings_dir() / filename
        if not file_path.exists():
            errors.append(f'{filename}: not found')
            continue

        try:
            file_path.unlink()
            deleted.append(filename)
        except Exception as e:
            errors.append(f'{filename}: {str(e)}')

    return jsonify({
        'success': len(errors) == 0,
        'deleted': deleted,
        'errors': errors
    })


@app.route('/api/recordings/batch/download', methods=['POST'])
@login_required
def batch_download_files():
    """Download multiple recording files as a zip archive"""
    import zipfile
    import tempfile
    import io

    data = request.json
    files = data.get('files', [])

    if not files:
        return jsonify({'error': 'No files specified'}), 400

    # Create zip file in memory
    zip_buffer = io.BytesIO()

    try:
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for filename in files:
                file_path = get_recordings_dir() / filename
                if file_path.exists() and file_path.is_file():
                    zip_file.write(file_path, filename)

        zip_buffer.seek(0)

        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f'recordings-{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Filename Configuration Routes
@app.route('/api/config/filename', methods=['GET'])
@login_required
def get_filename_config():
    """Get current filename configuration"""
    try:
        left_row = db_utils.fetch_one(scheduler.DB_PATH,
            "SELECT value FROM system_config WHERE key = 'channel_left_suffix'")
        left_suffix = left_row[0] if left_row else 'L'

        right_row = db_utils.fetch_one(scheduler.DB_PATH,
            "SELECT value FROM system_config WHERE key = 'channel_right_suffix'")
        right_suffix = right_row[0] if right_row else 'R'

        return jsonify({
            'left_suffix': left_suffix,
            'right_suffix': right_suffix
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/config/filename', methods=['POST'])
@login_required
def save_filename_config():
    """Save filename configuration"""
    data = request.json
    left_suffix = data.get('left_suffix', '').strip()
    right_suffix = data.get('right_suffix', '').strip()
    
    if not left_suffix or not right_suffix:
        return jsonify({'error': 'Both suffixes are required'}), 400
    
    if len(left_suffix) > 10 or len(right_suffix) > 10:
        return jsonify({'error': 'Suffixes must be 10 characters or less'}), 400
    
    try:
        def _update_config(conn, cursor):
            cursor.execute('''
                INSERT OR REPLACE INTO system_config (key, value, updated_at)
                VALUES ('channel_left_suffix', ?, datetime('now'))
            ''', (left_suffix,))

            cursor.execute('''
                INSERT OR REPLACE INTO system_config (key, value, updated_at)
                VALUES ('channel_right_suffix', ?, datetime('now'))
            ''', (right_suffix,))

        db_utils.execute_transaction(scheduler.DB_PATH, _update_config)

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Storage Path Configuration Routes
@app.route('/api/config/storage', methods=['GET'])
@login_required
def get_storage_config():
    """Get current storage path configuration"""
    storage_path = scheduler.get_system_config('storage_path', '/mnt/usb_recorder')

    # Check if path exists and is writable
    path_obj = Path(storage_path)
    exists = path_obj.exists()
    is_writable = exists and os.access(storage_path, os.W_OK)

    return jsonify({
        'storage_path': storage_path,
        'exists': exists,
        'is_writable': is_writable
    })


@app.route('/api/config/storage', methods=['POST'])
@login_required
def save_storage_config():
    """Save storage path configuration"""
    data = request.json
    storage_path = data.get('storage_path', '').strip()

    if not storage_path:
        return jsonify({'error': 'Storage path is required'}), 400

    # Validate path
    path_obj = Path(storage_path)

    # Try to create the directory if it doesn't exist
    try:
        path_obj.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return jsonify({'error': f'Cannot create directory: {e}'}), 400

    # Check if writable
    if not os.access(storage_path, os.W_OK):
        return jsonify({'error': 'Directory is not writable'}), 400

    scheduler.set_system_config('storage_path', storage_path)

    return jsonify({'success': True})


# Directory Browser API Endpoints
@app.route('/api/directories/list', methods=['POST'])
@login_required
def list_directories():
    """
    List directories at a given path for the directory browser.
    Returns only directories (not files), excluding hidden folders.
    """
    import os
    from pathlib import Path

    data = request.get_json()
    requested_path = data.get('path', '/')

    # Validate path using existing validation
    valid, error, validated_path = validate_path(requested_path, "Path", allow_relative=False)
    if not valid:
        return jsonify({'success': False, 'error': error}), 400

    try:
        # Resolve path to prevent traversal attacks
        path_obj = Path(validated_path).resolve()

        # Check if path exists and is a directory
        if not path_obj.exists():
            return jsonify({'success': False, 'error': 'Directory does not exist'}), 404

        if not path_obj.is_dir():
            return jsonify({'success': False, 'error': 'Path is not a directory'}), 400

        # Get parent path (None if at root)
        parent_path = str(path_obj.parent) if path_obj.parent != path_obj else None

        # List directories only, excluding hidden folders
        directories = []
        try:
            for entry in sorted(path_obj.iterdir()):
                # Skip hidden folders (starting with .)
                if entry.name.startswith('.'):
                    continue

                # Only include directories
                if entry.is_dir():
                    # Check if directory is writable
                    is_writable = os.access(str(entry), os.W_OK)

                    directories.append({
                        'name': entry.name,
                        'path': str(entry),
                        'writable': is_writable
                    })
        except PermissionError:
            return jsonify({
                'success': False,
                'error': 'Permission denied: Cannot read directory contents'
            }), 403

        return jsonify({
            'success': True,
            'current_path': str(path_obj),
            'parent_path': parent_path,
            'directories': directories
        })

    except Exception as e:
        app.logger.error(f"Error listing directories: {str(e)}")
        return jsonify({'success': False, 'error': f'Failed to list directories: {str(e)}'}), 500


@app.route('/api/directories/create', methods=['POST'])
@login_required
def create_directory():
    """
    Create a new directory within a parent path.
    Validates folder name and checks permissions.
    """
    import os
    from pathlib import Path
    import re

    data = request.get_json()
    parent_path = data.get('parent_path')
    folder_name = data.get('folder_name')

    # Validate required parameters
    if not parent_path or not folder_name:
        return jsonify({'success': False, 'error': 'parent_path and folder_name are required'}), 400

    # Validate parent path
    valid, error, validated_parent = validate_path(parent_path, "Parent path", allow_relative=False)
    if not valid:
        return jsonify({'success': False, 'error': error}), 400

    # Validate folder name - alphanumeric, underscore, hyphen only
    folder_name_pattern = r'^[a-zA-Z0-9_\-]+$'
    if not re.match(folder_name_pattern, folder_name):
        return jsonify({
            'success': False,
            'error': 'Folder name can only contain letters, numbers, underscores, and hyphens'
        }), 400

    # Reject names starting with . or containing path separators
    if folder_name.startswith('.') or '/' in folder_name or '\\' in folder_name:
        return jsonify({
            'success': False,
            'error': 'Invalid folder name: cannot start with . or contain path separators'
        }), 400

    try:
        # Resolve parent path to prevent traversal
        parent_obj = Path(validated_parent).resolve()

        # Check if parent exists and is a directory
        if not parent_obj.exists():
            return jsonify({'success': False, 'error': 'Parent directory does not exist'}), 404

        if not parent_obj.is_dir():
            return jsonify({'success': False, 'error': 'Parent path is not a directory'}), 400

        # Check if parent is writable
        if not os.access(str(parent_obj), os.W_OK):
            return jsonify({'success': False, 'error': 'Parent directory is not writable'}), 403

        # Construct new directory path
        new_dir_path = parent_obj / folder_name

        # Check if directory already exists
        if new_dir_path.exists():
            return jsonify({'success': False, 'error': 'Directory already exists'}), 409

        # Create the directory
        new_dir_path.mkdir(mode=0o755, parents=False)

        # Log the creation
        username = session.get('username', 'unknown')
        app.logger.info(f"Directory created by {username}: {str(new_dir_path)}")

        return jsonify({
            'success': True,
            'path': str(new_dir_path),
            'name': folder_name
        })

    except PermissionError:
        return jsonify({'success': False, 'error': 'Permission denied: Cannot create directory'}), 403
    except Exception as e:
        app.logger.error(f"Error creating directory: {str(e)}")
        return jsonify({'success': False, 'error': f'Failed to create directory: {str(e)}'}), 500


# Calendar View Route (also accessible via /calendar for backwards compatibility)
@app.route('/calendar')
@login_required
def calendar_page():
    """Multi-week calendar view - redirects to root"""
    return redirect(url_for('index'))


# Settings Page Route
@app.route('/settings')
@login_required
def settings_page():
    """System settings interface"""
    # Get current audio device config
    audio_device = scheduler.get_system_config('audio_device', 'auto')
    return render_template('settings.html', current_device=audio_device)


# Audio Device Configuration API
@app.route('/api/audio/devices', methods=['GET'])
@login_required
def get_audio_devices():
    """List available audio devices"""
    devices = recorder.get_available_audio_devices()
    current_device = scheduler.get_system_config('audio_device', 'auto')
    
    # Determine actual device being used
    if current_device == 'auto':
        actual_device = recorder.auto_detect_audio_device()
    else:
        actual_device = current_device
    
    return jsonify({
        'devices': devices,
        'current_device': current_device,
        'actual_device': actual_device,
        'auto_detected': recorder.auto_detect_audio_device()
    })


@app.route('/api/audio/config', methods=['GET'])
@login_required
def get_audio_config():
    """Get current audio device configuration"""
    current_device = scheduler.get_system_config('audio_device', 'auto')
    
    # Get device info
    if current_device == 'auto':
        actual_device = recorder.auto_detect_audio_device()
    else:
        actual_device = current_device
    
    # Find device details
    devices = recorder.get_available_audio_devices()
    device_info = None
    for dev in devices:
        if dev['alsa_id'] == actual_device:
            device_info = dev
            break
    
    return jsonify({
        'current_device': current_device,
        'actual_device': actual_device,
        'device_info': device_info,
        'is_connected': device_info is not None
    })


@app.route('/api/audio/config', methods=['POST'])
@login_required
def set_audio_config():
    """Set audio device configuration"""
    data = request.json
    device = data.get('device', 'auto')
    
    # Validate device exists if not auto
    if device != 'auto':
        devices = recorder.get_available_audio_devices()
        valid = any(d['alsa_id'] == device for d in devices)
        if not valid:
            return jsonify({'error': 'Invalid device - not found in system'}), 400
    
    # Save configuration
    scheduler.set_system_config('audio_device', device)
    
    return jsonify({
        'success': True,
        'device': device,
        'message': 'Audio device configuration updated'
    })


@app.route('/api/audio/test', methods=['POST'])
@login_required
def test_audio_device():
    """Test audio device with short recording"""
    data = request.json
    device = data.get('device', 'auto')
    duration = data.get('duration', 3)
    
    # Resolve device
    if device == 'auto':
        device = recorder.auto_detect_audio_device()
    
    # Test recording to /tmp
    test_file = f'/tmp/audio_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.wav'
    
    cmd = [
        'arecord',
        '-D', device,
        '-f', 'S16_LE',
        '-r', '48000',
        '-c', '2',
        '-d', str(duration),
        test_file
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=duration+2, text=True)
        
        if result.returncode == 0 and Path(test_file).exists():
            file_size = Path(test_file).stat().st_size
            Path(test_file).unlink()  # Clean up
            
            return jsonify({
                'success': True,
                'device': device,
                'duration': duration,
                'file_size': file_size,
                'file_size_mb': round(file_size / (1024 * 1024), 2)
            })
        else:
            return jsonify({
                'success': False,
                'error': result.stderr or 'Recording failed',
                'device': device
            }), 400
            
    except subprocess.TimeoutExpired:
        return jsonify({
            'success': False,
            'error': 'Test recording timed out'
        }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# Log Viewer API
def _get_log_file_path(log_type):
    """Get the file path for a given log type"""
    home_log_dir = Path.home() / '.audio-recorder'
    var_log_dir = Path('/var/log/audio-recorder')

    log_paths = {
        'app': var_log_dir / 'app.log',
        'error': var_log_dir / 'error.log',
        'recorder': home_log_dir / 'recorder.log',
        'scheduler': home_log_dir / 'scheduler.log',
        'ffmpeg': home_log_dir / 'ffmpeg.log'
    }
    return log_paths.get(log_type, var_log_dir / f'{log_type}.log')


@app.route('/api/logs/paths', methods=['GET'])
@login_required
def get_log_paths():
    """Get all log file paths for display in Settings"""
    home_log_dir = Path.home() / '.audio-recorder'
    var_log_dir = Path('/var/log/audio-recorder')

    return jsonify({
        'app': str(var_log_dir / 'app.log'),
        'error': str(var_log_dir / 'error.log'),
        'recorder': str(home_log_dir / 'recorder.log'),
        'scheduler': str(home_log_dir / 'scheduler.log'),
        'ffmpeg': str(home_log_dir / 'ffmpeg.log')
    })


@app.route('/api/logs', methods=['GET'])
@login_required
def get_logs():
    """Get application logs"""
    log_type = request.args.get('type', 'app')
    lines = int(request.args.get('lines', 100))

    log_file = _get_log_file_path(log_type)

    if not log_file.exists():
        return jsonify({
            'logs': [],
            'message': 'Log file not found',
            'file_path': str(log_file)
        })

    try:
        # Read last N lines
        with open(log_file, 'r') as f:
            all_lines = f.readlines()
            log_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines

        return jsonify({
            'logs': log_lines,
            'total_lines': len(all_lines),
            'showing_lines': len(log_lines),
            'log_type': log_type,
            'file_path': str(log_file)
        })
    except Exception as e:
        return jsonify({'error': str(e), 'file_path': str(log_file)}), 500


# Backup/Restore API Endpoints (Refactored)
@app.route('/api/export/<export_type>', methods=['GET'])
@login_required
def export_data(export_type):
    """
    Export schedules or configuration as downloadable file
    
    Args:
        export_type: 'schedules' or 'config'
    """
    if export_type not in ['schedules', 'config']:
        return jsonify({'error': 'Invalid export type. Use "schedules" or "config"'}), 400
    
    import tempfile
    from datetime import datetime as dt
    
    timestamp = dt.now().strftime('%Y%m%d_%H%M%S')
    
    # Determine file extension and filename
    extension = '.sched' if export_type == 'schedules' else '.conf'
    filename = f'audio-recorder-{export_type}-{timestamp}{extension}'
    
    try:
        # Create temporary database copy
        with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as tmp:
            tmp_path = tmp.name
        
        import shutil
        shutil.copy(scheduler.DB_PATH, tmp_path)

        # Remove unwanted tables based on export type
        def _cleanup_export(conn, cursor):
            if export_type == 'schedules':
                # Keep only schedules
                cursor.execute("DROP TABLE IF EXISTS system_config")
                cursor.execute("DROP TABLE IF EXISTS recording_templates")
            else:  # config
                # Keep only system configuration
                cursor.execute("DROP TABLE IF EXISTS scheduled_jobs")
                cursor.execute("DROP TABLE IF EXISTS recording_templates")

        db_utils.execute_transaction(tmp_path, _cleanup_export)

        return send_file(tmp_path, as_attachment=True, download_name=filename)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/import/<import_type>', methods=['POST'])
@login_required
def import_data(import_type):
    """
    Import schedules or configuration from uploaded file with auto-backup
    
    Args:
        import_type: 'schedules' or 'config'
    """
    if import_type not in ['schedules', 'config']:
        return jsonify({'error': 'Invalid import type. Use "schedules" or "config"'}), 400
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    expected_ext = '.sched' if import_type == 'schedules' else '.conf'
    
    if not file.filename.endswith(expected_ext):
        return jsonify({'error': f'Invalid file type. Must be {expected_ext} file'}), 400
    
    try:
        # Create auto-backup first
        backup_dir = Path.home() / '.audio-recorder' / 'backups'
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_filename = f'{import_type}{expected_ext}.last'
        backup_path = backup_dir / backup_filename

        # Backup current state
        conn_src = None
        conn_backup = None
        try:
            conn_src = sqlite3.connect(scheduler.DB_PATH)
            conn_backup = sqlite3.connect(str(backup_path))
            conn_src.backup(conn_backup)

            # Remove unwanted tables from backup
            cursor_backup = conn_backup.cursor()
            if import_type == 'schedules':
                cursor_backup.execute("DROP TABLE IF EXISTS system_config")
                cursor_backup.execute("DROP TABLE IF EXISTS recording_templates")
            else:  # config
                cursor_backup.execute("DROP TABLE IF EXISTS scheduled_jobs")
                cursor_backup.execute("DROP TABLE IF EXISTS recording_templates")

            conn_backup.commit()
        finally:
            if conn_src:
                conn_src.close()
            if conn_backup:
                conn_backup.close()

        # Save and process uploaded file
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=expected_ext) as tmp:
            file.save(tmp.name)
            upload_path = tmp.name

        # Import data
        conn_upload = None
        conn_main = None
        try:
            conn_upload = sqlite3.connect(upload_path)
            conn_main = sqlite3.connect(scheduler.DB_PATH)
            cursor_main = conn_main.cursor()
            cursor_upload = conn_upload.cursor()

            if import_type == 'schedules':
                # Clear and import schedules
                cursor_main.execute("DELETE FROM scheduled_jobs")

                # Copy scheduled_jobs
                cursor_upload.execute("SELECT * FROM scheduled_jobs")
                for row in cursor_upload.fetchall():
                    placeholders = ','.join(['?' for _ in row])
                    cursor_main.execute(f"INSERT INTO scheduled_jobs VALUES ({placeholders})", row)

                # Reload scheduler
                conn_main.commit()

                scheduler.scheduler.remove_all_jobs()
                scheduler.restore_jobs_on_startup()

            else:  # config
                # Clear and import configuration
                cursor_main.execute("DELETE FROM system_config")

                cursor_upload.execute("SELECT * FROM system_config")
                for row in cursor_upload.fetchall():
                    placeholders = ','.join(['?' for _ in row])
                    cursor_main.execute(f"INSERT INTO system_config VALUES ({placeholders})", row)

                conn_main.commit()
        finally:
            if conn_upload:
                conn_upload.close()
            if conn_main:
                conn_main.close()

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/revert/<revert_type>', methods=['POST'])
@login_required
def revert_data(revert_type):
    """
    Revert to last backup before import
    
    Args:
        revert_type: 'schedules' or 'config'
    """
    if revert_type not in ['schedules', 'config']:
        return jsonify({'error': 'Invalid revert type. Use "schedules" or "config"'}), 400
    
    extension = '.sched' if revert_type == 'schedules' else '.conf'
    backup_path = Path.home() / '.audio-recorder' / 'backups' / f'{revert_type}{extension}.last'
    
    if not backup_path.exists():
        return jsonify({'error': 'No backup available'}), 404
    
    try:
        conn_backup = None
        conn_main = None
        try:
            conn_backup = sqlite3.connect(str(backup_path))
            conn_main = sqlite3.connect(scheduler.DB_PATH)
            cursor_main = conn_main.cursor()
            cursor_backup = conn_backup.cursor()

            if revert_type == 'schedules':
                # Clear and restore schedules
                cursor_main.execute("DELETE FROM scheduled_jobs")

                cursor_backup.execute("SELECT * FROM scheduled_jobs")
                for row in cursor_backup.fetchall():
                    placeholders = ','.join(['?' for _ in row])
                    cursor_main.execute(f"INSERT INTO scheduled_jobs VALUES ({placeholders})", row)

                conn_main.commit()

                # Reload scheduler
                scheduler.scheduler.remove_all_jobs()
                scheduler.restore_jobs_on_startup()

            else:  # config
                # Clear and restore configuration
                cursor_main.execute("DELETE FROM system_config")

                cursor_backup.execute("SELECT * FROM system_config")
                for row in cursor_backup.fetchall():
                    placeholders = ','.join(['?' for _ in row])
                    cursor_main.execute(f"INSERT INTO system_config VALUES ({placeholders})", row)

                conn_main.commit()
        finally:
            if conn_backup:
                conn_backup.close()
            if conn_main:
                conn_main.close()

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/revert/available', methods=['GET'])
@login_required
def check_revert_available():
    """Check if revert backups exist for schedules and/or config"""
    backup_dir = Path.home() / '.audio-recorder' / 'backups'

    return jsonify({
        'schedules_available': (backup_dir / 'schedules.sched.last').exists(),
        'config_available': (backup_dir / 'config.conf.last').exists()
    })


# ============================================================================
# Disk Space Monitoring API
# ============================================================================

@app.route('/api/system/disk', methods=['GET'])
@login_required
def get_disk_space():
    """
    Get disk space information for the recordings directory.

    Returns:
        - total_gb: Total disk space in GB
        - used_gb: Used disk space in GB
        - free_gb: Free disk space in GB
        - percent_used: Percentage of disk used
        - hours_remaining: Estimated recording hours remaining
        - low_space_warning: True if less than 10 hours of recording space
        - scheduled_warning: True if scheduled recordings would fill disk
    """
    import shutil

    recordings_dir = get_recordings_dir()

    try:
        disk_usage = shutil.disk_usage(recordings_dir)

        total_gb = disk_usage.total / (1024 ** 3)
        used_gb = disk_usage.used / (1024 ** 3)
        free_gb = disk_usage.free / (1024 ** 3)
        percent_used = (disk_usage.used / disk_usage.total) * 100

        # Calculate estimated recording hours remaining
        # WAV at 48kHz, 16-bit, stereo = ~345 MB/hour per channel
        # Dual mono = 2 channels = ~690 MB/hour total
        mb_per_hour = 690
        free_mb = disk_usage.free / (1024 ** 2)
        hours_remaining = free_mb / mb_per_hour

        # Low space warning if less than 10 hours of recording space
        low_space_warning = hours_remaining < 10

        # Check if scheduled recordings would fill disk
        scheduled_warning = False
        scheduled_hours = 0

        try:
            jobs = scheduler.get_all_jobs()
            now = datetime.now()

            for job in jobs:
                if job.get('status') == 'pending':
                    # Calculate hours for this job
                    duration_hours = job.get('duration', 0) / 3600

                    if job.get('is_recurring'):
                        # For recurring jobs, estimate next 7 days worth
                        scheduled_hours += duration_hours * 7
                    else:
                        # One-time job
                        job_time = datetime.fromisoformat(job.get('start_time', ''))
                        if job_time > now:
                            scheduled_hours += duration_hours

            # Warning if scheduled recordings would use more than available space
            scheduled_warning = scheduled_hours > hours_remaining

        except Exception as e:
            # If we can't check scheduled jobs, just skip this warning
            pass

        return jsonify({
            'success': True,
            'total_gb': round(total_gb, 2),
            'used_gb': round(used_gb, 2),
            'free_gb': round(free_gb, 2),
            'percent_used': round(percent_used, 1),
            'hours_remaining': round(hours_remaining, 1),
            'low_space_warning': low_space_warning,
            'scheduled_warning': scheduled_warning,
            'scheduled_hours': round(scheduled_hours, 1)
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/system/time', methods=['GET'])
@login_required
def get_server_time():
    """
    Get current server time in ISO format.
    Used by frontend to sync time calculations and avoid client clock drift issues.

    Returns:
        - server_time: Current server time in ISO format
    """
    return jsonify({
        'success': True,
        'server_time': datetime.now().isoformat()
    })


# ============================================================================
# Video Recording & Camera Control API
# ============================================================================

@app.route('/camera')
@login_required
def camera_page():
    """Camera control and video recording interface"""
    return render_template('camera.html')


@app.route('/api/camera/preset/<int:preset_id>', methods=['GET', 'POST'])
@login_required
def call_camera_preset(preset_id):
    """
    Call a PTZ preset on the camera

    Args:
        preset_id: Preset number (1-255)
    """
    success, message = video_recorder.call_camera_preset(preset_id)

    if success:
        return jsonify({'success': True, 'message': message})
    else:
        return jsonify({'success': False, 'error': message}), 400


@app.route('/api/camera/config', methods=['GET'])
@login_required
def get_camera_config():
    """Get camera configuration"""
    config = video_recorder.get_camera_config()

    # Don't send password in plain text
    config_safe = config.copy()
    config_safe['camera_password'] = '****' if config['camera_password'] else ''

    return jsonify(config_safe)


@app.route('/api/camera/config', methods=['POST'])
@login_required
def set_camera_config():
    """Save camera configuration"""
    data = request.json

    # Save each config value
    if 'camera_ip' in data:
        video_recorder.set_camera_config('camera_ip', data['camera_ip'].strip())

    if 'camera_username' in data:
        video_recorder.set_camera_config('camera_username', data['camera_username'].strip())

    if 'camera_password' in data and data['camera_password'] != '****':
        video_recorder.set_camera_config('camera_password', data['camera_password'])

    if 'preset_names' in data:
        video_recorder.set_preset_names(data['preset_names'])

    return jsonify({'success': True, 'message': 'Camera configuration saved'})


@app.route('/api/camera/test', methods=['POST'])
@login_required
def test_camera_connection():
    """Test connection to the camera"""
    success, message = video_recorder.test_camera_connection()

    if success:
        return jsonify({'success': True, 'message': message})
    else:
        return jsonify({'success': False, 'error': message}), 400


@app.route('/api/camera/stream', methods=['GET'])
@login_required
def get_stream_info():
    """Get live stream viewing information"""
    return jsonify(video_recorder.get_live_stream_info())


@app.route('/api/video/status', methods=['GET'])
@login_required
def get_video_status():
    """Get combined video recording and transcode status"""
    # Sync with actual recorder state
    actual_status = video_recorder.get_video_recording_status()
    transcode_status = video_recorder.get_transcode_status()

    # Update global status tracker
    video_recording_status['is_recording'] = actual_status['is_recording']
    video_recording_status['current_file'] = actual_status['current_file']
    video_recording_status['start_time'] = actual_status['start_time']

    return jsonify({
        'recording': actual_status,
        'transcode': transcode_status
    })


@app.route('/api/video/start', methods=['POST'])
@login_required
def start_video_recording():
    """Start video recording from RTSP stream"""
    data = request.json or {}

    # Validate input parameters
    schema = {
        'duration': {
            'type': 'duration',
            'required': False,
            'default': None,
            'allow_none': True,  # None means indefinite recording
            'allow_override': False
        }
    }

    valid, error_msg, validated = validation.validate_request_data(data, schema)
    if not valid:
        return jsonify({'error': error_msg}), 400

    duration = validated['duration']

    if video_recorder.is_video_recording():
        return jsonify({'error': 'Video recording already in progress'}), 400

    try:
        result = video_recorder.start_video_recording(duration)

        video_recording_status['is_recording'] = True
        video_recording_status['current_file'] = result['file']
        video_recording_status['start_time'] = datetime.now().isoformat()

        return jsonify({
            'success': True,
            'file': result['file'],
            'timestamp': result['timestamp']
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/video/stop', methods=['POST'])
@login_required
def stop_video_recording():
    """Stop video recording (gracefully finalize MP4)"""
    if not video_recorder.is_video_recording():
        return jsonify({'error': 'No video recording in progress'}), 400

    try:
        result = video_recorder.stop_video_recording()

        video_recording_status['is_recording'] = False
        video_recording_status['current_file'] = None
        video_recording_status['start_time'] = None

        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/video/storage', methods=['GET'])
@login_required
def get_video_storage():
    """Get video storage disk space information"""
    return jsonify(video_recorder.get_storage_info())


@app.route('/api/video/files', methods=['GET'])
@login_required
def list_video_files():
    """List video files (raw and processed)"""
    return jsonify(video_recorder.list_video_files())


@app.route('/api/video/transcode/cancel', methods=['POST'])
@login_required
def cancel_transcode():
    """Cancel ongoing video transcoding"""
    if video_recorder.cancel_transcode():
        return jsonify({'success': True, 'message': 'Transcode cancelled'})
    else:
        return jsonify({'error': 'No transcoding in progress'}), 400


if __name__ == '__main__':
    # Run on all interfaces for headless access
    app.run(host='0.0.0.0', port=5000, debug=False)
