import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

# La clave real se pasa por variable de entorno, esta es solo para correr en local (HS256 pide 32 bytes o mas)
SECRET_KEY = os.getenv("SECRET_KEY", "clave-solo-para-desarrollo-local-no-usar")
ALGORITHM = "HS256"
MINUTOS_EXPIRACION = int(os.getenv("JWT_MINUTOS_EXPIRACION", "30"))

ROL_OPERADOR = "operador"
ROL_CONSULTA = "consulta"

# auto_error en False para devolver nosotros el 401 con el formato de error de la API
_bearer = HTTPBearer(auto_error=False)


def hashear_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verificar_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def crear_token(username: str, rol: str) -> str:
    expira = datetime.now(timezone.utc) + timedelta(minutes=MINUTOS_EXPIRACION)
    return jwt.encode({"sub": username, "rol": rol, "exp": expira}, SECRET_KEY, algorithm=ALGORITHM)


def _no_autenticado(mensaje: str):
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"codigo": "ERR_401", "mensaje": mensaje},
        headers={"WWW-Authenticate": "Bearer"},
    )


def usuario_actual(credenciales: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> dict:
    if credenciales is None:
        raise _no_autenticado("Falta el token de autenticación.")
    try:
        # jwt.decode revisa la firma y tambien que el token no este vencido
        payload = jwt.decode(credenciales.credentials, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise _no_autenticado("El token expiró.")
    except jwt.InvalidTokenError:
        raise _no_autenticado("Token inválido.")
    return {"username": payload["sub"], "rol": payload["rol"]}


def requiere_operador(usuario: dict = Depends(usuario_actual)) -> dict:
    # El usuario ya esta autenticado, aca solo se revisa si tiene permiso para modificar
    if usuario["rol"] != ROL_OPERADOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"codigo": "ERR_403", "mensaje": "No tiene permisos para realizar esta operación."},
        )
    return usuario
