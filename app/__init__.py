"""Grow — Flask app factory."""

from flask import Flask, send_from_directory, jsonify
from flask_wtf.csrf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix
from config import Config
from app.models import db, init_default_user
from app.migrate import auto_migrate

csrf = CSRFProtect()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Trust Caddy reverse proxy headers (X-Forwarded-Proto, X-Forwarded-Host)
    # so url_for() generates https:// URLs for OAuth callbacks
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    # Initialize extensions
    db.init_app(app)
    csrf.init_app(app)

    with app.app_context():
        db.create_all()
        auto_migrate(app)  # Add any missing columns (no more "rm grow.db"!)
        init_default_user(app)

        # Seed micro-habit pool (safe to call multiple times)
        from app.services.micro_habits import seed_micro_habit_pool
        seed_micro_habit_pool()

    # Security headers
    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        return response

    # Serve service worker from root (scope must be / for push on all browsers)
    @app.route("/sw.js")
    def service_worker():
        response = send_from_directory(app.static_folder, "sw.js")
        response.headers["Content-Type"] = "application/javascript"
        response.headers["Service-Worker-Allowed"] = "/"
        response.headers["Cache-Control"] = "no-cache"
        return response

    # Web app manifest (required by Firefox Android for push)
    @app.route("/manifest.json")
    def manifest():
        return jsonify({
            "name": "Grow",
            "short_name": "Grow",
            "start_url": "/",
            "display": "standalone",
            "background_color": "#f5f3ef",
            "theme_color": "#3d6b4f",
        })

    # Register routes
    from app.routes.dashboard import bp as dashboard_bp
    from app.routes.auth import bp as auth_bp
    from app.routes.tracking import bp as tracking_bp
    from app.routes.push import bp as push_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(tracking_bp)
    app.register_blueprint(push_bp)

    return app
