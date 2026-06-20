"""
Benchmark DifmapBatchManager vs traitement séquentiel.

Mesure le temps de traitement d'un pipeline complet (observe + select +
mapsize + invert + clean + restore) sur N fichiers, pour différents nombres
de workers parallèles. Génère 3 graphiques de preuve.

Usage :
    python benchmark_batch.py
"""

import os
import sys
import time
import shutil
import json
import pathlib
import warnings
import numpy as np
import matplotlib

from difmap_wrapper.core.manager import DifmapBatchManager
matplotlib.use("Agg")  # pas de fenêtre — on sauvegarde directement
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from concurrent.futures import ProcessPoolExecutor

# ─────────────────────────────────────────────────────────
# Configuration du benchmark
# ─────────────────────────────────────────────────────────

SOURCE_FILE   = "tests/test_data/0003-067.uvf"   # fichier de référence
N_FILES       = 16               # nombre de copies à traiter
MAPSIZE       = 1024             # taille de la grille (px × px)
CELLSIZE      = 0.1              # taille du pixel en mas
CLEAN_NITER   = 5000             # itérations CLEAN (~1s par fichier)
CLEAN_GAIN    = 0.05
WORKERS_LIST  = [1, 2, 4, 6, 8, 12, 16] # points fins : montée → pic à 8 cœurs → régression
N_REPEATS     = 2                # répétitions pour la médiane
OUTPUT_DIR    = pathlib.Path("benchmark_results")
TMPDIR        = pathlib.Path("benchmark_tmp")

# ─────────────────────────────────────────────────────────
# Fonction worker  pour traiter un fichier dans un processus séparé
# ─────────────────────────────────────────────────────────

def _process_one(filepath: str) -> dict:
    """
    Pipeline complet sur un fichier UVFITS.
    Exécuté dans un processus OS séparé par DifmapBatchManager.
    Chaque processus a sa propre instance DifmapSession et ses propres
    pointeurs globaux C (vlbob, vlbmap) — aucune collision mémoire.
    """
    import time as _time
    import os as _os
    t0 = _time.perf_counter()

    # Redirige stdout/stderr vers /dev/null pour supprimer les logs C
    devnull = _os.open(_os.devnull, _os.O_WRONLY)
    old_stdout, old_stderr = _os.dup(1), _os.dup(2)
    _os.dup2(devnull, 1)
    _os.dup2(devnull, 2)
    try:
        from difmap_wrapper import DifmapSession
        with DifmapSession() as session:
            session.observe(filepath)
            session.obs.select(pol="RR")
            session.imager.mapsize(MAPSIZE, CELLSIZE)
            session.imager.invert()
            session.imager.clean(CLEAN_NITER, CLEAN_GAIN, 0.0)
            session.imager.restore()
    finally:
        _os.dup2(old_stdout, 1)
        _os.dup2(old_stderr, 2)
        _os.close(devnull)
        _os.close(old_stdout)
        _os.close(old_stderr)

    elapsed = _time.perf_counter() - t0
    return {"file": os.path.basename(filepath), "elapsed": elapsed}


# ─────────────────────────────────────────────────────────
# Traitement séquentiel de référence
# ─────────────────────────────────────────────────────────

def _run_sequential(files: list[str]) -> float:
    """Traite les fichiers un à un et retourne le temps total."""
    t0 = time.perf_counter()
    for f in files:
        _process_one(f)
    return time.perf_counter() - t0


# ─────────────────────────────────────────────────────────
# Traitement parallèle via DifmapBatchManager
# ─────────────────────────────────────────────────────────

def _run_parallel(files: list[str], n_workers: int) -> float:
    """Traite les fichiers en parallèle et retourne le temps total."""
    from difmap_wrapper.core.manager import DifmapBatchManager
    mgr = DifmapBatchManager(max_workers=n_workers)
    t0 = time.perf_counter()
    mgr.run_batch(_process_one, files)
    return time.perf_counter() - t0


# ─────────────────────────────────────────────────────────
# Préparation des fichiers de test
# ─────────────────────────────────────────────────────────

def setup_test_files() -> list[str]:
    TMPDIR.mkdir(exist_ok=True)
    files = []
    for i in range(N_FILES):
        dst = TMPDIR / f"source_{i:02d}.uvf"
        if not dst.exists():
            shutil.copy(SOURCE_FILE, dst)
        files.append(str(dst))
    print(f"  {N_FILES} fichiers prêts dans {TMPDIR}/")
    return files


def cleanup_test_files():
    if TMPDIR.exists():
        shutil.rmtree(TMPDIR)


# ─────────────────────────────────────────────────────────
# Collecte des mesures
# ─────────────────────────────────────────────────────────

def collect_measurements(files: list[str]) -> dict:
    results = {}

    print(f"\n{'='*55}")
    print(f"  Pipeline : mapsize={MAPSIZE}px, CLEAN {CLEAN_NITER} iter")
    print(f"  Fichiers : {N_FILES}  |  Répétitions : {N_REPEATS}")
    print(f"{'='*55}")

    # Séquentiel
    seq_times = []
    print(f"\n[1/1] Séquentiel ({N_FILES} fichiers × {N_REPEATS} répétitions)...")
    for r in range(N_REPEATS):
        t = _run_sequential(files)
        seq_times.append(t)
        print(f"      run {r+1}/{N_REPEATS} : {t:.2f}s")
    results["sequential"] = {
        "times": seq_times,
        
        "median": float(np.median(seq_times)),
        "std":    float(np.std(seq_times)),
    }
    t_seq = results["sequential"]["median"]
    print(f"  → médiane = {t_seq:.2f}s")

    # Parallèle pour chaque nombre de workers
    results["parallel"] = {}
    for n_w in WORKERS_LIST:
        par_times = []
        print(f"\n[W={n_w}] Parallèle {n_w} worker(s) × {N_REPEATS} répétitions...")
        for r in range(N_REPEATS):
            t = _run_parallel(files, n_w)
            par_times.append(t)
            speedup = t_seq / t
            print(f"      run {r+1}/{N_REPEATS} : {t:.2f}s  (speedup {speedup:.2f}×)")
        median_t = float(np.median(par_times))
        results["parallel"][n_w] = {
            "times":   par_times,
            "median":  median_t,
            "std":     float(np.std(par_times)),
            "speedup": t_seq / median_t,
        }
        print(f"  → médiane = {median_t:.2f}s  |  speedup = {t_seq/median_t:.2f}×")

    return results


# ─────────────────────────────────────────────────────────
# Graphiques
# ─────────────────────────────────────────────────────────

COLORS = {
    "seq":      "#991b1b",
    "par1":     "#1e3a8a",
    "par2":     "#1d4ed8",
    "par4":     "#2563eb",
    "par8":     "#60a5fa",
    "ideal":    "#d1d5db",
    "accent":   "#339933",
}

def _worker_color(n: int) -> str:
    return {1: COLORS["par1"], 2: COLORS["par2"],
            4: COLORS["par4"], 8: COLORS["par8"]}.get(n, "#555")


def plot_time_comparison(results: dict, out: pathlib.Path):
    """Graphique 1 — Temps total séquentiel vs parallèle."""
    fig, ax = plt.subplots(figsize=(9, 5))

    t_seq = results["sequential"]["median"]
    e_seq = results["sequential"]["std"]

    workers = sorted(results["parallel"].keys())
    times   = [results["parallel"][w]["median"] for w in workers]
    errors  = [results["parallel"][w]["std"]    for w in workers]
    speedups= [results["parallel"][w]["speedup"] for w in workers]

    labels = ["Séquentiel"] + [f"Parallèle\n{w} worker{'s' if w>1 else ''}" for w in workers]
    vals   = [t_seq] + times
    errs   = [e_seq] + errors
    clrs   = [COLORS["seq"]] + [_worker_color(w) for w in workers]

    bars = ax.bar(labels, vals, color=clrs, width=0.55, zorder=3,
                  edgecolor="white", linewidth=0.8)
    ax.errorbar(labels, vals, yerr=errs, fmt="none", color="#333",
                capsize=5, linewidth=1.5, zorder=4)

    # Annotation du speedup sur chaque barre parallèle
    for i, (bar, sp) in enumerate(zip(bars[1:], speedups), 1):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + max(errs) * 0.5,
                f"{sp:.2f}×", ha="center", va="bottom",
                fontsize=11, fontweight="bold", color=COLORS["accent"])

    ax.set_ylabel("Temps total (secondes)", fontsize=12)
    ax.set_title(
        f"Temps de traitement — {N_FILES} fichiers UVFITS\n"
        f"(pipeline : mapsize {MAPSIZE}px, CLEAN {CLEAN_NITER} iter, "
        f"médiane sur {N_REPEATS} runs)",
        fontsize=11
    )
    ax.set_ylim(0, t_seq * 1.25)
    ax.yaxis.grid(True, linestyle="--", alpha=0.4, zorder=0)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)

    fig.tight_layout()
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Graphique 1 → {out}")


def plot_speedup_curve(results: dict, out: pathlib.Path):
    """Graphique 2 — Courbe de speedup mesuré vs speedup idéal."""
    fig, ax = plt.subplots(figsize=(7, 5))

    workers  = sorted(results["parallel"].keys())
    speedups = [results["parallel"][w]["speedup"] for w in workers]
    errors   = [results["parallel"][w]["std"] / results["sequential"]["median"]
                for w in workers]

    # Speedup idéal (linéaire)
    w_ideal = np.linspace(1, max(workers), 100)
    ax.plot(w_ideal, w_ideal, "--", color=COLORS["ideal"], linewidth=1.5,
            label="Speedup idéal (linéaire)", zorder=2)

    # Speedup mesuré
    ax.plot(workers, speedups, "o-", color=COLORS["par4"], linewidth=2.5,
            markersize=9, markerfacecolor="white", markeredgewidth=2.5,
            label="Speedup mesuré", zorder=3)
    ax.errorbar(workers, speedups, yerr=errors, fmt="none",
                color=COLORS["par4"], capsize=5, linewidth=1.5, zorder=4)

    # Annotations
    for w, sp in zip(workers, speedups):
        ax.annotate(f"{sp:.2f}×",
                    xy=(w, sp), xytext=(5, 8), textcoords="offset points",
                    fontsize=10, color=COLORS["par4"], fontweight="bold")

    ax.set_xlabel("Nombre de workers (processus parallèles)", fontsize=12)
    ax.set_ylabel("Speedup  (T_séq / T_par)", fontsize=12)
    ax.set_title(
        f"Courbe de speedup — DifmapBatchManager\n"
        f"({N_FILES} fichiers UVFITS, machine {os.cpu_count()} cœurs)",
        fontsize=11
    )
    ax.set_xticks(workers)
    ax.set_xlim(0.5, max(workers) + 0.5)
    ax.set_ylim(0, max(workers) * 1.15)
    ax.legend(fontsize=10)
    ax.yaxis.grid(True, linestyle="--", alpha=0.4, zorder=0)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)

    fig.tight_layout()
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Graphique 2 → {out}")


def plot_per_file_distribution(files: list[str], out: pathlib.Path):
    """
    Graphique 3 — Distribution des temps par fichier en parallèle (8 workers).
    Montre que chaque processus traite son fichier indépendamment.
    """
    from difmap_wrapper.core.manager import DifmapBatchManager

    print(f"\n  Collecte distribution par fichier (8 workers)...")
    mgr = DifmapBatchManager(max_workers=min(8, len(files)))
    results_detail = mgr.run_batch(_process_one, files)

    fig, ax = plt.subplots(figsize=(10, 4))

    file_labels = [r["file"].replace(".uvf", "") for r in results_detail]
    file_times  = [r["elapsed"] for r in results_detail]

    colors = [_worker_color(8)] * len(file_times)
    bars = ax.barh(range(len(file_labels)), file_times, color=colors,
                   edgecolor="white", linewidth=0.5, height=0.65)

    ax.set_yticks(range(len(file_labels)))
    ax.set_yticklabels(file_labels, fontsize=8)
    ax.set_xlabel("Temps de traitement par fichier (secondes)", fontsize=11)
    ax.set_title(
        f"Distribution des temps par fichier — exécution parallèle (8 workers)\n"
        f"Chaque fichier est traité dans un processus OS isolé",
        fontsize=11
    )

    mean_t = np.mean(file_times)
    ax.axvline(mean_t, color=COLORS["seq"], linewidth=1.8, linestyle="--",
               label=f"Moyenne = {mean_t:.2f}s")
    ax.legend(fontsize=10)

    for bar, t in zip(bars, file_times):
        ax.text(t + 0.02, bar.get_y() + bar.get_height() / 2,
                f"{t:.2f}s", va="center", fontsize=8)

    ax.xaxis.grid(True, linestyle="--", alpha=0.4, zorder=0)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)

    fig.tight_layout()
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Graphique 3 → {out}")


# ─────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────

def main():
    print("\n" + "=" * 55)
    print("  Benchmark DifmapBatchManager")
    print("=" * 55)

    OUTPUT_DIR.mkdir(exist_ok=True)

    print("\n[Setup] Préparation des fichiers de test...")
    files = setup_test_files()

    print("\n[Mesures] Démarrage des benchmarks...")
    results = collect_measurements(files)

    # Métadonnées du run (utiles pour les graphiques)
    results["meta"] = {
        "n_files":     N_FILES,
        "mapsize":     MAPSIZE,
        "clean_niter": CLEAN_NITER,
        "n_repeats":   N_REPEATS,
        "cpu_count":   os.cpu_count(),
    }

    # Sauvegarde JSON des résultats bruts
    json_path = OUTPUT_DIR / "benchmark_results.json"
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n  Résultats bruts → {json_path}")

    print("\n[Graphiques] Génération...")
    plot_time_comparison(results, OUTPUT_DIR / "1_time_comparison.png")
    plot_speedup_curve(  results, OUTPUT_DIR / "2_speedup_curve.png")
    # graphique 3 optionnel — décommenter si la machine le supporte
    # plot_per_file_distribution(files, OUTPUT_DIR / "3_per_file_distribution.png")

    # Résumé terminal
    t_seq = results["sequential"]["median"]
    print(f"\n{'='*55}")
    print(f"  RÉSUMÉ BENCHMARK")
    print(f"{'='*55}")
    print(f"  Séquentiel ({N_FILES} fichiers) : {t_seq:.2f}s")
    for w in sorted(results["parallel"].keys()):
        d = results["parallel"][w]
        print(f"  Parallèle {w:2d} workers       : {d['median']:.2f}s  "
              f"(speedup {d['speedup']:.2f}×)")
    print(f"\n  Graphiques dans : {OUTPUT_DIR}/")
    print("=" * 55 + "\n")

    print("[Cleanup] Suppression des fichiers temporaires...")
    cleanup_test_files()
    print("  Done.\n")


if __name__ == "__main__":
    main()

manager = DifmapBatchManager(max_workers=4)
files   = setup_test_files()           # 8 copies du fichier de référence
results = manager.run_batch(_process_one, files)