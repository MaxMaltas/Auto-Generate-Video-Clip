from flask import Flask, render_template
from app.routes.main_routes import main_bp
from app.routes.media_routes import media_bp
from app.routes.process_routes import process_bp
from app.routes.titular_routes import titular_bp
from app.services.logger_service import RequestLogger

def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    RequestLogger(app)

    app.register_blueprint(main_bp)
    app.register_blueprint(media_bp)
    app.register_blueprint(process_bp)
    app.register_blueprint(titular_bp)

    @app.route("/")
    def index():
        return render_template("index.html")

    return app