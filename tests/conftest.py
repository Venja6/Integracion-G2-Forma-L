import copy
import os
import sys
import uuid
from pathlib import Path

import grpc
import httpx
import jsonschema
import pytest
import yaml
from grpc_tools import protoc

RAIZ = Path(__file__).resolve().parent.parent
API_URL = os.getenv("API_URL", "http://localhost:8000")
FLOTA_HOST = os.getenv("GRPC_FLOTA_HOST", "localhost:50051")

# Los stubs se generan desde el mismo flota.proto del servidor, si el contrato cambia las pruebas lo notan
_GENERADO = RAIZ / "tests" / "_generado"
_GENERADO.mkdir(exist_ok=True)
protoc.main([
    "grpc_tools.protoc",
    f"-I{RAIZ / 'gRPC_Flota'}",
    f"--python_out={_GENERADO}",
    f"--grpc_python_out={_GENERADO}",
    str(RAIZ / "gRPC_Flota" / "flota.proto"),
])
sys.path.insert(0, str(_GENERADO))
import flota_pb2  # noqa: E402
import flota_pb2_grpc  # noqa: E402

_CONTRATO = yaml.safe_load((RAIZ / "API_Despachos" / "openapi.yaml").read_text(encoding="utf-8"))
_ESQUEMAS = _CONTRATO["components"]["schemas"]


def _resolver(esquema):
    """Reemplaza los $ref por el esquema real y prohibe campos que el contrato no declara"""
    if isinstance(esquema, list):
        return [_resolver(e) for e in esquema]
    if not isinstance(esquema, dict):
        return esquema
    if "$ref" in esquema:
        return _resolver(copy.deepcopy(_ESQUEMAS[esquema["$ref"].split("/")[-1]]))
    resuelto = {k: _resolver(v) for k, v in esquema.items()}
    # El contrato no puede tener campos de mas, si la API manda algo que no esta declarado la prueba falla
    if resuelto.get("type") == "object" and "properties" in resuelto and "additionalProperties" not in resuelto:
        resuelto["additionalProperties"] = False
    return resuelto


def validar(datos, nombre_esquema: str):
    esquema = _resolver({"$ref": f"#/components/schemas/{nombre_esquema}"})
    # OpenAPI 3.0 usa exclusiveMinimum booleano igual que el draft 4 de JSON Schema
    jsonschema.Draft4Validator(esquema, format_checker=jsonschema.FormatChecker()).validate(datos)


def validar_lista(datos, nombre_esquema: str):
    assert isinstance(datos, list)
    for elemento in datos:
        validar(elemento, nombre_esquema)


@pytest.fixture(scope="session")
def api():
    with httpx.Client(base_url=f"{API_URL}/v1", timeout=10) as cliente:
        yield cliente


@pytest.fixture(scope="session")
def flota():
    canal = grpc.insecure_channel(FLOTA_HOST)
    yield flota_pb2_grpc.ServicioFlotaStub(canal)
    canal.close()


def _token(api, username, password):
    respuesta = api.post("/auth/token", json={"username": username, "password": password})
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()["access_token"]


@pytest.fixture(scope="session")
def operador(api):
    return {"Authorization": f"Bearer {_token(api, 'operador', 'operador123')}"}


@pytest.fixture(scope="session")
def consulta(api):
    return {"Authorization": f"Bearer {_token(api, 'consulta', 'consulta123')}"}


@pytest.fixture
def cliente(api, operador):
    respuesta = api.post("/clientes", headers=operador, json={"nombre": "Cliente prueba", "email": f"{uuid.uuid4()}@prueba.cl"})
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def capacidad(flota, camion_id: str, origen: str, destino: str) -> float:
    camion = flota.ConsultarCamion(flota_pb2.ConsultarCamionRequest(camion_id=camion_id))
    for ruta in camion.rutas:
        if ruta.origen == origen and ruta.destino == destino:
            return ruta.capacidad_disponible_kg
    raise AssertionError(f"{camion_id} no opera {origen} - {destino}")
