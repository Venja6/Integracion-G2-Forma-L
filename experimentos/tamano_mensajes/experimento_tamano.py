"""
Experimento complementario para el ADR D2: tamano y tiempo de serializacion de la flota en Protocol Buffers
frente a JSON, con y sin gzip.

Se usa el mismo mensaje Camion de flota.proto. Del lado JSON se usan los mismos campos con los mismos nombres,
que es lo que devolveria una API REST con la misma informacion.

No necesita Docker. Uso: python experimentos/tamano_mensajes/experimento_tamano.py
"""
import csv
import gzip
import json
import random
import statistics
import sys
import tempfile
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from grpc_tools import protoc  # noqa: E402

RAIZ = Path(__file__).resolve().parents[2]
SALIDA = Path(__file__).resolve().parent / "resultados"

CANTIDADES_CAMIONES = [1, 10, 100, 1000, 10000]
REPETICIONES_TIEMPO = 30
SEMILLA = 42  # misma semilla, mismos datos en cada corrida

CIUDADES = ["Concepcion", "Santiago", "Temuco", "Puerto Montt", "Valparaiso", "Chillan", "Los Angeles",
            "Talca", "La Serena", "Antofagasta", "Rancagua", "Valdivia", "Osorno", "Iquique"]
CAPACIDADES = [3000.0, 5000.0, 8000.0, 10000.0, 12000.0]

# Se genera el codigo desde el mismo flota.proto del servicio
_generado = Path(tempfile.mkdtemp())
protoc.main(["grpc_tools.protoc", f"-I{RAIZ / 'gRPC_Flota'}", f"--python_out={_generado}", str(RAIZ / "gRPC_Flota" / "flota.proto")])
sys.path.insert(0, str(_generado))
import flota_pb2  # noqa: E402


def generar_flota(cantidad: int, aleatorio: random.Random):
    """Devuelve la flota como lista de diccionarios, igual a lo que se serializaria en JSON"""
    flota = []
    for i in range(cantidad):
        maxima = aleatorio.choice(CAPACIDADES)
        rutas = []
        for _ in range(aleatorio.randint(1, 4)):
            origen, destino = aleatorio.sample(CIUDADES, 2)
            rutas.append({
                "origen": origen,
                "destino": destino,
                "capacidad_total_kg": maxima,
                "capacidad_disponible_kg": round(aleatorio.uniform(0, maxima), 1),
            })
        flota.append({"camion_id": f"CAM-{i + 1:05d}", "rutas": rutas})
    return flota


def a_protobuf(flota):
    return [
        flota_pb2.Camion(camion_id=c["camion_id"], rutas=[flota_pb2.CapacidadRuta(**r) for r in c["rutas"]])
        for c in flota
    ]


def bytes_stream_grpc(mensajes) -> bytes:
    # ListarFlota es server streaming, cada camion viaja como un mensaje con 5 bytes de encabezado de gRPC
    # (1 byte de compresion y 4 de largo), por eso se suman 5 bytes por mensaje
    partes = []
    for m in mensajes:
        cuerpo = m.SerializeToString()
        partes.append(b"\x00" + len(cuerpo).to_bytes(4, "big") + cuerpo)
    return b"".join(partes)


def bytes_json(flota) -> bytes:
    # Separadores compactos, igual que FastAPI al responder
    return json.dumps(flota, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def mediana_ms(funcion) -> float:
    tiempos = []
    for _ in range(REPETICIONES_TIEMPO):
        inicio = time.perf_counter()
        funcion()
        tiempos.append((time.perf_counter() - inicio) * 1000)
    return statistics.median(tiempos)


def medir(cantidad: int) -> dict:
    flota = generar_flota(cantidad, random.Random(SEMILLA))
    mensajes = a_protobuf(flota)

    pb = bytes_stream_grpc(mensajes)
    js = bytes_json(flota)
    pb_gzip, js_gzip = gzip.compress(pb), gzip.compress(js)

    serializados = [m.SerializeToString() for m in mensajes]
    return {
        "camiones": cantidad,
        "protobuf_bytes": len(pb),
        "json_bytes": len(js),
        "protobuf_gzip_bytes": len(pb_gzip),
        "json_gzip_bytes": len(js_gzip),
        "protobuf_vs_json_pct": round(100 * len(pb) / len(js), 1),
        "con_gzip_protobuf_vs_json_pct": round(100 * len(pb_gzip) / len(js_gzip), 1),
        "protobuf_serializar_ms": round(mediana_ms(lambda: [m.SerializeToString() for m in mensajes]), 3),
        "json_serializar_ms": round(mediana_ms(lambda: bytes_json(flota)), 3),
        "protobuf_leer_ms": round(mediana_ms(lambda: [flota_pb2.Camion.FromString(s) for s in serializados]), 3),
        "json_leer_ms": round(mediana_ms(lambda: json.loads(js)), 3),
    }


def guardar(resultados):
    SALIDA.mkdir(parents=True, exist_ok=True)
    with open(SALIDA / "resultados.csv", "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=list(resultados[0].keys()))
        escritor.writeheader()
        escritor.writerows(resultados)

    lineas = [
        "| Camiones | Protobuf (bytes) | JSON (bytes) | Protobuf / JSON | Protobuf gzip | JSON gzip | Con gzip, Protobuf / JSON | Serializar PB / JSON (ms) | Leer PB / JSON (ms) |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in resultados:
        lineas.append(
            f"| {r['camiones']} | {r['protobuf_bytes']:,} | {r['json_bytes']:,} | {r['protobuf_vs_json_pct']} % | "
            f"{r['protobuf_gzip_bytes']:,} | {r['json_gzip_bytes']:,} | {r['con_gzip_protobuf_vs_json_pct']} % | "
            f"{r['protobuf_serializar_ms']} / {r['json_serializar_ms']} | {r['protobuf_leer_ms']} / {r['json_leer_ms']} |"
        )
    # Separador de miles con espacio para no confundirlo con los decimales
    (SALIDA / "resumen.md").write_text("\n".join(lineas).replace(",", " ") + "\n", encoding="utf-8")


def graficar(resultados):
    x = [r["camiones"] for r in resultados]
    fig, ejes = plt.subplots(1, 3, figsize=(16, 4.8))

    for clave, etiqueta in [("json_bytes", "JSON"), ("protobuf_bytes", "Protobuf"),
                            ("json_gzip_bytes", "JSON + gzip"), ("protobuf_gzip_bytes", "Protobuf + gzip")]:
        ejes[0].plot(x, [r[clave] for r in resultados], marker="o", label=etiqueta)
    ejes[0].set_xscale("log")
    ejes[0].set_yscale("log")
    ejes[0].set_title("Tamaño de la flota serializada")
    ejes[0].set_ylabel("bytes (escala log)")
    ejes[0].legend()

    ejes[1].plot(x, [r["protobuf_vs_json_pct"] for r in resultados], marker="o", label="sin compresión")
    ejes[1].plot(x, [r["con_gzip_protobuf_vs_json_pct"] for r in resultados], marker="o", label="con gzip")
    ejes[1].axhline(100, color="gray", linestyle="--", linewidth=1)
    ejes[1].set_xscale("log")
    ejes[1].set_ylim(0, 110)
    ejes[1].set_title("Tamaño de Protobuf como % de JSON")
    ejes[1].set_ylabel("% (100 = igual que JSON)")
    ejes[1].legend()

    for clave, etiqueta in [("json_serializar_ms", "JSON serializar"), ("protobuf_serializar_ms", "Protobuf serializar"),
                            ("json_leer_ms", "JSON leer"), ("protobuf_leer_ms", "Protobuf leer")]:
        ejes[2].plot(x, [r[clave] for r in resultados], marker="o", label=etiqueta)
    ejes[2].set_xscale("log")
    ejes[2].set_yscale("log")
    ejes[2].set_title(f"Tiempo en Python (mediana de {REPETICIONES_TIEMPO})")
    ejes[2].set_ylabel("ms (escala log)")
    ejes[2].legend()

    for eje in ejes:
        eje.set_xlabel("Camiones en la flota (escala log)")
        eje.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(SALIDA / "grafico.png", dpi=150)


def main():
    resultados = []
    for cantidad in CANTIDADES_CAMIONES:
        r = medir(cantidad)
        resultados.append(r)
        print(
            f"{cantidad:>6} camiones | PB {r['protobuf_bytes']:>9} B | JSON {r['json_bytes']:>9} B | "
            f"PB/JSON {r['protobuf_vs_json_pct']:>5}% | con gzip {r['con_gzip_protobuf_vs_json_pct']:>5}%",
            flush=True,
        )
    guardar(resultados)
    graficar(resultados)
    print(f"Resultados en {SALIDA}")


if __name__ == "__main__":
    main()
