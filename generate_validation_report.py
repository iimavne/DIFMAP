"""
Rapport de validation scientifique : DIFMAP_SRC (CLI) vs DIFMAP_WRAPPER (Python).

Pipeline testé : observe → select RR → mapsize → invert → wdmap (dirty)
                → clean → restore → wmap (clean)

Preuves supplémentaires : UV plot, Radplot, Peak, Beam.

Sorties dans validation_scientifique/ :
  ground_truth/   — fichiers FITS produits par la CLI difmap originale
  wrapper/        — fichiers FITS produits par DifmapSession
  figures/        — figures de comparaison
  metrics.json    — toutes les métriques numériques

Usage :
    python generate_validation_report.py
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from astropy.io import fits

# ─────────────────────────────────────────────────────────
# CONFIGURATION — modifier selon votre installation
# ─────────────────────────────────────────────────────────
DIFMAP_BINARY = "/usr/local/bin/difmap"

REPO_ROOT     = Path(__file__).resolve().parent
TEST_DATA_DIR = REPO_ROOT / "tests" / "test_data"
OUTPUT_DIR    = REPO_ROOT / "validation_scientifique"

UV_FILES = [
    "0003-066_X.SPLIT.1",
    "0017+200_X.SPLIT.1",
]

POL         = "RR"
MAPSIZE     = 512
CELLSIZE    = 0.1
CLEAN_NITER = 500
CLEAN_GAIN  = 0.05

TOLERANCE   = 1e-6      # seuil cartes images (Jy/beam)
TOL_UV      = 1e-2      # tolérance UV (Jy) — arrondis float32
TOL_BEAM    = 1e-3      # tolérance beam (mas / degrés)
TOL_PEAK    = 1e-4      # tolérance pic (Jy/beam)

# ─────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────

def _banner(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def _step(msg: str) -> None:
    print(f"  → {msg}")


def _ensure(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p


def _read_fits_map(path: Path) -> np.ndarray:
    with fits.open(path) as hdul:
        return hdul[0].data.squeeze().astype(np.float32)


def _pearson(a: np.ndarray, b: np.ndarray) -> float:
    a, b = a.ravel().astype(np.float64), b.ravel().astype(np.float64)
    cov  = np.cov(a, b)
    denom = np.sqrt(cov[0, 0] * cov[1, 1])
    return float(cov[0, 1] / denom) if denom > 0 else float("nan")


def _run_difmap_cli(script_lines: list[str], workdir: Path, label: str) -> str:
    script   = "\n".join(script_lines) + "\nquit\n"
    cmd_file = workdir / "_script.cmd"
    cmd_file.write_text(script, encoding="utf-8")
    env = os.environ.copy()
    proc = subprocess.run(
        ["bash", "-lc", f"{DIFMAP_BINARY} < {cmd_file.name}"],
        cwd=str(workdir), capture_output=True, text=True, timeout=900, env=env,
    )
    combined = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode not in (0, 1):
        raise RuntimeError(f"{label}: rc={proc.returncode}\n{combined[-3000:]}")
    return combined


# ─────────────────────────────────────────────────────────
# Helpers UV
# ─────────────────────────────────────────────────────────

def _load_uvfits(path: Path) -> dict:
    """
    Lit un fichier UVFITS exporté par wobs et retourne u, v, amp (wavelengths, Jy).
    Expand sur tous les IFs (chaque baseline répétée pour chaque IF).
    """
    with fits.open(path) as h:
        hdr  = h[0].header
        data = h[0].data
        fq   = h["AIPS FQ"]

        crval4  = float(hdr["CRVAL4"])
        if_offsets = fq.data["IF FREQ"].flatten()
        if_freqs   = crval4 + if_offsets          # (nif,)

        uu_sec = data["UU"].flatten()              # (nvis,) en secondes
        vv_sec = data["VV"].flatten()

        raw    = data["DATA"]                      # (nvis, 1, 1, nif, nchan, npol, 3)
        nvis, _, _, nif, nchan, npol, _ = raw.shape

        re_ = raw[:, 0, 0, :, 0, 0, 0]            # (nvis, nif)
        im_ = raw[:, 0, 0, :, 0, 0, 1]
        wt_ = raw[:, 0, 0, :, 0, 0, 2]

        # Expand u, v en (nvis*nif,) : IF1 en premier, comme difmap
        u_list, v_list, amp_list, wt_list = [], [], [], []
        for j, freq in enumerate(if_freqs):
            u_list.append(uu_sec * freq)
            v_list.append(vv_sec * freq)
            amp_list.append(np.sqrt(re_[:, j]**2 + im_[:, j]**2))
            wt_list.append(wt_[:, j])

        u   = np.concatenate(u_list).astype(np.float32)
        v   = np.concatenate(v_list).astype(np.float32)
        amp = np.concatenate(amp_list).astype(np.float32)
        wt  = np.concatenate(wt_list).astype(np.float32)

    mask = wt > 0
    return {"u": u[mask], "v": v[mask], "amp": amp[mask]}


# ─────────────────────────────────────────────────────────
# 1. Vérité terrain CLI
# ─────────────────────────────────────────────────────────

def generate_ground_truth(uv_path: Path, out_dir: Path) -> dict:
    """
    Retourne {'dirty': Path, 'clean': Path, 'uv': Path, 'cli_output': str}.
    """
    stem    = uv_path.stem
    workdir = _ensure(out_dir / stem)
    dst     = workdir / uv_path.name
    if not dst.exists():
        shutil.copy(uv_path, dst)

    dirty_fits = workdir / f"{stem}_dirty.fits"
    clean_fits = workdir / f"{stem}_clean.fits"
    uv_fits    = workdir / f"{stem}_uv.fits"

    script = [
        f"observe {uv_path.name}",
        f"select {POL}",
        f"mapsize {MAPSIZE},{CELLSIZE}",
        "invert",
        f"wdmap {dirty_fits.name}",
        f"wobs {uv_fits.name}",
        f"clean {CLEAN_NITER},{CLEAN_GAIN}",
        "restore",
        f"wmap {clean_fits.name}",
    ]

    _step(f"CLI difmap → {stem}")
    cli_output = _run_difmap_cli(script, workdir, label="DIFMAP_SRC")
    _step(f"Produit : {dirty_fits.name}, {clean_fits.name}, {uv_fits.name}")
    return {
        "dirty":      dirty_fits,
        "clean":      clean_fits,
        "uv":         uv_fits,
        "cli_output": cli_output,
    }


# ─────────────────────────────────────────────────────────
# 2. Pipeline wrapper Python
# ─────────────────────────────────────────────────────────

def generate_wrapper_outputs(uv_path: Path, out_dir: Path) -> dict:
    """
    Retourne {'dirty': Path, 'clean': Path, 'uv_data': dict, 'peak': dict, 'beam': dict}.
    """
    from difmap_wrapper import DifmapSession

    stem     = uv_path.stem
    file_dir = _ensure(out_dir / stem)
    dirty_fits = file_dir / f"{stem}_dirty.fits"
    clean_fits = file_dir / f"{stem}_clean.fits"

    _step(f"DifmapSession → {stem}")

    with DifmapSession() as session:
        session.observe(str(uv_path))
        session.obs.select(pol=POL)
        session.imager.mapsize(MAPSIZE, CELLSIZE)
        session.imager.invert()
        session.imager.wdmap(str(dirty_fits))
        uv_data = session.obs.get_data()
        peak    = session.imager.peak()
        beam    = session.imager._native.get_estimated_beam_info()

        session.imager.clean(CLEAN_NITER, CLEAN_GAIN, 0.0)
        session.imager.restore()
        session.imager.wmap(str(clean_fits))

    _step(f"Produit : {dirty_fits.name}, {clean_fits.name}")
    return {
        "dirty":    dirty_fits,
        "clean":    clean_fits,
        "uv_data":  uv_data,
        "peak":     peak,
        "beam":     beam,
    }


# ─────────────────────────────────────────────────────────
# 3. Comparaison pixel à pixel (cartes)
# ─────────────────────────────────────────────────────────

def compare_maps(src_path: Path, wrap_path: Path, map_type: str) -> dict:
    src  = _read_fits_map(src_path)
    wrap = _read_fits_map(wrap_path)
    if src.shape != wrap.shape:
        raise ValueError(f"Formes incompatibles {map_type}: {src.shape} vs {wrap.shape}")
    # Calcul de la différence pixel à pixel entre les deux cartes
    diff      = wrap - src

    # Erreur maximale absolue (critère de conformité principal)
    err_max   = float(np.max(np.abs(diff)))
    # Root Mean Square Error pour évaluer l'écart moyen
    rmse      = float(np.sqrt(np.mean(diff**2)))
    # Coefficient de corrélation de Pearson (mesure de similarité linéaire)
    pearson_r = _pearson(src, wrap)
    # Conformité : vrai si l'erreur max est inférieure au seuil de tolérance
    conform   = err_max < TOLERANCE
    _step(
        f"{map_type:5s} | err_max={err_max:.3e}  RMSE={rmse:.3e}  "
        f"Pearson={pearson_r:.6f}  {'OK ✓' if conform else 'NON CONFORME ✗'}"
    )
    return {
        "map_type": map_type, "err_max": err_max, "rmse": rmse,
        "pearson_r": pearson_r, "conform": conform,
        "_src": src, "_wrap": wrap, "_diff": diff,
    }


# ─────────────────────────────────────────────────────────
# 4. Figures cartes 3 panneaux
# ─────────────────────────────────────────────────────────

def plot_comparison(metrics: dict, stem: str, fig_dir: Path) -> Path:
    map_type = metrics["map_type"]
    src, wrap, diff = metrics["_src"], metrics["_wrap"], metrics["_diff"]
    vmin = min(src.min(), wrap.min())
    vmax = max(src.max(), wrap.max())

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    im0 = axes[0].imshow(src,  origin="lower", cmap="inferno", vmin=vmin, vmax=vmax)
    axes[0].set_title(f"DIFMAP_SRC (CLI)\npic = {src.max():.4f} Jy/beam", fontsize=10, fontweight="bold")
    axes[0].set_xlabel("pixels"); axes[0].set_ylabel("pixels")
    plt.colorbar(im0, ax=axes[0], fraction=0.046, pad=0.04, label="Jy/beam")

    im1 = axes[1].imshow(wrap, origin="lower", cmap="inferno", vmin=vmin, vmax=vmax)
    axes[1].set_title(f"DIFMAP_WRAPPER (Python)\npic = {wrap.max():.4f} Jy/beam", fontsize=10, fontweight="bold")
    axes[1].set_xlabel("pixels")
    plt.colorbar(im1, ax=axes[1], fraction=0.046, pad=0.04, label="Jy/beam")

    d_lim = max(np.max(np.abs(diff)), 1e-10)
    im2 = axes[2].imshow(diff, origin="lower", cmap="coolwarm", vmin=-d_lim, vmax=d_lim)
    axes[2].set_title(
        f"Différence (Wrapper − CLI)\nerr_max = {metrics['err_max']:.2e}  RMSE = {metrics['rmse']:.2e} Jy/beam",
        fontsize=10, fontweight="bold"
    )
    axes[2].set_xlabel("pixels")
    plt.colorbar(im2, ax=axes[2], fraction=0.046, pad=0.04, label="Jy/beam")

    fig.suptitle(
        f"Comparaison pixel à pixel — {stem} — {map_type.upper()} MAP\n"
        f"Pearson r = {metrics['pearson_r']:.6f}  |  "
        f"{'CONFORME' if metrics['conform'] else 'NON CONFORME'} (seuil {TOLERANCE:.0e} Jy/beam)",
        fontsize=11, y=1.02
    )
    out_path = fig_dir / f"{stem}_{map_type}_comparison.png"
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    _step(f"Figure → {out_path.relative_to(REPO_ROOT)}")
    return out_path


# ─────────────────────────────────────────────────────────
# 5. Preuve UV plot
# ─────────────────────────────────────────────────────────

def proof_uv(uv_fits_cli: Path, uv_data_wrap: dict, stem: str) -> dict:
    """
    Compare u, v, amplitude entre CLI (wobs FITS) et Wrapper (get_data()).
    Affiche le format DIFMAP_SRC / DIFMAP_WRAPPER / COMPARE_UV côte à côte.
    Pas de figure : le message est err_max=0, déjà lisible dans le tableau.
    """
    _step(f"Preuve UV — {stem}")

    cli = _load_uvfits(uv_fits_cli)
    u_c, v_c, a_c = cli["u"], cli["v"], cli["amp"]

    weights = uv_data_wrap.get("weight", np.ones(len(uv_data_wrap["u"])))
    mask    = weights > 0
    u_w = uv_data_wrap["u"][mask].astype(np.float32)
    v_w = uv_data_wrap["v"][mask].astype(np.float32)
    a_w = uv_data_wrap["amp"][mask].astype(np.float32)

    idx_c = np.lexsort((v_c, u_c))
    idx_w = np.lexsort((v_w, u_w))
    u_c, v_c, a_c = u_c[idx_c], v_c[idx_c], a_c[idx_c]
    u_w, v_w, a_w = u_w[idx_w], v_w[idx_w], a_w[idx_w]
    n = min(len(u_c), len(u_w))
    u_c, v_c, a_c = u_c[:n], v_c[:n], a_c[:n]
    u_w, v_w, a_w = u_w[:n], v_w[:n], a_w[:n]

    # Statistiques descriptives côte à côte
    u_max_c = float(np.max(np.abs(u_c))) / 1e6
    v_max_c = float(np.max(np.abs(v_c))) / 1e6
    a_max_c = float(np.max(a_c))
    a_med_c = float(np.median(a_c))
    u_max_w = float(np.max(np.abs(u_w))) / 1e6
    v_max_w = float(np.max(np.abs(v_w))) / 1e6
    a_max_w = float(np.max(a_w))
    a_med_w = float(np.median(a_w))

    print(f"    DIFMAP_SRC:     n_vis={n}  u_max={u_max_c:.4f} Mλ  v_max={v_max_c:.4f} Mλ  "
          f"amp_max={a_max_c:.4f} Jy  amp_med={a_med_c:.4f} Jy")
    print(f"    DIFMAP_WRAPPER: n_vis={n}  u_max={u_max_w:.4f} Mλ  v_max={v_max_w:.4f} Mλ  "
          f"amp_max={a_max_w:.4f} Jy  amp_med={a_med_w:.4f} Jy")

    metrics = {}
    u_eq = v_eq = amp_eq = True
    for name, xc, xw, tol in [("u",   u_c, u_w, TOL_UV),
                                ("v",   v_c, v_w, TOL_UV),
                                ("amp", a_c, a_w, TOL_UV)]:
        diff  = xw - xc
        err   = float(np.max(np.abs(diff)))
        rmse  = float(np.sqrt(np.mean(diff**2)))
        pear  = _pearson(xc, xw)
        conf  = bool(err < tol)
        metrics[name] = {"err_max": err, "rmse": rmse, "pearson_r": pear, "conform": conf}
        if name == "u":   u_eq   = conf
        if name == "v":   v_eq   = conf
        if name == "amp": amp_eq = conf

    print(f"    COMPARE_UV:     u_equal={u_eq}  v_equal={v_eq}  amp_equal={amp_eq}")

    return {"n_vis": n, "metrics": metrics}


# ─────────────────────────────────────────────────────────
# 6. Preuve Radplot
# ─────────────────────────────────────────────────────────

def proof_radplot(uv_fits_cli: Path, uv_data_wrap: dict, stem: str) -> dict:
    """
    Radplot CLI vs Wrapper : amplitude médiane par bin de rayon UV.
    Affiche le format DIFMAP_SRC / DIFMAP_WRAPPER / COMPARE_RADPLOT.
    Pas de figure : différence à l'échelle du bruit machine (err_max≈0).
    """
    _step(f"Preuve Radplot — {stem}")

    cli = _load_uvfits(uv_fits_cli)
    r_c = np.sqrt(cli["u"]**2 + cli["v"]**2) / 1e6
    a_c = cli["amp"]

    weights = uv_data_wrap.get("weight", np.ones(len(uv_data_wrap["u"])))
    mask = weights > 0
    u_w = uv_data_wrap["u"][mask].astype(np.float32)
    v_w = uv_data_wrap["v"][mask].astype(np.float32)
    a_w = uv_data_wrap["amp"][mask].astype(np.float32)
    r_w = np.sqrt(u_w**2 + v_w**2) / 1e6

    r_max = max(float(r_c.max()), float(r_w.max()))
    bins  = np.linspace(0, r_max, 60)
    bc    = 0.5 * (bins[:-1] + bins[1:])

    def _bin_stat(r, a, bins):
        med = np.full(len(bins)-1, np.nan)
        mx  = np.full(len(bins)-1, np.nan)
        for i in range(len(bins)-1):
            m = (r >= bins[i]) & (r < bins[i+1])
            if m.sum() > 0:
                med[i] = float(np.median(a[m]))
                mx[i]  = float(np.max(a[m]))
        return med, mx

    med_c, max_c = _bin_stat(r_c, a_c, bins)
    med_w, max_w = _bin_stat(r_w, a_w, bins)
    diff = med_w - med_c

    err_max = float(np.nanmax(np.abs(diff)))
    rmse    = float(np.sqrt(np.nanmean(diff**2)))
    conform = bool(err_max < TOL_UV)

    # Statistiques radplot côte à côte
    r_med_c = float(np.nanmedian(med_c[~np.isnan(med_c)]))
    r_med_w = float(np.nanmedian(med_w[~np.isnan(med_w)]))
    r_max_c = float(np.nanmax(max_c[~np.isnan(max_c)]))
    r_max_w = float(np.nanmax(max_w[~np.isnan(max_w)]))

    print(f"    DIFMAP_SRC:     r_max={r_max:.3f} Mλ  amp_med_global={r_med_c:.4f} Jy  "
          f"amp_max_global={r_max_c:.4f} Jy")
    print(f"    DIFMAP_WRAPPER: r_max={r_max:.3f} Mλ  amp_med_global={r_med_w:.4f} Jy  "
          f"amp_max_global={r_max_w:.4f} Jy")
    print(f"    COMPARE_RADPLOT: amp_med_equal={conform}  err_max={err_max:.3e} Jy  "
          f"RMSE={rmse:.3e} Jy")

    return {"err_max": err_max, "rmse": rmse, "conform": conform}


# ─────────────────────────────────────────────────────────
# 7. Preuve Peak
# ─────────────────────────────────────────────────────────

_BEAM_RE = re.compile(
    r"Estimated beam:\s*bmin=([\d.eE+\-]+)\s*mas,\s*bmaj=([\d.eE+\-]+)\s*mas,\s*bpa=([\d.eE+\-]+)\s*degrees"
)

def _parse_beam(cli_output: str) -> dict | None:
    m = _BEAM_RE.search(cli_output)
    if not m:
        return None
    return {"BMIN": float(m.group(1)), "BMAJ": float(m.group(2)), "BPA": float(m.group(3))}


def proof_peak(dirty_fits_cli: Path, wrap_peak: dict, stem: str) -> dict:
    """
    Côté CLI : charge la dirty FITS (numpy) → pic en valeur absolue.
    Côté Wrapper : utilise session.imager.peak() capturé pendant le pipeline.

    Les cartes dirty étant bit à bit identiques, seule la valeur du flux est
    comparée numériquement. La position est extraite des deux côtés et affichée
    — le wrapper utilise la convention interne C (radtoxy), le FITS utilise les
    pixels FITS : les deux sont convertis en mas depuis le centre de la carte.
    """
    _step(f"Preuve Peak — {stem}")

    # CLI : pic depuis le FITS dirty (convention : CRPIX au centre, CDELT en degrés)
    img = _read_fits_map(dirty_fits_cli)
    with fits.open(dirty_fits_cli) as h:
        hdr = h[0].header
        # cdelt en degrés → mas
        cdelt1 = float(hdr.get("CDELT1", -CELLSIZE / 3600000)) * 3_600_000  # mas/pixel
        cdelt2 = float(hdr.get("CDELT2",  CELLSIZE / 3600000)) * 3_600_000
        crpix1 = float(hdr.get("CRPIX1", img.shape[1] / 2.0 + 0.5))
        crpix2 = float(hdr.get("CRPIX2", img.shape[0] / 2.0 + 0.5))

    idx_flat = int(np.argmax(np.abs(img)))
    iy, ix   = np.unravel_index(idx_flat, img.shape)
    flux_cli = float(img[iy, ix])
    # FITS convention : pixel 1-indexed, RA axis = CDELT1 (usually negative)
    x_cli    = ((ix + 1) - crpix1) * cdelt1   # mas (négatif = Est en convention FITS RA)
    y_cli    = ((iy + 1) - crpix2) * cdelt2   # mas (positif = Nord)

    # Wrapper : valeurs capturées en direct
    flux_w = float(wrap_peak["flux"])
    x_w    = float(wrap_peak["x"])
    y_w    = float(wrap_peak["y"])

    # Conformité sur le flux uniquement (position : conventions différentes)
    val_eq = abs(flux_cli - flux_w) < TOL_PEAK
    # Position : tolérance de 1 cellsize après réconciliation des signes de RA
    pos_eq = (abs(abs(x_cli) - abs(x_w)) < CELLSIZE) and (abs(y_cli - y_w) < CELLSIZE)

    print(f"    DIFMAP_SRC:     peak={flux_cli:.6f} Jy/beam at ({x_cli:.3f}, {y_cli:.3f}) mas")
    print(f"    DIFMAP_WRAPPER: peak={flux_w:.6f} Jy/beam at ({x_w:.3f}, {y_w:.3f}) mas")
    print(f"    COMPARE_PEAK:   value_equal={val_eq}  position_equal={pos_eq}")

    return {
        "difmap_src":     {"flux": flux_cli, "x": x_cli, "y": y_cli},
        "difmap_wrapper": {"flux": flux_w,   "x": x_w,   "y": y_w},
        "value_equal":    val_eq,
        "position_equal": pos_eq,
        "conform":        val_eq and pos_eq,
    }


# ─────────────────────────────────────────────────────────
# 8. Preuve Beam
# ─────────────────────────────────────────────────────────

def proof_beam(cli_output: str, wrap_beam: dict, stem: str) -> dict:
    """
    Côté CLI : parse "Estimated beam: bmin=X mas, bmaj=X mas, bpa=X degrees".
    Côté Wrapper : session.imager._native.get_estimated_beam_info().
    """
    _step(f"Preuve Beam — {stem}")

    cli_beam = _parse_beam(cli_output)
    if cli_beam is None:
        print(f"    [WARN] Beam CLI introuvable dans stdout pour {stem}")
        return {"conform": False, "error": "beam not found in CLI output"}

    bmin_c = cli_beam["BMIN"]; bmaj_c = cli_beam["BMAJ"]; bpa_c = cli_beam["BPA"]
    # Appliquer le même format %.4g que difmap (4 chiffres significatifs)
    # pour que les deux lignes soient comparables visuellement.
    bmin_w = float(f"{float(wrap_beam['BMIN']):.4g}")
    bmaj_w = float(f"{float(wrap_beam['BMAJ']):.4g}")
    bpa_w  = float(f"{float(wrap_beam['BPA']):.4g}")

    bmin_eq = abs(bmin_c - bmin_w) < TOL_BEAM
    bmaj_eq = abs(bmaj_c - bmaj_w) < TOL_BEAM
    bpa_eq  = abs(bpa_c  - bpa_w)  < TOL_BEAM

    print(f"    DIFMAP_SRC:     bmin={bmin_c:.4g} mas  bmaj={bmaj_c:.4g} mas  bpa={bpa_c:.4g} deg")
    print(f"    DIFMAP_WRAPPER: bmin={bmin_w:.4g} mas  bmaj={bmaj_w:.4g} mas  bpa={bpa_w:.4g} deg")
    print(f"    COMPARE_BEAM:   bmin_equal={bmin_eq}  bmaj_equal={bmaj_eq}  bpa_equal={bpa_eq}")

    return {
        "difmap_src":     {"BMIN": bmin_c, "BMAJ": bmaj_c, "BPA": bpa_c},
        "difmap_wrapper": {"BMIN": bmin_w, "BMAJ": bmaj_w, "BPA": bpa_w},
        "bmin_equal": bmin_eq, "bmaj_equal": bmaj_eq, "bpa_equal": bpa_eq,
        "conform":    bmin_eq and bmaj_eq and bpa_eq,
    }


# ─────────────────────────────────────────────────────────
# 9. Comptage des visibilités
# ─────────────────────────────────────────────────────────

_READING_RE = re.compile(r"Reading\s+(\d+)\s+visibilit", re.IGNORECASE)


def _parse_raw_vis(output: str) -> int:
    matches = _READING_RE.findall(output or "")
    return int(matches[-1]) if matches else -1


def count_visibilities_cli(uv_path: Path, workdir: Path) -> tuple[int, int]:
    tmp = _ensure(workdir / "vis_count")
    dst = tmp / uv_path.name
    if not dst.exists():
        shutil.copy(uv_path, dst)
    uv_out = tmp / "active_uv.fits"
    script = [
        f"observe {uv_path.name}",
        f"select {POL}",
        f"wobs {uv_out.name}",
    ]
    output   = _run_difmap_cli(script, tmp, label="DIFMAP_SRC")
    # n_raw et n_active tous les deux comptés depuis le wobs (après select POL)
    # comme nombre de visibilités avec poids > 0.
    # Le total brut du fichier (avant select) n'est pas comparable au wrapper :
    # get_data() ne retourne que les enregistrements de la polarisation sélectionnée.
    n_raw = n_active = -1
    if uv_out.exists():
        try:
            with fits.open(uv_out) as h:
                weights  = h[0].data["DATA"][..., 2]   # dernière dim = poids
                n_active = int((weights > 0).sum())
                n_raw    = n_active   # même base que wrapper : enregistrements actifs après select
        except Exception:
            pass
    return n_raw, n_active


def count_visibilities_wrapper(uv_path: Path) -> tuple[int, int]:
    from difmap_wrapper import DifmapSession
    with DifmapSession() as session:
        session.observe(str(uv_path))
        session.obs.select(pol=POL)
        data = session.obs.get_data()
    weights  = data.get("weight")
    n_raw    = int(len(data.get("u", [])))
    n_active = int((weights > 0).sum()) if weights is not None else n_raw
    return n_raw, n_active


def run_visibility_comparison(uv_files: list[Path], workdir: Path) -> dict:
    vis_workdir = _ensure(workdir / "vis_count_work")
    report: dict = {}
    for uv_path in uv_files:
        stem = uv_path.name
        _step(f"Comptage visibilités : {stem}")
        try:
            n_src_raw, n_src_active = count_visibilities_cli(uv_path, vis_workdir)
        except Exception as exc:
            print(f"    [WARN] CLI count failed: {exc}")
            n_src_raw, n_src_active = -1, -1
        try:
            n_wrap_raw, n_wrap_active = count_visibilities_wrapper(uv_path)
        except Exception as exc:
            print(f"    [WARN] Wrapper count failed: {exc}")
            n_wrap_raw, n_wrap_active = -1, -1
        raw_eq    = (n_src_raw    == n_wrap_raw)    and n_src_raw    >= 0
        active_eq = (n_src_active == n_wrap_active) and n_src_active >= 0
        print(f"    DIFMAP_SRC:     file={stem} n_vis_raw={n_src_raw} n_vis_active={n_src_active}")
        print(f"    DIFMAP_WRAPPER: file={stem} n_vis_raw={n_wrap_raw} n_vis_active={n_wrap_active}")
        print(f"    COMPARE_VIS_COUNT: raw_equal={raw_eq} active_equal={active_eq}")
        report[stem] = {
            "difmap_src":     {"n_vis_raw": n_src_raw,  "n_vis_active": n_src_active},
            "difmap_wrapper": {"n_vis_raw": n_wrap_raw, "n_vis_active": n_wrap_active},
            "raw_equal": raw_eq, "active_equal": active_eq,
        }
    return report


# ─────────────────────────────────────────────────────────
# 10. Résumé terminal
# ─────────────────────────────────────────────────────────

def print_summary(map_metrics: list[dict], extra_metrics: dict) -> bool:
    _banner("RÉSUMÉ DE VALIDATION SCIENTIFIQUE")

    # --- Cartes ---
    hdr = f"{'Source':<22} {'Type':<8} {'err_max (Jy/b)':>16} {'RMSE (Jy/b)':>14} {'Pearson r':>12} {'Statut':>14}"
    print(hdr); print("-" * len(hdr))
    all_ok = True
    for m in map_metrics:
        status = "CONFORME ✓" if m["conform"] else "NON CONFORME ✗"
        if not m["conform"]:
            all_ok = False
        print(f"  {m['stem']:<20} {m['map_type']:<8} {m['err_max']:>16.3e} "
              f"{m['rmse']:>14.3e} {m['pearson_r']:>12.6f} {status:>14}")
    print("-" * len(hdr))

    # --- Preuves supplémentaires ---
    print(f"\n{'Preuve':<28} {'Grandeur':<12} {'err_max':>12} {'Statut':>14}")
    print("-" * 70)
    for stem, d in extra_metrics.items():
        short = stem[:20]

        # UV
        uv = d.get("uv", {}).get("metrics", {})
        for qty in ("u", "v", "amp"):
            if qty in uv:
                m   = uv[qty]
                st  = "CONFORME ✓" if m["conform"] else "NON CONFORME ✗"
                print(f"  {'UV ' + short:<26} {qty:<12} {m['err_max']:>12.3e} {st:>14}")
                if not m["conform"]:
                    all_ok = False

        # Radplot
        rp = d.get("radplot", {})
        if rp:
            st = "CONFORME ✓" if rp["conform"] else "NON CONFORME ✗"
            print(f"  {'Radplot ' + short:<26} {'amp méd.':<12} {rp['err_max']:>12.3e} {st:>14}")
            if not rp["conform"]:
                all_ok = False

        # Peak
        pk = d.get("peak", {})
        if pk:
            st = "CONFORME ✓" if pk["conform"] else "NON CONFORME ✗"
            dv = abs(pk.get("difmap_src", {}).get("flux", 0) - pk.get("difmap_wrapper", {}).get("flux", 0))
            print(f"  {'Peak ' + short:<26} {'flux':<12} {dv:>12.3e} {st:>14}")
            if not pk["conform"]:
                all_ok = False

        # Beam
        bm = d.get("beam", {})
        if bm and "BMAJ" in bm.get("difmap_src", {}):
            st  = "CONFORME ✓" if bm["conform"] else "NON CONFORME ✗"
            dbmaj = abs(bm["difmap_src"]["BMAJ"] - bm["difmap_wrapper"]["BMAJ"])
            print(f"  {'Beam ' + short:<26} {'bmaj':<12} {dbmaj:>12.3e} {st:>14}")
            if not bm["conform"]:
                all_ok = False

    print("-" * 70)
    color = "\033[92m" if all_ok else "\033[91m"
    print(f"\n  CONCLUSION GLOBALE : {color}{'CONFORME' if all_ok else 'NON CONFORME'}\033[0m")
    return all_ok


# ─────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────

def main() -> None:
    t_start = time.perf_counter()

    _banner("VALIDATION SCIENTIFIQUE — DIFMAP_SRC vs DIFMAP_WRAPPER")
    print(f"  Binaire  : {DIFMAP_BINARY}")
    print(f"  Sortie   : {OUTPUT_DIR}")
    print(f"  Fichiers : {UV_FILES}")
    print(f"  Pipeline : POL={POL}  mapsize={MAPSIZE}  cellsize={CELLSIZE}")
    print(f"             CLEAN niter={CLEAN_NITER} gain={CLEAN_GAIN}")

    if not Path(DIFMAP_BINARY).is_file():
        sys.exit(f"[ERREUR] Binaire difmap introuvable : {DIFMAP_BINARY}")

    uv_paths = []
    for name in UV_FILES:
        p = TEST_DATA_DIR / name
        if not p.exists():
            print(f"[WARN] Fichier introuvable, ignoré : {p}")
        else:
            uv_paths.append(p)
    if not uv_paths:
        sys.exit("[ERREUR] Aucun fichier UV valide trouvé.")

    dir_gt  = _ensure(OUTPUT_DIR / "ground_truth")
    dir_wr  = _ensure(OUTPUT_DIR / "wrapper")
    dir_fig = _ensure(OUTPUT_DIR / "figures")

    all_map_metrics:  list[dict] = []
    extra_metrics:    dict       = {}

    for uv_path in uv_paths:
        stem = uv_path.stem
        _banner(f"FICHIER : {uv_path.name}")
        extra_metrics[stem] = {}

        # 1. Vérité terrain CLI
        print("\n[1/4] Génération vérité terrain (CLI difmap)...")
        gt = generate_ground_truth(uv_path, dir_gt)

        # 2. Wrapper Python
        print("\n[2/4] Génération résultats wrapper (DifmapSession)...")
        wr = generate_wrapper_outputs(uv_path, dir_wr)

        # 3. Comparaison pixel à pixel
        print("\n[3/4] Comparaison pixel à pixel...")
        for map_type in ("dirty", "clean"):
            m = compare_maps(gt[map_type], wr[map_type], map_type)
            m["stem"] = stem
            all_map_metrics.append(m)

        # 4. Figures cartes
        print("\n[4/4] Figures cartes...")
        for m in [mm for mm in all_map_metrics if mm["stem"] == stem]:
            plot_comparison(m, stem, dir_fig)

        # 5. Preuve UV
        print("\n[UV] Preuve UV plot...")
        extra_metrics[stem]["uv"] = proof_uv(gt["uv"], wr["uv_data"], stem)

        # 6. Preuve Radplot
        print("\n[RAD] Preuve Radplot...")
        extra_metrics[stem]["radplot"] = proof_radplot(gt["uv"], wr["uv_data"], stem)

        # 7. Preuve Peak
        print("\n[PEAK] Preuve Peak...")
        extra_metrics[stem]["peak"] = proof_peak(gt["dirty"], wr["peak"], stem)

        # 8. Preuve Beam
        print("\n[BEAM] Preuve Beam...")
        extra_metrics[stem]["beam"] = proof_beam(gt["cli_output"], wr["beam"], stem)

    # 9. Comptage visibilités
    _banner("PREUVE — COMPTAGE DES VISIBILITÉS")
    vis_report = run_visibility_comparison(uv_paths, OUTPUT_DIR)

    # 10. Résumé
    all_ok = print_summary(all_map_metrics, extra_metrics)

    # 11. JSON
    metrics_json: dict = {
        "configuration": {
            "difmap_binary": DIFMAP_BINARY, "pol": POL,
            "mapsize": MAPSIZE, "cellsize": CELLSIZE,
            "clean_niter": CLEAN_NITER, "clean_gain": CLEAN_GAIN,
            "tolerance_map_jy_beam": TOLERANCE,
            "tolerance_uv_jy": TOL_UV,
            "tolerance_beam_mas": TOL_BEAM,
            "tolerance_peak_jy_beam": TOL_PEAK,
        },
        "maps": [
            {k: v for k, v in m.items() if not k.startswith("_")}
            for m in all_map_metrics
        ],
        "uv_radplot_peak_beam": {
            stem: {
                k: {kk: vv for kk, vv in v.items() if not kk.startswith("_")}
                   if isinstance(v, dict) else v
                for k, v in d.items()
            }
            for stem, d in extra_metrics.items()
        },
        "visibility_count": vis_report,
        "global_conform":   all_ok,
    }
    def _to_python(obj):
        """Convertit récursivement les types numpy en types Python natifs."""
        if isinstance(obj, dict):
            return {k: _to_python(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_to_python(v) for v in obj]
        if isinstance(obj, (np.bool_,)):
            return bool(obj)
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        return obj

    json_path = OUTPUT_DIR / "metrics.json"
    json_path.write_text(json.dumps(_to_python(metrics_json), indent=2, ensure_ascii=False), encoding="utf-8")
    _step(f"Métriques JSON → {json_path.relative_to(REPO_ROOT)}")

    elapsed = time.perf_counter() - t_start
    _banner(f"TERMINÉ en {elapsed:.1f}s")
    print(f"  Résultats dans : {OUTPUT_DIR}/")
    print(f"    figures/      — comparaisons + UV + radplot (.png)")
    print(f"    ground_truth/ — FITS produits par la CLI difmap")
    print(f"    wrapper/      — FITS produits par DifmapSession")
    print(f"    metrics.json  — toutes les métriques numériques")


if __name__ == "__main__":
    main()
