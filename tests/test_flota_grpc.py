import grpc
import pytest

import flota_pb2


def test_consultar_camion(flota):
    camion = flota.ConsultarCamion(flota_pb2.ConsultarCamionRequest(camion_id="CAM-01"))
    assert camion.camion_id == "CAM-01"
    assert {(r.origen, r.destino) for r in camion.rutas} == {("Concepcion", "Santiago"), ("Santiago", "Concepcion")}


def test_consultar_camion_inexistente_da_not_found(flota):
    with pytest.raises(grpc.RpcError) as error:
        flota.ConsultarCamion(flota_pb2.ConsultarCamionRequest(camion_id="CAM-99"))
    assert error.value.code() == grpc.StatusCode.NOT_FOUND


def test_listar_flota_es_un_stream(flota):
    camiones = list(flota.ListarFlota(flota_pb2.ListarFlotaRequest()))
    assert [c.camion_id for c in camiones] == ["CAM-01", "CAM-02", "CAM-03", "CAM-04", "CAM-05"]


def test_buscar_disponibles_filtra_por_ruta_y_carga(flota):
    respuesta = flota.BuscarDisponibles(flota_pb2.BuscarDisponiblesRequest(origen="concepcion", destino="santiago", carga_minima_kg=11000))
    assert [c.camion_id for c in respuesta.camiones] == ["CAM-03"]


def test_no_se_puede_liberar_mas_que_la_capacidad_maxima(flota):
    respuesta = flota.ActualizarCapacidad(flota_pb2.ActualizarCapacidadRequest(
        camion_id="CAM-01", origen="Santiago", destino="Concepcion", variacion_kg=999999
    ))
    assert not respuesta.exito


def test_actualizar_ruta_que_el_camion_no_opera_da_not_found(flota):
    with pytest.raises(grpc.RpcError) as error:
        flota.ActualizarCapacidad(flota_pb2.ActualizarCapacidadRequest(
            camion_id="CAM-01", origen="Arica", destino="Iquique", variacion_kg=-1
        ))
    assert error.value.code() == grpc.StatusCode.NOT_FOUND
