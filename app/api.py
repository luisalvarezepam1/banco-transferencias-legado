"""API JSON de Transferencias Inmediatas (/api)."""
from flask import Blueprint, current_app, jsonify, request

from . import reglas, servicio
from .db import cargar_semilla, conexion
from .reglas import ErrorNegocio

VERSION = "1.4.2"

api = Blueprint("api", __name__, url_prefix="/api")


def _simulada():
    """En modo demo, la cabecera X-Demo-Ahora fija la hora (para pruebas)."""
    if current_app.config.get("DEMO_MODE"):
        return request.headers.get("X-Demo-Ahora") or None
    return None


def _limite(defecto, maximo):
    try:
        return max(1, min(maximo, int(request.args.get("limite", defecto))))
    except ValueError:
        return defecto


@api.errorhandler(ErrorNegocio)
def _error_negocio(e):
    return jsonify({"error": {"codigo": e.codigo, "mensaje": e.mensaje}}), e.estado_http


@api.get("/salud")
def salud():
    return jsonify({"estado": "ok", "version": VERSION, "ahora": reglas.ahora(_simulada()).isoformat(timespec="seconds")})


@api.get("/clientes")
def clientes():
    return jsonify(servicio.listar_clientes())


@api.get("/cuentas/<numero>")
def cuenta(numero):
    return jsonify(servicio.obtener_cuenta(numero))


@api.get("/cuentas/<numero>/movimientos")
def movimientos(numero):
    return jsonify(servicio.movimientos(numero, _limite(50, 500)))


@api.get("/transferencias")
def transferencias():
    return jsonify(servicio.listar_transferencias(request.args.get("cuenta"), _limite(50, 500)))


@api.post("/transferencias")
def crear():
    datos = request.get_json(silent=True)
    clave = (request.headers.get("Idempotency-Key") or "").strip() or None
    if clave and len(clave) > 64:
        raise ErrorNegocio("VALIDACION", "Idempotency-Key admite hasta 64 caracteres.", 400)
    t, repetida = servicio.crear_transferencia(datos, clave, _simulada())
    resp = jsonify(t)
    if repetida:
        resp.headers["Idempotent-Replay"] = "true"
        return resp, 200
    return resp, 201


@api.get("/transferencias/<tid>")
def transferencia(tid):
    return jsonify(servicio.obtener_transferencia(tid))


@api.post("/transferencias/<tid>/reverso")
def reverso(tid):
    return jsonify(servicio.reversar(tid, _simulada()))


@api.get("/auditoria")
def auditoria():
    return jsonify(servicio.auditoria(_limite(100, 1000)))


@api.post("/demo/reiniciar")
def reiniciar():
    """Vuelve a los datos de ejemplo. Solo existe en modo demo."""
    if not current_app.config.get("DEMO_MODE"):
        return jsonify({"error": {"codigo": "NO_ENCONTRADO", "mensaje": "No encontrado."}}), 404
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
