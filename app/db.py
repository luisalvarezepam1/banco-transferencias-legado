"""Acceso a datos: SQLite con SQL directo (sin ORM).

Los importes se guardan en centavos (enteros) para no perder precisión.
"""
import os
import sqlite3

from flask import current_app, g

ESQUEMA = """
CREATE TABLE IF NOT EXISTS clientes (
    id TEXT PRIMARY KEY,
    nombre TEXT NOT NULL,
    documento TEXT NOT NULL,
    segmento TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cuentas (
    numero TEXT PRIMARY KEY,
    cliente_id TEXT NOT NULL REFERENCES clientes(id),
    tipo TEXT NOT NULL,
    moneda TEXT NOT NULL,
    saldo_centavos INTEGER NOT NULL,
    estado TEXT NOT NULL DEFAULT 'ACTIVA'
);
CREATE TABLE IF NOT EXISTS transferencias (
    id TEXT PRIMARY KEY,
    seq INTEGER NOT NULL UNIQUE,
    tipo TEXT NOT NULL,
    cuenta_origen TEXT NOT NULL,
    cuenta_destino TEXT NOT NULL,
    banco_destino TEXT NOT NULL,
    monto_centavos INTEGER NOT NULL,
    comision_centavos INTEGER NOT NULL,
    impuesto_centavos INTEGER NOT NULL,
    moneda TEXT NOT NULL,
    concepto TEXT NOT NULL,
    estado TEXT NOT NULL,
    fecha TEXT NOT NULL,
    fecha_local TEXT NOT NULL,
    cliente_id TEXT NOT NULL,
    clave_idempotencia TEXT UNIQUE,
    huella TEXT,
    fecha_reverso TEXT
);
CREATE TABLE IF NOT EXISTS movimientos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cuenta TEXT NOT NULL,
    fecha TEXT NOT NULL,
    tipo TEXT NOT NULL,
    descripcion TEXT NOT NULL,
    importe_centavos INTEGER NOT NULL,
    saldo_centavos INTEGER NOT NULL,
    transferencia_id TEXT
);
CREATE TABLE IF NOT EXISTS auditoria (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha TEXT NOT NULL,
    accion TEXT NOT NULL,
    resultado TEXT NOT NULL,
    detalle TEXT NOT NULL
);
"""

# Datos ficticios. No representan clientes ni cuentas reales.
CLIENTES = [
    ("C001", "María Fernández", "001-0000001-1", "PERSONAL"),
    ("C002", "José Ramírez", "001-0000002-2", "PERSONAL"),
    ("C003", "Colmado La Esquina SRL", "1-30-00003-3", "PYME"),
    ("C004", "Ana Lucía Peña", "001-0000004-4", "PERSONAL"),
    ("C005", "Inversiones del Caribe SRL", "1-30-00005-5", "EMPRESA"),
    ("C006", "Pedro Almonte", "001-0000006-6", "PERSONAL"),
]
CUENTAS = [
    ("7001-0001", "C001", "AHORRO", "DOP", 8_500_000, "ACTIVA"),
    ("7001-0002", "C001", "CORRIENTE", "DOP", 1_250_000, "ACTIVA"),
    ("7001-0003", "C002", "AHORRO", "DOP", 320_000, "ACTIVA"),
    ("7001-0004", "C003", "CORRIENTE", "DOP", 64_000_000, "ACTIVA"),
    ("7001-0005", "C004", "AHORRO", "DOP", 15_000_000, "ACTIVA"),
    ("7001-0006", "C005", "CORRIENTE", "DOP", 250_000_000, "ACTIVA"),
    ("7001-0007", "C005", "AHORRO", "USD", 4_000_000, "ACTIVA"),
    ("7001-0008", "C006", "AHORRO", "DOP", 90_000, "ACTIVA"),
    ("7001-0009", "C006", "AHORRO", "DOP", 0, "BLOQUEADA"),
    ("7001-0010", "C001", "AHORRO", "USD", 100_000, "ACTIVA"),
]


def ruta_bd():
    return current_app.config["DATABASE"]


def conexion():
    if "bd" not in g:
        ruta = ruta_bd()
        if ruta != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(ruta)), exist_ok=True)
        g.bd = sqlite3.connect(ruta, isolation_level=None, timeout=10)
        g.bd.row_factory = sqlite3.Row
        g.bd.execute("PRAGMA foreign_keys = ON")
    return g.bd


def cerrar(_e=None):
    bd = g.pop("bd", None)
    if bd is not None:
        bd.close()


def crear_esquema(bd):
    bd.executescript(ESQUEMA)


def cargar_semilla(bd):
    bd.execute("BEGIN")
    for tabla in ("movimientos", "transferencias", "auditoria", "cuentas", "clientes"):
        bd.execute(f"DELETE FROM {tabla}")
    bd.execute("DELETE FROM sqlite_sequence WHERE name IN ('movimientos', 'auditoria')")
    bd.executemany("INSERT INTO clientes VALUES (?, ?, ?, ?)", CLIENTES)
    bd.executemany("INSERT INTO cuentas VALUES (?, ?, ?, ?, ?, ?)", CUENTAS)
    bd.execute("COMMIT")


def inicializar(app):
    """Crea el esquema y carga los datos de ejemplo si la base está vacía."""
    with app.app_context():
        bd = conexion()
        crear_esquema(bd)
        if bd.execute("SELECT COUNT(*) FROM clientes").fetchone()[0] == 0:
            cargar_semilla(bd)
        cerrar()
