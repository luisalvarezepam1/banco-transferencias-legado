"""Reglas de negocio de Transferencias Inmediatas (versión 1.4).

Todos los importes se manejan en centavos (int). Los porcentajes se calculan
con Decimal y se redondean a centavos "mitad hacia arriba" (ROUND_HALF_UP),
como lo exige la norma interna de cálculo de cargos.
"""
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from zoneinfo import ZoneInfo

ZONA = ZoneInfo("America/Santo_Domingo")
BANCO_PROPIO = "POPULAR"

MONTO_MAXIMO = 1_000_000_000  # DOP 10,000,000.00 en centavos

# Límite diario por cliente y moneda (no aplica a transferencias entre cuentas propias)
LIMITE_DIARIO = {"DOP": 50_000_000, "USD": 2_500_000}

# Comisión fija para transferencias a terceros dentro del banco
COMISION_TERCEROS = {"DOP": 1_000, "USD": 50}

# Interbancarias (solo DOP): porcentaje con mínimo y máximo
PCT_INTERBANCARIA = Decimal("0.0025")
COMISION_INTERBANCARIA_MIN = 2_500
COMISION_INTERBANCARIA_MAX = 30_000

# Impuesto DGII sobre transferencias a terceros e interbancarias
PCT_IMPUESTO = Decimal("0.0015")


class ErrorNegocio(Exception):
    def __init__(self, codigo, mensaje, estado_http=422):
        super().__init__(mensaje)
        self.codigo = codigo
        self.mensaje = mensaje
        self.estado_http = estado_http


def redondear_centavos(valor):
    """Decimal en centavos -> int, mitad hacia arriba."""
    return int(valor.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def a_centavos(texto):
    """Convierte un monto recibido ("1670.00", 1670, 1670.5) a centavos.

    Rechaza más de dos decimales, negativos, cero y valores no numéricos.
    """
    if isinstance(texto, bool) or texto is None:
        raise ErrorNegocio("VALIDACION", "El monto es obligatorio y debe ser numérico.", 400)
    try:
        valor = Decimal(str(texto).strip())
    except (InvalidOperation, ValueError):
        raise ErrorNegocio("VALIDACION", "El monto debe ser numérico.", 400)
    if not valor.is_finite():
        raise ErrorNegocio("VALIDACION", "El monto debe ser numérico.", 400)
    if valor <= 0:
        raise ErrorNegocio("VALIDACION", "El monto debe ser mayor que cero.", 400)
    if valor != valor.quantize(Decimal("0.01")):
        raise ErrorNegocio("VALIDACION", "El monto admite como máximo dos decimales.", 400)
    centavos = int(valor * 100)
    if centavos > MONTO_MAXIMO:
        raise ErrorNegocio("VALIDACION", "El monto supera el máximo por operación.", 400)
    return centavos


def a_texto(centavos):
    """Centavos -> texto con dos decimales ("1670.00")."""
    signo = "-" if centavos < 0 else ""
    centavos = abs(centavos)
    return f"{signo}{centavos // 100}.{centavos % 100:02d}"


def tipo_transferencia(cliente_origen, cliente_destino, banco_destino):
    if banco_destino != BANCO_PROPIO:
        return "INTERBANCARIA"
    if cliente_origen == cliente_destino:
        return "PROPIA"
    return "TERCEROS"


def comision(tipo, moneda, monto):
    if tipo == "PROPIA":
        return 0
    if tipo == "TERCEROS":
        return COMISION_TERCEROS[moneda]
    calculada = redondear_centavos(Decimal(monto) * PCT_INTERBANCARIA)
    return max(COMISION_INTERBANCARIA_MIN, min(COMISION_INTERBANCARIA_MAX, calculada))


def impuesto(tipo, monto):
    if tipo == "PROPIA":
        return 0
    return redondear_centavos(Decimal(monto) * PCT_IMPUESTO)


def ahora(simulada=None):
    """Hora actual en Santo Domingo. En modo demo se puede simular (para pruebas)."""
    if simulada:
        try:
            dt = datetime.fromisoformat(simulada)
        except ValueError:
            raise ErrorNegocio("VALIDACION", "X-Demo-Ahora debe ser una fecha ISO 8601.", 400)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZONA)
        return dt.astimezone(ZONA)
    return datetime.now(ZONA)
