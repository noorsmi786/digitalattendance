# 🎓 Smart Digital Attendance & Student ID Card Management System

A high-speed, offline-first digital attendance and student identification platform. Features an automated AI-powered serial photo booth, printable CR80 plastic card studio, PWA gate kiosk scanner with wake-lock, comprehensive admin management, and automated webhook notifications.

---

## 🌟 Core Modules

### 1. 📱 Offline-Ready Kiosk QR Scanner (PWA)
* **Kiosk Stand Mode**: Optimized for smartphones or tablets mounted on stands at school entrance gates.
* **Screen WakeLock API**: Keeps device screens awake throughout morning rush hour.
* **100% Offline Capability**: Scans are stored securely in browser `IndexedDB` when network connectivity drops and automatically sync with the server once reconnected.
* **High-Speed Audio & Visual Feedback**: Distinct instant tones and color flashes for Present, Late, Already Scanned, and On Leave.
* **Dual Camera Support**: Easy one-tap toggle between Front and Rear lenses.
* **Manual Entry Fallback**: Quick numerical pad for manual roll number check-ins if cards are damaged.

### 2. 📸 Serial Photo Booth with AI Virtual Backgrounds
* **Client-Side AI Segmentation**: Real-time virtual background replacement (MediaPipe) running locally on phone or laptop browsers with zero VPS CPU load.
* **Studio-Grade Backgrounds**: Passport Navy, Royal Blue, Institution Green, Clean White, Cream/Ivory, and Studio Grey.
* **Rapid Serial Capture**: Sequential student queues with Spacebar, on-screen tap, or Bluetooth selfie remote shutter triggers.
* **Smart Filter Queue**: Filter by Class, Gender, or Missing Photo status to shoot missing student batches in minutes.

### 3. 🖨️ CR80 Plastic ID Card & QR Sticker Studio
* **Standard CR80 Credit-Card Dimensions**: Formatted for standard 85.6mm × 54mm PVC/Plastic card printers.
* **Multi-Theme Studio**:
  * *Royal Classic Blue*
  * *Emerald Lanyard Green*
  * *Cyber Navy Dark*
  * *Crimson Red*
  * *Eco Ink-Saver Monochrome*
* **A4 Multi-Up Layouts**: Batch-print 8 CR80 cards per A4 sheet with clean cut marks.
* **Peel & Stick Sticker Sheets**: 24-up QR badge sheets to stick onto existing plastic cards or student diaries.

### 4. 👨‍💼 School Administration & Management Panel
* **Live Daily Dashboard**: Real-time KPI summaries for Present, Late arrivals, Absents, and Approved Leaves.
* **Student Roster Management**: Search and filter by Class, Gender, Photo Status, and missing details (e.g. missing father names).
* **Automated Roll Calling**: Single-click "Close Day" to automatically mark all un-scanned students as Absent.
* **Leave Management**: Schedule and approve sick, family, casual, or emergency leaves with date ranges.
* **Multi-Format Reports**: Export attendance records to Excel (`.xlsx`) or print formatted register sheets with signature lines.
* **Bulk Import & Template Generator**: Instant Excel upload for rosters with automatic student code and QR generation.

### 5. 🔔 Automated Webhook & Notification Engine
* Built-in webhook triggers for n8n, Make, or custom API endpoints.
* Easily integrated with WhatsApp Gateways (Evolution API, Baileys, Twilio) for automatic absent parent alerts.

---

## 🚀 Quick Start (Local Development)

### 1. Clone & Install
```bash
git clone https://github.com/noorsmi786/digitalattendance.git
cd digitalattendance
pip install -r requirements.txt
```

### 2. Start Application
```bash
python run.py
```

### 3. Access Portals
* **Admin Dashboard**: `http://localhost:8000/admin` *(Default Password: `admin123`)*
* **Photo Booth**: `http://localhost:8000/photo-booth`
* **Gate Scanner**: `http://localhost:8000/scanner`

---

## 🐳 Docker & VPS Deployment

The project includes pre-configured Docker and Traefik reverse-proxy support with automatic Let's Encrypt SSL.

### Run with Docker Compose
```bash
docker compose up -d --build
```

---

## 📋 Technology Stack
* **Backend**: FastAPI, Python 3.11, SQLite, Uvicorn
* **Frontend**: HTML5, Vanilla JavaScript, CSS3, Jinja2 Templates
* **Computer Vision & AI**: MediaPipe Selfie Segmentation, HTML5-QRCode
* **PWA & Storage**: Service Workers, Cache API, IndexedDB
* **DevOps**: Docker, Docker Compose, Traefik, Systemd, Nginx
