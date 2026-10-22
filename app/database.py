import sqlite3
import json
import hashlib
import os
from datetime import datetime
from typing import List, Dict, Any, Optional

DB_DIR = os.path.join(os.path.dirname(__file__), "data")
DB_PATH = os.path.join(DB_DIR, "attendance.db")

def get_db_connection() -> sqlite3.Connection:
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Settings table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)

    # Students table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_code TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            father_name TEXT DEFAULT '',
            class_name TEXT NOT NULL,
            roll_no TEXT NOT NULL,
            parent_phone TEXT DEFAULT '',
            gender TEXT DEFAULT 'Male',
            dob TEXT DEFAULT '',
            address TEXT DEFAULT '',
            photo_url TEXT DEFAULT '',
            qr_payload TEXT UNIQUE NOT NULL,
            is_active INTEGER DEFAULT 1,
            created_at TEXT NOT NULL
        )
    """)

    # Attendance table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
            date TEXT NOT NULL,
            scan_time TEXT,
            status TEXT NOT NULL, -- 'Present', 'Late', 'Absent', 'Leave'
            scan_method TEXT DEFAULT 'QR', -- 'QR', 'Manual', 'OfflineSync'
            sync_id TEXT UNIQUE,
            notes TEXT DEFAULT '',
            updated_by TEXT DEFAULT 'scanner',
            updated_at TEXT NOT NULL,
            UNIQUE(student_id, date)
        )
    """)

    # Leaves table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS leaves (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            reason TEXT DEFAULT '',
            leave_type TEXT DEFAULT 'Sick', -- 'Sick', 'Casual', 'Family', 'Other'
            created_at TEXT NOT NULL
        )
    """)

    # Audit log
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            student_id INTEGER,
            details TEXT,
            timestamp TEXT NOT NULL
        )
    """)

    # Default settings
    default_classes = ["KG", "1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th", "9th", "10th"]
    defaults = {
        "school_name": "Shaheen Public High School Loi Shalman",
        "school_address": "Loi Shalman",
        "school_start_time": "07:50",
        "late_threshold_time": "08:05",
        "school_end_time": "12:30",
        "classes": json.dumps(default_classes),
        "principal_password_hash": hash_password("admin123"),
        "n8n_webhook_url": "",
        "n8n_webhook_secret": "",
        "n8n_notifications_enabled": "0",
        "sound_enabled": "1",
        "allow_manual_entry_on_scanner": "1",
        "scanner_access_code": "52186"
    }

    for k, v in defaults.items():
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

    conn.commit()
    conn.close()

# Helper queries
def get_setting(key: str, default: str = "") -> str:
    conn = get_db_connection()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default

def set_setting(key: str, value: str):
    conn = get_db_connection()
    conn.execute("INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))
    conn.commit()
    conn.close()

def get_all_settings() -> Dict[str, Any]:
    conn = get_db_connection()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    conn.close()
    settings = {row["key"]: row["value"] for row in rows}
    if "classes" in settings:
        try:
            settings["classes_list"] = json.loads(settings["classes"])
        except Exception:
            settings["classes_list"] = []
    return settings
