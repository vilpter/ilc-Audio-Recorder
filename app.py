#!/usr/bin/env python3
"""
Headless Dual-Mono Audio Recording System
Main Flask Application
"""

from flask import Flask, render_template, jsonify, request, send_file, redirect, url_for, flash
from flask_login import login_required, login_user, logout_user, current_user
from pathlib import Path
import json
import subprocess
import sqlite3
from datetime import datetime
import recorder
import scheduler
import auth

app = Flask(__name__)
app.config['RECORDINGS_DIR'] = Path.home() / 'recordings'
app.config['RECORDINGS_DIR'].mkdir(exist_ok=True)

# Session configuration
app.secret_key = auth.generate_secret_key()

# Initialize Flask-Login
auth.login_manager.init_app(app)

# Initialize auth database
auth.init_auth_db()

# Global status tracker
recording_status = {
    'is_recording': False,
    'current_job': None,
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
    jobs = scheduler.get_all_jobs()
    return render_template('calendar.html', jobs=jobs)


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
    """Manual recording start"""
    data = request.json
    duration = data.get('duration', 3600)  # Default 1 hour
    allow_override = data.get('allow_override', False)
    
    if recording_status['is_recording']:
        return jsonify({'error': 'Recording already in progress'}), 400
    
    try:
        job_id = recorder.start_capture(duration, allow_override=allow_override)
        recording_status['is_recording'] = True
        recording_status['current_job'] = job_id
        recording_status['start_time'] = datetime.now().isoformat()
        return jsonify({'success': True, 'job_id': job_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/record/stop', methods=['POST'])
@login_required
def stop_recording():
    """Manual recording stop"""
    # Check actual recorder state, not cached status
    if not recorder.is_recording():
        return jsonify({'error': 'No recording in progress'}), 400
    
    try:
        recorder.stop_capture()
        recording_status['is_recording'] = False
        recording_status['current_job'] = None
        recording_status['start_time'] = None
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/schedule')
@login_required
def schedule_page():
    """Scheduling interface"""
    jobs = scheduler.get_all_jobs()
    return render_template('schedule.html', jobs=jobs)


@app.route('/api/schedule', methods=['POST'])
@login_required
def create_schedule():
    """Create new scheduled recording"""
    data = request.json
    try:
        job_id = scheduler.create_job(
            start_time=data['start_time'],
            duration=data['duration'],
            name=data.get('name', 'Unnamed Recording'),
            notes=data.get('notes', ''),
            is_recurring=data.get('is_recurring', False),
            recurrence_pattern=data.get('recurrence_pattern'),
            allow_override=data.get('allow_override', False)
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


@app.route('/recordings')
@login_required
def recordings_page():
    """File browser interface"""
    recordings_dir = app.config['RECORDINGS_DIR']
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
    file_path = app.config['RECORDINGS_DIR'] / filename
    if not file_path.exists() or not file_path.is_file():
        return jsonify({'error': 'File not found'}), 404
    
    return send_file(file_path, as_attachment=True)


@app.route('/api/recordings/<filename>', methods=['DELETE'])
@login_required
def delete_file(filename):
    """Delete a recording file"""
    file_path = app.config['RECORDINGS_DIR'] / filename
    if not file_path.exists():
        return jsonify({'error': 'File not found'}), 404
    
    try:
        file_path.unlink()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Filename Configuration Routes
@app.route('/api/config/filename', methods=['GET'])
@login_required
def get_filename_config():
    """Get current filename configuration"""
    try:
        conn = sqlite3.connect(scheduler.DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("SELECT value FROM system_config WHERE key = 'channel_left_suffix'")
        left_row = cursor.fetchone()
        left_suffix = left_row[0] if left_row else 'L'
        
        cursor.execute("SELECT value FROM system_config WHERE key = 'channel_right_suffix'")
        right_row = cursor.fetchone()
        right_suffix = right_row[0] if right_row else 'R'
        
        conn.close()
        
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
        conn = sqlite3.connect(scheduler.DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO system_config (key, value, updated_at)
            VALUES ('channel_left_suffix', ?, datetime('now'))
        ''', (left_suffix,))
        
        cursor.execute('''
            INSERT OR REPLACE INTO system_config (key, value, updated_at)
            VALUES ('channel_right_suffix', ?, datetime('now'))
        ''', (right_suffix,))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


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
@app.route('/api/logs', methods=['GET'])
@login_required
def get_logs():
    """Get application logs"""
    log_type = request.args.get('type', 'app')  # 'app' or 'error'
    lines = int(request.args.get('lines', 100))
    
    log_file = Path('/var/log/audio-recorder') / f'{log_type}.log'
    
    if not log_file.exists():
        return jsonify({'logs': [], 'message': 'Log file not found'})
    
    try:
        # Read last N lines
        with open(log_file, 'r') as f:
            all_lines = f.readlines()
            log_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
        
        return jsonify({
            'logs': log_lines,
            'total_lines': len(all_lines),
            'showing_lines': len(log_lines),
            'log_type': log_type
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


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
        conn = sqlite3.connect(tmp_path)
        cursor = conn.cursor()
        
        if export_type == 'schedules':
            # Keep only schedules
            cursor.execute("DROP TABLE IF EXISTS system_config")
            cursor.execute("DROP TABLE IF EXISTS recording_templates")
        else:  # config
            # Keep only system configuration
            cursor.execute("DROP TABLE IF EXISTS scheduled_jobs")
            cursor.execute("DROP TABLE IF EXISTS recording_templates")
        
        conn.commit()
        conn.close()
        
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
        conn_src.close()
        conn_backup.close()
        
        # Save and process uploaded file
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=expected_ext) as tmp:
            file.save(tmp.name)
            upload_path = tmp.name
        
        # Import data
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
            conn_upload.close()
            conn_main.close()

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
            conn_upload.close()
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
            conn_backup.close()
            conn_main.close()

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
            conn_backup.close()
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


if __name__ == '__main__':
    # Run on all interfaces for headless access
    app.run(host='0.0.0.0', port=5000, debug=False)
