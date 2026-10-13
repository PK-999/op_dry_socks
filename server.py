"""Dry Socks dashboard: python server.py [--config PATH] [--port 5111]."""

import argparse
import threading

from flask import Flask, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException

from services.configuration import ROOT, ConfigurationError
from services.dashboard import dashboard

WEB_DIR = ROOT / "web"


def create_app(config_path=None, *, demo=False):
    """Build an isolated local app; importing this module starts no server."""
    app = Flask(__name__, static_folder=None)
    app.config.update(CONFIG_PATH=config_path, DEMO=demo, MAX_CONTENT_LENGTH=1024 * 1024)
    app.extensions["config_lock"] = threading.Lock()
    if demo:
        from services.demo import config

        app.extensions["demo_config"] = config()
    app.register_blueprint(dashboard)

    @app.before_request
    def local_requests_only():
        # Reject DNS rebinding and cross-origin mutations of this local service.
        if request.host.split(":")[0] not in ("localhost", "127.0.0.1"):
            return jsonify(error="This app accepts local connections only."), 403
        if request.method == "POST":
            origin = request.headers.get("Origin")
            if origin and origin != request.host_url.rstrip("/"):
                return jsonify(error="Cross-origin requests are not allowed."), 403
            if request.headers.get("Sec-Fetch-Site") == "cross-site":
                return jsonify(error="Cross-site requests are not allowed."), 403

    @app.after_request
    def response_headers(response):
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = (
            "strict-origin-when-cross-origin" if response.mimetype == "text/html" else "same-origin"
        )
        return response

    @app.errorhandler(ValueError)
    def invalid_request(error):
        return jsonify(error=str(error)), 400

    @app.errorhandler(ConfigurationError)
    def invalid_configuration(error):
        return jsonify(error=str(error)), 500

    @app.errorhandler(HTTPException)
    def http_error(error):
        if request.path.startswith("/api/"):
            return jsonify(error=error.description), error.code
        return error

    @app.get("/")
    def index():
        return send_from_directory(WEB_DIR, "index.html")

    @app.get("/<path:filename>")
    def static_files(filename):
        return send_from_directory(WEB_DIR, filename)

    return app


app = create_app()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", help="Read and save a separate configuration file")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Explore synthetic data offline; saves last until restart",
    )
    parser.add_argument("--port", type=int, default=5111, help="Local port (default: 5111)")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    print(f"Dry Socks — http://localhost:{args.port}")
    create_app(args.config, demo=args.demo).run(host="127.0.0.1", port=args.port, debug=False)


if __name__ == "__main__":
    main()
