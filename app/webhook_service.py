import requests
import json
import threading
from typing import Dict, Any
from app.database import get_setting, get_db_connection
from datetime import datetime
from zoneinfo import ZoneInfo

PKT = ZoneInfo("Asia/Karachi")

def _dispatch_request(url: str, secret: str, data: Dict[str, Any]):
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "SPHS-Attendance-System/1.0"
    }
    if secret:
        headers["X-Webhook-Secret"] = secret

    try:
        response = requests.post(url, json=data, headers=headers, timeout=5)
        # Log success/failure in audit
        conn = get_db_connection()
        conn.execute(
            "INSERT INTO audit_log (action, details, timestamp) VALUES (?, ?, ?)",
            ("webhook_dispatched", f"URL: {url} | Status: {response.status_code}", datetime.now(PKT).isoformat())
        )
        conn.commit()
        conn.close()
    except Exception as e:
        conn = get_db_connection()
        conn.execute(
            "INSERT INTO audit_log (action, details, timestamp) VALUES (?, ?, ?)",
            ("webhook_error", f"URL: {url} | Error: {str(e)}", datetime.now(PKT).isoformat())
        )
        conn.commit()
        conn.close()

def trigger_n8n_event(event_type: str, data: Dict[str, Any]):
    """Asynchronously triggers n8n webhook so scanning remains super fast (<100ms)"""
    enabled = get_setting("n8n_notifications_enabled", "0")
    if enabled != "1":
        return

    webhook_url = get_setting("n8n_webhook_url", "").strip()
    if not webhook_url:
        return

    secret = get_setting("n8n_webhook_secret", "").strip()

    payload = {
        "event": event_type,
        "school_name": get_setting("school_name", "Shaheen Public High School Loi Shalman"),
        "timestamp": datetime.now(PKT).isoformat(),
        "data": data
    }

    # Run in background daemon thread
    thread = threading.Thread(target=_dispatch_request, args=(webhook_url, secret, payload), daemon=True)
    thread.start()

def test_webhook_endpoint(webhook_url: str, secret: str = "") -> Dict[str, Any]:
    """Test button for Admin dashboard to verify n8n webhook setup"""
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "SPHS-Attendance-System/1.0"
    }
    if secret:
        headers["X-Webhook-Secret"] = secret

    test_payload = {
        "event": "test_ping",
        "message": "Connection test from Shaheen Public High School Attendance System",
        "timestamp": datetime.now(PKT).isoformat(),
        "data": {
            "test": True,
            "sample_student": {
                "full_name": "Test Student",
                "class_name": "10th",
                "roll_no": "01",
                "parent_phone": "+923001234567"
            }
        }
    }

    try:
        response = requests.post(webhook_url, json=test_payload, headers=headers, timeout=6)
        return {
            "success": response.status_code < 400,
            "status_code": response.status_code,
            "response": response.text[:200]
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
