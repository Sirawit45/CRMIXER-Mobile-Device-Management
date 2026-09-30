import os
import sys
import webbrowser
import threading
import time
import uvicorn

# Ensure python path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

def open_browser(url: str, delay: float = 1.5):
    time.sleep(delay)
    print(f"\n[MDM] Opening browser at {url} ...")
    webbrowser.open(url)

if __name__ == "__main__":
    host = "127.0.0.1"
    port = 8000
    app_url = f"http://{host}:{port}"

    print("=" * 65)
    print("   CRMIXER MOBILE DEVICE MANAGEMENT v0.5.4")
    print("   Multi-Device Control & Screen Mirroring System")
    print("=" * 65)
    print(f"[*] Starting Server on {app_url}")
    print("[*] Plug in Android devices with USB Debugging enabled")
    print("=" * 65)

    # Launch browser automatically
    threading.Thread(target=open_browser, args=(app_url,), daemon=True).start()

    # Start FastAPI server via uvicorn
    uvicorn.run("app.server:app", host=host, port=port, log_level="info")
