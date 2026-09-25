from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


def _respuesta_error(status_code: int, codigo: str, mensaje: str, headers=None):
    return JSONResponse(status_code=status_code, content={"codigo": codigo, "mensaje": mensaje}, headers=headers)


def registrar_manejadores(app: FastAPI):
    # Sin estos manejadores FastAPI envuelve todo en {"detail": ...} y no calza con el esquema Error del contrato

    @app.exception_handler(StarletteHTTPException)
    async def manejar_http(request: Request, exc: StarletteHTTPException):
        if isinstance(exc.detail, dict) and "codigo" in exc.detail:
            return _respuesta_error(exc.status_code, exc.detail["codigo"], exc.detail["mensaje"], exc.headers)
        # Errores que lanza el propio framework, por ejemplo una ruta que no existe (404) o un metodo no permitido (405)
        return _respuesta_error(exc.status_code, f"ERR_{exc.status_code}", str(exc.detail), exc.headers)

    @app.exception_handler(RequestValidationError)
    async def manejar_validacion(request: Request, exc: RequestValidationError):
        # Se junta cada problema como "campo, motivo" para que el cliente sepa que corregir
        problemas = []
        for error in exc.errors():
            campo = ".".join(str(parte) for parte in error["loc"] if parte != "body")
            problemas.append(f"{campo} {error['msg']}")
        return _respuesta_error(422, "ERR_422", "Datos inválidos. " + "; ".join(problemas))
