"""Operaciones de Transferencias Inmediatas.

Cada operación corre en una transacción (BEGIN IMMEDIATE) y deja rastro en auditoría.
"""
import hashlib
import json

from . import reglas
from .db import conexion
from .reglas import ErrorNegocio, a_centavos, a_texto


# ---------- consultas ----------

def _cuenta(bd, numero):
    fila = bd.execute(
        "SELECT c.*, cl.nombre AS cliente_nombre FROM cuentas c JOIN clientes cl ON cl.id = c.cliente_id WHERE c.numero = ?",
        (numero,),
    ).fetchone()
    if fila is None:
        raise ErrorNegocio("CUENTA_NO_EXISTE", f"La cuenta {numero} no existe.", 404)
    return fila


def cuenta_json(fila):
    return {
        "numero": fila["numero"],
        "cliente": {"id": fila["cliente_id"], "nombre": fila["cliente_nombre"]},
        "tipo": fila["tipo"],
        "moneda": fila["moneda"],
        "saldo": a_texto(fila["saldo_centavos"]),
        "estado": fila["estado"],
    }


def obtener_cuenta(numero):
    return cuenta_json(_cuenta(conexion(), numero))


def listar_clientes():
    bd = conexion()
    salida = []
    for cl in bd.execute("SELECT * FROM clientes ORDER BY id").fetchall():
        cuentas = bd.execute(
            "SELECT c.*, ? AS cliente_nombre FROM cuentas c WHERE cliente_id = ? ORDER BY numero",
            (cl["nombre"], cl["id"]),
        ).fetchall()
        salida.append({
            "id": cl["id"],
            "nombre": cl["nombre"],
            "segmento": cl["segmento"],
            "cuentas": [cuenta_json(c) for c in cuentas],
        })
    return salida


def movimientos(numero, limite=50):
    bd = conexion()
    _cuenta(bd, numero)
    filas = bd.execute(
        "SELECT * FROM movimientos WHERE cuenta = ? ORDER BY id DESC LIMIT ?", (numero, limite)
    ).fetchall()
    return [{
        "fecha": f["fecha"],
        "tipo": f["tipo"],
        "descripcion": f["descripcion"],
        "importe": a_texto(f["importe_centavos"]),
        "saldo": a_texto(f["saldo_centavos"]),
        "transferencia_id": f["transferencia_id"],
    } for f in filas]


def transferencia_json(t):
    return {
        "id": t["id"],
        "tipo": t["tipo"],
        "cuenta_origen": t["cuenta_origen"],
        "cuenta_destino": t["cuenta_destino"],
        "banco_destino": t["banco_destino"],
        "moneda": t["moneda"],
        "monto": a_texto(t["monto_centavos"]),
        "comision": a_texto(t["comision_centavos"]),
        "impuesto": a_texto(t["impuesto_centavos"]),
        "total_debitado": a_texto(t["monto_centavos"] + t["comision_centavos"] + t["impuesto_centavos"]),
        "concepto": t["concepto"],
        "estado": t["estado"],
        "fecha": t["fecha"],
        "fecha_reverso": t["fecha_reverso"],
    }


def obtener_transferencia(tid):
    t = conexion().execute("SELECT * FROM transferencias WHERE id = ?", (tid,)).fetchone()
    if t is None:
        raise ErrorNegocio("TRANSFERENCIA_NO_EXISTE", f"La transferencia {tid} no existe.", 404)
    return transferencia_json(t)


def listar_transferencias(cuenta=None, limite=50):
    bd = conexion()
    if cuenta:
        filas = bd.execute(
            "SELECT * FROM transferencias WHERE cuenta_origen = ? OR cuenta_destino = ? ORDER BY seq DESC LIMIT ?",
            (cuenta, cuenta, limite),
        ).fetchall()
    else:
        filas = bd.execute("SELECT * FROM transferencias ORDER BY seq DESC LIMIT ?", (limite,)).fetchall()
    return [transferencia_json(t) for t in filas]


def auditoria(limite=100):
    filas = conexion().execute("SELECT * FROM auditoria ORDER BY id DESC LIMIT ?", (limite,)).fetchall()
    return [{"fecha": f["fecha"], "accion": f["accion"], "resultado": f["resultado"], "detalle": json.loads(f["detalle"])} for f in filas]


# ---------- escrituras ----------

def _auditar(bd, cuando, accion, resultado, detalle):
    bd.execute(
        "INSERT INTO auditoria (fecha, accion, resultado, detalle) VALUES (?, ?, ?, ?)",
        (cuando.isoformat(timespec="seconds"), accion, resultado, json.dumps(detalle, ensure_ascii=False)),
    )


def _mover(bd, cuenta, cuando, tipo, descripcion, importe, tid):
    bd.execute("UPDATE cuentas SET saldo_centavos = saldo_centavos + ? WHERE numero = ?", (importe, cuenta))
    saldo = bd.execute("SELECT saldo_centavos FROM cuentas WHERE numero = ?", (cuenta,)).fetchone()[0]
    bd.execute(
        "INSERT INTO movimientos (cuenta, fecha, tipo, descripcion, importe_centavos, saldo_centavos, transferencia_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (cuenta, cuando.isoformat(timespec="seconds"), tipo, descripcion, importe, saldo, tid),
    )


def _huella(datos):
    canon = json.dumps({k: datos.get(k) for k in ("cuenta_origen", "cuenta_destino", "banco_destino", "monto", "concepto")}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def crear_transferencia(datos, clave=None, simulada=None):
    """Crea una transferencia. Devuelve (transferencia, es_repeticion)."""
    if not isinstance(datos, dict):
        raise ErrorNegocio("VALIDACION", "El cuerpo debe ser un objeto JSON.", 400)
    origen = str(datos.get("cuenta_origen") or "").strip()
    destino = str(datos.get("cuenta_destino") or "").strip()
    banco = str(datos.get("banco_destino") or reglas.BANCO_PROPIO).strip().upper()
    concepto = str(datos.get("concepto") or "Transferencia").strip()[:80]
    if not origen or not destino:
        raise ErrorNegocio("VALIDACION", "cuenta_origen y cuenta_destino son obligatorias.", 400)
    if origen == destino and banco == reglas.BANCO_PROPIO:
        raise ErrorNegocio("MISMA_CUENTA", "La cuenta de origen y destino no pueden ser la misma.", 400)
    monto = a_centavos(datos.get("monto"))
    cuando = reglas.ahora(simulada)

    bd = conexion()
    bd.execute("BEGIN IMMEDIATE")
    try:
        cta_o = _cuenta(bd, origen)
        if cta_o["estado"] != "ACTIVA":
            raise ErrorNegocio("CUENTA_BLOQUEADA", f"La cuenta {origen} no está activa.")
        if banco == reglas.BANCO_PROPIO:
            cta_d = _cuenta(bd, destino)
            if cta_d["estado"] != "ACTIVA":
                raise ErrorNegocio("CUENTA_BLOQUEADA", f"La cuenta {destino} no está activa.")
            if cta_d["moneda"] != cta_o["moneda"]:
                raise ErrorNegocio("MONEDA_DISTINTA", "Las cuentas deben estar en la misma moneda.")
            cliente_d = cta_d["cliente_id"]
        else:
            if cta_o["moneda"] != "DOP":
                raise ErrorNegocio("NO_PERMITIDA", "Las transferencias interbancarias solo se permiten en DOP.")
            cliente_d = None

        moneda = cta_o["moneda"]
        tipo = reglas.tipo_transferencia(cta_o["cliente_id"], cliente_d, banco)
        com = reglas.comision(tipo, moneda, monto)
        imp = reglas.impuesto(tipo, monto)

        # El cargo por servicio se registra al iniciar la operación.
        if com:
            _mover(bd, origen, cuando, "COMISION", "Comisión por transferencia", -com, None)

        if clave:
            previa = bd.execute("SELECT * FROM transferencias WHERE clave_idempotencia = ?", (clave,)).fetchone()
            if previa is not None:
                if previa["huella"] != _huella(datos):
                    raise ErrorNegocio("IDEMPOTENCIA_CONFLICTO", "La clave de idempotencia ya se usó con otros datos.", 409)
                _auditar(bd, cuando, "TRANSFERENCIA", "REPETIDA", {"id": previa["id"], "clave": clave})
                bd.execute("COMMIT")
                return transferencia_json(previa), True

        total = monto + com + imp
        disponible = bd.execute("SELECT saldo_centavos FROM cuentas WHERE numero = ?", (origen,)).fetchone()[0] + com
        if disponible < total:
            raise ErrorNegocio("SALDO_INSUFICIENTE", "La cuenta no tiene saldo suficiente para el monto, la comisión y el impuesto.")

        if tipo != "PROPIA":
            usado = bd.execute(
                "SELECT COALESCE(SUM(monto_centavos), 0) FROM transferencias WHERE cliente_id = ? AND moneda = ? AND fecha_local = ? AND estado = 'APLICADA' AND tipo <> 'PROPIA'",
                (cta_o["cliente_id"], moneda, cuando.date().isoformat()),
            ).fetchone()[0]
            if usado + monto > reglas.LIMITE_DIARIO[moneda]:
                raise ErrorNegocio("LIMITE_DIARIO", f"Se supera el límite diario de {moneda} {a_texto(reglas.LIMITE_DIARIO[moneda])}.")

        seq = bd.execute("SELECT COALESCE(MAX(seq), 0) + 1 FROM transferencias").fetchone()[0]
        tid = f"T{seq:06d}"
        bd.execute(
            "INSERT INTO transferencias (id, seq, tipo, cuenta_origen, cuenta_destino, banco_destino, monto_centavos, comision_centavos, impuesto_centavos, moneda, concepto, estado, fecha, fecha_local, cliente_id, clave_idempotencia, huella) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'APLICADA', ?, ?, ?, ?, ?)",
            (tid, seq, tipo, origen, destino, banco, monto, com, imp, moneda, concepto, cuando.isoformat(timespec="seconds"), cuando.date().isoformat(), cta_o["cliente_id"], clave, _huella(datos)),
        )
        if com:
            bd.execute("UPDATE movimientos SET transferencia_id = ? WHERE id = (SELECT MAX(id) FROM movimientos WHERE cuenta = ? AND tipo = 'COMISION')", (tid, origen))
        _mover(bd, origen, cuando, "DEBITO", f"Transferencia {tid} a {destino}", -monto, tid)
        if imp:
            _mover(bd, origen, cuando, "IMPUESTO", "Impuesto DGII 0.15%", -imp, tid)
        if banco == reglas.BANCO_PROPIO:
            _mover(bd, destino, cuando, "CREDITO", f"Transferencia {tid} de {origen}", monto, tid)
        _auditar(bd, cuando, "TRANSFERENCIA", "OK", {"id": tid, "tipo": tipo, "monto": a_texto(monto), "origen": origen, "destino": destino})
        t = bd.execute("SELECT * FROM transferencias WHERE id = ?", (tid,)).fetchone()
        bd.execute("COMMIT")
        return transferencia_json(t), False
    except ErrorNegocio as e:
        bd.execute("ROLLBACK")
        _registrar_rechazo(bd, cuando, "TRANSFERENCIA", e, {"origen": origen, "destino": destino, "monto": a_texto(monto)})
        raise
    except Exception:
        bd.execute("ROLLBACK")
        raise


def reversar(tid, simulada=None):
    cuando = reglas.ahora(simulada)
    bd = conexion()
    bd.execute("BEGIN IMMEDIATE")
    try:
        t = bd.execute("SELECT * FROM transferencias WHERE id = ?", (tid,)).fetchone()
        if t is None:
            raise ErrorNegocio("TRANSFERENCIA_NO_EXISTE", f"La transferencia {tid} no existe.", 404)
        if t["estado"] == "REVERSADA":
            raise ErrorNegocio("YA_REVERSADA", "La transferencia ya fue reversada.", 409)
        if t["tipo"] == "INTERBANCARIA":
            raise ErrorNegocio("NO_REVERSABLE", "Las transferencias interbancarias no se pueden reversar.")
        if t["fecha_local"] != cuando.date().isoformat():
            raise ErrorNegocio("REVERSO_FUERA_DE_PLAZO", "Solo se puede reversar el mismo día de la transferencia.")
        destino_saldo = bd.execute("SELECT saldo_centavos FROM cuentas WHERE numero = ?", (t["cuenta_destino"],)).fetchone()[0]
        if destino_saldo < t["monto_centavos"]:
            raise ErrorNegocio("SALDO_INSUFICIENTE_DESTINO", "La cuenta destino ya no tiene el saldo para el reverso.")
        # Se devuelve el monto y el impuesto; la comisión no es reembolsable.
        _mover(bd, t["cuenta_destino"], cuando, "DEBITO", f"Reverso de {tid}", -t["monto_centavos"], tid)
        _mover(bd, t["cuenta_origen"], cuando, "CREDITO", f"Reverso de {tid}", t["monto_centavos"], tid)
        if t["impuesto_centavos"]:
            _mover(bd, t["cuenta_origen"], cuando, "CREDITO", "Devolución impuesto DGII", t["impuesto_centavos"], tid)
        bd.execute("UPDATE transferencias SET estado = 'REVERSADA', fecha_reverso = ? WHERE id = ?", (cuando.isoformat(timespec="seconds"), tid))
        _auditar(bd, cuando, "REVERSO", "OK", {"id": tid})
        t = bd.execute("SELECT * FROM transferencias WHERE id = ?", (tid,)).fetchone()
        bd.execute("COMMIT")
        return transferencia_json(t)
    except ErrorNegocio as e:
        bd.execute("ROLLBACK")
        _registrar_rechazo(bd, cuando, "REVERSO", e, {"id": tid})
        raise
    except Exception:
        bd.execute("ROLLBACK")
        raise


def _registrar_rechazo(bd, cuando, accion, error, detalle):
    detalle = dict(detalle, codigo=error.codigo)
    bd.execute("BEGIN")
    _auditar(bd, cuando, accion, "RECHAZADA", detalle)
    bd.execute("COMMIT")
