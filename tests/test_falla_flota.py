import subprocess
import time
import uuid

import grpc
import pytest

from conftest import FLOTA_HOST, RAIZ, validar

pytestmark = pytest.mark.falla


def _compose(*args):
    subprocess.run(["docker", "compose", *args], cwd=RAIZ, check=True, capture_output=True)


def _encender_flota(api, operador):
    _compose("start", "grpc_flota")
    grpc.channel_ready_future(grpc.insecure_channel(FLOTA_HOST)).result(timeout=30)
    # Flota ya acepta conexiones, pero la API puede tardar un poco en reconectar su canal.
    # Se usa una ruta al azar para que la respuesta nunca venga de la cache
    for _ in range(20):
        ruta = {"origen": str(uuid.uuid4()), "destino": "x"}
        if api.get("/camiones/disponibles", headers=operador, params=ruta).status_code == 200:
            return
        time.sleep(0.5)
    raise AssertionError("La API no se reconecto a Flota")


def _nuevo_despacho(cliente):
    return {"cliente_id": cliente["id"], "camion_id": "CAM-02", "origen": "Temuco", "destino": "Puerto Montt", "carga_kg": 10}


def test_flota_caida_responde_503_rapido(api, operador, cliente):
    _compose("stop", "grpc_flota")
    try:
        inicio = time.monotonic()
        respuesta = api.post("/despachos", headers=operador, json=_nuevo_despacho(cliente))
        duracion = time.monotonic() - inicio
    finally:
        _encender_flota(api, operador)

    assert respuesta.status_code == 503
    validar(respuesta.json(), "Error")
    # El timeout de 2 s corta la espera, la API no se queda colgada
    assert duracion < 3


def test_revertir_con_flota_caida_responde_503(api, operador, cliente):
    creado = api.post("/despachos", headers=operador, json=_nuevo_despacho(cliente)).json()
    _compose("stop", "grpc_flota")
    try:
        respuesta = api.delete(f"/despachos/{creado['id']}", headers=operador)
    finally:
        _encender_flota(api, operador)

    assert respuesta.status_code == 503
    # Cuando Flota vuelve se puede revertir normalmente
    assert api.delete(f"/despachos/{creado['id']}", headers=operador).status_code == 204
