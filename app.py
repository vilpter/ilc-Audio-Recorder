#!/usr/bin/env python3
"""
Headless Dual-Mono Audio Recording System
Main Flask Application
"""

from flask import Flask, render_template, jsonify, request, send_file
from pathlib import Path
import json
import subprocess
from datetime import datetime
import recorder
import scheduler
import templates_manager

app = Flask(__name__)
app.config['RECORDINGS_DIR'] = Path.home() / 'recordings'
app.config['RECORDINGS_DIR'].mkdir(exist_ok=True)

# Global status tracker
recording_status = {
    'is_recording': False,
    'current_job': None,
    'start_time': None
}


@app.route('/')
def index():
    """Dashboard - show current status and manual controls"""
    return render_template('index.html', status=recording_status)


@app.route('/api/status')
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
def schedule_page():
    """Scheduling interface"""
    jobs = scheduler.get_all_jobs()
    return render_template('schedule.html', jobs=jobs)


@app.route('/api/schedule', methods=['POST'])
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
            template_id=data.get('template_id'),
            allow_override=data.get('allow_override', False)
        )
        return jsonify({'success': True, 'job_id': job_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/schedule/<job_id>', methods=['DELETE'])
def delete_schedule(job_id):
    """Delete scheduled recording"""
    try:
        scheduler.delete_job(job_id)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/recordings')
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
def download_file(filename):
    """Download a recording file"""
    file_path = app.config['RECORDINGS_DIR'] / filename
    if not file_path.exists() or not file_path.is_file():
        return jsonify({'error': 'File not found'}), 404
    
    return send_file(file_path, as_attachment=True)


@app.route('/api/recordings/<filename>', methods=['DELETE'])
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


# Template Management Routes
@app.route('/templates')
def templates_page():
    """Template management interface"""
    templates = templates_manager.get_all_templates()
    return render_template('templates_mgmt.html', templates=templates)


@app.route('/api/templates', methods=['GET'])
def get_templates():
    """Get all templates"""
    templates = templates_manager.get_all_templates()
    return jsonify(templates)


@app.route('/api/templates', methods=['POST'])
def create_template():
    """Create new template"""
    data = request.json
    try:
        template_id = templates_manager.create_template(
            name=data['name'],
            duration=data['duration'],
            recurrence_pattern=data.get('recurrence_pattern'),
            notes=data.get('notes', '')
        )
        return jsonify({'success': True, 'template_id': template_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/templates/<template_id>', methods=['GET'])
def get_template(template_id):
    """Get specific template"""
    template = templates_manager.get_template(template_id)
    if not template:
        return jsonify({'error': 'Template not found'}), 404
    return jsonify(template)


@app.route('/api/templates/<template_id>', methods=['PUT'])
def update_template(template_id):
    """Update template"""
    data = request.json
    try:
        templates_manager.update_template(
            template_id=template_id,
            name=data.get('name'),
            duration=data.get('duration'),
            recurrence_pattern=data.get('recurrence_pattern'),
            notes=data.get('notes')
        )
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/templates/<template_id>', methods=['DELETE'])
def delete_template(template_id):
    """Delete template"""
    try:
        templates_manager.delete_template(template_id)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Filename Configuration Routes
@app.route('/api/config/filename', methods=['GET'])
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


# Calendar View Route
@app.route('/calendar')
def calendar_page():
    """Multi-week calendar view"""
    # Get all scheduled jobs for calendar display
    jobs = scheduler.get_all_jobs()
    return render_template('calendar.html', jobs=jobs)


# Settings Page Route
@app.route('/settings')
def settings_page():
    """System settings interface"""
    # Get current audio device config
    audio_device = scheduler.get_system_config('audio_device', 'auto')
    return render_template('settings.html', current_device=audio_device)


# Audio Device Configuration API
@app.route('/api/audio/devices', methods=['GET'])
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
            # Keep only schedules and templates
            cursor.execute("DROP TABLE IF EXISTS system_config")
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
            # Clear and import schedules/templates
            cursor_main.execute("DELETE FROM scheduled_jobs")
            cursor_main.execute("DELETE FROM recording_templates")
            
            # Copy scheduled_jobs
            cursor_upload.execute("SELECT * FROM scheduled_jobs")
            for row in cursor_upload.fetchall():
                placeholders = ','.join(['?' for _ in row])
                cursor_main.execute(f"INSERT INTO scheduled_jobs VALUES ({placeholders})", row)
            
            # Copy recording_templates
            cursor_upload.execute("SELECT * FROM recording_templates")
            for row in cursor_upload.fetchall():
                placeholders = ','.join(['?' for _ in row])
                cursor_main.execute(f"INSERT INTO recording_templates VALUES ({placeholders})", row)
            
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
            # Clear and restore schedules/templates
            cursor_main.execute("DELETE FROM scheduled_jobs")
            cursor_main.execute("DELETE FROM recording_templates")
            
            cursor_backup.execute("SELECT * FROM scheduled_jobs")
            for row in cursor_backup.fetchall():
                placeholders = ','.join(['?' for _ in row])
                cursor_main.execute(f"INSERT INTO scheduled_jobs VALUES ({placeholders})", row)
            
            cursor_backup.execute("SELECT * FROM recording_templates")
            for row in cursor_backup.fetchall():
                placeholders = ','.join(['?' for _ in row])
                cursor_main.execute(f"INSERT INTO recording_templates VALUES ({placeholders})", row)
            
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
