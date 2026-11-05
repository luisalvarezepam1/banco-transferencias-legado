"""Operaciones del módulo de transferencias. Cada escritura corre en una transacción (BEGIN IMMEDIATE)."""
import hashlib
import json

from . import reglas
from .db import conexion
from .reglas import ErrorNegocio, a_centavos, a_texto


def _cuenta(bd, numero):
    fila = bd.execute("SELECT * FROM cuentas WHERE numero = ?", (numero,)).fetchone()
    if fila is None:
        raise ErrorNegocio("CUENTA_NO_EXISTE", f"La cuenta {numero} no existe.", 404)
    return fila


def cuenta_json(c):
    return {"numero": c["numero"], "titular": c["titular"], "moneda": reglas.MONEDA, "saldo": a_texto(c["saldo_centavos"]), "estado": c["estado"]}


def listar_cuentas():
    return [cuenta_json(c) for c in conexion().execute("SELECT * FROM cuentas ORDER BY numero").fetchall()]


def obtener_cuenta(numero):
    return cuenta_json(_cuenta(conexion(), numero))


def transferencia_json(t):
    return {
        "id": t["id"], "tipo": t["tipo"], "cuenta_origen": t["cuenta_origen"], "cuenta_destino": t["cuenta_destino"],
        "moneda": reglas.MONEDA, "monto": a_texto(t["monto_centavos"]), "comision": a_texto(t["comision_centavos"]),
        "impuesto": a_texto(t["impuesto_centavos"]),
        "total_debitado": a_texto(t["monto_centavos"] + t["comision_centavos"] + t["impuesto_centavos"]),
        "concepto": t["concepto"], "fecha": t["fecha"],
    }


def obtener_transferencia(tid):
    t = conexion().execute("SELECT * FROM transferencias WHERE id = ?", (tid,)).fetchone()
    if t is None:
        raise ErrorNegocio("TRANSFERENCIA_NO_EXISTE", f"La transferencia {tid} no existe.", 404)
    return transferencia_json(t)


def listar_transferencias(cuenta=None, limite=20):
    bd = conexion()
    if cuenta:
        filas = bd.execute("SELECT * FROM transferencias WHERE cuenta_origen = ? OR cuenta_destino = ? ORDER BY seq DESC LIMIT ?", (cuenta, cuenta, limite)).fetchall()
    else:
        filas = bd.execute("SELECT * FROM transferencias ORDER BY seq DESC LIMIT ?", (limite,)).fetchall()
    return [transferencia_json(t) for t in filas]


def _huella(datos):
    canon = json.dumps({k: datos.get(k) for k in ("cuenta_origen", "cuenta_destino", "monto", "concepto")}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def _mover(bd, cuenta, importe):
    bd.execute("UPDATE cuentas SET saldo_centavos = saldo_centavos + ? WHERE numero = ?", (importe, cuenta))


def crear_transferencia(datos, clave=None, simulada=None):
    """Devuelve (transferencia, es_repeticion)."""
    if not isinstance(datos, dict):
        raise ErrorNegocio("VALIDACION", "El cuerpo debe ser un objeto JSON.", 400)
    origen = str(datos.get("cuenta_origen") or "").strip()
    destino = str(datos.get("cuenta_destino") or "").strip()
    concepto = str(datos.get("concepto") or "Transferencia").strip()[:80]
    if not origen or not destino:
        raise ErrorNegocio("VALIDACION", "cuenta_origen y cuenta_destino son obligatorias.", 400)
    if origen == destino:
        raise ErrorNegocio("MISMA_CUENTA", "La cuenta de origen y destino no pueden ser la misma.", 400)
    monto = a_centavos(datos.get("monto"))
    cuando = reglas.ahora(simulada)

    bd = conexion()
    bd.execute("BEGIN IMMEDIATE")
    try:
        cta_o, cta_d = _cuenta(bd, origen), _cuenta(bd, destino)
        for c in (cta_o, cta_d):
            if c["estado"] != "ACTIVA":
                raise ErrorNegocio("CUENTA_BLOQUEADA", f"La cuenta {c['numero']} no está activa.")
        tipo_t = reglas.tipo(cta_o["cliente_id"], cta_d["cliente_id"])
        com, imp = reglas.comision(tipo_t), reglas.impuesto(tipo_t, monto)

        # El cargo por servicio se registra al iniciar la operación.
        if com:
            _mover(bd, origen, -com)

        if clave:
            previa = bd.execute("SELECT * FROM transferencias WHERE clave_idempotencia = ?", (clave,)).fetchone()
            if previa is not None:
                if previa["huella"] != _huella(datos):
                    raise ErrorNegocio("IDEMPOTENCIA_CONFLICTO", "La clave de idempotencia ya se usó con otros datos.", 409)
                bd.execute("COMMIT")
                return transferencia_json(previa), True

        saldo = bd.execute("SELECT saldo_centavos FROM cuentas WHERE numero = ?", (origen,)).fetchone()[0] + com
        if saldo < monto + com + imp:
            raise ErrorNegocio("SALDO_INSUFICIENTE", "La cuenta no tiene saldo suficiente para el monto, la comisión y el impuesto.")
        if tipo_t != "PROPIA":
            usado = bd.execute("SELECT COALESCE(SUM(monto_centavos), 0) FROM transferencias WHERE cliente_id = ? AND fecha_local = ? AND tipo <> 'PROPIA'",
                               (cta_o["cliente_id"], cuando.date().isoformat())).fetchone()[0]
            if usado + monto > reglas.LIMITE_DIARIO:
                raise ErrorNegocio("LIMITE_DIARIO", f"Se supera el límite diario de DOP {a_texto(reglas.LIMITE_DIARIO)}.")

        seq = bd.execute("SELECT COALESCE(MAX(seq), 0) + 1 FROM transferencias").fetchone()[0]
        tid = f"T{seq:06d}"
        bd.execute("INSERT INTO transferencias VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                   (tid, seq, tipo_t, origen, destino, monto, com, imp, concepto, cuando.isoformat(timespec="seconds"),
                    cuando.date().isoformat(), cta_o["cliente_id"], clave, _huella(datos)))
        _mover(bd, origen, -(monto + imp))
        _mover(bd, destino, monto)
        t = bd.execute("SELECT * FROM transferencias WHERE id = ?", (tid,)).fetchone()
        bd.execute("COMMIT")
        return transferencia_json(t), False
    except Exception:
        bd.execute("ROLLBACK")
        raise
