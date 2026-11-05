import pytest

from app import create_app

AHORA = "2026-11-05T10:00:00-04:00"


@pytest.fixture()
def cli(tmp_path):
    app = create_app({"DATABASE": str(tmp_path / "t.db"), "DEMO_MODE": True, "TESTING": True})
    return app.test_client()


def transferir(cli, cuerpo, clave=None, ahora=AHORA):
    h = {"X-Demo-Ahora": ahora}
    if clave:
        h["Idempotency-Key"] = clave
    return cli.post("/api/transferencias", json=cuerpo, headers=h)


def saldo(cli, numero):
    return cli.get(f"/api/cuentas/{numero}").get_json()["saldo"]


def test_salud(cli):
    r = cli.get("/api/salud")
    assert r.status_code == 200 and r.get_json()["estado"] == "ok"


def test_clientes_semilla(cli):
    datos = cli.get("/api/clientes").get_json()
    assert len(datos) == 6
    assert datos[0]["cuentas"][0] == {"numero": "7001-0001", "cliente": {"id": "C001", "nombre": "María Fernández"},
                                      "tipo": "AHORRO", "moneda": "DOP", "saldo": "85000.00", "estado": "ACTIVA"}


def test_propia_sin_cargos(cli):
    r = transferir(cli, {"cuenta_origen": "7001-0001", "cuenta_destino": "7001-0002", "monto": "1000.00"})
    t = r.get_json()
    assert r.status_code == 201
    assert (t["tipo"], t["comision"], t["impuesto"], t["total_debitado"]) == ("PROPIA", "0.00", "0.00", "1000.00")
    assert saldo(cli, "7001-0001") == "84000.00"
    assert saldo(cli, "7001-0002") == "13500.00"


def test_terceros_comision_e_impuesto(cli):
    t = transferir(cli, {"cuenta_origen": "7001-0001", "cuenta_destino": "7001-0003", "monto": "1670.00"}).get_json()
    assert t["tipo"] == "TERCEROS"
    assert t["comision"] == "10.00"
    assert t["impuesto"] == "2.51"  # 1670.00 x 0.15% = 2.505 -> 2.51
    assert t["total_debitado"] == "1682.51"
    assert saldo(cli, "7001-0001") == "83317.49"


def test_interbancaria_minimo_y_maximo(cli):
    chica = transferir(cli, {"cuenta_origen": "7001-0005", "cuenta_destino": "998877", "banco_destino": "BANCO_A", "monto": "500"}).get_json()
    assert (chica["tipo"], chica["comision"]) == ("INTERBANCARIA", "25.00")
    grande = transferir(cli, {"cuenta_origen": "7001-0006", "cuenta_destino": "112233", "banco_destino": "BANCO_B", "monto": "200000.00"}).get_json()
    assert grande["comision"] == "300.00"
    assert grande["impuesto"] == "300.00"


def test_validaciones(cli):
    assert transferir(cli, {"cuenta_origen": "7001-0001", "cuenta_destino": "7001-0003", "monto": "10.123"}).status_code == 400
    assert transferir(cli, {"cuenta_origen": "7001-0001", "cuenta_destino": "7001-0003", "monto": "-5"}).status_code == 400
    assert transferir(cli, {"cuenta_origen": "7001-0001", "cuenta_destino": "7001-0001", "monto": "5"}).get_json()["error"]["codigo"] == "MISMA_CUENTA"
    assert transferir(cli, {"cuenta_origen": "7001-0001", "cuenta_destino": "7001-0099", "monto": "5"}).status_code == 404
    assert transferir(cli, {"cuenta_origen": "7001-0001", "cuenta_destino": "7001-0007", "monto": "5"}).get_json()["error"]["codigo"] == "MONEDA_DISTINTA"
    assert transferir(cli, {"cuenta_origen": "7001-0008", "cuenta_destino": "7001-0009", "monto": "5"}).get_json()["error"]["codigo"] == "CUENTA_BLOQUEADA"
    assert transferir(cli, {"cuenta_origen": "7001-0008", "cuenta_destino": "7001-0003", "monto": "895.00"}).get_json()["error"]["codigo"] == "SALDO_INSUFICIENTE"


def test_limite_diario(cli):
    base = {"cuenta_origen": "7001-0006", "cuenta_destino": "7001-0005"}
    assert transferir(cli, dict(base, monto="300000.00")).status_code == 201
    r = transferir(cli, dict(base, monto="200000.01"))
    assert r.get_json()["error"]["codigo"] == "LIMITE_DIARIO"
    # Al día siguiente (hora de Santo Domingo) el límite se renueva
    assert transferir(cli, dict(base, monto="200000.01"), ahora="2026-11-06T00:30:00-04:00").status_code == 201


def test_idempotencia_misma_respuesta(cli):
    cuerpo = {"cuenta_origen": "7001-0001", "cuenta_destino": "7001-0002", "monto": "50.00"}
    a = transferir(cli, cuerpo, clave="abc-1")
    b = transferir(cli, cuerpo, clave="abc-1")
    assert a.status_code == 201 and b.status_code == 200
    assert a.get_json()["id"] == b.get_json()["id"]
    assert b.headers["Idempotent-Replay"] == "true"
    otro = transferir(cli, dict(cuerpo, monto="51.00"), clave="abc-1")
    assert otro.status_code == 409


def test_reverso(cli):
    t = transferir(cli, {"cuenta_origen": "7001-0001", "cuenta_destino": "7001-0003", "monto": "1000.00"}).get_json()
    r = cli.post(f"/api/transferencias/{t['id']}/reverso", headers={"X-Demo-Ahora": AHORA})
    assert r.status_code == 200 and r.get_json()["estado"] == "REVERSADA"
    assert saldo(cli, "7001-0001") == "84990.00"  # la comisión no se devuelve
    assert cli.post(f"/api/transferencias/{t['id']}/reverso", headers={"X-Demo-Ahora": AHORA}).status_code == 409


def test_auditoria_registra_rechazos(cli):
    transferir(cli, {"cuenta_origen": "7001-0008", "cuenta_destino": "7001-0003", "monto": "895.00"})
    a = cli.get("/api/auditoria").get_json()
    assert a[0]["resultado"] == "RECHAZADA" and a[0]["detalle"]["codigo"] == "SALDO_INSUFICIENTE"


def test_pantallas(cli):
    assert cli.get("/").status_code == 200
    assert cli.get("/cuentas/7001-0001").status_code == 200
    assert cli.get("/transferir").status_code == 200
