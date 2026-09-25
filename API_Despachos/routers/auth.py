from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from models import UsuarioModel
from schemas_generated import LoginInput, Token, Error
from auth import verificar_password, crear_token, MINUTOS_EXPIRACION

router = APIRouter(prefix="/v1/auth", tags=["Autenticación"])


@router.post("/token", response_model=Token, responses={401: {"model": Error}})
def obtener_token(login: LoginInput, db: Session = Depends(get_db)):
    # password llega como SecretStr (por el format password del contrato), asi no aparece en logs
    usuario = db.query(UsuarioModel).filter(UsuarioModel.username == login.username).first()
    # Mismo mensaje si no existe el usuario o si la clave esta mal, asi no se puede adivinar que usuarios existen
    if not usuario or not verificar_password(login.password.get_secret_value(), usuario.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"codigo": "ERR_401", "mensaje": "Usuario o contraseña incorrectos."}
        )
    return Token(
        access_token=crear_token(usuario.username, usuario.rol),
        token_type="bearer",
        expires_in=MINUTOS_EXPIRACION * 60
    )
