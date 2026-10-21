import qrcode
import io
import base64
import re
from typing import Tuple

def compute_student_code_and_roll(class_name: str, raw_roll: str) -> Tuple[str, str]:
    """
    Computes human-friendly code and clean roll:
    Example: Class '5th', Roll '1' or 'SPS001' -> ('S501', '01')
             Class '5th', Roll '12' -> ('S512', '12')
             Class '10th', Roll '1' -> ('S1001', '01')
             Class 'KG', Roll '1'   -> ('SKG01', '01')
    """
    nums = re.findall(r'\d+', str(raw_roll or '1'))
    roll_num = int(nums[-1]) if nums else 1
    clean_roll = f"{roll_num:02d}"

    c_nums = re.findall(r'\d+', str(class_name or '0'))
    if c_nums:
        c_prefix = c_nums[0]
    else:
        clean_c = re.sub(r'[^a-zA-Z]', '', str(class_name or 'KG')).upper()
        c_prefix = clean_c[:3] if clean_c else 'KG'

    student_code = f"S{c_prefix}{clean_roll}"
    return student_code, clean_roll

def generate_qr_payload(student_code: str) -> str:
    """Returns ultra-compact payload (e.g. S501, S512) for maximum QR scan robustness"""
    return student_code.strip()

def verify_qr_payload(payload: str) -> str:
    """Verifies payload format. Returns clean student_code."""
    payload = payload.strip()
    if payload.startswith("SPHS:"):
        parts = payload.split(":")
        if len(parts) >= 2:
            return parts[1]
    return payload

def generate_qr_base64(payload: str) -> str:
    """
    Generate QR code as base64 data URI PNG.
    With short 4-6 char payload, Version 1 (21x21 modules) with Error Correction H (30%)
    provides massive black blocks and indestructible readability.
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H, # 30% error correction!
        box_size=10,
        border=2,
    )
    qr.add_data(payload)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    b64_str = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{b64_str}"
