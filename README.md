# Transferencias Inmediatas · legado (Python)

Módulo de transferencias de un **banco ficticio**, con su pantalla web y su API. Es el sistema de origen que la [fábrica de migración](https://github.com/luisalvarezepam1/fabrica-migracion) analiza y migra a otro stack.

> Todos los datos son inventados. No representa a ningún banco, cliente ni cuenta real.

**En Azure:** https://app-bancolegado-439f6a.azurewebsites.net · API: [/api/salud](https://app-bancolegado-439f6a.azurewebsites.net/api/salud)

## Qué hace

- Seis cuentas de ejemplo en DOP.
- Transferencias propias y a terceros, con comisión, impuesto, límite diario e idempotencia (`Idempotency-Key`).
- Una pantalla web (`/`) para ver las cuentas, transferir y ver el historial, sobre la misma API JSON (`/api`).

Stack: Python 3.12, Flask 3, SQLite (SQL directo) y gunicorn.

> La versión anterior, más grande (clientes, movimientos, reversos, auditoría, USD e interbancarias), está en la rama [`v1.4-completa`](https://github.com/luisalvarezepam1/banco-transferencias-legado/tree/v1.4-completa).

## Correr en local

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
pytest -q
python wsgi.py                     # http://127.0.0.1:5050 (variable PORT para cambiarlo)
```

La base se crea en `instance/transferencias.db` con datos de ejemplo. Para volver al estado inicial: `POST /api/demo/reiniciar`. Con `DEMO_MODE=1` (por defecto), la cabecera `X-Demo-Ahora` simula la hora.

## Documentación

- [API](docs/API.md)
- Despliegue en Azure: [infra/](infra/) y [.github/workflows/](.github/workflows/)
