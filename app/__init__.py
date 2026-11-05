"""Transferencias Inmediatas: aplicación de ejemplo (legado) para la fábrica de migración.

Banco ficticio y datos ficticios. No representa a ningún banco real.
"""
import os

from flask import Flask

from . import db


def create_app(config=None):
    app = Flask(__name__)
    app.config.update(
        DATABASE=os.environ.get("DATABASE_PATH", os.path.join(app.instance_path, "transferencias.db")),
        DEMO_MODE=os.environ.get("DEMO_MODE", "1") == "1",
        JSON_AS_ASCII=False,
    )
    app.json.ensure_ascii = False
    app.json.sort_keys = False
    if config:
        app.config.update(config)

    from .api import api
    from .web import web

    app.register_blueprint(api)
    app.register_blueprint(web)
    app.teardown_appcontext(db.cerrar)

    @app.after_request
    def _cabeceras(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Cache-Control", "no-store")
        return resp

    db.inicializar(app)
    return app
