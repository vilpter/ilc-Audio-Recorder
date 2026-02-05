#!/usr/bin/env python3
"""
Authentication Module for Audio Recorder
Handles user management and session authentication
"""

import sqlite3
import secrets
from pathlib import Path
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin
import db_utils

# Database path - same directory as scheduler database
AUTH_DB_PATH = Path.home() / '.audio-recorder' / 'auth.db'

# User roles - defines permission levels
ROLE_VIEWER = 'viewer'      # No Settings access
ROLE_OPERATOR = 'operator'  # Limited Settings (Audio device, Camera config only)
ROLE_ADMIN = 'admin'        # Full access including user management

VALID_ROLES = [ROLE_VIEWER, ROLE_OPERATOR, ROLE_ADMIN]

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'


class User(UserMixin):
    """User model for Flask-Login"""

    def __init__(self, user_id, username, password_hash, role='admin', is_primary_admin=False, session_token=None):
        self.id = user_id
        self.username = username
        self.password_hash = password_hash
        self.role = role
        self.is_primary_admin = is_primary_admin
        self.session_token = session_token

    def check_password(self, password):
        """Verify password against stored hash"""
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        """Check if user has admin role"""
        return self.role == ROLE_ADMIN

    def is_operator(self):
        """Check if user has operator role or higher"""
        return self.role in [ROLE_OPERATOR, ROLE_ADMIN]

    def can_access_settings(self):
        """Check if user can access any settings"""
        return self.role in [ROLE_OPERATOR, ROLE_ADMIN]

    def can_manage_users(self):
        """Check if user can manage other users"""
        return self.role == ROLE_ADMIN

    def can_access_full_settings(self):
        """Check if user can access all settings (admin only)"""
        return self.role == ROLE_ADMIN

    @staticmethod
    def get_by_id(user_id):
        """Load user by ID"""
        row = db_utils.fetch_one(AUTH_DB_PATH,
            'SELECT id, username, password_hash, role, is_primary_admin, session_token FROM users WHERE id = ?',
            (user_id,))

        if row:
            return User(row[0], row[1], row[2], row[3] or 'admin', bool(row[4]), row[5])
        return None

    @staticmethod
    def get_by_username(username):
        """Load user by username"""
        row = db_utils.fetch_one(AUTH_DB_PATH,
            'SELECT id, username, password_hash, role, is_primary_admin, session_token FROM users WHERE username = ?',
            (username,))

        if row:
            return User(row[0], row[1], row[2], row[3] or 'admin', bool(row[4]), row[5])
        return None

    @staticmethod
    def get_all_users():
        """Get all users (for admin user management)"""
        rows = db_utils.fetch_all(AUTH_DB_PATH,
            'SELECT id, username, role, is_primary_admin, session_token, created_at FROM users ORDER BY id')

        users = []
        for row in rows:
            users.append({
                'id': row[0],
                'username': row[1],
                'role': row[2] or 'admin',
                'is_primary_admin': bool(row[3]),
                'has_active_session': bool(row[4]),
                'created_at': row[5]
            })
        return users

    @staticmethod
    def create(username, password, role='admin', is_primary_admin=False):
        """Create new user"""
        password_hash = generate_password_hash(password)

        try:
            def _create_user(conn, cursor):
                cursor.execute(
                    'INSERT INTO users (username, password_hash, role, is_primary_admin) VALUES (?, ?, ?, ?)',
                    (username, password_hash, role, 1 if is_primary_admin else 0)
                )
                return cursor.lastrowid

            user_id = db_utils.execute_transaction(AUTH_DB_PATH, _create_user)
            return User(user_id, username, password_hash, role, is_primary_admin)
        except sqlite3.IntegrityError:
            return None

    @staticmethod
    def update_password(username, new_password):
        """Update user password"""
        password_hash = generate_password_hash(new_password)

        db_utils.execute_query(AUTH_DB_PATH,
            'UPDATE users SET password_hash = ? WHERE username = ?',
            (password_hash, username), commit=True)

    @staticmethod
    def update_role(user_id, new_role):
        """Update user role"""
        if new_role not in VALID_ROLES:
            return False

        # Check if user is primary admin - cannot change their role
        user = User.get_by_id(user_id)
        if user and user.is_primary_admin:
            return False

        db_utils.execute_query(AUTH_DB_PATH,
            'UPDATE users SET role = ? WHERE id = ?',
            (new_role, user_id), commit=True)
        return True

    @staticmethod
    def delete_user(user_id):
        """Delete a user (cannot delete primary admin)"""
        user = User.get_by_id(user_id)
        if user and user.is_primary_admin:
            return False

        db_utils.execute_query(AUTH_DB_PATH,
            'DELETE FROM users WHERE id = ? AND is_primary_admin = 0',
            (user_id,), commit=True)
        return True

    @staticmethod
    def set_session_token(user_id, token):
        """Set session token for a user (used to track active sessions)"""
        db_utils.execute_query(AUTH_DB_PATH,
            'UPDATE users SET session_token = ? WHERE id = ?',
            (token, user_id), commit=True)

    @staticmethod
    def clear_session_token(user_id):
        """Clear session token (logout)"""
        db_utils.execute_query(AUTH_DB_PATH,
            'UPDATE users SET session_token = NULL WHERE id = ?',
            (user_id,), commit=True)

    @staticmethod
    def invalidate_session(user_id):
        """Invalidate a user's session (force logout)"""
        # Generate a new random token that won't match their current session
        db_utils.execute_query(AUTH_DB_PATH,
            'UPDATE users SET session_token = ? WHERE id = ?',
            (secrets.token_hex(8), user_id), commit=True)

    @staticmethod
    def validate_session(user_id, token):
        """Check if session token is valid"""
        row = db_utils.fetch_one(AUTH_DB_PATH,
            'SELECT session_token FROM users WHERE id = ?',
            (user_id,))

        if row and row[0]:
            return row[0] == token
        return True  # No token stored means session is valid (backwards compatibility)

    @staticmethod
    def count_users():
        """Count total users in database"""
        row = db_utils.fetch_one(AUTH_DB_PATH,
            'SELECT COUNT(*) FROM users')
        return row[0] if row else 0

    @staticmethod
    def count_admins():
        """Count total admin users"""
        row = db_utils.fetch_one(AUTH_DB_PATH,
            'SELECT COUNT(*) FROM users WHERE role = ?',
            (ROLE_ADMIN,))
        return row[0] if row else 0


@login_manager.user_loader
def load_user(user_id):
    """Flask-Login user loader callback"""
    return User.get_by_id(int(user_id))


def init_auth_db():
    """Initialize authentication database and tables"""
    # Ensure directory exists
    AUTH_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    def _init_transaction(conn, cursor):
        # Create users table with role support
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'admin',
                is_primary_admin INTEGER DEFAULT 0,
                session_token TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Migration: Add new columns if they don't exist (for existing databases)
        cursor.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'role' not in columns:
            cursor.execute('ALTER TABLE users ADD COLUMN role TEXT DEFAULT "admin"')

        if 'is_primary_admin' not in columns:
            cursor.execute('ALTER TABLE users ADD COLUMN is_primary_admin INTEGER DEFAULT 0')
            # Mark the first user (lowest ID) as primary admin
            cursor.execute('UPDATE users SET is_primary_admin = 1 WHERE id = (SELECT MIN(id) FROM users)')

        if 'session_token' not in columns:
            cursor.execute('ALTER TABLE users ADD COLUMN session_token TEXT')

        # Ensure first user is marked as primary admin if not already set
        cursor.execute('SELECT COUNT(*) FROM users WHERE is_primary_admin = 1')
        primary_count = cursor.fetchone()[0]
        if primary_count == 0:
            cursor.execute('UPDATE users SET is_primary_admin = 1, role = "admin" WHERE id = (SELECT MIN(id) FROM users)')

    db_utils.execute_transaction(AUTH_DB_PATH, _init_transaction)


def generate_secret_key():
    """Generate a secure secret key for Flask sessions"""
    secret_key_path = Path.home() / '.audio-recorder' / 'secret_key'

    if secret_key_path.exists():
        return secret_key_path.read_text().strip()

    # Generate new secret key
    secret_key = secrets.token_hex(32)
    secret_key_path.parent.mkdir(parents=True, exist_ok=True)
    secret_key_path.write_text(secret_key)

    return secret_key


def needs_setup():
    """Check if initial setup (admin user creation) is needed"""
    init_auth_db()
    return User.count_users() == 0
