from datetime import datetime, time
from typing import Dict, Any, List, Optional
import sqlite3
from app.database import get_db_connection, get_setting
from app.qr_service import verify_qr_payload
from app.webhook_service import trigger_n8n_event

def get_current_school_date() -> str:
    """Returns YYYY-MM-DD"""
    return datetime.now().strftime("%Y-%m-%d")

def get_current_school_time() -> str:
    """Returns HH:MM:SS"""
    return datetime.now().strftime("%H:%M:%S")

def parse_time_str(t_str: str) -> time:
    """Parses HH:MM or HH:MM:SS string to time object"""
    parts = t_str.strip().split(":")
    h = int(parts[0])
    m = int(parts[1]) if len(parts) > 1 else 0
    s = int(parts[2]) if len(parts) > 2 else 0
    return time(h, m, s)

def check_student_leave(cursor: sqlite3.Cursor, student_id: int, date_str: str) -> Optional[Dict[str, Any]]:
    row = cursor.execute("""
        SELECT * FROM leaves 
        WHERE student_id = ? AND start_date <= ? AND end_date >= ?
        LIMIT 1
    """, (student_id, date_str, date_str)).fetchone()
    if row:
        return dict(row)
    return None

def determine_status_for_time(scan_time_str: str) -> str:
    """
    Compares scan time against configured late_threshold_time.
    e.g. start=07:50, late_threshold=08:05, end=12:30
    """
    late_threshold_str = get_setting("late_threshold_time", "08:05")
    try:
        scan_t = parse_time_str(scan_time_str)
        threshold_t = parse_time_str(late_threshold_str)
        if scan_t <= threshold_t:
            return "Present"
        else:
            return "Late"
    except Exception:
        return "Present"

def process_scan(
    qr_payload: str,
    scan_timestamp: Optional[str] = None,
    scan_method: str = "QR",
    sync_id: Optional[str] = None,
    operator: str = "scanner"
) -> Dict[str, Any]:
    """
    Main scan processing pipeline:
    - Resolves student code from QR payload
    - Checks for existing attendance today
    - Checks for active leave
    - Determines Present vs Late
    - Records entry and triggers n8n webhook
    """
    code = verify_qr_payload(qr_payload)
    if not code:
        return {"success": False, "error_type": "invalid_qr", "message": "Invalid QR Code format"}

    conn = get_db_connection()
    cursor = conn.cursor()

    # Find student — supports new short code (S501), old SPHS- code, direct qr_payload, or roll_no
    student_row = cursor.execute("""
        SELECT * FROM students 
        WHERE (student_code = ? OR qr_payload = ? OR roll_no = ? OR UPPER(student_code) = UPPER(?)) AND is_active = 1
        LIMIT 1
    """, (code, qr_payload, code, code)).fetchone()

    if not student_row:
        conn.close()
        return {"success": False, "error_type": "student_not_found", "message": f"Student not found for code '{code}'"}

    student = dict(student_row)
    student_id = student["id"]

    # Parse scan date and time
    if scan_timestamp:
        try:
            # Format expected: ISO string or 'YYYY-MM-DD HH:MM:SS'
            if "T" in scan_timestamp:
                dt = datetime.fromisoformat(scan_timestamp.replace("Z", "+00:00"))
            else:
                dt = datetime.strptime(scan_timestamp, "%Y-%m-%d %H:%M:%S")
            scan_date = dt.strftime("%Y-%m-%d")
            scan_time = dt.strftime("%H:%M:%S")
        except Exception:
            scan_date = get_current_school_date()
            scan_time = get_current_school_time()
    else:
        scan_date = get_current_school_date()
        scan_time = get_current_school_time()

    # Check if already marked today
    existing = cursor.execute("""
        SELECT * FROM attendance WHERE student_id = ? AND date = ?
    """, (student_id, scan_date)).fetchone()

    if existing:
        existing_data = dict(existing)
        conn.close()
        return {
            "success": True,
            "already_marked": True,
            "message": f"Already marked today as {existing_data['status']} at {existing_data['scan_time']}",
            "student": student,
            "record": existing_data,
            "status": existing_data["status"],
            "scan_time": existing_data["scan_time"],
            "date": scan_date
        }

    # Check for active leave
    leave_rec = check_student_leave(cursor, student_id, scan_date)
    if leave_rec:
        status = "Leave"
        notes = f"Approved Leave ({leave_rec.get('leave_type', 'Sick')})"
    else:
        status = determine_status_for_time(scan_time)
        notes = ""

    now_iso = datetime.now().isoformat()
    cursor.execute("""
        INSERT INTO attendance (student_id, date, scan_time, status, scan_method, sync_id, notes, updated_by, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (student_id, scan_date, scan_time, status, scan_method, sync_id, notes, operator, now_iso))

    conn.commit()
    conn.close()

    # Asynchronous WhatsApp / n8n notification dispatch
    trigger_n8n_event("attendance_marked", {
        "student_code": student["student_code"],
        "student_name": student["full_name"],
        "class_name": student["class_name"],
        "roll_no": student["roll_no"],
        "parent_phone": student["parent_phone"],
        "date": scan_date,
        "time": scan_time,
        "status": status,
        "notes": notes
    })

    return {
        "success": True,
        "already_marked": False,
        "message": f"Marked {status} at {scan_time}",
        "student": student,
        "status": status,
        "scan_time": scan_time,
        "date": scan_date
    }

def sync_batch_scans(scans: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Process array of scans queued by the offline PWA.
    Scans have: {sync_id, qr_payload, timestamp}
    """
    synced = 0
    already_marked = 0
    errors = []

    for item in scans:
        sync_id = item.get("sync_id")
        qr_payload = item.get("qr_payload") or item.get("code")
        timestamp = item.get("timestamp")

        if not qr_payload:
            continue

        res = process_scan(
            qr_payload=qr_payload,
            scan_timestamp=timestamp,
            scan_method="OfflineSync",
            sync_id=sync_id,
            operator="offline_pwa"
        )

        if res.get("success"):
            if res.get("already_marked"):
                already_marked += 1
            else:
                synced += 1
        else:
            errors.append({"item": item, "error": res.get("message")})

    return {
        "synced_count": synced,
        "already_marked_count": already_marked,
        "errors_count": len(errors),
        "errors": errors
    }

def manual_attendance_update(
    student_id: int,
    date_str: str,
    new_status: str,
    reason: str = "",
    operator: str = "Principal"
) -> Dict[str, Any]:
    """Allows the principal to manually mark or correct attendance for any student"""
    conn = get_db_connection()
    cursor = conn.cursor()
    now_iso = datetime.now().isoformat()

    existing = cursor.execute("""
        SELECT * FROM attendance WHERE student_id = ? AND date = ?
    """, (student_id, date_str)).fetchone()

    old_status = existing["status"] if existing else "None"

    if existing:
        cursor.execute("""
            UPDATE attendance 
            SET status = ?, notes = ?, updated_by = ?, updated_at = ?
            WHERE student_id = ? AND date = ?
        """, (new_status, reason, operator, now_iso, student_id, date_str))
    else:
        cursor.execute("""
            INSERT INTO attendance (student_id, date, scan_time, status, scan_method, notes, updated_by, updated_at)
            VALUES (?, ?, ?, ?, 'Manual', ?, ?, ?)
        """, (student_id, date_str, get_current_school_time(), new_status, reason, operator, now_iso))

    # Audit log entry
    cursor.execute("""
        INSERT INTO audit_log (action, student_id, details, timestamp)
        VALUES (?, ?, ?, ?)
    """, ("manual_correction", student_id, f"Changed status from {old_status} to {new_status}. Reason: {reason} by {operator}", now_iso))

    conn.commit()
    conn.close()

    return {"success": True, "old_status": old_status, "new_status": new_status, "date": date_str}

def delete_attendance_entry(
    student_id: int,
    date_str: str,
    operator: str = "Principal"
) -> Dict[str, Any]:
    """Permanently removes an attendance record for a student on a specific date (e.g. mistaken scan)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    now_iso = datetime.now().isoformat()

    existing = cursor.execute("""
        SELECT * FROM attendance WHERE student_id = ? AND date = ?
    """, (student_id, date_str)).fetchone()

    if not existing:
        conn.close()
        return {"success": False, "message": "No attendance record found for this student on this date."}

    old_status = existing["status"]
    old_time = existing["scan_time"]

    cursor.execute("""
        DELETE FROM attendance WHERE student_id = ? AND date = ?
    """, (student_id, date_str))

    cursor.execute("""
        INSERT INTO audit_log (action, student_id, details, timestamp)
        VALUES (?, ?, ?, ?)
    """, ("delete_attendance", student_id, f"Removed attendance entry (was {old_status} at {old_time}) by {operator}", now_iso))

    conn.commit()
    conn.close()

    return {
        "success": True,
        "message": "Attendance entry removed successfully. Student is now unmarked.",
        "student_id": student_id,
        "date": date_str
    }

def auto_mark_absentees(target_date: Optional[str] = None) -> int:
    """Marks all active students who haven't scanned today as Absent (or Leave if on leave)"""
    if not target_date:
        target_date = get_current_school_date()

    conn = get_db_connection()
    cursor = conn.cursor()

    # Find students with no attendance record on target_date
    unmarked_students = cursor.execute("""
        SELECT s.id, s.full_name, s.class_name, s.roll_no, s.parent_phone 
        FROM students s
        WHERE s.is_active = 1
        AND s.id NOT IN (
            SELECT a.student_id FROM attendance a WHERE a.date = ?
        )
    """, (target_date,)).fetchall()

    count = 0
    now_iso = datetime.now().isoformat()
    absent_students_list = []

    for stu in unmarked_students:
        s_id = stu["id"]
        leave_rec = check_student_leave(cursor, s_id, target_date)
        if leave_rec:
            status = "Leave"
            notes = f"Leave ({leave_rec.get('leave_type', 'Sick')})"
        else:
            status = "Absent"
            notes = "Auto-marked end of day"
            absent_students_list.append(dict(stu))

        cursor.execute("""
            INSERT OR IGNORE INTO attendance (student_id, date, scan_time, status, scan_method, notes, updated_by, updated_at)
            VALUES (?, ?, NULL, ?, 'AutoSystem', ?, 'system', ?)
        """, (s_id, target_date, status, notes, now_iso))
        count += 1

    conn.commit()
    conn.close()

    # Dispatch daily absent summary to n8n if any absentees
    if absent_students_list:
        trigger_n8n_event("daily_absent_summary", {
            "date": target_date,
            "absent_count": len(absent_students_list),
            "students": absent_students_list
        })

    return count

def get_daily_dashboard_data(target_date: Optional[str] = None, class_filter: Optional[str] = None) -> Dict[str, Any]:
    if not target_date:
        target_date = get_current_school_date()

    conn = get_db_connection()
    cursor = conn.cursor()

    # Total active students
    class_clause = "AND class_name = ?" if class_filter else ""
    params_students = (class_filter,) if class_filter else ()

    total_students = cursor.execute(f"SELECT COUNT(*) as c FROM students WHERE is_active = 1 {class_clause}", params_students).fetchone()["c"]

    # Attendance query for target_date
    query = """
        SELECT 
            s.id as student_id,
            s.student_code,
            s.full_name,
            s.father_name,
            s.class_name,
            s.roll_no,
            s.parent_phone,
            s.photo_url,
            COALESCE(a.status, 'Unmarked') as status,
            a.scan_time,
            a.scan_method,
            a.notes,
            a.updated_by
        FROM students s
        LEFT JOIN attendance a ON s.id = a.student_id AND a.date = ?
        WHERE s.is_active = 1
    """
    params = [target_date]
    if class_filter:
        query += " AND s.class_name = ?"
        params.append(class_filter)
    query += " ORDER BY s.class_name ASC, CAST(s.roll_no AS INTEGER) ASC, s.roll_no ASC"

    records = [dict(r) for r in cursor.execute(query, params).fetchall()]

    # Counts
    present_cnt = sum(1 for r in records if r["status"] == "Present")
    late_cnt = sum(1 for r in records if r["status"] == "Late")
    absent_cnt = sum(1 for r in records if r["status"] == "Absent")
    leave_cnt = sum(1 for r in records if r["status"] == "Leave")
    unmarked_cnt = sum(1 for r in records if r["status"] == "Unmarked")

    # If it's during or after school hours, unmarked can be treated as absent or pending
    total_marked = present_cnt + late_cnt + absent_cnt + leave_cnt
    attendance_rate = round(((present_cnt + late_cnt) / total_students * 100), 1) if total_students > 0 else 0.0

    # Class-wise breakdowns
    class_stats = {}
    for r in records:
        c = r["class_name"]
        if c not in class_stats:
            class_stats[c] = {"class_name": c, "total": 0, "present": 0, "late": 0, "absent": 0, "leave": 0, "unmarked": 0}
        class_stats[c]["total"] += 1
        st = r["status"].lower()
        if st in class_stats[c]:
            class_stats[c][st] += 1

    conn.close()

    return {
        "date": target_date,
        "class_filter": class_filter,
        "total_students": total_students,
        "present": present_cnt,
        "late": late_cnt,
        "absent": absent_cnt,
        "leave": leave_cnt,
        "unmarked": unmarked_cnt,
        "attendance_rate": attendance_rate,
        "class_stats": list(class_stats.values()),
        "records": records
    }
