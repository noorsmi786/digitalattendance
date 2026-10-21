import uvicorn
import socket

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

if __name__ == "__main__":
    local_ip = get_local_ip()
    port = 8000

    print("=" * 60)
    print("SHAHEEN PUBLIC HIGH SCHOOL LOI SHALMAN")
    print("Digital QR Attendance System Server Starting...")
    print("=" * 60)
    print(f"Phone Scanner URL:   http://{local_ip}:{port}/scanner")
    print(f"Principal Dashboard: http://localhost:{port}/admin")
    print(f"Mobile Dashboard:    http://{local_ip}:{port}/admin")
    print("Initial Password:    admin123")
    print("=" * 60)
    print("Press Ctrl + C to stop the server.\n")

    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
