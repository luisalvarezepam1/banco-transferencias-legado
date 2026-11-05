import pytest

from app import create_app

AHORA = "2026-11-05T10:00:00-04:00"


@pytest.fixture()
def cli(tmp_path):
    return create_app({"DATABASE": str(tmp_path / "t.db"), "DEMO_MODE": True, "TESTING": True}).test_client()


def transferir(cli, cuerpo, clave=None, ahora=AHORA):
    h = {"X-Demo-Ahora": ahora}
    if clave:
        h["Idempotency-Key"] = clave
    return cli.post("/api/transferencias", json=cuerpo, headers=h)


def saldo(cli, numero):
    return cli.get(f"/api/cuentas/{numero}").get_json()["saldo"]


def test_salud_y_cuentas(cli):
    assert cli.get("/api/salud").get_json()["estado"] == "ok"
    cuentas = cli.get("/api/cuentas").get_json()
    assert len(cuentas) == 6 and cuentas[0]["saldo"] == "85000.00"


def test_propia_sin_cargos(cli):
    t = transferir(cli, {"cuenta_origen": "7001-0001", "cuenta_destino": "7001-0002", "monto": "1000.00"}).get_json()
    assert (t["tipo"], t["comision"], t["impuesto"], t["total_debitado"]) == ("PROPIA", "0.00", "0.00", "1000.00")


def test_terceros_comision_e_impuesto(cli):
    r = transferir(cli, {"cuenta_origen": "7001-0001", "cuenta_destino": "7001-0003", "monto": "1670.00"})
    t = r.get_json()
    assert r.status_code == 201
    assert (t["comision"], t["impuesto"], t["total_debitado"]) == ("10.00", "2.51", "1682.51")
    assert saldo(cli, "7001-0001") == "83317.49"
    assert saldo(cli, "7001-0003") == "4870.00"


def test_validaciones(cli):
    base = {"cuenta_origen": "7001-0001", "cuenta_destino": "7001-0003"}
    assert transferir(cli, dict(base, monto="10.123")).status_code == 400
    assert transferir(cli, dict(base, monto="0")).status_code == 400
    assert transferir(cli, dict(base, cuenta_destino="7001-0001", monto="5")).get_json()["error"]["codigo"] == "MISMA_CUENTA"
    assert transferir(cli, dict(base, cuenta_destino="7001-0099", monto="5")).status_code == 404
    assert transferir(cli, dict(base, cuenta_destino="7001-0006", monto="5")).get_json()["error"]["codigo"] == "CUENTA_BLOQUEADA"
    assert transferir(cli, {"cuenta_origen": "7001-0003", "cuenta_destino": "7001-0001", "monto": "3195.00"}).get_json()["error"]["codigo"] == "SALDO_INSUFICIENTE"


def test_limite_diario(cli):
    base = {"cuenta_origen": "7001-0005", "cuenta_destino": "7001-0004"}
    assert transferir(cli, dict(base, monto="300000.00")).status_code == 201
    assert transferir(cli, dict(base, monto="200000.01")).get_json()["error"]["codigo"] == "LIMITE_DIARIO"
    assert transferir(cli, dict(base, monto="200000.01"), ahora="2026-11-06T00:30:00-04:00").status_code == 201


def test_idempotencia(cli):
    cuerpo = {"cuenta_origen": "7001-0001", "cuenta_destino": "7001-0002", "monto": "50.00"}
    a, b = transferir(cli, cuerpo, clave="k-1"), transferir(cli, cuerpo, clave="k-1")
    assert (a.status_code, b.status_code) == (201, 200)
    assert a.get_json()["id"] == b.get_json()["id"] and b.headers["Idempotent-Replay"] == "true"
    assert transferir(cli, dict(cuerpo, monto="51.00"), clave="k-1").status_code == 409


def test_pantalla(cli):
    r = cli.get("/")
    assert r.status_code == 200 and b"Nueva transferencia" in r.data
