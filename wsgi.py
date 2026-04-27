"""Entry point for the Grow app."""

import os
from app import create_app

app = create_app()

if __name__ == "__main__":
    ssl_context = None
    if os.path.exists("cert.pem") and os.path.exists("key.pem"):
        ssl_context = ("cert.pem", "key.pem")
        print("Running with HTTPS (self-signed certificate)")
    else:
        print("Running with HTTP (no cert.pem/key.pem found)")

    is_dev = os.getenv("FLASK_ENV", "production") != "production"
    app.run(host="0.0.0.0", port=8080, debug=is_dev, ssl_context=ssl_context)
