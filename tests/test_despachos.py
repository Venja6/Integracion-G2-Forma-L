import uuid

import pytest

from conftest import capacidad, validar, validar_lista

# CAM-04 opera Concepcion -> Chillan con 5000 kg
CAMION, ORIGEN, DESTINO = "CAM-04", "Concepcion", "Chillan"


@pytest.fixture
def datos_despacho(cliente):
    return {"cliente_id": cliente["id"], "camion_id": CAMION, "origen": ORIGEN, "destino": DESTINO, "carga_kg": 100}


def test_buscar_camiones_disponibles(api, operador):
    respuesta = api.get("/camiones/disponibles", headers=operador, params={"origen": ORIGEN, "destino": DESTINO})
    assert respuesta.status_code == 200
    assert respuesta.headers["x-cache"] in ("HIT", "MISS", "BYPASS")
    validar_lista(respuesta.json(), "CamionDisponible")
    assert CAMION in [c["camion_id"] for c in respuesta.json()]


def test_buscar_filtra_por_carga(api, operador):
    respuesta = api.get("/camiones/disponibles", headers=operador, params={"origen": ORIGEN, "destino": DESTINO, "carga_kg": 999999})
    assert respuesta.json() == []


def test_registrar_y_revertir_despacho(api, operador, flota, datos_despacho):
    antes = capacidad(flota, CAMION, ORIGEN, DESTINO)

    creado = api.post("/despachos", headers=operador, json=datos_despacho)
    assert creado.status_code == 201
    validar(creado.json(), "Despacho")
    despacho = creado.json()
    assert despacho["estado"] == "REGISTRADO"
    assert "revertir" in despacho["_links"]
    assert capacidad(flota, CAMION, ORIGEN, DESTINO) == antes - 100

    assert api.delete(f"/despachos/{despacho['id']}", headers=operador).status_code == 204
    assert capacidad(flota, CAMION, ORIGEN, DESTINO) == antes

    cancelado = api.get(f"/despachos/{despacho['id']}", headers=operador).json()
    assert cancelado["estado"] == "CANCELADO"
    assert "revertir" not in cancelado["_links"]

    # Revertir otra vez no libera capacidad de nuevo
    assert api.delete(f"/despachos/{despacho['id']}", headers=operador).status_code == 204
    assert capacidad(flota, CAMION, ORIGEN, DESTINO) == antes


def test_listar_despachos(api, operador):
    respuesta = api.get("/despachos", headers=operador)
    assert respuesta.status_code == 200
    validar_lista(respuesta.json(), "Despacho")


def test_sin_capacidad_responde_409(api, operador, flota, datos_despacho):
    antes = capacidad(flota, CAMION, ORIGEN, DESTINO)
    respuesta = api.post("/despachos", headers=operador, json={**datos_despacho, "carga_kg": antes + 1})
    assert respuesta.status_code == 409
    validar(respuesta.json(), "Error")
    assert capacidad(flota, CAMION, ORIGEN, DESTINO) == antes


def test_camion_que_no_opera_la_ruta_responde_400(api, operador, datos_despacho):
    respuesta = api.post("/despachos", headers=operador, json={**datos_despacho, "destino": "Santiago"})
    assert respuesta.status_code == 400
    validar(respuesta.json(), "Error")


def test_cliente_inexistente_responde_400(api, operador, datos_despacho):
    respuesta = api.post("/despachos", headers=operador, json={**datos_despacho, "cliente_id": "no-existe"})
    assert respuesta.status_code == 400


@pytest.mark.parametrize("carga", [0, -50])
def test_carga_no_positiva_responde_422(api, operador, datos_despacho, carga):
    respuesta = api.post("/despachos", headers=operador, json={**datos_despacho, "carga_kg": carga})
    assert respuesta.status_code == 422
    validar(respuesta.json(), "Error")


def test_despacho_inexistente_responde_404(api, operador):
    assert api.get("/despachos/no-existe", headers=operador).status_code == 404
    assert api.delete("/despachos/no-existe", headers=operador).status_code == 404


def test_idempotency_key_no_duplica_el_despacho(api, operador, flota, datos_despacho):
    antes = capacidad(flota, CAMION, ORIGEN, DESTINO)
    cabeceras = {**operador, "Idempotency-Key": str(uuid.uuid4())}

    primero = api.post("/despachos", headers=cabeceras, json=datos_despacho)
    reintento = api.post("/despachos", headers=cabeceras, json=datos_despacho)

    assert primero.status_code == reintento.status_code == 201
    assert reintento.headers["idempotent-replayed"] == "true"
    assert primero.json()["id"] == reintento.json()["id"]
    assert capacidad(flota, CAMION, ORIGEN, DESTINO) == antes - 100

    otros_datos = api.post("/despachos", headers=cabeceras, json={**datos_despacho, "carga_kg": 5})
    assert otros_datos.status_code == 422

    api.delete(f"/despachos/{primero.json()['id']}", headers=operador)
