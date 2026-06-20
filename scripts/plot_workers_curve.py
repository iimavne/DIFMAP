"""
Courbe d'évolution des performances en fonction du nombre de workers.

Lit benchmark_results/benchmark_results.json et trace une figure 2 panneaux :
  • Gauche  : temps total vs nombre de workers (avec référence séquentielle)
  • Droite  : speedup mesuré vs speedup idéal (linéaire)

La capacité matérielle réelle de la machine (cœurs physiques / logiques) est
détectée automatiquement et annotée sur les graphiques, afin de situer la zone
au-delà de laquelle ajouter des workers ne rapporte plus de cœur physique.

Usage : python scripts/plot_workers_curve.py
Prérequis : avoir lancé scripts/benchmark_batch.py au moins une fois.
"""

import os
import json
import pathlib
import subprocess

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

JSON = pathlib.Path("benchmark_results/benchmark_results.json")
OUT  = pathlib.Path("benchmark_results/workers_curve.png")


# ─────────────────────────────────────────────────────────
# Détection matérielle
# ─────────────────────────────────────────────────────────
def detect_hardware() -> dict:
    """Retourne cœurs physiques, CPU logiques, threads/cœur et modèle."""
    logical = os.cpu_count() or 1
    physical = logical
    threads_per_core = 1
    model = "CPU inconnu"
    try:
        out = subprocess.check_output(["lscpu"], text=True)
        cores_per_socket = sockets = tpc = None
        for line in out.splitlines():
            low = line.lower()
            val = line.split(":")[-1].strip()
            if "core(s) per socket" in low or "cœur(s) par socket" in low:
                cores_per_socket = int(val)
            elif "socket(s)" in low:
                sockets = int(val)
            elif "thread(s) per core" in low or "thread(s) par cœur" in low:
                tpc = int(val)
            elif "model name" in low or "nom de modèle" in low:
                model = val
        if cores_per_socket and sockets:
            physical = cores_per_socket * sockets
        if tpc:
            threads_per_core = tpc
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    return {
        "logical":  logical,
        "physical": physical,
        "tpc":      threads_per_core,
        "model":    model,
    }


# ─────────────────────────────────────────────────────────
# Chargement des mesures
# ─────────────────────────────────────────────────────────
def load_data():
    with open(JSON) as f:
        data = json.load(f)
    t_seq   = data["sequential"]["median"]
    std_seq = data["sequential"]["std"]
    par     = data["parallel"]
    workers  = sorted(int(w) for w in par)
    times    = [par[str(w)]["median"]  for w in workers]
    speedups = [par[str(w)]["speedup"] for w in workers]
    meta     = data.get("meta", {})
    return t_seq, std_seq, workers, times, speedups, meta


# ─────────────────────────────────────────────────────────
# Couleurs
# ─────────────────────────────────────────────────────────
C_TIME  = "#1d4ed8"
C_SEQ   = "#991b1b"
C_SPEED = "#2563eb"
C_IDEAL = "#9ca3af"
C_PHYS  = "#16a34a"
C_BG    = "#f8fafc"
C_GRID  = "#e2e8f0"


def main():
    if not JSON.exists():
        raise SystemExit(
            f"  {JSON} introuvable — lancez d'abord scripts/benchmark_batch.py"
        )

    hw = detect_hardware()
    t_seq, std_seq, workers, times, speedups, meta = load_data()
    n_files = meta.get("n_files", "?")

    fig, ax_s = plt.subplots(1, 1, figsize=(8, 5.5), facecolor="white")

    # ═════════════════════════════════════════════════════
    # Speedup vs workers
    # ═════════════════════════════════════════════════════
    w_max = max(workers)
    w_ideal = np.linspace(1, w_max, 100)
    ax_s.plot(w_ideal, w_ideal, "--", color=C_IDEAL, linewidth=1.6,
              zorder=2, label="Speedup idéal (linéaire)")

    ax_s.plot(workers, speedups, "o-", color=C_SPEED, linewidth=2.5,
              markersize=9, markerfacecolor="white", markeredgewidth=2.5,
              zorder=4, label="Speedup mesuré")

    for w, sp in zip(workers, speedups):
        ax_s.annotate(f"{sp:.2f}×", xy=(w, sp), xytext=(6, -14),
                      textcoords="offset points", fontsize=9.5,
                      color=C_SPEED, fontweight="bold")

    # Limite des cœurs physiques : au-delà, plus de cœur dédié disponible
    if workers[0] <= hw["physical"] <= w_max:
        ax_s.axvline(hw["physical"], color=C_PHYS, linestyle=":",
                     linewidth=2, alpha=0.85, zorder=3,
                     label=f"{hw['physical']} cœurs physiques")

    ax_s.set_xlabel("Nombre de workers (processus parallèles)", fontsize=11)
    ax_s.set_ylabel("Speedup  (T_séq / T_par)", fontsize=11)
    ax_s.set_title("Accélération vs workers", fontsize=11.5, pad=8)
    # Marque le pic de speedup
    best_i = int(np.argmax(speedups))
    ax_s.annotate(
        f"pic : {speedups[best_i]:.2f}× à {workers[best_i]} workers",
        xy=(workers[best_i], speedups[best_i]),
        xytext=(0, 22), textcoords="offset points", ha="center",
        fontsize=9, color=C_PHYS, fontweight="bold",
        arrowprops=dict(arrowstyle="->", color=C_PHYS, lw=1.3))

    ax_s.set_xticks(workers)
    ax_s.set_xlim(0.5, w_max + 0.5)
    # Échelle Y centrée sur les valeurs mesurées (la courbe idéale sort en haut)
    ax_s.set_ylim(0, max(speedups) * 1.45)
    ax_s.set_facecolor(C_BG)
    ax_s.grid(True, color=C_GRID, linewidth=1, zorder=0)
    ax_s.set_axisbelow(True)
    ax_s.spines[["top", "right"]].set_visible(False)
    ax_s.legend(fontsize=9.5, loc="upper left")

    # ── Titre global avec capacité matérielle ─────────────
    fig.suptitle(
        f"Évolution des performances selon le nombre de workers\n"
        f"{hw['model']}  —  {hw['physical']} cœurs physiques · "
        f"{hw['logical']} CPU logiques ({hw['tpc']} threads/cœur)",
        fontsize=12.5, fontweight="bold", y=1.02
    )

    fig.tight_layout()
    fig.savefig(OUT, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"Graphique sauvegardé → {OUT}")
    print(f"Machine : {hw['model']}")
    print(f"  {hw['physical']} cœurs physiques · {hw['logical']} CPU logiques "
          f"({hw['tpc']} threads/cœur)")


if __name__ == "__main__":
    main()
