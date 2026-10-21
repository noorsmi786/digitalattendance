# 🏫 Shaheen Public High School Loi Shalman — Digital Attendance System

A modern, high-speed, QR code-based digital attendance system specifically built for **Shaheen Public High School Loi Shalman**. Designed to run on an **Android mobile phone fixed on a stand**, with 100% offline scanning capability, automatic VPS sync, and a single-user Principal Dashboard.

---

## 🌟 Key Features

1. **📱 Ultra-Lightweight Android Scanner (< 500 KB PWA)**:
   - Fixed-stand kiosk view with zero clutter.
   - Screen **WakeLock API** prevents the phone screen from sleeping while on the stand.
   - Uses Web Audio API for built-in audio beeps (no external audio files to download).
   - Instant visual flash: 🟢 Green (Present), 🟡 Amber (Late / Already Marked), 🔴 Red (Error).
   - Camera toggle button (Front / Back camera) with memory.
   - Manual Roll No entry fallback button if a card is crumpled or dirty.

2. **📴 100% Offline Capability**:
   - Stores scans in `IndexedDB` on the phone when internet/Wi-Fi is down.
   - Preserves actual scan timestamps so offline arrival times remain 100% accurate.
   - Auto-syncs to the Hostinger VPS whenever internet is restored, plus a manual "Sync Now" button.

3. **🖨️ Two QR Printing Options for Students**:
   - **Full Student ID Cards**: Printable A4 sheet (standard 85.6mm x 54mm ID badge size) with school letterhead, student name, class, roll number, and QR code.
   - **QR Sticker Sheets (Peel & Stick)**: Printable label grid to cut or peel and stick directly onto existing student cards.

4. **👨‍💼 Single-User Principal Dashboard**:
   - Protected with password (default: `admin123`, changeable in Settings).
   - Real-time KPIs: Present today, Late today, Absent today, Approved Leave, Attendance %.
   - Class-by-Class progress bars.
   - Search by student name, roll number, or filter by class and status.
   - **Manual Corrections**: Principal can edit any student's status with reason and audit log.
   - **Close Day & Auto-Mark Absentees**: One click marks all unmarked students as Absent.

5. **📊 Reports & Analytics**:
   - Daily, Weekly, and Monthly reports with custom date filters.
   - Download multi-sheet Excel files (`.xlsx`) or `.csv`.
   - Printable Daily Attendance Register with School Letterhead and Principal Signature line.
   - **Consecutive Absentees Alert**: Highlights any student absent 3+ days in a row with parent contact phone.

6. **📅 Leave Management**:
   - Register sick, casual, emergency, or family leave for students with date ranges.
   - Phone scanner automatically recognizes approved leave and avoids marking absent.

7. **📥 Bulk Student Excel Import**:
   - Upload student roster via Excel (`.xlsx`) or CSV.
   - Built-in "Download Sample Excel Template" button.
   - Automatically generates unique sequential codes (`SPHS-1001`, `SPHS-1002`...) and encrypted QR codes.

8. **📲 WhatsApp Notifications via n8n (Pre-Wired)**:
   - Settings tab has an n8n Webhook configuration box with a **⚡ Test Connection** button.
   - Included `sample_n8n_workflow.json` ready to import into your Hostinger KVM4 VPS n8n.

---

## 🚀 Quick Start (Running Locally on Windows)

1. Open PowerShell or Command Prompt in this folder.
2. Ensure dependencies are installed:
   ```bash
   pip install -r requirements.txt
   ```
3. Start the server:
   ```bash
   python run.py
   # or double-click start.bat
   ```
4. Access the URLs:
   - **Principal Admin Dashboard**: `http://localhost:8000/admin` (Password: `admin123`)
   - **Phone Scanner App**: `http://<your-local-ip>:8000/scanner`

---

## ☁️ Deployment on Hostinger KVM4 VPS (Ubuntu / Debian)

1. **Upload or clone this project folder** to your VPS:
   ```bash
   scp -r "digital attendance" user@your-vps-ip:/home/user/attendance
   ```

2. **SSH into your VPS**:
   ```bash
   ssh user@your-vps-ip
   cd attendance
   ```

3. **Run the automated deployment script**:
   ```bash
   chmod +x deploy.sh
   ./deploy.sh
   ```
   *This automatically sets up Python virtualenv, installs packages, and configures `attendance.service` as a 24/7 background systemd service.*

4. **(Optional) Configure Nginx reverse proxy**:
   ```bash
   sudo cp nginx.conf /etc/nginx/sites-available/attendance
   # Edit domain name or IP:
   sudo nano /etc/nginx/sites-available/attendance
   sudo ln -s /etc/nginx/sites-available/attendance /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl restart nginx
   ```

5. **(Optional) Enable Free SSL with Certbot**:
   ```bash
   sudo apt-get install certbot python3-certbot-nginx -y
   sudo certbot --nginx -d your-domain.com
   ```

---

## 📱 Setting Up the Android Phone on Stand

1. Open **Google Chrome** on the phone.
2. Visit `http://your-vps-ip:8000/scanner` (or your domain with HTTPS).
3. Allow camera permission when prompted.
4. Tap the three dots menu in Chrome → tap **"Add to Home Screen"** or **"Install App"**.
5. Tap the new **SPHS Scanner** icon on the home screen to open it in **full-screen kiosk mode**.
6. Place the phone on the stand facing students. Done!

---

## ⚙️ Default Timings & Rules

- **School Start Time**: 07:50 AM
- **Late Threshold Time**: 08:05 AM (Arrivals between 08:05 AM and 12:30 PM are marked Late)
- **School Dismissal**: 12:30 PM
- **Classes**: KG, 1st, 2nd, 3rd, 4th, 5th, 6th, 7th, 8th, 9th, 10th
- *All of these can be changed anytime from the Settings tab in the Admin Dashboard!*
