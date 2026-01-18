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
        conn = sqlite3.connect(AUTH_DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT id, username, password_hash FROM users WHERE id = ?', (user_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return User(row[0], row[1], row[2])
        return None

    @staticmethod
    def get_by_username(username):
        """Load user by username"""
        conn = sqlite3.connect(AUTH_DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT id, username, password_hash FROM users WHERE username = ?', (username,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return User(row[0], row[1], row[2])
        return None

    @staticmethod
    def create(username, password):
        """Create new user"""
        password_hash = generate_password_hash(password)

        conn = sqlite3.connect(AUTH_DB_PATH)
        cursor = conn.cursor()

        try:
            cursor.execute(
                'INSERT INTO users (username, password_hash) VALUES (?, ?)',
                (username, password_hash)
            )
            conn.commit()
            user_id = cursor.lastrowid
            conn.close()
            return User(user_id, username, password_hash)
        except sqlite3.IntegrityError:
            conn.close()
            return None

    @staticmethod
    def update_password(username, new_password):
        """Update user password"""
        password_hash = generate_password_hash(new_password)

        conn = sqlite3.connect(AUTH_DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE users SET password_hash = ? WHERE username = ?',
            (password_hash, username)
        )
        conn.commit()
        conn.close()

    @staticmethod
    def count_users():
        """Count total users in database"""
        conn = sqlite3.connect(AUTH_DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM users')
        count = cursor.fetchone()[0]
        conn.close()
        return count


@login_manager.user_loader
def load_user(user_id):
    """Flask-Login user loader callback"""
    return User.get_by_id(int(user_id))


def init_auth_db():
    """Initialize authentication database and tables"""
    # Ensure directory exists
    AUTH_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(AUTH_DB_PATH)
    cursor = conn.cursor()

    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()


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
