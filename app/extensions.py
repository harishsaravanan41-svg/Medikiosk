from flask_cors import CORS
from flask_socketio import SocketIO

cors = CORS()
socketio = SocketIO(cors_allowed_origins="*", async_mode="threading")


def init_extensions(app):
    cors.init_app(app)
    socketio.init_app(app)

