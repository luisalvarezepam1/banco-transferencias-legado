# API de Transferencias Inmediatas

Base: `/api`. Respuestas en JSON (UTF-8). Los importes viajan como **texto con dos decimales** (`"1670.00"`).

Errores:

```json
{ "error": { "codigo": "SALDO_INSUFICIENTE", "mensaje": "..." } }
```

| Código HTTP | Cuándo |
|---|---|
| 400 | Validación (`VALIDACION`, `MISMA_CUENTA`) |
| 404 | No existe (`CUENTA_NO_EXISTE`, `TRANSFERENCIA_NO_EXISTE`, `NO_ENCONTRADO`) |
| 409 | Conflicto (`IDEMPOTENCIA_CONFLICTO`, `YA_REVERSADA`) |
| 422 | Regla de negocio (`SALDO_INSUFICIENTE`, `LIMITE_DIARIO`, `MONEDA_DISTINTA`, `CUENTA_BLOQUEADA`, `NO_PERMITIDA`, `NO_REVERSABLE`, `REVERSO_FUERA_DE_PLAZO`, `SALDO_INSUFICIENTE_DESTINO`) |

## Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/salud` | Estado, versión y hora del servidor |
| GET | `/clientes` | Clientes con sus cuentas |
| GET | `/cuentas/{numero}` | Una cuenta |
| GET | `/cuentas/{numero}/movimientos?limite=50` | Movimientos, del más reciente al más antiguo |
| GET | `/transferencias?cuenta=&limite=50` | Transferencias |
| POST | `/transferencias` | Crea una transferencia (201; 200 si es repetición idempotente) |
| GET | `/transferencias/{id}` | Una transferencia |
| POST | `/transferencias/{id}/reverso` | Reversa una transferencia |
| GET | `/auditoria?limite=100` | Bitácora de auditoría |
| POST | `/demo/reiniciar` | Vuelve a los datos de ejemplo (solo en modo demo) |

### POST /transferencias

Cabecera opcional `Idempotency-Key` (hasta 64 caracteres).

```json
{
  "cuenta_origen": "7001-0001",
  "cuenta_destino": "7001-0003",
  "banco_destino": "POPULAR",
  "monto": "1670.00",
  "concepto": "Pago de alquiler"
}
```

Respuesta:

```json
{
  "id": "T000001",
  "tipo": "TERCEROS",
  "cuenta_origen": "7001-0001",
  "cuenta_destino": "7001-0003",
  "banco_destino": "POPULAR",
  "moneda": "DOP",
  "monto": "1670.00",
  "comision": "10.00",
  "impuesto": "2.51",
  "total_debitado": "1682.51",
  "concepto": "Pago de alquiler",
  "estado": "APLICADA",
  "fecha": "2026-11-05T10:00:00-04:00",
  "fecha_reverso": null
}
```

## Reglas de negocio

- **Tipos:** `PROPIA` (mismo cliente), `TERCEROS` (otro cliente del banco) e `INTERBANCARIA` (`banco_destino` distinto de `POPULAR`; solo DOP).
- **Comisión:** propias sin cargo; terceros DOP 10.00 (USD 0.50); interbancarias 0.25 % con mínimo DOP 25.00 y máximo DOP 300.00.
- **Impuesto DGII:** 0.15 % del monto en terceros e interbancarias.
- **Redondeo:** a centavos, mitad hacia arriba.
- **Límite diario:** DOP 300,000.00 por cliente (USD 25,000.00), sin contar transferencias propias.
- **Reverso:** solo el mismo día; devuelve monto e impuesto; la comisión no es reembolsable. Las interbancarias no se reversan.
- **Idempotencia:** la misma clave con los mismos datos devuelve la transferencia original; con otros datos devuelve 409.
