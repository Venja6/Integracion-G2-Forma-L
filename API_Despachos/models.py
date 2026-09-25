import uuid
from sqlalchemy import Column, String, Float
from database import Base

class ClienteModel(Base):
    __tablename__ = "clientes"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    nombre = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)

class UsuarioModel(Base):
    __tablename__ = "usuarios"

    username = Column(String, primary_key=True)
    password_hash = Column(String, nullable=False)
    rol = Column(String, nullable=False)

class DespachoModel(Base):
    __tablename__ = "despachos"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    cliente_id = Column(String, nullable=False)
    camion_id = Column(String, nullable=False)
    origen = Column(String, nullable=False)
    destino = Column(String, nullable=False)
    carga_kg = Column(Float, nullable=False)
    estado = Column(String, default="REGISTRADO")
    # Clave que manda el cliente para que un reintento no cree dos despachos, unique para que la BD lo garantice
    idempotency_key = Column(String(255), unique=True, nullable=True)
    request_hash = Column(String(64), nullable=True)