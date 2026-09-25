import os
from sqlalchemy import create_engine, String, Float, ForeignKey, UniqueConstraint
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Mapped, mapped_column, relationship
from typing import List

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://flota_user:flotapassword@localhost:5433/flota_db")

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

class Camion(Base):
    __tablename__="camiones"

    camion_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    # Carga maxima que soporta el camion, es el tope de capacidad en cada ruta
    capacidad_maxima_kg: Mapped[float] = mapped_column(Float, nullable=False)

    rutas: Mapped[List["CamionRuta"]] = relationship(
        back_populates="camion",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

class Ruta(Base):
    __tablename__="rutas"
    __table_args__ = (UniqueConstraint("origen", "destino"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    origen: Mapped[str] = mapped_column(String(100), nullable=False)
    destino: Mapped[str] = mapped_column(String(100), nullable=False)

class CamionRuta(Base):
    __tablename__="camion_rutas"
    __table_args__ = (UniqueConstraint("camion_id", "ruta_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    camion_id: Mapped[str] = mapped_column(ForeignKey("camiones.camion_id", ondelete="CASCADE"))
    ruta_id: Mapped[int] = mapped_column(ForeignKey("rutas.id", ondelete="CASCADE"))
    # La capacidad libre es por ruta, un mismo camion puede ir lleno en una ruta y vacio en otra
    capacidad_disponible_kg: Mapped[float] = mapped_column(Float, nullable=False)

    camion: Mapped["Camion"] = relationship(back_populates="rutas")
    ruta: Mapped["Ruta"] = relationship(lazy="selectin")


# (camion, capacidad maxima, rutas que opera como (origen, destino))
CAMIONES_INICIALES = [
    ("CAM-01", 10000.0, [("Concepcion", "Santiago"), ("Santiago", "Concepcion")]),
    ("CAM-02", 8000.0, [("Concepcion", "Temuco"), ("Temuco", "Puerto Montt")]),
    ("CAM-03", 12000.0, [("Concepcion", "Santiago"), ("Santiago", "Valparaiso")]),
    ("CAM-04", 5000.0, [("Concepcion", "Chillan"), ("Concepcion", "Temuco")]),
    ("CAM-05", 3000.0, [("Los Angeles", "Concepcion"), ("Concepcion", "Chillan")]),
]

def init_db():
    Base.metadata.create_all(bind=engine)
    seed_db()

def seed_db():
    # Solo carga los camiones iniciales si la tabla esta vacia, asi no se duplican al reiniciar
    with SessionLocal() as db:
        if db.query(Camion).first() is not None:
            return
        rutas = {}
        for camion_id, capacidad, rutas_camion in CAMIONES_INICIALES:
            camion = Camion(camion_id=camion_id, capacidad_maxima_kg=capacidad)
            for origen, destino in rutas_camion:
                if (origen, destino) not in rutas:
                    rutas[(origen, destino)] = Ruta(origen=origen, destino=destino)
                camion.rutas.append(CamionRuta(ruta=rutas[(origen, destino)], capacidad_disponible_kg=capacidad))
            db.add(camion)
        db.commit()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
