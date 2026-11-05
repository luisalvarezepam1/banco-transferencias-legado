"""Acceso a datos: SQLite con SQL directo (sin ORM). Importes en centavos (enteros)."""
import os
import sqlite3

from flask import current_app, g

ESQUEMA = """
CREATE TABLE IF NOT EXISTS cuentas (
    numero TEXT PRIMARY KEY,
    titular TEXT NOT NULL,
    cliente_id TEXT NOT NULL,
    saldo_centavos INTEGER NOT NULL,
    estado TEXT NOT NULL DEFAULT 'ACTIVA'
);
CREATE TABLE IF NOT EXISTS transferencias (
    id TEXT PRIMARY KEY,
    seq INTEGER NOT NULL UNIQUE,
    tipo TEXT NOT NULL,
    cuenta_origen TEXT NOT NULL,
    cuenta_destino TEXT NOT NULL,
    monto_centavos INTEGER NOT NULL,
    comision_centavos INTEGER NOT NULL,
    impuesto_centavos INTEGER NOT NULL,
    concepto TEXT NOT NULL,
    fecha TEXT NOT NULL,
    fecha_local TEXT NOT NULL,
    cliente_id TEXT NOT NULL,
    clave_idempotencia TEXT UNIQUE,
    huella TEXT
);
"""

# Datos ficticios. No representan clientes ni cuentas reales.
CUENTAS = [
    ("7001-0001", "María Fernández", "C001", 8_500_000, "ACTIVA"),
    ("7001-0002", "María Fernández", "C001", 1_250_000, "ACTIVA"),
    ("7001-0003", "José Ramírez", "C002", 320_000, "ACTIVA"),
    ("7001-0004", "Colmado La Esquina SRL", "C003", 64_000_000, "ACTIVA"),
    ("7001-0005", "Inversiones del Caribe SRL", "C004", 250_000_000, "ACTIVA"),
    ("7001-0006", "Pedro Almonte", "C005", 0, "BLOQUEADA"),
]


def conexion():
    if "bd" not in g:
        ruta = current_app.config["DATABASE"]
        os.makedirs(os.path.dirname(os.path.abspath(ruta)), exist_ok=True)
        g.bd = sqlite3.connect(ruta, isolation_level=None, timeout=10)
        g.bd.row_factory = sqlite3.Row
    return g.bd


def cerrar(_e=None):
    bd = g.pop("bd", None)
    if bd is not None:
        bd.close()


def cargar_semilla(bd):
    bd.execute("BEGIN")
    bd.execute("DELETE FROM transferencias")
    bd.execute("DELETE FROM cuentas")
    bd.executemany("INSERT INTO cuentas VALUES (?, ?, ?, ?, ?)", CUENTAS)
    bd.execute("COMMIT")


def inicializar(app):
    """Crea el esquema y carga los datos de ejemplo si la base está vacía."""
    with app.app_context():
        bd = conexion()
        bd.executescript(ESQUEMA)
        if bd.execute("SELECT COUNT(*) FROM cuentas").fetchone()[0] == 0:
            cargar_semilla(bd)
        cerrar()
