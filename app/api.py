"""API JSON del módulo de transferencias (/api) y la pantalla web (/)."""
from flask import Blueprint, current_app, jsonify, request, send_from_directory

from . import reglas, servicio
from .db import cargar_semilla, conexion
from .reglas import ErrorNegocio

VERSION = "2.0.0"

api = Blueprint("api", __name__, url_prefix="/api")
web = Blueprint("web", __name__)


def _simulada():
    if current_app.config.get("DEMO_MODE"):
        return request.headers.get("X-Demo-Ahora") or None
    return None


@api.errorhandler(ErrorNegocio)
def _error_negocio(e):
    return jsonify({"error": {"codigo": e.codigo, "mensaje": e.mensaje}}), e.estado_http


@api.get("/salud")
def salud():
    return jsonify({"estado": "ok", "version": VERSION, "ahora": reglas.ahora(_simulada()).isoformat(timespec="seconds")})


@api.get("/cuentas")
def cuentas():
    return jsonify(servicio.listar_cuentas())


@api.get("/cuentas/<numero>")
def cuenta(numero):
    return jsonify(servicio.obtener_cuenta(numero))


@api.get("/transferencias")
def transferencias():
    try:
        limite = max(1, min(100, int(request.args.get("limite", 20))))
    except ValueError:
        limite = 20
    return jsonify(servicio.listar_transferencias(request.args.get("cuenta"), limite))


@api.post("/transferencias")
def crear():
    clave = (request.headers.get("Idempotency-Key") or "").strip() or None
    if clave and len(clave) > 64:
        raise ErrorNegocio("VALIDACION", "Idempotency-Key admite hasta 64 caracteres.", 400)
    t, repetida = servicio.crear_transferencia(request.get_json(silent=True), clave, _simulada())
    resp = jsonify(t)
    if repetida:
        resp.headers["Idempotent-Replay"] = "true"
        return resp, 200
    return resp, 201


@api.get("/transferencias/<tid>")
def transferencia(tid):
    return jsonify(servicio.obtener_transferencia(tid))


@api.post("/demo/reiniciar")
def reiniciar():
    if not current_app.config.get("DEMO_MODE"):
        return jsonify({"error": {"codigo": "NO_ENCONTRADO", "mensaje": "Recurso no encontrado."}}), 404
    cargar_semilla(conexion())
    return jsonify({"estado": "reiniciado"})


@api.app_errorhandler(404)
def _no_encontrado(_e):
    if request.path.startswith("/api/"):
        return jsonify({"error": {"codigo": "NO_ENCONTRADO", "mensaje": "Recurso no encontrado."}}), 404
    return "No encontrado", 404


@api.app_errorhandler(405)
def _metodo(_e):
    return jsonify({"error": {"codigo": "METODO_NO_PERMITIDO", "mensaje": "Método no permitido."}}), 405


@web.get("/")
def inicio():
    return send_from_directory(current_app.static_folder, "index.html")
