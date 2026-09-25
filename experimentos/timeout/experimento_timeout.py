"""
Experimento de la Competencia 6: efecto del timeout de la API cuando Flota responde lento.

Para cada combinacion de timeout (en la API) y latencia media (en Flota) se registran N despachos seguidos
y se mide el tiempo de respuesta, el codigo HTTP y las reservas huerfanas (la API respondio 503 por timeout
pero Flota igual alcanzo a reservar la capacidad).

Requisitos: el sistema levantado con docker compose up y las dependencias de requirements.txt.
Uso: python experimentos/timeout/experimento_timeout.py
"""
import csv
import os
import statistics
import subprocess
import time
import uuid
from pathlib import Path

import httpx
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

RAIZ = Path(__file__).resolve().parents[2]
SALIDA = Path(__file__).resolve().parent / "resultados"
API = "http://localhost:8000"

TIMEOUTS_S = [0.5, 1, 2, 30]  # 30 s se usa como "practicamente sin timeout"
LATENCIAS_MS = [0, 250, 500, 1000, 2000]  # media de la latencia de Flota, con variacion de 30 porciento
REPETICIONES = 30
CARGA_KG = 10

# Ruta con capacidad de sobra para que ningun despacho falle por falta de capacidad (409)
CAMION, ORIGEN, DESTINO = "CAM-03", "Concepcion", "Santiago"


def compose(*args, env=None):
    return subprocess.run(
        ["docker", "compose", *args], cwd=RAIZ, check=True, capture_output=True, text=True,
        env={**os.environ, **(env or {})},
    ).stdout


def sql_flota(consulta: str) -> str:
    return compose("exec", "-T", "db_flota", "psql", "-U", "flota_user", "-d", "flota_db", "-tAc", consulta).strip()


def sql_despachos(consulta: str) -> str:
    return compose("exec", "-T", "db", "psql", "-U", "postgres", "-d", "despachos_db", "-tAc", consulta).strip()


FILTRO_RUTA = (
    f"camion_id = '{CAMION}' AND ruta_id = "
    f"(SELECT id FROM rutas WHERE origen = '{ORIGEN}' AND destino = '{DESTINO}')"
)


def capacidad_actual() -> float:
    return float(sql_flota(f"SELECT capacidad_disponible_kg FROM camion_rutas WHERE {FILTRO_RUTA}"))


def reiniciar_capacidad():
    sql_flota(
        f"UPDATE camion_rutas SET capacidad_disponible_kg = "
        f"(SELECT capacidad_maxima_kg FROM camiones WHERE camion_id = '{CAMION}') WHERE {FILTRO_RUTA}"
    )


def fijar_latencia(ms: int):
    compose("exec", "-T", "grpc_flota", "sh", "-c", f"echo {ms} > /tmp/latencia_ms")


def quitar_latencia():
    compose("exec", "-T", "grpc_flota", "rm", "-f", "/tmp/latencia_ms")


def fijar_timeout(segundos: float) -> str:
    # Cambiar la variable de entorno obliga a recrear el contenedor de la API
    compose("up", "-d", "api_despachos", env={"GRPC_FLOTA_TIMEOUT": str(segundos)})
    return esperar_api()


def esperar_api() -> str:
    """Espera a que la API responda y a que su canal gRPC llegue a Flota, y devuelve un token de operador"""
    for _ in range(60):
        try:
            r = httpx.post(f"{API}/v1/auth/token", json={"username": "operador", "password": "operador123"}, timeout=2)
            if r.status_code == 200:
                token = r.json()["access_token"]
                prueba = httpx.get(
                    f"{API}/v1/camiones/disponibles", params={"origen": str(uuid.uuid4()), "destino": "x"},
                    headers={"Authorization": f"Bearer {token}"}, timeout=5,
                )
                if prueba.status_code == 200:
                    return token
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    raise RuntimeError("La API no quedo lista")


def percentil(valores, p):
    ordenados = sorted(valores)
    k = (len(ordenados) - 1) * p / 100
    inferior, superior = int(k), min(int(k) + 1, len(ordenados) - 1)
    return ordenados[inferior] + (ordenados[superior] - ordenados[inferior]) * (k - inferior)


def ejecutar_combinacion(cliente_http, token, cliente_id, timeout_s, latencia_ms):
    cabeceras = {"Authorization": f"Bearer {token}"}
    cuerpo = {"cliente_id": cliente_id, "camion_id": CAMION, "origen": ORIGEN, "destino": DESTINO, "carga_kg": CARGA_KG}

    fijar_latencia(latencia_ms)
    # Dos peticiones de calentamiento que no se miden, para que la conexion ya este abierta
    for _ in range(2):
        cliente_http.post("/v1/despachos", json=cuerpo, headers=cabeceras)
    time.sleep(latencia_ms * 2 / 1000 + 0.5)
    reiniciar_capacidad()

    filas = []
    for i in range(REPETICIONES):
        inicio = time.perf_counter()
        respuesta = cliente_http.post("/v1/despachos", json=cuerpo, headers=cabeceras)
        filas.append({
            "timeout_s": timeout_s, "latencia_media_ms": latencia_ms, "repeticion": i + 1,
            "codigo": respuesta.status_code, "tiempo_ms": round((time.perf_counter() - inicio) * 1000, 1),
        })

    # Flota puede seguir procesando peticiones que la API ya dio por perdidas, se espera a que terminen
    time.sleep(latencia_ms * 2 / 1000 + 1)
    consumido_kg = float(sql_flota(f"SELECT capacidad_maxima_kg FROM camiones WHERE camion_id = '{CAMION}'")) - capacidad_actual()
    exitos = sum(1 for f in filas if f["codigo"] == 201)
    huerfanas = round((consumido_kg - exitos * CARGA_KG) / CARGA_KG)
    return filas, huerfanas


def resumir(filas, huerfanas):
    tiempos = [f["tiempo_ms"] for f in filas]
    n = len(filas)
    return {
        "timeout_s": filas[0]["timeout_s"],
        "latencia_media_ms": filas[0]["latencia_media_ms"],
        "n": n,
        "exito_201_pct": round(100 * sum(f["codigo"] == 201 for f in filas) / n, 1),
        "rechazo_503_pct": round(100 * sum(f["codigo"] == 503 for f in filas) / n, 1),
        "otros_codigos": sum(f["codigo"] not in (201, 503) for f in filas),
        "p50_ms": round(statistics.median(tiempos), 1),
        "p95_ms": round(percentil(tiempos, 95), 1),
        "max_ms": round(max(tiempos), 1),
        "reservas_huerfanas": huerfanas,
    }


def guardar_csv(ruta, filas):
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=list(filas[0].keys()))
        escritor.writeheader()
        escritor.writerows(filas)


def guardar_tabla_md(ruta, resumen):
    lineas = [
        "| Timeout API (s) | Latencia media Flota (ms) | Éxito 201 (%) | Rechazo 503 (%) | p50 (ms) | p95 (ms) | Máx (ms) | Reservas huérfanas |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in resumen:
        lineas.append(
            f"| {r['timeout_s']} | {r['latencia_media_ms']} | {r['exito_201_pct']} | {r['rechazo_503_pct']} | "
            f"{r['p50_ms']} | {r['p95_ms']} | {r['max_ms']} | {r['reservas_huerfanas']} de {r['n']} |"
        )
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")


def graficar(ruta, resumen):
    fig, ejes = plt.subplots(1, 3, figsize=(16, 4.8))
    for timeout in TIMEOUTS_S:
        datos = [r for r in resumen if r["timeout_s"] == timeout]
        x = [r["latencia_media_ms"] for r in datos]
        etiqueta = f"timeout {timeout} s" if timeout < 30 else "timeout 30 s (sin timeout)"
        ejes[0].plot(x, [r["p95_ms"] for r in datos], marker="o", label=etiqueta)
        ejes[1].plot(x, [r["rechazo_503_pct"] for r in datos], marker="o", label=etiqueta)
        ejes[2].plot(x, [r["reservas_huerfanas"] for r in datos], marker="o", label=etiqueta)

    ejes[0].set_title("Tiempo de respuesta de la API (p95)")
    ejes[0].set_ylabel("ms")
    ejes[1].set_title("Despachos rechazados con 503")
    ejes[1].set_ylabel("% de las peticiones")
    ejes[2].set_title(f"Reservas huérfanas (de {REPETICIONES})")
    ejes[2].set_ylabel("cantidad")
    for eje in ejes:
        eje.set_xlabel("Latencia media de Flota (ms)")
        eje.grid(alpha=0.3)
    ejes[0].legend()
    fig.tight_layout()
    fig.savefig(ruta, dpi=150)


def main():
    SALIDA.mkdir(exist_ok=True)
    token = esperar_api()
    with httpx.Client(base_url=API, timeout=60) as cliente_http:
        cliente_id = cliente_http.post(
            "/v1/clientes", json={"nombre": "Cliente experimento", "email": f"exp-{uuid.uuid4()}@prueba.cl"},
            headers={"Authorization": f"Bearer {token}"},
        ).json()["id"]

        crudos, resumen = [], []
        try:
            for timeout in TIMEOUTS_S:
                token = fijar_timeout(timeout)
                for latencia in LATENCIAS_MS:
                    filas, huerfanas = ejecutar_combinacion(cliente_http, token, cliente_id, timeout, latencia)
                    crudos.extend(filas)
                    resumen.append(resumir(filas, huerfanas))
                    # Se guarda despues de cada combinacion para no perder datos si el experimento se corta
                    guardar_csv(SALIDA / "resultados_crudos.csv", crudos)
                    guardar_csv(SALIDA / "resumen.csv", resumen)
                    r = resumen[-1]
                    print(
                        f"timeout {timeout:>4} s | latencia {latencia:>4} ms | 201 {r['exito_201_pct']:>5}% | "
                        f"503 {r['rechazo_503_pct']:>5}% | p95 {r['p95_ms']:>7} ms | huerfanas {huerfanas}",
                        flush=True,
                    )
        finally:
            # Deja el sistema como estaba aunque el experimento se corte a la mitad
            quitar_latencia()
            reiniciar_capacidad()
            sql_despachos(f"DELETE FROM despachos WHERE cliente_id = '{cliente_id}'")
            sql_despachos(f"DELETE FROM clientes WHERE id = '{cliente_id}'")
            compose("up", "-d", "api_despachos", env={"GRPC_FLOTA_TIMEOUT": "2"})

    guardar_csv(SALIDA / "resultados_crudos.csv", crudos)
    guardar_csv(SALIDA / "resumen.csv", resumen)
    guardar_tabla_md(SALIDA / "resumen.md", resumen)
    graficar(SALIDA / "grafico.png", resumen)
    print(f"Resultados en {SALIDA}")


if __name__ == "__main__":
    main()
