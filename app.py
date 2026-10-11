"""Blinkit quick-commerce demo - entry point.  Run:  python app.py  ->  http://127.0.0.1:5001"""
from flask import Flask, send_from_directory

from db import init_db
from modules import admin, catalog, dispatch, inventory, orders, tracking


def create_app():
    app = Flask(__name__, static_folder="static", static_url_path="/static")
    init_db()
    for module in (catalog, inventory, orders, tracking, dispatch, admin):
        app.register_blueprint(module.bp)

    @app.get("/")
    def index():
        return send_from_directory("static", "index.html")

    return app


if __name__ == "__main__":
    # Port 5001: macOS reserves 5000 for AirPlay Receiver.
    create_app().run(host="127.0.0.1", port=5001, debug=True)
