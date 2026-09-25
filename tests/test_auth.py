from conftest import validar


def test_login_correcto_entrega_token(api):
    respuesta = api.post("/auth/token", json={"username": "operador", "password": "operador123"})
    assert respuesta.status_code == 200
    validar(respuesta.json(), "Token")
    assert respuesta.json()["token_type"] == "bearer"


def test_login_no_revela_si_el_usuario_existe(api):
    clave_mala = api.post("/auth/token", json={"username": "operador", "password": "mala"})
    usuario_malo = api.post("/auth/token", json={"username": "nadie", "password": "mala"})
    assert clave_mala.status_code == usuario_malo.status_code == 401
    validar(clave_mala.json(), "Error")
    assert clave_mala.json() == usuario_malo.json()


def test_sin_token_responde_401_con_www_authenticate(api):
    respuesta = api.get("/clientes")
    assert respuesta.status_code == 401
    assert respuesta.headers["www-authenticate"] == "Bearer"
    validar(respuesta.json(), "Error")


def test_token_invalido_responde_401(api):
    respuesta = api.get("/clientes", headers={"Authorization": "Bearer no.es.token"})
    assert respuesta.status_code == 401


def test_rol_consulta_puede_leer(api, consulta):
    assert api.get("/despachos", headers=consulta).status_code == 200


def test_rol_consulta_no_puede_modificar(api, consulta, cliente):
    crear_cliente = api.post("/clientes", headers=consulta, json={"nombre": "X", "email": "x@prueba.cl"})
    despachar = api.post("/despachos", headers=consulta, json={
        "cliente_id": cliente["id"], "camion_id": "CAM-01", "origen": "Concepcion", "destino": "Santiago", "carga_kg": 1
    })
    assert crear_cliente.status_code == despachar.status_code == 403
    validar(despachar.json(), "Error")
