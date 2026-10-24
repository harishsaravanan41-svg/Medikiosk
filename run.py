"""
MediKiosk Flask Application Entry Point
--------------------------------------
Run with:  python run.py
"""

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app import create_app
from app.config import Config
from app.extensions import socketio

app = create_app()


if __name__ == "__main__":
    print(f"Starting MediKiosk Real-Time Voice/Text AI on http://{Config.HOST}:{Config.PORT}")
    socketio.run(app, host=Config.HOST, port=Config.PORT, debug=Config.DEBUG, allow_unsafe_werkzeug=True)