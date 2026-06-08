"""
Graphique de benchmark amélioré — figure combinée 2 panneaux.

Panneau gauche : barres horizontales (temps + % économisé).
Panneau droit  : timeline Gantt (distribution des fichiers sur les workers).

Usage : python plot_benchmark_clear.py
Prérequis : benchmark_results/benchmark_results.json doit exister
            (lancez benchmark_batch.py d'abord).
"""

import json
import pathlib
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec

# ─── Données ──────────────────────────────────────────────
JSON = pathlib.Path("benchmark_results/benchmark_results.json")
OUT  = pathlib.Path("benchmark_results/benchmark_clear.png")

with open(JSON) as f:
    data = json.load(f)

t_seq  = data["sequential"]["median"]
t_par2 = data["parallel"]["2"]["median"]
t_par4 = data["parallel"]["4"]["median"]

# Temps moyen par fichier pour chaque config (8 fichiers)
N = 8
tpf_seq  = t_seq  / N
tpf_par2 = t_par2 / (N // 2)   # 4 fichiers par worker
tpf_par4 = t_par4 / (N // 4)   # 2 fichiers par worker

# ─── Palette ──────────────────────────────────────────────
C_SEQ  = "#991b1b"
C_P2   = "#1d4ed8"
C_P4   = "#2563eb"
C_BG   = "#f8fafc"
C_GRID = "#e2e8f0"

# ─── Figure ───────────────────────────────────────────────
fig = plt.figure(figsize=(15, 6.5), facecolor="white")
gs  = GridSpec(1, 2, figure=fig, width_ratios=[1, 1.8], wspace=0.08)

ax_bar   = fig.add_subplot(gs[0])
ax_gantt = fig.add_subplot(gs[1])

# ══════════════════════════════════════════════════════════
# PANNEAU GAUCHE — barres horizontales
# ══════════════════════════════════════════════════════════
configs = [
    ("4 workers",  t_par4, C_P4),
    ("2 workers",  t_par2, C_P2),
    ("Séquentiel", t_seq,  C_SEQ),
]

y_pos = [2, 1, 0]
bar_h = 0.52

for y, (lbl, t, c) in zip(y_pos, configs):
    ax_bar.barh(y, t, height=bar_h, color=c, alpha=0.92,
                edgecolor="white", linewidth=1.5, zorder=3)

    # Temps exact à droite de la barre
    ax_bar.text(t + 0.12, y, f"{t:.2f} s",
                va="center", ha="left", fontsize=11.5,
                fontweight="bold", color=c)

    # % économisé à l'intérieur de la barre (sauf séquentiel)
    saving = (t_seq - t) / t_seq * 100
    if saving > 1:
        ax_bar.text(t / 2, y, f"−{saving:.0f} %",
                    va="center", ha="center", fontsize=10.5,
                    color="white", fontweight="bold")

# Ligne de référence séquentielle
ax_bar.axvline(t_seq, color=C_SEQ, linestyle="--",
               alpha=0.25, linewidth=1.5, zorder=2)

ax_bar.set_yticks(y_pos)
ax_bar.set_yticklabels([c[0] for c in configs], fontsize=11.5)
ax_bar.set_xlabel("Temps total pour 8 fichiers (s)", fontsize=10.5)
ax_bar.set_xlim(0, t_seq * 1.28)
ax_bar.set_ylim(-0.55, 2.55)
ax_bar.set_facecolor(C_BG)
ax_bar.spines[["top", "right"]].set_visible(False)
ax_bar.xaxis.grid(True, color=C_GRID, linewidth=1, zorder=0)
ax_bar.set_axisbelow(True)
ax_bar.set_title(
    f"Temps de traitement — 8 fichiers UVFITS\n"
    f"(mapsize 1024 px · CLEAN 5 000 iter · médiane 2 runs)",
    fontsize=10, pad=10
)

# ══════════════════════════════════════════════════════════
# PANNEAU DROIT — timeline Gantt
# ══════════════════════════════════════════════════════════
# Disposition (de bas en haut) :
#   [0]   Séquentiel : 1 ligne
#   [2-3] 2 workers  : 2 lignes
#   [5-8] 4 workers  : 4 lignes

FILE_COLORS = ["#bfdbfe", "#93c5fd", "#60a5fa", "#3b82f6",
               "#2563eb", "#1d4ed8", "#1e40af", "#1e3a8a"]

def draw_gantt_row(ax, y, tpf, n_files, color, row_h=0.55):
    """Trace n_files cases bout-à-bout sur la ligne y."""
    for f in range(n_files):
        ax.barh(y, tpf, left=f * tpf, height=row_h,
                color=color, alpha=0.82,
                edgecolor="white", linewidth=1.2, zorder=3)
        ax.text(f * tpf + tpf / 2, y, str(f + 1),
                ha="center", va="center",
                fontsize=8, color="white", fontweight="bold", zorder=4)


# ── Séquentiel : 1 worker, 8 fichiers en série
GANTT_CONFIGS = [
    # (y_rows_start, n_workers, tpf, color, label_y_center, label)
    (0,   1, tpf_seq,  C_SEQ, 0,   "Séquentiel"),
    (1.6, 2, tpf_par2, C_P2,  2.3, "2 workers"),
    (4.0, 4, tpf_par4, C_P4,  5.5, "4 workers"),
]

ytick_pos, ytick_lbl = [], []

for y_start, n_workers, tpf, color, lbl_y, lbl in GANTT_CONFIGS:
    files_per_worker = N // n_workers
    for w in range(n_workers):
        y = y_start + w
        draw_gantt_row(ax_gantt, y, tpf, files_per_worker, color)
        ytick_pos.append(y)
        ytick_lbl.append(f"W{w + 1}")

    # Label de config à gauche
    ax_gantt.text(-0.35, y_start + (n_workers - 1) / 2, lbl,
                  ha="right", va="center", fontsize=10.5,
                  fontweight="bold", color=color,
                  transform=ax_gantt.get_yaxis_transform())

    # Séparateur horizontal entre configs
    sep_y = y_start + n_workers + 0.15
    ax_gantt.axhline(sep_y, color=C_GRID, linewidth=1.2, zorder=1)

# Lignes de fin verticales colorées
for t_end, color, label in [
    (t_par4, C_P4, f"{t_par4:.2f} s"),
    (t_par2, C_P2, f"{t_par2:.2f} s"),
    (t_seq,  C_SEQ, f"{t_seq:.2f} s"),
]:
    ax_gantt.axvline(t_end, color=color, linestyle="--",
                     linewidth=1.8, alpha=0.6, zorder=2)
    ax_gantt.text(t_end, 7.85, label,
                  ha="center", va="bottom", fontsize=8.5,
                  color=color, fontweight="bold",
                  bbox=dict(boxstyle="round,pad=0.2", fc="white", ec=color, alpha=0.85))

ax_gantt.set_yticks(ytick_pos)
ax_gantt.set_yticklabels(ytick_lbl, fontsize=9)
ax_gantt.set_xlabel("Temps (secondes)", fontsize=10.5)
ax_gantt.set_xlim(-0.05, t_seq + 0.4)
ax_gantt.set_ylim(-0.55, 8.1)
ax_gantt.set_facecolor(C_BG)
ax_gantt.spines[["top", "right"]].set_visible(False)
ax_gantt.xaxis.grid(True, color=C_GRID, linewidth=1, zorder=0)
ax_gantt.set_axisbelow(True)
ax_gantt.set_title(
    "Distribution des 8 fichiers sur les workers\n"
    "(chaque case = 1 fichier traité · numéros = index fichier)",
    fontsize=10, pad=10
)

# ── Titre global ──────────────────────────────────────────
fig.suptitle(
    "DifmapBatchManager — Preuve de parallélisme",
    fontsize=13.5, fontweight="bold", y=1.01
)

plt.savefig(OUT, dpi=150, bbox_inches="tight", facecolor="white")
print(f"Graphique sauvegardé → {OUT}")
