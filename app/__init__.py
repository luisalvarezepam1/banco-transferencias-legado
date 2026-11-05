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

    @app.template_filter("dinero")
    def _dinero(texto):
        """"85000.00" -> "85,000.00" (solo para pantalla; la API conserva el formato sin separadores)."""
        entero, _, dec = str(texto).partition(".")
        signo = "-" if entero.startswith("-") else ""
        return f"{signo}{int(entero.lstrip('-') or 0):,}.{dec or '00'}"

    @app.template_filter("fecha")
    def _fecha(iso):
        """"2026-11-05T10:00:00-04:00" -> "05/11/2026 10:00"."""
        if not iso:
            return ""
        d, _, h = str(iso).partition("T")
        a, m, dia = d.split("-")
        return f"{dia}/{m}/{a} {h[:5]}"

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
