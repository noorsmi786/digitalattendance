#!/usr/bin/env bash
# One-click updater for Digital Attendance System on VPS
set -e

echo "=========================================="
echo "🔄 Updating Digital Attendance System..."
echo "=========================================="

cd /opt/digitalattendance
git pull origin main
docker compose up -d --build

echo "=========================================="
echo "✅ Update complete! App is LIVE."
echo "=========================================="
