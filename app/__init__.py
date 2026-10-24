from flask import Flask, render_template

from app.config import Config
from app.extensions import init_extensions, cors


def create_app(config_class=Config):
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
        static_url_path="/static",
    )
    app.config.from_object(config_class)

    init_extensions(app)

    from app.routes.chat import chat_bp
    from app.routes.audio import audio_bp
    from app.routes.session import session_bp
    from app.routes.config_routes import config_bp
    from app.routes.auth import auth_bp
    from app.routes.doctor import doctor_bp

    app.register_blueprint(chat_bp)
    app.register_blueprint(audio_bp)
    app.register_blueprint(session_bp)
    app.register_blueprint(config_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(doctor_bp)

    @app.route("/")
    def index():
        return render_template("index.html")

    return app
