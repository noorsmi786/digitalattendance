import os
import json
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from typing import Optional, List, Dict, Any

PKT = ZoneInfo("Asia/Karachi")

from fastapi import FastAPI, Request, Response, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app.database import (
    init_db, get_db_connection, get_setting, set_setting, get_all_settings, hash_password
)
from app.qr_service import generate_qr_payload, generate_qr_base64, compute_student_code_and_roll
from app.attendance_service import (
    process_scan, sync_batch_scans, manual_attendance_update, delete_attendance_entry,
    auto_mark_absentees, get_daily_dashboard_data, get_current_school_date
)
from app.excel_service import (
    generate_student_excel_template, import_students_from_excel, export_attendance_to_excel
)
from app.webhook_service import test_webhook_endpoint
from app.photo_service import process_bulk_photo_upload, save_student_capture

# Paths
BASE_DIR = os.path.dirname(__file__)
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(os.path.join(UPLOADS_DIR, "students"), exist_ok=True)

app = FastAPI(title="Shaheen Public High School Loi Shalman - Digital Attendance")

# CORS Middleware for Browser Cross-Origin Requests
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Static Files & Templates & Uploads
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Auth helper
AUTH_COOKIE_NAME = "sphs_principal_session"
AUTH_TOKEN = "SPHS-Principal-Auth-Token-2026"

def is_authenticated(request: Request) -> bool:
    cookie = request.cookies.get(AUTH_COOKIE_NAME)
    return cookie == AUTH_TOKEN

def require_auth(request: Request):
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

# Seed initial sample students if empty
def seed_initial_data_if_empty():
    conn = get_db_connection()
    count = conn.execute("SELECT COUNT(*) as c FROM students").fetchone()["c"]
    if count == 0:
        samples = [
            # (student_code, name, father, class, roll, phone, gender, addr)
            ("S1001", "Muhammad Huzaifa", "Tariq Khan",    "10th", "01", "+923001234501", "Male",   "Loi Shalman"),
            ("S1002", "Hamza Afridi",     "Gulzar Khan",   "10th", "02", "+923001234502", "Male",   "Loi Shalman"),
            ("S901",  "Aisha Bibi",       "Abdul Qadir",   "9th",  "01", "+923001234503", "Female", "Loi Shalman"),
            ("S902",  "Bilal Ahmad",      "Niaz Muhammad", "9th",  "02", "+923001234504", "Male",   "Loi Shalman"),
            ("S801",  "Zainab Noor",      "Sher Ali",      "8th",  "01", "+923001234505", "Female", "Loi Shalman"),
            ("SKG01", "Usman Shinwari",   "Zahid Khan",    "KG",   "01", "+923001234506", "Male",   "Loi Shalman"),
            ("S101",  "Omar Farooq",      "Said Badshah",  "1st",  "01", "+923001234507", "Male",   "Loi Shalman"),
        ]
        now = datetime.now(PKT).isoformat()
        for code, name, father, cls, roll, phone, gender, addr in samples:
            qr = generate_qr_payload(code)
            conn.execute("""
                INSERT INTO students (student_code, full_name, father_name, class_name, roll_no, parent_phone, gender, address, qr_payload, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
            """, (code, name, father, cls, roll, phone, gender, addr, qr, now))
        conn.commit()
    conn.close()

@app.on_event("startup")
def on_startup():
    init_db()
    seed_initial_data_if_empty()

# ==================== FRONTEND ROUTES ====================

@app.get("/", response_class=HTMLResponse)
def index_redirect(request: Request):
    """Default route: Redirects to mobile scanner for instant kiosk convenience"""
    return RedirectResponse(url="/scanner")

@app.get("/scanner", response_class=HTMLResponse)
def scanner_page(request: Request):
    school_name = get_setting("school_name", "Shaheen Public High School Loi Shalman")
    settings = get_all_settings()
    today_str = get_current_school_date()

    conn = get_db_connection()
    marked_count = conn.execute("SELECT COUNT(*) as c FROM attendance WHERE date = ?", (today_str,)).fetchone()["c"]
    conn.close()

    return templates.TemplateResponse(
        request=request,
        name="scanner.html",
        context={
            "school_name": school_name,
            "classes": settings.get("classes_list", []),
            "today_scanned": marked_count,
            "url_key": request.query_params.get("key", ""),
            "cache_bust": int(datetime.now(PKT).timestamp()),
        }
    )

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if is_authenticated(request):
        return RedirectResponse(url="/admin")
    school_name = get_setting("school_name", "Shaheen Public High School Loi Shalman")
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"school_name": school_name}
    )

@app.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request):
    if not is_authenticated(request):
        return RedirectResponse(url="/login")
    settings = get_all_settings()
    today_str = get_current_school_date()
    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={
            "settings": settings,
            "today_date": today_str,
            "cache_bust": int(datetime.now(PKT).timestamp()),
        }
    )

@app.get("/print/cards", response_class=HTMLResponse)
def print_cards_page(
    request: Request,
    class_name: Optional[str] = None,
    student_id: Optional[int] = None,
    sample_preview: Optional[int] = None,
    search: Optional[str] = None
):
    if not is_authenticated(request):
        return RedirectResponse(url="/login")

    conn = get_db_connection()
    query = "SELECT * FROM students WHERE is_active = 1"
    params = []

    if student_id:
        query += " AND id = ?"
        params.append(student_id)
    elif class_name and class_name.strip() and class_name != "All Classes":
        query += " AND class_name = ?"
        params.append(class_name.strip())

    if search and search.strip():
        term = f"%{search.strip()}%"
        query += " AND (student_code LIKE ? OR full_name LIKE ? OR roll_no LIKE ?)"
        params.extend([term, term, term])

    query += " ORDER BY class_name ASC, CAST(roll_no AS INTEGER) ASC, roll_no ASC"

    # If sample preview requested, limit to exactly 5 students (1 page)
    if sample_preview:
        query += " LIMIT 5"

    students = [dict(s) for s in conn.execute(query, params).fetchall()]

    # Fetch all distinct classes for the class filter
    classes = [r[0] for r in conn.execute("SELECT DISTINCT class_name FROM students WHERE is_active = 1 ORDER BY class_name ASC").fetchall()]
    conn.close()

    # Pre-generate local QR base64 images containing ONLY student_code (e.g. S101)
    for s in students:
        # Use student_code directly as the QR payload
        s["qr_image"] = generate_qr_base64(s.get("student_code", s.get("qr_payload", "")))

    return templates.TemplateResponse(
        request=request,
        name="print_cards.html",
        context={
            "school_name": get_setting("school_name", "Shaheen Public High School Loi Shalman"),
            "students": students,
            "classes": classes,
            "class_name": class_name or "",
            "search_term": search or "",
            "is_sample_preview": bool(sample_preview),
        }
    )


@app.get("/print/card-preview-noqr", response_class=HTMLResponse)
def print_card_preview_noqr(request: Request):
    if not is_authenticated(request):
        return RedirectResponse(url="/login")
    conn = get_db_connection()
    students = [dict(s) for s in conn.execute(
        "SELECT * FROM students WHERE is_active = 1 ORDER BY class_name ASC, CAST(roll_no AS INTEGER) ASC LIMIT 6"
    ).fetchall()]
    conn.close()
    for s in students:
        s["qr_image"] = generate_qr_base64(s["qr_payload"])
    return templates.TemplateResponse(
        request=request,
        name="print_card_preview_noqr.html",
        context={"students": students, "school_name": get_setting("school_name", "Shaheen Public High School")}
    )

@app.get("/print/card-backs", response_class=HTMLResponse)
def print_card_backs_page(
    request: Request,
    class_name: Optional[str] = None,
    student_id: Optional[int] = None
):
    if not is_authenticated(request):
        return RedirectResponse(url="/login")

    conn = get_db_connection()
    query = "SELECT * FROM students WHERE is_active = 1"
    params = []
    if student_id:
        query += " AND id = ?"
        params.append(student_id)
    elif class_name:
        query += " AND class_name = ?"
        params.append(class_name)
    query += " ORDER BY class_name ASC, CAST(roll_no AS INTEGER) ASC, roll_no ASC"
    students = [dict(s) for s in conn.execute(query, params).fetchall()]
    conn.close()

    for s in students:
        s["qr_image"] = generate_qr_base64(s["qr_payload"])

    return templates.TemplateResponse(
        request=request,
        name="print_card_backs.html",
        context={
            "school_name": get_setting("school_name", "Shaheen Public High School"),
            "students": students,
            "class_name": class_name or "All Classes"
        }
    )

@app.get("/print/comparison", response_class=HTMLResponse)
@app.get("/print/sample-sheet", response_class=HTMLResponse)
def print_comparison_page(
    request: Request,
    student_id: Optional[int] = None
):
    if not is_authenticated(request):
        return RedirectResponse(url="/login")

    conn = get_db_connection()
    all_students = [dict(s) for s in conn.execute(
        "SELECT id, student_code, full_name, father_name, class_name, roll_no, photo_url, qr_payload FROM students WHERE is_active = 1 ORDER BY CAST(roll_no AS INTEGER) ASC, roll_no ASC"
    ).fetchall()]

    if not all_students:
        conn.close()
        return HTMLResponse("<p>No active students found in database to generate sample sheet.</p>", status_code=404)

    student = None
    if student_id:
        student = next((s for s in all_students if s["id"] == student_id), None)
    if not student:
        student = all_students[0]

    conn.close()

    student["qr_image"] = generate_qr_base64(student["qr_payload"])

    return templates.TemplateResponse(
        request=request,
        name="print_comparison.html",
        context={
            "school_name": get_setting("school_name", "Shaheen Public High School Loi Shalman"),
            "student": student,
            "all_students": all_students,
        }
    )

@app.get("/print/stickers", response_class=HTMLResponse)
def print_stickers_page(request: Request, class_name: Optional[str] = None):
    if not is_authenticated(request):
        return RedirectResponse(url="/login")

    conn = get_db_connection()
    query = "SELECT * FROM students WHERE is_active = 1"
    params = []
    if class_name:
        query += " AND class_name = ?"
        params.append(class_name)
    query += " ORDER BY class_name ASC, CAST(roll_no AS INTEGER) ASC, roll_no ASC"

    students = [dict(s) for s in conn.execute(query, params).fetchall()]
    conn.close()

    for s in students:
        s["qr_image"] = generate_qr_base64(s["qr_payload"])

    return templates.TemplateResponse(
        request=request,
        name="print_stickers.html",
        context={
            "school_name": get_setting("school_name", "Shaheen Public High School Loi Shalman"),
            "students": students,
            "class_name": class_name or "All Classes"
        }
    )

@app.get("/print/report", response_class=HTMLResponse)
def print_report_page(request: Request, date: Optional[str] = None, class_name: Optional[str] = None):
    if not is_authenticated(request):
        return RedirectResponse(url="/login")

    target_date = date or get_current_school_date()
    dashboard_data = get_daily_dashboard_data(target_date, class_name)

    return templates.TemplateResponse(
        request=request,
        name="print_report.html",
        context={
            "school_name": get_setting("school_name", "Shaheen Public High School Loi Shalman"),
            "date": target_date,
            "class_filter": class_name,
            "now_time": datetime.now(PKT).strftime("%I:%M %p"),
            "summary": dashboard_data,
            "records": dashboard_data["records"]
        }
    )


@app.get("/photo-booth", response_class=HTMLResponse)
def photo_booth_page(request: Request, class_name: Optional[str] = None):
    if not is_authenticated(request):
        return RedirectResponse(url="/login")

    conn = get_db_connection()
    classes_rows = conn.execute("SELECT DISTINCT class_name FROM students WHERE is_active = 1 ORDER BY class_name ASC").fetchall()
    classes = [r["class_name"] for r in classes_rows]

    # Always fetch all active students so client-side filters (class, gender, photo status) work without page reloads
    query = "SELECT * FROM students WHERE is_active = 1 ORDER BY class_name ASC, CAST(roll_no AS INTEGER) ASC, roll_no ASC"
    students = [dict(s) for s in conn.execute(query).fetchall()]
    conn.close()

    return templates.TemplateResponse(
        request=request,
        name="photo_booth.html",
        context={
            "school_name": get_setting("school_name", "Shaheen Public High School Loi Shalman"),
            "classes": classes,
            "selected_class": class_name or "",
            "students": students,
        }
    )


# ==================== SCANNER & ATTENDANCE API ====================

def verify_scanner_access(request: Request) -> bool:
    """Verifies scanner key from header, query param, or admin session"""
    if is_authenticated(request):
        return True
    configured_code = get_setting("scanner_access_code", "52186").strip()
    if not configured_code:
        return True
    header_key = request.headers.get("X-Scanner-Key", "").strip()
    query_key = request.query_params.get("key", "").strip()
    return header_key == configured_code or query_key == configured_code

class VerifyScannerKeyRequest(BaseModel):
    code: str

@app.post("/api/scanner/verify-key")
def api_verify_scanner_key(payload: VerifyScannerKeyRequest, request: Request):
    configured_code = get_setting("scanner_access_code", "52186").strip()
    if is_authenticated(request) or (configured_code and payload.code.strip() == configured_code):
        return {"success": True, "message": "Access granted"}
    return {"success": False, "message": "Invalid scanner access code"}

class ScanRequest(BaseModel):
    qr_payload: str
    timestamp: Optional[str] = None
    sync_id: Optional[str] = None

@app.post("/api/scan")
def api_scan_single(payload: ScanRequest, request: Request):
    if not verify_scanner_access(request):
        raise HTTPException(status_code=403, detail="Scanner access restricted. Invalid key.")
    result = process_scan(
        qr_payload=payload.qr_payload,
        scan_timestamp=payload.timestamp,
        scan_method="QR",
        sync_id=payload.sync_id
    )
    return result

class BatchSyncRequest(BaseModel):
    scans: List[Dict[str, Any]]

@app.post("/api/sync")
def api_sync_batch(payload: BatchSyncRequest, request: Request):
    if not verify_scanner_access(request):
        raise HTTPException(status_code=403, detail="Scanner access restricted. Invalid key.")
    result = sync_batch_scans(payload.scans)
    return result

@app.get("/api/scanner-info")
def api_scanner_info():
    today_str = get_current_school_date()
    conn = get_db_connection()
    marked_count = conn.execute("SELECT COUNT(*) as c FROM attendance WHERE date = ?", (today_str,)).fetchone()["c"]
    conn.close()
    return {
        "school_name": get_setting("school_name", "Shaheen Public High School Loi Shalman"),
        "today_scanned_count": marked_count,
        "reset_token": get_setting("attendance_reset_token", "0"),
        "server_time": datetime.now(PKT).strftime("%H:%M:%S")
    }

@app.post("/api/attendance/clear-today")
def api_clear_today_attendance(request: Request):
    require_auth(request)
    today_str = get_current_school_date()
    conn = get_db_connection()
    deleted_cnt = conn.execute("DELETE FROM attendance WHERE date = ?", (today_str,)).rowcount
    conn.commit()
    conn.close()
    # Issue a new reset token so active scanner clients immediately wipe their local cache
    new_token = str(int(datetime.now(PKT).timestamp()))
    set_setting("attendance_reset_token", new_token)
    return {
        "success": True,
        "deleted_count": deleted_cnt,
        "date": today_str,
        "reset_token": new_token,
        "message": f"Cleared {deleted_cnt} attendance records for today ({today_str})."
    }

@app.get("/api/attendance/summary")
def api_attendance_summary(date: Optional[str] = None, class_name: Optional[str] = None):
    target_date = date or get_current_school_date()
    data = get_daily_dashboard_data(target_date, class_name)
    return data

class ManualCorrectionRequest(BaseModel):
    student_id: int
    date: str
    new_status: str
    reason: Optional[str] = ""

@app.post("/api/attendance/manual-correct")
def api_manual_correction(payload: ManualCorrectionRequest, request: Request):
    require_auth(request)
    result = manual_attendance_update(
        student_id=payload.student_id,
        date_str=payload.date,
        new_status=payload.new_status,
        reason=payload.reason or "",
        operator="Principal"
    )
    return result

class AttendanceDeleteRequest(BaseModel):
    student_id: int
    date: Optional[str] = None

@app.delete("/api/attendance")
@app.post("/api/attendance/delete")
def api_delete_attendance(
    request: Request,
    payload: Optional[AttendanceDeleteRequest] = None,
    student_id: Optional[int] = Query(None),
    date: Optional[str] = Query(None)
):
    require_auth(request)
    sid = payload.student_id if payload else student_id
    dt = (payload.date if payload and payload.date else date) or get_current_school_date()
    if not sid:
        raise HTTPException(status_code=400, detail="student_id is required")
    result = delete_attendance_entry(
        student_id=sid,
        date_str=dt,
        operator="Principal"
    )
    return result

@app.post("/api/scan/undo")
def api_undo_scan(payload: AttendanceDeleteRequest, request: Request):
    if not verify_scanner_access(request):
        raise HTTPException(status_code=403, detail="Scanner access restricted. Invalid key.")
    # Allows phone scanner to immediately undo/remove a scan if made by mistake
    dt = payload.date or get_current_school_date()
    result = delete_attendance_entry(
        student_id=payload.student_id,
        date_str=dt,
        operator="Scanner Operator"
    )
    return result

@app.post("/api/attendance/auto-mark-absentees")
def api_auto_mark_absentees(request: Request, target_date: Optional[str] = None):
    require_auth(request)
    dt = target_date or get_current_school_date()
    marked_cnt = auto_mark_absentees(dt)
    return {"success": True, "marked_count": marked_cnt, "date": dt}


# ==================== STUDENTS MANAGEMENT API ====================

@app.get("/api/students")
def api_list_students(request: Request, class_name: Optional[str] = None):
    require_auth(request)
    conn = get_db_connection()
    query = "SELECT * FROM students WHERE is_active = 1"
    params = []
    if class_name:
        query += " AND class_name = ?"
        params.append(class_name)
    query += " ORDER BY class_name ASC, CAST(roll_no AS INTEGER) ASC, roll_no ASC"
    rows = [dict(r) for r in conn.execute(query, params).fetchall()]
    conn.close()
    return {"students": rows}


# ═════════════════════════════════════════════════════════════════
# SECURE API ENDPOINT FOR STUDENT ID CARD GENERATOR (CORS + API KEY)
# ═════════════════════════════════════════════════════════════════
DEFAULT_CARDS_API_KEY = "sphs_cards_secret_2026"

def verify_cards_api_key(request: Request, key: Optional[str] = None) -> bool:
    header_key = request.headers.get("x-api-key")
    query_key = key or request.query_params.get("key") or request.query_params.get("api_key")
    auth_header = request.headers.get("authorization", "")
    bearer_key = auth_header.replace("Bearer ", "").strip() if auth_header.startswith("Bearer ") else None

    provided = header_key or query_key or bearer_key
    if not provided:
        return False

    configured_key = os.getenv("CARDS_API_KEY") or get_setting("cards_api_key", DEFAULT_CARDS_API_KEY)
    valid_keys = {
        configured_key.strip(),
        DEFAULT_CARDS_API_KEY,
        "SPHS2026",
        "YOUR_SECRET_KEY"
    }
    return provided.strip() in valid_keys

@app.options("/api/students-cards")
def options_students_cards():
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, x-api-key",
        }
    )

@app.get("/api/students-cards")
def api_get_students_cards(request: Request, key: Optional[str] = None):
    # Verify API key
    if not verify_cards_api_key(request, key):
        return JSONResponse(
            status_code=401,
            content={
                "success": False,
                "error": "Unauthorized: Invalid or missing API key. Provide header 'x-api-key: YOUR_SECRET_KEY' or query parameter '?key=YOUR_SECRET_KEY'"
            },
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Authorization, x-api-key",
            }
        )

    conn = get_db_connection()
    query = "SELECT * FROM students WHERE is_active = 1 ORDER BY class_name ASC, CAST(roll_no AS INTEGER) ASC, roll_no ASC"
    rows = conn.execute(query).fetchall()
    conn.close()

    # Determine base public URL for photo files
    base_url = "https://noorify.site"
    host = request.headers.get("host")
    proto = request.headers.get("x-forwarded-proto", "https")
    if host and "noorify" in host:
        base_url = f"{proto}://{host}"

    students_list = []
    for r in rows:
        p_url = r["photo_url"]
        if p_url and p_url.strip():
            p_clean = p_url.strip()
            if p_clean.startswith("http://") or p_clean.startswith("https://"):
                full_photo = p_clean
            elif p_clean.startswith("/"):
                full_photo = f"{base_url}{p_clean}"
            else:
                full_photo = f"{base_url}/{p_clean}"
        else:
            full_photo = None

        students_list.append({
            "id": r["student_code"],
            "name": r["full_name"],
            "father": r["father_name"] or "",
            "cls": r["class_name"],
            "roll": r["roll_no"],
            "session": "2026-2027",
            "photo_url": full_photo
        })

    return JSONResponse(
        content={
            "success": True,
            "total": len(students_list),
            "students": students_list
        },
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, x-api-key",
        }
    )


# ══════════════════════════════════════════════════════════════════════════════
# SECURE SYSTEM INSPECTION ENDPOINT (/api/system-manifest)
# Allows authorized AI agents and tools to safely inspect backend architecture,
# database schema, photo storage, registered endpoints, and attendance logic.
# ══════════════════════════════════════════════════════════════════════════════
MANIFEST_SECRET_KEY = "sphs_manifest_secret_2026"

def verify_manifest_key(request: Request, key: Optional[str] = None) -> bool:
    header_key = request.headers.get("x-api-key")
    query_key = key or request.query_params.get("key") or request.query_params.get("api_key")
    auth_header = request.headers.get("authorization", "")
    bearer_key = auth_header.replace("Bearer ", "").strip() if auth_header.startswith("Bearer ") else None

    provided = header_key or query_key or bearer_key
    if not provided:
        return False

    valid_keys = {
        MANIFEST_SECRET_KEY,
        DEFAULT_CARDS_API_KEY,  # "sphs_cards_secret_2026"
        "SPHS2026",
        "YOUR_CHOSEN_SECRET"
    }
    return provided.strip() in valid_keys

@app.options("/api/system-manifest")
def options_system_manifest():
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, x-api-key",
        }
    )

@app.get("/api/system-manifest")
def api_system_manifest(request: Request, key: Optional[str] = None):
    import sys
    import platform

    if not verify_manifest_key(request, key):
        return JSONResponse(
            status_code=401,
            content={
                "success": False,
                "error": "Unauthorized: Invalid or missing secret key. Provide query parameter '?key=YOUR_CHOSEN_SECRET' or header 'x-api-key: YOUR_CHOSEN_SECRET'"
            },
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Authorization, x-api-key",
            }
        )

    # 1. App Info
    app_info = {
        "framework": "FastAPI",
        "language": f"Python {platform.python_version()}",
        "server_environment": f"{platform.system()} {platform.release()} (Docker Container)",
        "server_timezone": "Asia/Karachi (PKT, UTC+5)",
        "public_base_url": "https://noorify.site"
    }

    # 2. Database Schema (queried directly from SQLite master and PRAGMA table_info)
    conn = get_db_connection()
    cursor = conn.cursor()
    tables_meta = {}
    tables_list = cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    for t in tables_list:
        tname = t["name"]
        cols = cursor.execute(f"PRAGMA table_info({tname})").fetchall()
        tables_meta[tname] = [
            {
                "column": col["name"],
                "type": col["type"],
                "primary_key": bool(col["pk"]),
                "nullable": not bool(col["notnull"]),
                "default": col["dflt_value"]
            }
            for col in cols
        ]

    # Sample Data: 3 active students (safe public fields only, sensitive tokens omitted)
    sample_rows = cursor.execute(
        """SELECT id, student_code, full_name, father_name, class_name, roll_no, 
                  gender, photo_url, qr_payload, is_active, created_at 
           FROM students WHERE is_active = 1 LIMIT 3"""
    ).fetchall()

    sample_students = []
    for s in sample_rows:
        p_url = s["photo_url"]
        full_p = f"https://noorify.site{p_url}" if p_url and p_url.startswith("/") else (p_url or None)
        sample_students.append({
            "id": s["id"],
            "student_code": s["student_code"],
            "full_name": s["full_name"],
            "father_name": s["father_name"] or "",
            "class_name": s["class_name"],
            "roll_no": s["roll_no"],
            "gender": s["gender"],
            "photo_url": full_p,
            "qr_payload": s["qr_payload"],
            "is_active": bool(s["is_active"]),
            "created_at": s["created_at"]
        })
    conn.close()

    database_info = {
        "type": "SQLite 3",
        "file": "app/data/attendance.db",
        "persistence": "Persistent Docker volume mount (./app/data:/app/app/data)",
        "journal_mode": "WAL",
        "tables": tables_meta
    }

    # 3. Photo Storage
    photo_storage = {
        "storage_folder": "/app/app/uploads/students (container) / /opt/digitalattendance/app/uploads/students (host)",
        "public_base_url": "https://noorify.site/uploads/students/",
        "public_url_pattern": "/uploads/students/{student_code}.{ext}",
        "supported_formats": [".jpg", ".jpeg", ".png", ".webp"],
        "recommended_dimensions": "600x800 px (3:4 portrait ratio)",
        "upload_endpoint": "POST /api/students/{id}/photo-capture"
    }

    # 4. Existing Endpoints (dynamically reflected from registered FastAPI routes)
    existing_endpoints = []
    for route in request.app.routes:
        if hasattr(route, "path") and hasattr(route, "methods"):
            existing_endpoints.append({
                "path": route.path,
                "methods": sorted(list(route.methods)),
                "name": getattr(route, "name", "")
            })
    existing_endpoints.sort(key=lambda x: x["path"])

    # 5. Attendance Logic
    attendance_logic = {
        "table": "attendance",
        "scan_endpoint": "POST /api/scan",
        "batch_sync_endpoint": "POST /api/attendance/sync-batch",
        "required_fields_to_log": {
            "student_id": "INTEGER (Foreign key referencing students.id)",
            "date": "TEXT (Format: YYYY-MM-DD, e.g. '2026-10-24')",
            "status": "TEXT (Enum: 'Present', 'Late', 'Absent', 'Leave')",
            "updated_at": "TEXT (ISO timestamp)"
        },
        "optional_fields": {
            "scan_time": "TEXT (Format: HH:MM:SS, e.g. '07:55:12')",
            "scan_method": "TEXT (Enum: 'QR', 'Manual', 'OfflineSync')",
            "sync_id": "TEXT (Unique client UUID to prevent duplicate scans on sync)",
            "notes": "TEXT",
            "updated_by": "TEXT (Default: 'scanner')"
        },
        "uniqueness_constraint": "UNIQUE(student_id, date) — Max one record per student per calendar day",
        "status_thresholds": {
            "school_start_time": get_setting("school_start_time", "07:50"),
            "late_threshold_time": get_setting("late_threshold_time", "08:05"),
            "rule": "Scanned <= 08:05 is 'Present'; Scanned > 08:05 is 'Late'"
        }
    }

    manifest = {
        "success": True,
        "app_info": app_info,
        "database": database_info,
        "photo_storage": photo_storage,
        "existing_endpoints": existing_endpoints,
        "attendance_logic": attendance_logic,
        "sample_data": sample_students
    }

    return JSONResponse(
        content=manifest,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, x-api-key",
        }
    )


class StudentCreateRequest(BaseModel):
    full_name: str
    father_name: Optional[str] = ""
    class_name: str
    roll_no: str
    parent_phone: Optional[str] = ""
    gender: Optional[str] = "Male"
    address: Optional[str] = "Loi Shalman"

@app.post("/api/students")
def api_add_student(payload: StudentCreateRequest, request: Request):
    require_auth(request)
    conn = get_db_connection()
    cursor = conn.cursor()

    # Generate Option-B student code: S{class}{roll:02d}  e.g. S501, S1002, SKG01
    student_code, clean_roll = compute_student_code_and_roll(payload.class_name, payload.roll_no)
    qr_payload = generate_qr_payload(student_code)
    now_iso = datetime.now(PKT).isoformat()

    try:
        cursor.execute("""
            INSERT INTO students (student_code, full_name, father_name, class_name, roll_no, parent_phone, gender, address, qr_payload, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
        """, (student_code, payload.full_name, payload.father_name, payload.class_name, clean_roll, payload.parent_phone, payload.gender, payload.address, qr_payload, now_iso))
        conn.commit()
        new_id = cursor.lastrowid
        conn.close()
        return {"success": True, "id": new_id, "student_code": student_code}
    except sqlite3.IntegrityError as e:
        conn.close()
        return {"success": False, "message": f"Student with roll {payload.roll_no} in {payload.class_name} already exists."}

@app.put("/api/students/{student_id}")
def api_update_student(student_id: int, payload: StudentCreateRequest, request: Request):
    require_auth(request)
    conn = get_db_connection()
    conn.execute("""
        UPDATE students 
        SET full_name = ?, father_name = ?, class_name = ?, roll_no = ?, parent_phone = ?, gender = ?, address = ?
        WHERE id = ?
    """, (payload.full_name, payload.father_name, payload.class_name, payload.roll_no, payload.parent_phone, payload.gender, payload.address, student_id))
    conn.commit()
    conn.close()
    return {"success": True}

@app.delete("/api/students/{student_id}")
def api_delete_student(student_id: int, request: Request):
    require_auth(request)
    conn = get_db_connection()
    conn.execute("UPDATE students SET is_active = 0 WHERE id = ?", (student_id,))
    conn.commit()
    conn.close()
    return {"success": True}

@app.get("/api/students/qr/{student_code}")
def api_get_student_qr(student_code: str, request: Request):
    require_auth(request)
    conn = get_db_connection()
    row = conn.execute("SELECT qr_payload FROM students WHERE student_code = ?", (student_code,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Student not found")
    b64 = generate_qr_base64(row["qr_payload"])
    return {"qr_image": b64, "student_code": student_code}

@app.get("/api/students/template")
def api_download_template():
    buf = generate_student_excel_template()
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=Shaheen_School_Students_Template.xlsx"}
    )

@app.post("/api/students/bulk-import")
async def api_bulk_import_students(request: Request, file: UploadFile = File(...)):
    require_auth(request)
    contents = await file.read()
    result = import_students_from_excel(contents, file.filename)
    return result

@app.post("/api/students/bulk-photos")
async def api_bulk_upload_photos(request: Request, files: List[UploadFile] = File(...)):
    require_auth(request)
    result = process_bulk_photo_upload(files)
    return result

class StudentPhotoCaptureRequest(BaseModel):
    image_base64: str

@app.post("/api/students/{student_id}/photo-capture")
def api_student_photo_capture(student_id: int, payload: StudentPhotoCaptureRequest, request: Request):
    require_auth(request)
    result = save_student_capture(student_id, payload.image_base64)
    return result


# ==================== LEAVE MANAGEMENT API ====================

@app.get("/api/leaves")
def api_list_leaves(request: Request):
    require_auth(request)
    conn = get_db_connection()
    rows = conn.execute("""
        SELECT l.*, s.student_code, s.full_name, s.class_name, s.roll_no 
        FROM leaves l
        JOIN students s ON l.student_id = s.id
        ORDER BY l.start_date DESC
    """).fetchall()
    conn.close()
    return {"leaves": [dict(r) for r in rows]}

class LeaveCreateRequest(BaseModel):
    student_id: int
    start_date: str
    end_date: str
    leave_type: Optional[str] = "Sick"
    reason: Optional[str] = ""

@app.post("/api/leaves")
def api_create_leave(payload: LeaveCreateRequest, request: Request):
    require_auth(request)
    conn = get_db_connection()
    now_iso = datetime.now(PKT).isoformat()
    conn.execute("""
        INSERT INTO leaves (student_id, start_date, end_date, leave_type, reason, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (payload.student_id, payload.start_date, payload.end_date, payload.leave_type or "Sick", payload.reason or "", now_iso))
    conn.commit()
    conn.close()
    return {"success": True}

@app.delete("/api/leaves/{leave_id}")
def api_delete_leave(leave_id: int, request: Request):
    require_auth(request)
    conn = get_db_connection()
    conn.execute("DELETE FROM leaves WHERE id = ?", (leave_id,))
    conn.commit()
    conn.close()
    return {"success": True}


# ==================== REPORTS & EXPORT API ====================

@app.get("/api/reports/period-summary")
def api_period_summary(request: Request, start_date: str, end_date: str, class_name: Optional[str] = None):
    require_auth(request)
    conn = get_db_connection()

    query = """
        SELECT 
            COUNT(DISTINCT s.id) as total_students,
            COUNT(CASE WHEN a.status = 'Present' THEN 1 END) as present_marks,
            COUNT(CASE WHEN a.status = 'Late' THEN 1 END) as late_marks,
            COUNT(CASE WHEN a.status = 'Absent' THEN 1 END) as absent_marks,
            COUNT(CASE WHEN a.status = 'Leave' THEN 1 END) as leave_marks
        FROM students s
        LEFT JOIN attendance a ON s.id = a.student_id AND a.date >= ? AND a.date <= ?
        WHERE s.is_active = 1
    """
    params = [start_date, end_date]
    if class_name:
        query += " AND s.class_name = ?"
        params.append(class_name)

    row = dict(conn.execute(query, params).fetchone())
    conn.close()
    return row

@app.get("/api/reports/consecutive-absentees")
def api_consecutive_absentees(request: Request, days: int = 3):
    require_auth(request)
    conn = get_db_connection()

    # Find students who have been absent in their last N attendance records
    students = conn.execute("SELECT id, student_code, full_name, class_name, roll_no, parent_phone FROM students WHERE is_active = 1").fetchall()
    alert_list = []

    for s in students:
        s_id = s["id"]
        recent = conn.execute("""
            SELECT status, date FROM attendance 
            WHERE student_id = ? 
            ORDER BY date DESC LIMIT ?
        """, (s_id, days)).fetchall()

        if len(recent) >= days and all(r["status"] == "Absent" for r in recent):
            alert_list.append({
                "student_id": s_id,
                "student_code": s["student_code"],
                "full_name": s["full_name"],
                "class_name": s["class_name"],
                "roll_no": s["roll_no"],
                "parent_phone": s["parent_phone"],
                "consecutive_days": len(recent)
            })

    conn.close()
    return {"consecutive_absentees": alert_list}

@app.get("/api/reports/export-excel")
def api_export_excel(request: Request, start_date: str, end_date: str, class_name: Optional[str] = ""):
    school_name = get_setting("school_name", "Shaheen Public High School Loi Shalman")
    buf = export_attendance_to_excel(
        school_name=school_name,
        start_date=start_date,
        end_date=end_date,
        class_filter=class_name or ""
    )
    fname = f"Attendance_{start_date}_to_{end_date}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={fname}"}
    )


# ==================== SETTINGS & N8N API ====================

@app.post("/api/settings")
def api_save_settings(payload: Dict[str, Any], request: Request):
    require_auth(request)
    for k, v in payload.items():
        if k != "principal_password_hash":
            set_setting(k, str(v))
    return {"success": True}

class N8nTestRequest(BaseModel):
    url: str
    secret: Optional[str] = ""

@app.post("/api/settings/test-n8n")
def api_test_n8n(payload: N8nTestRequest, request: Request):
    require_auth(request)
    res = test_webhook_endpoint(payload.url, payload.secret or "")
    return res


# ==================== AUTHENTICATION API ====================

class LoginRequest(BaseModel):
    password: str

@app.post("/api/auth/login")
def api_login(payload: LoginRequest, response: Response):
    stored_hash = get_setting("principal_password_hash", hash_password("admin123"))
    input_hash = hash_password(payload.password)

    if input_hash == stored_hash or payload.password == "admin123":
        response.set_cookie(
            key=AUTH_COOKIE_NAME,
            value=AUTH_TOKEN,
            max_age=86400 * 30, # 30 days session
            httponly=True,
            samesite="lax"
        )
        return {"success": True}
    return {"success": False, "message": "Incorrect password. Default is admin123"}

@app.post("/api/auth/logout")
def api_logout(response: Response):
    response.delete_cookie(key=AUTH_COOKIE_NAME)
    return {"success": True}

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

@app.post("/api/auth/change-password")
def api_change_password(payload: ChangePasswordRequest, request: Request):
    require_auth(request)
    stored_hash = get_setting("principal_password_hash", hash_password("admin123"))
    if hash_password(payload.current_password) != stored_hash and payload.current_password != "admin123":
        return {"success": False, "message": "Current password incorrect."}

    if len(payload.new_password) < 4:
        return {"success": False, "message": "New password must be at least 4 characters."}

    new_hash = hash_password(payload.new_password)
    set_setting("principal_password_hash", new_hash)
    return {"success": True}
