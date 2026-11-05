# Transferencias Inmediatas · legado (Python)

Aplicación de ejemplo de un **banco ficticio** para el workshop de IA agéntica. Es el sistema de origen que la [fábrica de migración](https://github.com/luisalvarezepam1/fabrica-migracion) analiza y migra a otro stack.

> Todos los datos son inventados. No representa a ningún banco, cliente ni cuenta real.

**En Azure:** https://app-bancolegado-439f6a.azurewebsites.net · API: [/api/salud](https://app-bancolegado-439f6a.azurewebsites.net/api/salud)

## Qué hace

- Clientes y cuentas de ahorro y corrientes en DOP y USD.
- Transferencias **propias**, a **terceros** del mismo banco e **interbancarias**, con comisión, impuesto y límite diario.
- Idempotencia con la cabecera `Idempotency-Key`.
- Reverso el mismo día.
- Movimientos por cuenta y bitácora de auditoría.
- Pantallas web sencillas y una API JSON en `/api`.

Stack: Python 3.12, Flask 3, SQLite (SQL directo, sin ORM) y gunicorn.

## Correr en local

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q
python wsgi.py          # http://127.0.0.1:5050 (PORT para cambiarlo)
```

La base se crea en `instance/transferencias.db` con datos de ejemplo. Para volver al estado inicial: `POST /api/demo/reiniciar`.

## Modo demo

Con `DEMO_MODE=1` (valor por defecto) la API acepta la cabecera `X-Demo-Ahora` con una fecha ISO 8601 para simular la hora. Sirve para probar el límite diario y los reversos.

## Documentación

- [API](docs/API.md)
- Despliegue en Azure: [infra/](infra/) y [.github/workflows/](.github/workflows/)
