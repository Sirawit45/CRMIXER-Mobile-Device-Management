import os
import sys
import threading
import time
import socket
import uvicorn
import webview

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

def get_free_port(default_port: int = 8000) -> int:
    """Finds an available TCP port."""
    for p in [default_port, 8055, 8080, 8088, 8888, 0]:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", p))
                return s.getsockname()[1]
        except OSError:
            continue
    return default_port

if __name__ == "__main__":
    HOST = "127.0.0.1"
    PORT = get_free_port(8000)
    APP_URL = f"http://{HOST}:{PORT}"

    print(f"[*] Launching CRMIXER MDM on {APP_URL} ...")

    def start_server():
        uvicorn.run("app.server:app", host=HOST, port=PORT, log_level="warning")

    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    time.sleep(1.2)

    # Open Native Windows Desktop Window
    window = webview.create_window(
        title="CRMIXER Mobile Device Management v0.5.4",
        url=APP_URL,
        width=1320,
        height=860,
        min_size=(960, 600),
        background_color="#0b0f17"
    )

    webview.start(debug=False)
