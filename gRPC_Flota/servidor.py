from concurrent import futures
import grpc
from sqlalchemy import func
import flota_pb2
import flota_pb2_grpc
from database import init_db, SessionLocal, Camion, Ruta, CamionRuta


def _filtro_ruta(origen: str, destino: str):
    # Se compara sin importar mayusculas ni espacios, "concepcion" y "Concepcion " son la misma ruta
    return (
        func.lower(Ruta.origen) == origen.strip().lower(),
        func.lower(Ruta.destino) == destino.strip().lower(),
    )


def _a_mensaje(camion: Camion) -> flota_pb2.Camion:
    return flota_pb2.Camion(
        camion_id=camion.camion_id,
        rutas=[
            flota_pb2.CapacidadRuta(
                origen=cr.ruta.origen,
                destino=cr.ruta.destino,
                capacidad_total_kg=camion.capacidad_maxima_kg,
                capacidad_disponible_kg=cr.capacidad_disponible_kg
            ) for cr in camion.rutas
        ]
    )


class FlotaService(flota_pb2_grpc.ServicioFlotaServicer):

    def ConsultarCamion(self, request, context):
        with SessionLocal() as db:
            camion = db.get(Camion, request.camion_id)
            if not camion:
                context.abort(grpc.StatusCode.NOT_FOUND, f"Camión {request.camion_id} no encontrado")
            return _a_mensaje(camion)

    def ListarFlota(self, request, context):
        # Server streaming, cada yield manda un camion y el cliente puede procesarlo sin esperar la lista completa
        with SessionLocal() as db:
            for camion in db.query(Camion).order_by(Camion.camion_id):
                yield _a_mensaje(camion)

    def BuscarDisponibles(self, request, context):
        with SessionLocal() as db:
            asignaciones = (
                db.query(CamionRuta)
                .join(Ruta)
                .filter(*_filtro_ruta(request.origen, request.destino))
                .filter(CamionRuta.capacidad_disponible_kg >= request.carga_minima_kg)
                .order_by(CamionRuta.capacidad_disponible_kg.desc())
                .all()
            )
            return flota_pb2.BuscarDisponiblesResponse(
                camiones=[
                    flota_pb2.CamionDisponible(camion_id=a.camion_id, capacidad_disponible_kg=a.capacidad_disponible_kg)
                    for a in asignaciones
                ]
            )

    def ActualizarCapacidad(self, request, context):
        with SessionLocal() as db:
            # FOR UPDATE bloquea solo la fila del camion en esa ruta hasta el commit, asi dos despachos no ocupan la misma capacidad
            asignacion = (
                db.query(CamionRuta)
                .join(Ruta)
                .filter(CamionRuta.camion_id == request.camion_id)
                .filter(*_filtro_ruta(request.origen, request.destino))
                .with_for_update(of=CamionRuta)
                .first()
            )
            if not asignacion:
                context.abort(
                    grpc.StatusCode.NOT_FOUND,
                    f"El camión {request.camion_id} no opera la ruta {request.origen} - {request.destino}"
                )

            nueva_capacidad = asignacion.capacidad_disponible_kg + request.variacion_kg

            if nueva_capacidad > asignacion.camion.capacidad_maxima_kg:
                return flota_pb2.ActualizarCapacidadResponse(
                    exito=False,
                    nueva_capacidad_kg=asignacion.capacidad_disponible_kg,
                    mensaje_error="Error de consistencia: se liberaría más capacidad que la máxima del camión."
                )

            if nueva_capacidad < 0:
                return flota_pb2.ActualizarCapacidadResponse(
                    exito=False,
                    nueva_capacidad_kg=asignacion.capacidad_disponible_kg,
                    mensaje_error="Capacidad insuficiente en el camión para esa ruta."
                )

            # Se modifica capacidad en la BD
            asignacion.capacidad_disponible_kg = nueva_capacidad
            db.commit()

            return flota_pb2.ActualizarCapacidadResponse(
                exito=True,
                nueva_capacidad_kg=asignacion.capacidad_disponible_kg,
                mensaje_error=""
            )


def iniciar():
    init_db()

    servidor = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    flota_pb2_grpc.add_ServicioFlotaServicer_to_server(FlotaService(), servidor)

    puerto = "50051"
    servidor.add_insecure_port(f"[::]:{puerto}")
    servidor.start()
    print(f"Servidor gRPC escuchando en el puerto {puerto}...")
    servidor.wait_for_termination()

if __name__ == "__main__":
    iniciar()
