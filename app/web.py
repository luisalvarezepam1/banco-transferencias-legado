"""Pantallas web (HTML) sobre el mismo servicio que usa la API."""
from flask import Blueprint, redirect, render_template, request, url_for

from . import servicio
from .reglas import ErrorNegocio

web = Blueprint("web", __name__)


@web.get("/")
def inicio():
    return render_template("inicio.html", clientes=servicio.listar_clientes())


@web.get("/cuentas/<numero>")
def cuenta(numero):
    try:
        c = servicio.obtener_cuenta(numero)
    except ErrorNegocio as e:
        return render_template("error.html", error=e), e.estado_http
    return render_template("cuenta.html", cuenta=c, movimientos=servicio.movimientos(numero, 50),
                           transferencias=servicio.listar_transferencias(numero, 20))


@web.route("/transferir", methods=["GET", "POST"])
def transferir():
    datos = {"cuenta_origen": request.args.get("origen", ""), "cuenta_destino": "", "banco_destino": "POPULAR", "monto": "", "concepto": ""}
    error = None
    if request.method == "POST":
        datos = {k: request.form.get(k, "").strip() for k in datos}
        try:
            t, _ = servicio.crear_transferencia(datos, request.form.get("clave") or None)
            return redirect(url_for("web.comprobante", tid=t["id"]))
        except ErrorNegocio as e:
            error = e
    return render_template("transferir.html", datos=datos, error=error, clientes=servicio.listar_clientes())


@web.get("/transferencias/<tid>")
def comprobante(tid):
    try:
        t = servicio.obtener_transferencia(tid)
    except ErrorNegocio as e:
        return render_template("error.html", error=e), e.estado_http
    return render_template("comprobante.html", t=t)


@web.post("/transferencias/<tid>/reverso")
def reverso(tid):
    try:
        servicio.reversar(tid)
    except ErrorNegocio as e:
        return render_template("error.html", error=e), e.estado_http
    return redirect(url_for("web.comprobante", tid=tid))
