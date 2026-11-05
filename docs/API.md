# API del módulo de transferencias

Base: `/api`. JSON en UTF-8. Los importes viajan como **texto con dos decimales** (`"1670.00"`). Moneda única: DOP.

Errores:

```json
{ "error": { "codigo": "SALDO_INSUFICIENTE", "mensaje": "..." } }
```

| HTTP | Códigos |
|---|---|
| 400 | `VALIDACION`, `MISMA_CUENTA` |
| 404 | `CUENTA_NO_EXISTE`, `TRANSFERENCIA_NO_EXISTE`, `NO_ENCONTRADO` |
| 409 | `IDEMPOTENCIA_CONFLICTO` |
| 422 | `SALDO_INSUFICIENTE`, `LIMITE_DIARIO`, `CUENTA_BLOQUEADA` |

## Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/salud` | Estado, versión y hora |
| GET | `/cuentas` | Cuentas con titular y saldo |
| GET | `/cuentas/{numero}` | Una cuenta |
| GET | `/transferencias?cuenta=&limite=20` | Transferencias, de la más reciente a la más antigua |
| POST | `/transferencias` | Crea una transferencia (201; 200 si es repetición idempotente, con `Idempotent-Replay: true`) |
| GET | `/transferencias/{id}` | Una transferencia |
| POST | `/demo/reiniciar` | Vuelve a los datos de ejemplo (solo en modo demo) |

La pantalla web está en `/` y usa esta misma API.

### POST /transferencias

Cabecera opcional `Idempotency-Key` (hasta 64 caracteres). En modo demo, `X-Demo-Ahora` fija la hora.

```json
{ "cuenta_origen": "7001-0001", "cuenta_destino": "7001-0003", "monto": "1670.00", "concepto": "Pago de alquiler" }
```

```json
{
  "id": "T000001", "tipo": "TERCEROS", "cuenta_origen": "7001-0001", "cuenta_destino": "7001-0003",
  "moneda": "DOP", "monto": "1670.00", "comision": "10.00", "impuesto": "2.51", "total_debitado": "1682.51",
  "concepto": "Pago de alquiler", "fecha": "2026-11-05T10:00:00-04:00"
}
```

## Reglas de negocio

- **Tipos:** `PROPIA` (mismo cliente) y `TERCEROS`.
- **Comisión:** propias sin cargo; terceros DOP 10.00.
- **Impuesto DGII:** 0.15 % del monto en transferencias a terceros, redondeado a centavos mitad hacia arriba.
- **Límite diario:** DOP 300,000.00 por cliente, sin contar transferencias propias.
- **Idempotencia:** la misma clave con los mismos datos devuelve la transferencia original; con otros datos, 409.
