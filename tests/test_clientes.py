from conftest import validar, validar_lista


def test_crear_y_consultar_cliente(api, operador, cliente):
    validar(cliente, "Cliente")
    respuesta = api.get(f"/clientes/{cliente['id']}", headers=operador)
    assert respuesta.status_code == 200
    assert respuesta.json() == cliente


def test_listar_clientes(api, operador, cliente):
    respuesta = api.get("/clientes", headers=operador)
    assert respuesta.status_code == 200
    validar_lista(respuesta.json(), "Cliente")
    assert cliente["id"] in [c["id"] for c in respuesta.json()]


def test_cliente_inexistente_responde_404(api, operador):
    respuesta = api.get("/clientes/no-existe", headers=operador)
    assert respuesta.status_code == 404
    validar(respuesta.json(), "Error")


def test_email_duplicado_responde_409(api, operador, cliente):
    respuesta = api.post("/clientes", headers=operador, json={"nombre": "Otro", "email": cliente["email"]})
    assert respuesta.status_code == 409
    validar(respuesta.json(), "Error")


def test_email_invalido_responde_422(api, operador):
    respuesta = api.post("/clientes", headers=operador, json={"nombre": "Otro", "email": "no-es-email"})
    assert respuesta.status_code == 422
    validar(respuesta.json(), "Error")
