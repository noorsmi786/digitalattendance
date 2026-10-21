#!/usr/bin/env bash
# Deployment script for Shaheen Public High School Attendance on Hostinger KVM4 VPS (Ubuntu / Debian)

set -e

echo "=========================================================="
echo "🏫 Shaheen Public High School - Hostinger VPS Deployment"
echo "=========================================================="

# 1. Update system packages
echo "Updating packages..."
sudo apt-get update -y
sudo apt-get install -y python3 python3-pip python3-venv nginx

# 2. Setup Virtual Environment
APP_DIR=$(pwd)
echo "Setting up virtual environment in $APP_DIR..."
python3 -m venv venv
source venv/bin/activate

# 3. Install requirements
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# 4. Setup Systemd Service for 24/7 background uptime
echo "Setting up systemd service..."
sudo bash -c "cat > /etc/systemd/system/attendance.service <<EOF
[Unit]
Description=Shaheen Public High School Digital Attendance Server
After=network.target

[Service]
User=$USER
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/venv/bin/python $APP_DIR/run.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF"

sudo systemctl daemon-reload
sudo systemctl enable attendance
sudo systemctl restart attendance

echo "=========================================================="
echo "✅ Attendance System is RUNNING as a systemd service!"
echo "Status check: sudo systemctl status attendance"
echo "Logs:         sudo journalctl -u attendance -f"
echo "=========================================================="
