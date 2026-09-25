"""
Compara las corridas del experimento del timeout sin y con la mitigacion en Flota
(no hacer commit si la API ya no espera la respuesta).

Uso: python experimentos/timeout/comparar.py
Lee resultados/sin_mitigacion/resumen.csv y resultados/con_mitigacion/resumen.csv
"""
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

RESULTADOS = Path(__file__).resolve().parent / "resultados"


def leer(carpeta):
    with open(RESULTADOS / carpeta / "resumen.csv", encoding="utf-8") as f:
        return {(float(r["timeout_s"]), int(r["latencia_media_ms"])): r for r in csv.DictReader(f)}


def main():
    sin, con = leer("sin_mitigacion"), leer("con_mitigacion")
    # Solo interesan las combinaciones donde hubo rechazos en alguna de las dos corridas
    claves = [k for k in sin if float(sin[k]["rechazo_503_pct"]) > 0 or float(con[k]["rechazo_503_pct"]) > 0]
    etiquetas = [f"{t:g} s / {l} ms" for t, l in claves]

    fig, ejes = plt.subplots(1, 2, figsize=(14, 4.8))
    ancho = 0.38
    posiciones = range(len(claves))

    ejes[0].bar([p - ancho / 2 for p in posiciones], [int(sin[k]["reservas_huerfanas"]) for k in claves], ancho, label="sin mitigación")
    ejes[0].bar([p + ancho / 2 for p in posiciones], [int(con[k]["reservas_huerfanas"]) for k in claves], ancho, label="con mitigación")
    ejes[0].set_title("Reservas huérfanas (de 30)")
    ejes[0].set_ylabel("cantidad")

    ejes[1].bar([p - ancho / 2 for p in posiciones], [float(sin[k]["rechazo_503_pct"]) for k in claves], ancho, label="sin mitigación")
    ejes[1].bar([p + ancho / 2 for p in posiciones], [float(con[k]["rechazo_503_pct"]) for k in claves], ancho, label="con mitigación")
    ejes[1].set_title("Despachos rechazados con 503")
    ejes[1].set_ylabel("% de las peticiones")

    for eje in ejes:
        eje.set_xticks(list(posiciones))
        eje.set_xticklabels(etiquetas, rotation=30, ha="right")
        eje.set_xlabel("Timeout API / latencia media Flota")
        eje.grid(alpha=0.3, axis="y")
        eje.legend()
    fig.tight_layout()
    fig.savefig(RESULTADOS / "comparacion.png", dpi=150)

    lineas = [
        "| Timeout / latencia | 503 sin mitigación | Huérfanas sin mitigación | 503 con mitigación | Huérfanas con mitigación |",
        "|---|---|---|---|---|",
    ]
    for k, etiqueta in zip(claves, etiquetas):
        lineas.append(
            f"| {etiqueta} | {sin[k]['rechazo_503_pct']} % | {sin[k]['reservas_huerfanas']} | "
            f"{con[k]['rechazo_503_pct']} % | {con[k]['reservas_huerfanas']} |"
        )
    total_sin = sum(int(r["reservas_huerfanas"]) for r in sin.values())
    total_con = sum(int(r["reservas_huerfanas"]) for r in con.values())
    lineas.append(f"| **Total (600 despachos)** | | **{total_sin}** | | **{total_con}** |")
    (RESULTADOS / "comparacion.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print("\n".join(lineas))


if __name__ == "__main__":
    main()
