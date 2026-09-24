from concurrent import futures
import grpc
import flota_pb2
import flota_pb2_grpc
from database import init_db, SessionLocal, Camion, RutaCamion

class FlotaService(flota_pb2_grpc.ServicioFlotaServicer):

    def ConsultarCamion(self, request, context):
        with SessionLocal() as db:
            camion = db.query(Camion).filter(Camion.camion_id == request.camion_id).first()

            return flota_pb2.ConsultarCamionResponse(
                camion_id=camion.camion_id,
                capacidad_disponible_kg=camion.capacidad_disponible_kg,
                rutas=[r.nombre_ruta for r in camion.rutas]
            )

    def ListarFlota(self, request, context):
        with SessionLocal() as db:
            camiones = db.query(Camion).all()

            return flota_pb2.ListarFlotaResponse(
                camiones=[
                    flota_pb2.ConsultarCamionResponse(
                        camion_id=c.camion_id,
                        capacidad_disponible_kg=c.capacidad_disponible_kg,
                        rutas=[r.nombre_ruta for r in c.rutas]
                    ) for c in camiones
                ]
            )

    def ActualizarCapacidad(self, request, context):
        with SessionLocal() as db:
            camion = db.query(Camion).filter(Camion.camion_id == request.camion_id).with_for_update().first()
            if not camion:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details(f"Camión {request.camion_id} no encontrado")
                return flota_pb2.ActualizarCapacidadResponse(
                    exito=False,
                    nueva_capacidad_kg=0.0,
                    mensaje_error=f"Camión {request.camion_id} no encontrado"
                )

            nueva_capacidad = camion.capacidad_disponible_kg + request.variacion_kg

            if nueva_capacidad > camion.capacidad_total_kg:
                return flota_pb2.ActualizarCapacidadResponse(
                    exito=False,
                    nueva_capacidad_kg=camion.capacidad_disponible_kg,
                    mensaje_error=f"Error de consistencia: Camión aumento de capacidad."
                )

            if nueva_capacidad < 0:
                return flota_pb2.ActualizarCapacidadResponse(
                    exito=False,
                    nueva_capacidad_kg=camion.capacidad_disponible_kg,
                    mensaje_error=f"Capacidad insuficiente en el camión."
                )

            # Se modifica capacidad en la BD
            camion.capacidad_disponible_kg = nueva_capacidad
            db.commit()

            return flota_pb2.ActualizarCapacidadResponse(
                exito=True,
                nueva_capacidad_kg=camion.capacidad_disponible_kg,
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