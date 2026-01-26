#!/usr/bin/env python3
"""
Authentication Module for Audio Recorder
Handles user management and session authentication
"""

import sqlite3
import secrets
from pathlib import Path
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin
import db_utils

# Database path - same directory as scheduler database
AUTH_DB_PATH = Path.home() / '.audio-recorder' / 'auth.db'

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'


class User(UserMixin):
    """User model for Flask-Login"""

    def __init__(self, user_id, username, password_hash):
        self.id = user_id
        self.username = username
        self.password_hash = password_hash

    def check_password(self, password):
        """Verify password against stored hash"""
        return check_password_hash(self.password_hash, password)

    @staticmethod
    def get_by_id(user_id):
        """Load user by ID"""
        row = db_utils.fetch_one(AUTH_DB_PATH,
            'SELECT id, username, password_hash FROM users WHERE id = ?',
            (user_id,))

        if row:
            return User(row[0], row[1], row[2])
        return None

    @staticmethod
    def get_by_username(username):
        """Load user by username"""
        row = db_utils.fetch_one(AUTH_DB_PATH,
            'SELECT id, username, password_hash FROM users WHERE username = ?',
            (username,))

        if row:
            return User(row[0], row[1], row[2])
        return None

    @staticmethod
    def create(username, password):
        """Create new user"""
        password_hash = generate_password_hash(password)

        try:
            def _create_user(conn, cursor):
                cursor.execute(
                    'INSERT INTO users (username, password_hash) VALUES (?, ?)',
                    (username, password_hash)
                )
                return cursor.lastrowid

            user_id = db_utils.execute_transaction(AUTH_DB_PATH, _create_user)
            return User(user_id, username, password_hash)
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
    def count_users():
        """Count total users in database"""
        row = db_utils.fetch_one(AUTH_DB_PATH,
            'SELECT COUNT(*) FROM users')
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
        # Create users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

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
