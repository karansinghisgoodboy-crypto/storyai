"""StoryAI - Flask application.

Run locally:   python app.py
Then open:     http://127.0.0.1:5000
"""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import HTTPException

from config import Config
from db.database import close_db, init_db
from routes.projects import bp as projects_bp
from routes.characters import bp as characters_bp
from routes.locations import bp as locations_bp
from routes.story import bp as story_bp
from routes.scenes import bp as scenes_bp
from routes.shots import bp as shots_bp
from routes.chat import bp as chat_bp
from routes.memory import bp as memory_bp
from routes.proposals import bp as proposals_bp
from routes.continuity import bp as continuity_bp
from routes.export import bp as export_bp
from services.errors import AppError

UPLOAD_SUBFOLDERS = ("characters", "locations", "panels")

HTTP_MESSAGES = {
    400: "That request wasn't valid.",
    404: "Not found.",
    405: "That action isn't allowed here.",
    413: "That request is too large.",
}


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    for name in UPLOAD_SUBFOLDERS:
        (Path(app.config["UPLOAD_DIR"]) / name).mkdir(parents=True, exist_ok=True)

    _setup_logging(app)
    init_db(app)

    app.teardown_appcontext(close_db)
    app.register_blueprint(projects_bp)
    app.register_blueprint(characters_bp)
    app.register_blueprint(locations_bp)
    app.register_blueprint(story_bp)
    app.register_blueprint(scenes_bp)
    app.register_blueprint(shots_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(memory_bp)
    app.register_blueprint(proposals_bp)
    app.register_blueprint(continuity_bp)
    app.register_blueprint(export_bp)

    @app.get("/")
    def index():
        return render_template("index.html")

    _register_headers(app)
    _register_error_handlers(app)
    return app


def _setup_logging(app):
    """Technical details go to a local log file, never to the browser."""
    if app.config.get("TESTING"):
        return
    handler = RotatingFileHandler(
        app.config["LOG_PATH"], maxBytes=500_000, backupCount=1, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)


def _register_headers(app):
    @app.after_request
    def add_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; frame-ancestors 'none'"
        )
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response


def _register_error_handlers(app):
    @app.errorhandler(AppError)
    def handle_app_error(err):
        return jsonify(error=err.message), err.status_code

    @app.errorhandler(HTTPException)
    def handle_http_error(err):
        if request.path.startswith("/api/"):
            return jsonify(error=HTTP_MESSAGES.get(err.code, err.name)), err.code
        return err

    @app.errorhandler(Exception)
    def handle_unexpected_error(err):
        app.logger.exception("Unexpected error on %s %s", request.method, request.path)
        return jsonify(error="Something went wrong on the server. Please try again."), 500


if __name__ == "__main__":
    application = create_app()
    application.run(
        host=application.config["HOST"], port=application.config["PORT"], debug=False
    )
