"""Grow — Flask app factory."""

from flask import Flask
from flask_wtf.csrf import CSRFProtect
from config import Config
from app.models import db, init_default_user
from app.migrate import auto_migrate

csrf = CSRFProtect()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

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

    # Register routes
    from app.routes.dashboard import bp as dashboard_bp
    from app.routes.auth import bp as auth_bp
    from app.routes.tracking import bp as tracking_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(tracking_bp)

    return app
