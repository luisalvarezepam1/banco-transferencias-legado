"""Reglas de negocio de Transferencias Inmediatas (módulo de transferencias, v2.0).

Importes en centavos (int). El impuesto se calcula con Decimal y se redondea a
centavos "mitad hacia arriba" (ROUND_HALF_UP), como lo exige la norma interna.
"""
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from zoneinfo import ZoneInfo

ZONA = ZoneInfo("America/Santo_Domingo")
MONEDA = "DOP"

MONTO_MAXIMO = 1_000_000_000      # DOP 10,000,000.00 por operación
LIMITE_DIARIO = 50_000_000        # DOP 500,000.00 por cliente y día (no cuenta propias)
COMISION_TERCEROS = 1_000         # DOP 10.00
PCT_IMPUESTO = Decimal("0.0015")  # Impuesto DGII 0.15 % en transferencias a terceros


class ErrorNegocio(Exception):
    def __init__(self, codigo, mensaje, estado_http=422):
        super().__init__(mensaje)
        self.codigo = codigo
        self.mensaje = mensaje
        self.estado_http = estado_http


def a_centavos(valor):
    """"1670.00", 1670 o 1670.5 -> centavos. Rechaza más de dos decimales, cero, negativos y no numéricos."""
    if isinstance(valor, bool) or valor is None:
        raise ErrorNegocio("VALIDACION", "El monto es obligatorio y debe ser numérico.", 400)
    try:
        d = Decimal(str(valor).strip())
    except (InvalidOperation, ValueError):
        raise ErrorNegocio("VALIDACION", "El monto debe ser numérico.", 400)
    if not d.is_finite():
        raise ErrorNegocio("VALIDACION", "El monto debe ser numérico.", 400)
    if d <= 0:
        raise ErrorNegocio("VALIDACION", "El monto debe ser mayor que cero.", 400)
    if d != d.quantize(Decimal("0.01")):
        raise ErrorNegocio("VALIDACION", "El monto admite como máximo dos decimales.", 400)
    centavos = int(d * 100)
    if centavos > MONTO_MAXIMO:
        raise ErrorNegocio("VALIDACION", "El monto supera el máximo por operación.", 400)
    return centavos


def a_texto(centavos):
    signo = "-" if centavos < 0 else ""
    centavos = abs(centavos)
    return f"{signo}{centavos // 100}.{centavos % 100:02d}"


def tipo(cliente_origen, cliente_destino):
    return "PROPIA" if cliente_origen == cliente_destino else "TERCEROS"


def comision(tipo_t):
    return 0 if tipo_t == "PROPIA" else COMISION_TERCEROS


def impuesto(tipo_t, monto):
    if tipo_t == "PROPIA":
        return 0
    return int((Decimal(monto) * PCT_IMPUESTO).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def ahora(simulada=None):
    """Hora actual en Santo Domingo. En modo demo se puede simular con X-Demo-Ahora."""
    if simulada:
        try:
            dt = datetime.fromisoformat(simulada)
        except ValueError:
            raise ErrorNegocio("VALIDACION", "X-Demo-Ahora debe ser una fecha ISO 8601.", 400)
        return (dt if dt.tzinfo else dt.replace(tzinfo=ZONA)).astimezone(ZONA)
    return datetime.now(ZONA)
