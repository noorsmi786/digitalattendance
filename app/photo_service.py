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

ARCHIVE_DIR = os.path.join(os.path.dirname(__file__), "uploads", "replaced_archive")
os.makedirs(ARCHIVE_DIR, exist_ok=True)

def archive_existing_photo(student_code: str):
    """
    If a photo already exists for this student on disk, preserves it by
    copying it to 'uploads/replaced_archive/{student_code}_{timestamp}.{ext}'.
    Prevents any previous photo from being permanently lost when replaced.
    """
    import datetime
    for ext in [".jpg", ".jpeg", ".png", ".webp"]:
        existing_path = os.path.join(UPLOAD_DIR, f"{student_code}{ext}")
        if os.path.exists(existing_path) and os.path.getsize(existing_path) > 0:
            mtime = os.path.getmtime(existing_path)
            ts = datetime.datetime.fromtimestamp(mtime).strftime("%Y%m%d_%H%M%S")
            archive_filename = f"{student_code}_{ts}{ext}"
            archive_path = os.path.join(ARCHIVE_DIR, archive_filename)
            try:
                shutil.copy2(existing_path, archive_path)
            except Exception as e:
                print(f"Failed to archive existing photo {existing_path}: {e}")

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

    # 1. Match exact student_code (e.g. SPHS-1001, S102) or prefix before separator (e.g. S102_Manahil -> S102)
    student = cursor.execute(
        "SELECT id, student_code, full_name, class_name, roll_no FROM students WHERE LOWER(student_code) = ? AND is_active = 1",
        (base_name.lower(),)
    ).fetchone()

    if not student:
        for sep in ["_", "-", " "]:
            if sep in base_name:
                code_prefix = base_name.split(sep)[0].strip().lower()
                student = cursor.execute(
                    "SELECT id, student_code, full_name, class_name, roll_no FROM students WHERE LOWER(student_code) = ? AND is_active = 1",
                    (code_prefix,)
                ).fetchone()
                if student:
                    break

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

    # Archive existing photo if one is already present before replacing
    archive_existing_photo(student['student_code'])

    # Optimize photo for high-resolution print (max 1200px, quality 90, Lanczos filter)
    file_bytes, ext = optimize_image_for_print(file_bytes, ext, max_dim=1200)

    # Save to uploads directory with student_code filename
    target_filename = f"{student['student_code']}{ext}"
    target_path = os.path.join(UPLOAD_DIR, target_filename)

    with open(target_path, "wb") as f:
        f.write(file_bytes)

    # Relative URL with cache-busting timestamp so browser immediately shows new face
    import time
    ts = int(time.time())
    photo_url = f"/uploads/students/{target_filename}?t={ts}"
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

        # Archive existing photo if present before overwriting
        archive_existing_photo(student['student_code'])

        filename = f"{student['student_code']}.jpg"
        target_path = os.path.join(UPLOAD_DIR, filename)
        img.save(target_path, "JPEG", quality=90, optimize=True)

        ts = int(time.time())
        photo_url = f"/uploads/students/{filename}?t={ts}"
        cursor.execute("UPDATE students SET photo_url = ? WHERE id = ?", (photo_url, student_id))
        conn.commit()
        conn.close()

        return {
            "success": True,
            "photo_url": photo_url,
            "student_code": student["student_code"],
            "full_name": student["full_name"],
            "class_name": student["class_name"],
            "roll_no": student["roll_no"]
        }
    except Exception as e:
        return {"success": False, "message": f"Photo save failed: {str(e)}"}

def save_direct_student_photo(student_id: int, file_bytes: bytes, original_filename: str) -> Dict[str, Any]:
    """
    Directly uploads or replaces a photo for a single student from Admin panel:
    - Archives previous photo if one already existed
    - Normalizes orientation and crops/resizes to 3:4 portrait (900x1200, Lanczos)
    - Updates DB with ?t= cache buster timestamp
    """
    import time
    from PIL import Image, ImageOps

    conn = get_db_connection()
    cursor = conn.cursor()
    student = cursor.execute("SELECT id, student_code, full_name, class_name, roll_no FROM students WHERE id = ?", (student_id,)).fetchone()
    if not student:
        conn.close()
        return {"success": False, "message": f"Student with ID {student_id} not found."}

    code = student["student_code"]

    try:
        # 1. Archive existing photo
        archive_existing_photo(code)

        # 2. Process image with PIL
        img = Image.open(io.BytesIO(file_bytes))
        img = ImageOps.exif_transpose(img)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

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

        img = img.resize((900, 1200), Image.Resampling.LANCZOS)
        filename = f"{code}.jpg"
        target_path = os.path.join(UPLOAD_DIR, filename)
        img.save(target_path, "JPEG", quality=90, optimize=True)

        ts = int(time.time())
        photo_url = f"/uploads/students/{filename}?t={ts}"
        cursor.execute("UPDATE students SET photo_url = ? WHERE id = ?", (photo_url, student_id))
        conn.commit()
        conn.close()

        return {
            "success": True,
            "photo_url": photo_url,
            "student_code": code,
            "full_name": student["full_name"],
            "message": f"Photo updated and old photo archived for {student['full_name']}!"
        }
    except Exception as e:
        conn.close()
        return {"success": False, "message": f"Photo save failed: {str(e)}"}

