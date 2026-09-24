import futures
import grpc
import flota_pb2
import flota_pb2_grpc

class FlotaService(flota_pb2_grpc.ServicioFlotaServicer):

    def ConsultarCamion(self, request, context):
        # Request es un objeto ConsultaCamionRequest de flota_pb2
        camion_id = request.camion_id

        # Implementar consulta a base de datos y retornar informacion del camion

    def ListarFlota(self, request, context):
        # Implementar consulta y retornar camiones y sus rutas
        pass

    def ActualizarCapacidad(self, request, context):
        # Request es un objeto ActualizarCapacidadRequest de flota_pb2
        camion_id = request.camion_id
        capacidad_disponible = request.capacidad_disponible_kg

        # Implementar consulta a la base de datos para actualizar la capacidad del camion y sus rutasd
        pass

def iniciar():
    servidor = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    flota_pb2_grpc.add_ServicioFlotaServicer_to_server(FlotaService(), servidor)

    puerto = "50051"
    servidor.add_insecure_port(f"[::]{puerto}")
    servidor.start()
    print(f"Servidor gRPC escuchando en el puerto {puerto}...")
    servidor.wait_for_termination()

if __name__ == "__main__":
    iniciar()