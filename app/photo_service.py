import os
import zipfile
import io
import shutil
import re
from typing import List, Dict, Any, Tuple
from fastapi import UploadFile
from app.database import get_db_connection

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads", "students")
os.makedirs(UPLOAD_DIR, exist_ok=True)

def sanitize_filename(name: str) -> str:
    return re.sub(r'[^a-zA-Z0-9_\-\.]', '', name)

def optimize_image_for_print(file_bytes: bytes, original_ext: str, max_dim: int = 1200) -> Tuple[bytes, str]:
    """
    Optimizes raw camera photos (4MB-10MB+) down to ultra-crisp print size (~120KB-180KB).
    - Preserves orientation via EXIF transpose.
    - Uses LANCZOS resampling (highest quality downsampling filter in imaging).
    - Caps longest edge at 1200px (equivalent to 600+ DPI on printed ID card).
    - If PNG with transparency, preserves RGBA/PNG.
    - If already small (< 300KB and <= 1200px), leaves bytes untouched.
    """
    try:
        from PIL import Image, ImageOps
        img = Image.open(io.BytesIO(file_bytes))
        img = ImageOps.exif_transpose(img)

        w, h = img.size
        # If already reasonable size, don't recompress
        if max(w, h) <= max_dim and len(file_bytes) < 300 * 1024:
            return file_bytes, original_ext

        # Scale preserving aspect ratio if larger than max_dim
        if max(w, h) > max_dim:
            if w > h:
                new_w = max_dim
                new_h = int(h * (max_dim / w))
            else:
                new_h = max_dim
                new_w = int(w * (max_dim / h))
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

        out_io = io.BytesIO()
        if original_ext.lower() == '.png' and img.mode in ('RGBA', 'LA', 'P'):
            img.save(out_io, 'PNG', optimize=True)
            return out_io.getvalue(), '.png'
        else:
            if img.mode != 'RGB':
                img = img.convert('RGB')
            img.save(out_io, 'JPEG', quality=90, optimize=True)
            return out_io.getvalue(), '.jpg'
    except Exception:
        # Fallback to original bytes if any error parsing
        return file_bytes, original_ext

def match_and_save_photo(file_bytes: bytes, original_filename: str) -> Tuple[bool, str, str]:
    """
    Matches photo filename to a student:
    - SPHS-1001.jpg -> Matches student_code SPHS-1001
    - 01.jpg or 15.jpg -> Matches roll_no 01 or 15
    - Muhammad_Ali.jpg -> Matches full_name
    Returns: (matched: bool, message: str, student_code: str)
    """
    base_name = os.path.splitext(original_filename)[0].strip()
    ext = os.path.splitext(original_filename)[1].lower()
    if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
        return False, f"Unsupported image extension {ext}", ""

    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Match exact student_code (e.g. SPHS-1001)
    student = cursor.execute(
        "SELECT id, student_code, full_name, class_name, roll_no FROM students WHERE LOWER(student_code) = ? AND is_active = 1",
        (base_name.lower(),)
    ).fetchone()

    # 2. Match exact roll_no (e.g. 01, 15) or clean roll
    if not student:
        # Check if base_name is digits or e.g. "10-01"
        clean_roll = base_name.lstrip('0')
        student = cursor.execute(
            "SELECT id, student_code, full_name, class_name, roll_no FROM students WHERE (roll_no = ? OR roll_no = ?) AND is_active = 1 LIMIT 1",
            (base_name, clean_roll)
        ).fetchone()

    # 3. Match normalized name (e.g. Muhammad_Ali -> Muhammad Ali)
    if not student:
        clean_name = base_name.replace('_', ' ').replace('-', ' ').strip().lower()
        student = cursor.execute(
            "SELECT id, student_code, full_name, class_name, roll_no FROM students WHERE LOWER(full_name) = ? AND is_active = 1 LIMIT 1",
            (clean_name,)
        ).fetchone()

    if not student:
        conn.close()
        return False, f"No matching student found for '{original_filename}'", ""

    # Optimize photo for high-resolution print (max 1200px, quality 90, Lanczos filter)
    file_bytes, ext = optimize_image_for_print(file_bytes, ext, max_dim=1200)

    # Save to uploads directory with student_code filename
    target_filename = f"{student['student_code']}{ext}"
    target_path = os.path.join(UPLOAD_DIR, target_filename)

    with open(target_path, "wb") as f:
        f.write(file_bytes)

    # Relative URL accessible via web
    photo_url = f"/uploads/students/{target_filename}"
    cursor.execute("UPDATE students SET photo_url = ? WHERE id = ?", (photo_url, student["id"]))
    conn.commit()
    conn.close()

    return True, f"Matched to {student['full_name']} (Class {student['class_name']}, Roll {student['roll_no']})", student["student_code"]

def process_bulk_photo_upload(files: List[UploadFile]) -> Dict[str, Any]:
    matched = []
    unmatched = []

    for f in files:
        filename = f.filename
        content = f.file.read()

        # If user uploaded a ZIP archive
        if filename.lower().endswith(".zip"):
            try:
                with zipfile.ZipFile(io.BytesIO(content)) as z:
                    for z_item in z.namelist():
                        if z_item.endswith("/") or "__MACOSX" in z_item:
                            continue
                        sub_file = os.path.basename(z_item)
                        if not sub_file:
                            continue
                        sub_bytes = z.read(z_item)
                        ok, msg, code = match_and_save_photo(sub_bytes, sub_file)
                        if ok:
                            matched.append({"filename": sub_file, "message": msg, "student_code": code})
                        else:
                            unmatched.append({"filename": sub_file, "reason": msg})
            except Exception as e:
                unmatched.append({"filename": filename, "reason": f"Corrupt ZIP file: {str(e)}"})
        else:
            ok, msg, code = match_and_save_photo(content, filename)
            if ok:
                matched.append({"filename": filename, "message": msg, "student_code": code})
            else:
                unmatched.append({"filename": filename, "reason": msg})

    return {
        "success": True,
        "matched_count": len(matched),
        "unmatched_count": len(unmatched),
        "matched": matched,
        "unmatched": unmatched,
        "message": f"Successfully processed: {len(matched)} photos matched & attached to students!"
    }

def save_student_capture(student_id: int, image_base64: str) -> Dict[str, Any]:
    """
    Saves webcam/phone capture directly for student_id:
    - Decodes base64 image data
    - Center-crops to 3:4 portrait ratio for ID cards
    - Saves as {student_code}.jpg
    - Updates student photo_url in database
    """
    import base64
    import time
    from PIL import Image

    if "," in image_base64:
        image_base64 = image_base64.split(",")[1]

    try:
        raw_bytes = base64.b64decode(image_base64)
        img = Image.open(io.BytesIO(raw_bytes))
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        # Center-crop to 3:4 portrait ratio
        w, h = img.size
        target_ratio = 3.0 / 4.0
        cur_ratio = w / h
        if cur_ratio > target_ratio:
            new_w = int(h * target_ratio)
            left = (w - new_w) // 2
            img = img.crop((left, 0, left + new_w, h))
        else:
            new_h = int(w / target_ratio)
            top = (h - new_h) // 2
            img = img.crop((0, top, w, top + new_h))

        # Upgrade to 900x1200 with LANCZOS resampling (equivalent to 600+ DPI on printed card)
        img = img.resize((900, 1200), Image.Resampling.LANCZOS)

        conn = get_db_connection()
        cursor = conn.cursor()
        student = cursor.execute("SELECT id, student_code, full_name, class_name, roll_no FROM students WHERE id = ?", (student_id,)).fetchone()
        if not student:
            conn.close()
            return {"success": False, "message": f"Student with ID {student_id} not found."}

        filename = f"{student['student_code']}.jpg"
        target_path = os.path.join(UPLOAD_DIR, filename)
        img.save(target_path, "JPEG", quality=90, optimize=True)

        photo_url = f"/uploads/students/{filename}"
        cursor.execute("UPDATE students SET photo_url = ? WHERE id = ?", (photo_url, student_id))
        conn.commit()
        conn.close()

        cache_busting_url = f"{photo_url}?t={int(time.time())}"
        return {
            "success": True,
            "photo_url": cache_busting_url,
            "student_code": student["student_code"],
            "full_name": student["full_name"],
            "class_name": student["class_name"],
            "roll_no": student["roll_no"]
        }
    except Exception as e:
        return {"success": False, "message": f"Photo save failed: {str(e)}"}
