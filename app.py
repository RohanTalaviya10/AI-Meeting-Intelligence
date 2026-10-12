import socket
import threading
import time
import uvicorn


def is_backend_running(host: str = "127.0.0.1", port: int = 8000) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            return s.connect_ex((host, port)) == 0
    except Exception:
        return False


def start_backend():
    from backend.main import app as fastapi_app
    uvicorn.run(fastapi_app, host="127.0.0.1", port=8000, log_level="warning")


if not is_backend_running():
    server_thread = threading.Thread(target=start_backend, daemon=True)
    server_thread.start()
    for _ in range(30):
        if is_backend_running():
            break
        time.sleep(0.1)

import frontend.app
