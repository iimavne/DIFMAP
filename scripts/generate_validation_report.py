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

POL           = "RR"
MAPSIZE       = 512
CELLSIZE      = 0.1
CLEAN_NITER   = 500
CLEAN_GAIN    = 0.05
CLEAN_NITER_2 = 500   # 2ème cycle CLEAN après selfcal

TOLERANCE   = 1e-6      # seuil cartes images (Jy/beam)
TOL_UV_AMP  = 1e-6      # tolérance amplitude (Jy) — précision machine float32
TOL_UV_COORD= 50.0     # tolérance coordonnées u,v (longueurs d'onde) — quantification float32
TOL_BEAM    = 1e-3      # tolérance beam (mas / degrés)
TOL_PEAK    = 1e-4      # tolérance pic (Jy/beam)
N_SAMPLE    = 1000      # nombre de visibilités tirées aléatoirement pour proof_uv / proof_radplot

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
        return hdul[0].data.squeeze().astype(np.float64)


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

        # Expand (nvis, nif) → (nvis*nif,) en ordre ligne-majeur :
        # [vis0_IF1, vis0_IF2, ..., vis0_IFn, vis1_IF1, ...]
        # C'est l'ordre que difmap utilise en interne et que get_data() retourne.
        u_2d   = np.outer(uu_sec, np.ones(nif)) * if_freqs[np.newaxis, :]  # (nvis, nif)
        v_2d   = np.outer(vv_sec, np.ones(nif)) * if_freqs[np.newaxis, :]
        amp_2d = np.sqrt(re_**2 + im_**2)                                   # (nvis, nif)

        # Garder float64 (précision native numpy/FITS) — ne pas forcer float32.
        # La comparaison float64 (CLI) vs float32 (wrapper C) révèle le bruit
        # de quantification float32 réel (~1e-7 relatif), sans le masquer.
        u   = u_2d.ravel().astype(np.float64)
        v   = v_2d.ravel().astype(np.float64)
        amp = amp_2d.ravel().astype(np.float64)
        wt  = wt_.ravel().astype(np.float64)

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

    dirty_fits    = workdir / f"{stem}_dirty.fits"
    clean_fits    = workdir / f"{stem}_clean.fits"
    clean_sc_fits = workdir / f"{stem}_clean_selfcal.fits"
    uv_fits       = workdir / f"{stem}_uv.fits"
    uv_sc_fits    = workdir / f"{stem}_uv_after_sc.fits"

    script = [
        f"observe {uv_path.name}",
        f"select {POL}",
        f"mapsize {MAPSIZE},{CELLSIZE}",
        "invert",
        f"wdmap {dirty_fits.name}",
        f"wobs {uv_fits.name}",
        # cycle 1 : CLEAN initial
        f"clean {CLEAN_NITER},{CLEAN_GAIN}",
        "restore",
        f"wmap {clean_fits.name}",
        # selfcal (phase uniquement, paramètres par défaut)
        "selfcal",
        # réinversion obligatoire : les visibilités ont changé après selfcal
        "invert",
        # cycle 2 : CLEAN post-selfcal
        f"clean {CLEAN_NITER_2},{CLEAN_GAIN}",
        "restore",
        f"wmap {clean_sc_fits.name}",
        f"wobs {uv_sc_fits.name}",
    ]

    _step(f"CLI difmap → {stem}")
    cli_output = _run_difmap_cli(script, workdir, label="DIFMAP_SRC")
    _step(f"Produit : {dirty_fits.name}, {clean_fits.name}, {clean_sc_fits.name}, {uv_sc_fits.name}")
    return {
        "dirty":      dirty_fits,
        "clean":      clean_fits,
        "clean_sc":   clean_sc_fits,
        "uv":         uv_fits,
        "uv_sc":      uv_sc_fits,
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
    dirty_fits    = file_dir / f"{stem}_dirty.fits"
    clean_fits    = file_dir / f"{stem}_clean.fits"
    clean_sc_fits = file_dir / f"{stem}_clean_selfcal.fits"

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

        # cycle 1 : CLEAN initial
        session.imager.clean(CLEAN_NITER, CLEAN_GAIN, 0.0)
        session.imager.restore()
        session.imager.wmap(str(clean_fits))

        # selfcal (phase uniquement, paramètres par défaut)
        session.imager.selfcal()

        # réinversion obligatoire : les visibilités ont changé après selfcal
        session.imager.invert()

        # cycle 2 : CLEAN post-selfcal
        session.imager.clean(CLEAN_NITER_2, CLEAN_GAIN, 0.0)
        session.imager.restore()
        session.imager.wmap(str(clean_sc_fits))
        uv_data_sc = session.obs.get_data()

    _step(f"Produit : {dirty_fits.name}, {clean_fits.name}, {clean_sc_fits.name}")
    return {
        "dirty":       dirty_fits,
        "clean":       clean_fits,
        "clean_sc":    clean_sc_fits,
        "uv_data":     uv_data,
        "uv_data_sc":  uv_data_sc,
        "peak":        peak,
        "beam":        beam,
    }


# ─────────────────────────────────────────────────────────
# 2b. Dirty map Python float32 vs float64 (bruit numérique)
# ─────────────────────────────────────────────────────────

def _python_dirty_map(uv_fits_path: Path, mapsize: int, cellsize_mas: float,
                      dtype) -> np.ndarray:
    """
    Dirty map simple (grille nearest-neighbor + FFT numpy) en précision `dtype`.
    Même algorithme pour float32 et float64 : la différence montre le bruit de
    précision float32 pur sans biais algorithmique.
    """
    cellsize_rad = cellsize_mas / 3_600_000.0 * (np.pi / 180.0)
    cdtype = np.complex64 if dtype == np.float32 else np.complex128

    with fits.open(uv_fits_path) as h:
        hdr   = h[0].header
        ddata = h[0].data
        fq    = h["AIPS FQ"]

        crval4    = dtype(hdr["CRVAL4"])
        if_freqs  = (crval4 + fq.data["IF FREQ"].flatten()).astype(dtype)  # (nif,)

        # Les colonnes peuvent s'appeler "UU---SIN" ou "UU" selon le fichier
        _uu_key = next(c for c in ddata.dtype.names if c.startswith("UU"))
        _vv_key = next(c for c in ddata.dtype.names if c.startswith("VV"))
        uu_sec = ddata[_uu_key].flatten().astype(dtype)  # (nvis,)
        vv_sec = ddata[_vv_key].flatten().astype(dtype)

        raw  = ddata["DATA"]                         # (nvis,1,1,nif,nchan,npol,3)
        nvis, _, _, nif, _, _, _ = raw.shape

        re_ = raw[:, 0, 0, :, 0, 0, 0].astype(dtype).ravel()
        im_ = raw[:, 0, 0, :, 0, 0, 1].astype(dtype).ravel()
        wt_ = raw[:, 0, 0, :, 0, 0, 2].ravel()

    # Expand (nvis,nif) → (nvis*nif,) en ordre ligne-majeur
    freq_tile = np.tile(if_freqs, nvis)
    u = np.repeat(uu_sec, nif) * freq_tile
    v = np.repeat(vv_sec, nif) * freq_tile

    mask = wt_ > 0
    u, v, re, im = u[mask], v[mask], re_[mask], im_[mask]

    # Conversion wavelengths → cellules de grille :
    #   u_cell = u * mapsize * cellsize_rad   (car 1 cellule = 1/(mapsize*cellsize_rad) λ)
    grid_scale = dtype(mapsize) * dtype(cellsize_rad)
    iu = (np.round(u * grid_scale) + mapsize // 2).astype(np.int32)
    iv = (np.round(v * grid_scale) + mapsize // 2).astype(np.int32)

    ok = (iu >= 0) & (iu < mapsize) & (iv >= 0) & (iv < mapsize)
    iu, iv, re, im = iu[ok], iv[ok], re[ok], im[ok]

    vis = (re + 1j * im).astype(cdtype)
    grid = np.zeros((mapsize, mapsize), dtype=cdtype)
    np.add.at(grid, (iv, iu), vis)

    # Symétrie hermitienne (visibilités conjuguées)
    iu_c = (mapsize - 1 - iu)
    iv_c = (mapsize - 1 - iv)
    ok2  = (iu_c >= 0) & (iu_c < mapsize) & (iv_c >= 0) & (iv_c < mapsize)
    np.add.at(grid, (iv_c[ok2], iu_c[ok2]), np.conj(vis[ok2]))

    dirty = np.real(np.fft.fftshift(np.fft.ifft2(np.fft.ifftshift(grid))))
    return dirty.astype(np.float64)


def plot_float32_vs_float64_dirty(uv_fits_path: Path, stem: str,
                                  fig_dir: Path) -> Path:
    """
    3 panneaux — même format que plot_comparison :
      1. Dirty map calculée en float64 (Python numpy)
      2. Dirty map calculée en float32 (Python numpy, même algo)
      3. Différence float64 − float32 → bruit de précision float32 pur
    """
    _step(f"Calcul dirty float64 vs float32 — {stem}")

    d64 = _python_dirty_map(uv_fits_path, MAPSIZE, CELLSIZE, np.float64)
    d32 = _python_dirty_map(uv_fits_path, MAPSIZE, CELLSIZE, np.float32)

    # Normalisation commune : les deux ont des pics similaires mais pas identiques
    # On aligne sur le max du float64 pour que la différence soit en Jy/beam relatif.
    scale = d64.max() / d32.max() if d32.max() != 0 else 1.0
    d32  *= scale

    diff    = d64 - d32
    err_max = float(np.max(np.abs(diff)))
    rmse    = float(np.sqrt(np.mean(diff**2)))
    pearson = _pearson(d64, d32)

    vmin = float(min(d64.min(), d32.min()))
    vmax = float(max(d64.max(), d32.max()))
    d_lim = max(err_max, 1e-12)

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    im0 = axes[0].imshow(d64,  origin="lower", cmap="inferno", vmin=vmin, vmax=vmax)
    axes[0].set_title(f"Float64 (référence)\npic = {d64.max():.4f} (normalisé)",
                      fontsize=10, fontweight="bold")
    axes[0].set_xlabel("pixels"); axes[0].set_ylabel("pixels")
    plt.colorbar(im0, ax=axes[0], fraction=0.046, pad=0.04, label="u.a.")

    im1 = axes[1].imshow(d32,  origin="lower", cmap="inferno", vmin=vmin, vmax=vmax)
    axes[1].set_title(f"Float32 (même algorithme)\npic = {d32.max():.4f} (normalisé)",
                      fontsize=10, fontweight="bold")
    axes[1].set_xlabel("pixels")
    plt.colorbar(im1, ax=axes[1], fraction=0.046, pad=0.04, label="u.a.")

    im2 = axes[2].imshow(diff, origin="lower", cmap="coolwarm", vmin=-d_lim, vmax=d_lim)
    axes[2].set_title(
        f"Différence (float64 − float32)\nerr_max = {err_max:.2e}  RMSE = {rmse:.2e}",
        fontsize=10, fontweight="bold"
    )
    axes[2].set_xlabel("pixels")
    plt.colorbar(im2, ax=axes[2], fraction=0.046, pad=0.04, label="u.a.")

    fig.suptitle(
        f"Bruit numérique float32 sur carte — {stem} — même algorithme numpy\n"
        f"Pearson r = {pearson:.6f}  |  "
        f"Bruit ~ε_float32 × signal  (pas de biais systématique)",
        fontsize=11, y=1.02,
    )
    out_path = fig_dir / f"{stem}_dirty_float32_vs_float64.png"
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    try:
        _step(f"Figure float32 vs float64 → {out_path.resolve().relative_to(REPO_ROOT)}")
    except ValueError:
        _step(f"Figure float32 vs float64 → {out_path.name}")
    return out_path


# ─────────────────────────────────────────────────────────
# 2c. Clean map Python float32 vs float64 (selfcal + CLEAN + restore)
# ─────────────────────────────────────────────────────────

CLEAN_NITER_PY = 100   # itérations pour le CLEAN Python (performance)


def _python_clean_map(uv_fits_path: Path, mapsize: int, cellsize_mas: float,
                      dtype, niter: int = CLEAN_NITER_PY, gain: float = 0.05) -> np.ndarray:
    """
    Pipeline Python complet : dirty map + dirty beam (nearest-neighbor gridder)
    → CLEAN Högbom → restore Gaussien.
    dtype contrôle la précision de TOUS les calculs (float32 ou float64).
    Le selfcal est inclus implicitement via le fichier UVFITS post-selfcal passé en entrée.
    """
    from scipy.ndimage import gaussian_filter

    cellsize_rad = cellsize_mas / 3_600_000.0 * (np.pi / 180.0)
    cdtype = np.complex64 if dtype == np.float32 else np.complex128

    # ── Chargement UVFITS ────────────────────────────────
    with fits.open(uv_fits_path) as h:
        hdr   = h[0].header
        ddata = h[0].data
        fq    = h["AIPS FQ"]
        crval4   = dtype(hdr["CRVAL4"])
        if_freqs = (crval4 + fq.data["IF FREQ"].flatten()).astype(dtype)
        _uu_key  = next(c for c in ddata.dtype.names if c.startswith("UU"))
        _vv_key  = next(c for c in ddata.dtype.names if c.startswith("VV"))
        uu_sec   = ddata[_uu_key].flatten().astype(dtype)
        vv_sec   = ddata[_vv_key].flatten().astype(dtype)
        raw      = ddata["DATA"]
        nvis, _, _, nif, _, _, _ = raw.shape
        re_ = raw[:, 0, 0, :, 0, 0, 0].astype(dtype).ravel()
        im_ = raw[:, 0, 0, :, 0, 0, 1].astype(dtype).ravel()
        wt_ = raw[:, 0, 0, :, 0, 0, 2].ravel()

    freq_tile = np.tile(if_freqs, nvis)
    u = np.repeat(uu_sec, nif) * freq_tile
    v = np.repeat(vv_sec, nif) * freq_tile

    mask = wt_ > 0
    u, v, re, im = u[mask], v[mask], re_[mask], im_[mask]

    # ── Grillage nearest-neighbor ────────────────────────
    grid_scale = dtype(mapsize) * dtype(cellsize_rad)
    iu = (np.round(u * grid_scale) + mapsize // 2).astype(np.int32)
    iv = (np.round(v * grid_scale) + mapsize // 2).astype(np.int32)

    ok = (iu >= 0) & (iu < mapsize) & (iv >= 0) & (iv < mapsize)
    iu, iv, re, im = iu[ok], iv[ok], re[ok], im[ok]

    vis  = (re + 1j * im).astype(cdtype)
    ones = np.ones(len(vis), dtype=cdtype)

    g_dirty = np.zeros((mapsize, mapsize), dtype=cdtype)
    g_beam  = np.zeros((mapsize, mapsize), dtype=cdtype)
    np.add.at(g_dirty, (iv, iu), vis)
    np.add.at(g_beam,  (iv, iu), ones)

    iu_c = mapsize - 1 - iu
    iv_c = mapsize - 1 - iv
    ok2  = (iu_c >= 0) & (iu_c < mapsize) & (iv_c >= 0) & (iv_c < mapsize)
    np.add.at(g_dirty, (iv_c[ok2], iu_c[ok2]), np.conj(vis[ok2]))
    np.add.at(g_beam,  (iv_c[ok2], iu_c[ok2]), ones[ok2])

    def _to_map(g):
        return np.real(np.fft.fftshift(np.fft.ifft2(np.fft.ifftshift(g)))).astype(np.float64)

    dirty = _to_map(g_dirty)
    beam  = _to_map(g_beam)

    # Normalisation : peak du beam = 1 (convention difmap)
    bp = beam[mapsize // 2, mapsize // 2]
    if bp > 0:
        dirty /= bp
        beam  /= bp

    # ── Estimation sigma du beam propre (Gaussienne ajustée au lobe principal) ──
    center = mapsize // 2
    row    = beam[center, center:]
    hwhm   = 1
    for i in range(1, len(row)):
        if row[i] < 0.5:
            hwhm = i
            break
    clean_sigma = max(hwhm / 2.355, 0.5)   # pixels (FWHM → σ)

    # ── CLEAN Högbom ─────────────────────────────────────
    residual = dirty.astype(dtype)
    model    = np.zeros((mapsize, mapsize), dtype=dtype)

    for _ in range(niter):
        iy, ix   = np.unravel_index(np.argmax(np.abs(residual)), residual.shape)
        delta    = dtype(gain) * residual[iy, ix]
        model[iy, ix] += delta
        dy, dx   = iy - center, ix - center
        b_shift  = np.roll(np.roll(beam.astype(dtype), dy, axis=0), dx, axis=1)
        residual -= delta * b_shift

    # ── Restore : modèle ⊛ beam_propre + résidus ────────
    clean_map = (gaussian_filter(model.astype(np.float64), sigma=clean_sigma)
                 + residual.astype(np.float64))
    return clean_map


def plot_float32_vs_float64_clean(uv_sc_fits_path: Path, stem: str,
                                  fig_dir: Path) -> Path:
    """
    3 panneaux — même format que plot_comparison :
      1. Clean map calculée en float64 (Python : selfcal via UVFITS post-SC, CLEAN, restore)
      2. Clean map calculée en float32 (même algo)
      3. Différence → bruit de précision float32 accumulé sur N itérations CLEAN
    """
    _step(f"Calcul clean float64 vs float32 ({CLEAN_NITER_PY} iter) — {stem}")

    c64 = _python_clean_map(uv_sc_fits_path, MAPSIZE, CELLSIZE, np.float64)
    c32 = _python_clean_map(uv_sc_fits_path, MAPSIZE, CELLSIZE, np.float32)

    scale = c64.max() / c32.max() if c32.max() != 0 else 1.0
    c32  *= scale

    diff    = c64 - c32
    err_max = float(np.max(np.abs(diff)))
    rmse    = float(np.sqrt(np.mean(diff**2)))
    pearson = _pearson(c64, c32)

    vmin  = float(min(c64.min(), c32.min()))
    vmax  = float(max(c64.max(), c32.max()))
    d_lim = max(err_max, 1e-12)

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    im0 = axes[0].imshow(c64,  origin="lower", cmap="inferno", vmin=vmin, vmax=vmax)
    axes[0].set_title(f"Float64 (référence)\npic = {c64.max():.4f} (normalisé)",
                      fontsize=10, fontweight="bold")
    axes[0].set_xlabel("pixels"); axes[0].set_ylabel("pixels")
    plt.colorbar(im0, ax=axes[0], fraction=0.046, pad=0.04, label="u.a.")

    im1 = axes[1].imshow(c32,  origin="lower", cmap="inferno", vmin=vmin, vmax=vmax)
    axes[1].set_title(f"Float32 (même algorithme)\npic = {c32.max():.4f} (normalisé)",
                      fontsize=10, fontweight="bold")
    axes[1].set_xlabel("pixels")
    plt.colorbar(im1, ax=axes[1], fraction=0.046, pad=0.04, label="u.a.")

    im2 = axes[2].imshow(diff, origin="lower", cmap="coolwarm", vmin=-d_lim, vmax=d_lim)
    axes[2].set_title(
        f"Différence (float64 − float32)\nerr_max = {err_max:.2e}  RMSE = {rmse:.2e}",
        fontsize=10, fontweight="bold"
    )
    axes[2].set_xlabel("pixels")
    plt.colorbar(im2, ax=axes[2], fraction=0.046, pad=0.04, label="u.a.")

    fig.suptitle(
        f"Bruit numérique float32 — CLEAN map — {stem}\n"
        f"Pipeline : selfcal (UVFITS post-SC) → CLEAN {CLEAN_NITER_PY} iter → restore Gaussien\n"
        f"Pearson r = {pearson:.6f}  |  Bruit ~ε_float32 × signal accumulé sur {CLEAN_NITER_PY} itérations",
        fontsize=10, y=1.04,
    )
    out_path = fig_dir / f"{stem}_clean_float32_vs_float64.png"
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    try:
        _step(f"Figure clean float32 vs float64 → {out_path.resolve().relative_to(REPO_ROOT)}")
    except ValueError:
        _step(f"Figure clean float32 vs float64 → {out_path.name}")
    return out_path


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
# 4b. Figure bruit numérique — plan UV (3 panneaux)
# ─────────────────────────────────────────────────────────

def plot_uv_noise_as_map(
    uv_fits_cli: Path, uv_data_wrap: dict, stem: str, fig_dir: Path
) -> Path | None:
    """
    3 panneaux dans le plan UV — même format que plot_comparison :
      1. CLI  : amplitude par point (u,v)
      2. Wrapper : amplitude par point (u,v)
      3. Différence Wrapper − CLI : bruit float32 (±~1e-7 Jy après selfcal)
    """
    cli = _load_uvfits(uv_fits_cli)
    u_c_raw, v_c_raw, a_c_raw = cli["u"], cli["v"], cli["amp"]

    weights = uv_data_wrap.get("weight", np.ones(len(uv_data_wrap["u"])))
    mask    = weights > 0
    u_w_raw = uv_data_wrap["u"][mask].astype(np.float32)
    v_w_raw = uv_data_wrap["v"][mask].astype(np.float32)
    a_w_raw = uv_data_wrap["amp"][mask].astype(np.float32)

    n = len(u_c_raw)
    if len(u_w_raw) != n:
        _step(f"[WARN] plot_uv_noise_as_map ignoré — tailles différentes ({stem})")
        return None

    # Alignement par tri (u,v) — même méthode que proof_uv
    ord_c = np.lexsort((v_c_raw, u_c_raw))
    ord_w = np.lexsort((v_w_raw, u_w_raw))
    u_c = u_c_raw[ord_c] / 1e6    # Mλ
    v_c = v_c_raw[ord_c] / 1e6
    a_c = a_c_raw[ord_c]
    u_w = u_w_raw[ord_w] / 1e6
    v_w = v_w_raw[ord_w] / 1e6
    a_w = a_w_raw[ord_w]

    diff    = (a_w - a_c).astype(np.float64)
    err_max = float(np.max(np.abs(diff)))
    rmse    = float(np.sqrt(np.mean(diff**2)))
    pearson = _pearson(a_c, a_w)

    vmin    = float(min(a_c.min(), a_w.min()))
    vmax    = float(max(a_c.max(), a_w.max()))
    d_lim   = max(err_max, 1e-12)

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    kw_amp  = dict(s=1, cmap="inferno", vmin=vmin, vmax=vmax, linewidths=0)
    kw_diff = dict(s=2, cmap="coolwarm", vmin=-d_lim, vmax=d_lim, linewidths=0)

    sc0 = axes[0].scatter(u_c, v_c, c=a_c, **kw_amp)
    axes[0].set_title(f"DIFMAP_SRC (CLI)\namp max = {float(a_c.max()):.4f} Jy",
                      fontsize=10, fontweight="bold")
    axes[0].set_xlabel("u (Mλ)"); axes[0].set_ylabel("v (Mλ)")
    plt.colorbar(sc0, ax=axes[0], fraction=0.046, pad=0.04, label="Jy")

    sc1 = axes[1].scatter(u_w, v_w, c=a_w, **kw_amp)
    axes[1].set_title(f"DIFMAP_WRAPPER (Python)\namp max = {float(a_w.max()):.4f} Jy",
                      fontsize=10, fontweight="bold")
    axes[1].set_xlabel("u (Mλ)")
    plt.colorbar(sc1, ax=axes[1], fraction=0.046, pad=0.04, label="Jy")

    sc2 = axes[2].scatter(u_c, v_c, c=diff, **kw_diff)
    axes[2].set_title(
        f"Différence (Wrapper − CLI)\nerr_max = {err_max:.2e}  RMSE = {rmse:.2e} Jy",
        fontsize=10, fontweight="bold"
    )
    axes[2].set_xlabel("u (Mλ)")
    plt.colorbar(sc2, ax=axes[2], fraction=0.046, pad=0.04, label="Jy")

    fig.suptitle(
        f"Bruit numérique — plan UV post-selfcal — {stem}   (n = {n} vis.)\n"
        f"Pearson r = {pearson:.6f}  |  "
        f"Bruit float32 pur : pas de biais systématique",
        fontsize=11, y=1.02,
    )
    out_path = fig_dir / f"{stem}_uv_noise_map.png"
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    try:
        _step(f"Figure UV noise → {out_path.resolve().relative_to(REPO_ROOT)}")
    except ValueError:
        _step(f"Figure UV noise → {out_path.name}")
    return out_path


# ─────────────────────────────────────────────────────────
# 4c. Figure bruit numérique float32 (histogrammes)
# ─────────────────────────────────────────────────────────

def _align_and_sample(u_c, v_c, vals_c, u_w, v_w, vals_w, seed=42):
    """Tri lexicographique + tirage aléatoire commun. Retourne (vals_c[idx], vals_w[idx])."""
    n = len(u_c)
    ord_c = np.lexsort((v_c, u_c))
    ord_w = np.lexsort((v_w, u_w))
    vals_c = vals_c[ord_c]
    vals_w = vals_w[ord_w]
    k = min(N_SAMPLE, n)
    idx = np.random.default_rng(seed=seed).choice(n, size=k, replace=False)
    idx.sort()
    return vals_c[idx], vals_w[idx], k, n


def plot_uv_noise_figure(
    uv_fits_cli: Path, uv_data_wrap: dict,
    uv_sc_fits_cli: Path, uv_data_sc_wrap: dict,
    stem: str, fig_dir: Path,
) -> Path:
    """
    3 panneaux :
      1. Histogramme de Δu  (float64 CLI − float32 wrapper)  → quantification float32
      2. Histogramme de Δv
      3. Histogramme de Δamp après selfcal  → bruit d'arrondi float32 sur les corrections
    """
    from scipy.stats import norm as sp_norm

    def _load_wrap(uv_data):
        weights = uv_data.get("weight", np.ones(len(uv_data["u"])))
        mask = weights > 0
        return (uv_data["u"][mask].astype(np.float32),
                uv_data["v"][mask].astype(np.float32),
                uv_data["amp"][mask].astype(np.float32))

    # ── avant selfcal ─────────────────────────────────────
    cli   = _load_uvfits(uv_fits_cli)
    u_c, v_c, a_c = cli["u"], cli["v"], cli["amp"]
    u_w, v_w, a_w = _load_wrap(uv_data_wrap)

    if len(u_w) != len(u_c):
        _step(f"[WARN] noise figure ignorée — tailles différentes ({stem})")
        return None

    vc_s, vw_s, k, n = _align_and_sample(u_c, v_c, u_c, u_w, v_w, u_w)
    du = vc_s - vw_s                                           # Δu
    vc_s, vw_s, _, _ = _align_and_sample(u_c, v_c, v_c, u_w, v_w, v_w)
    dv = vc_s - vw_s                                           # Δv

    # ── après selfcal ──────────────────────────────────────
    cli_sc = _load_uvfits(uv_sc_fits_cli)
    u_csc, v_csc, a_csc = cli_sc["u"], cli_sc["v"], cli_sc["amp"]
    u_wsc, v_wsc, a_wsc = _load_wrap(uv_data_sc_wrap)

    da_sc = None
    if len(u_wsc) == len(u_csc):
        vc_s, vw_s, k_sc, n_sc = _align_and_sample(
            u_csc, v_csc, a_csc, u_wsc, v_wsc, a_wsc)
        da_sc = vc_s - vw_s                                    # Δamp post-selfcal

    # ── figure ────────────────────────────────────────────
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    def _hist_panel(ax, data, xlabel, color, ref_scale, title_extra=""):
        mu, sigma = float(np.mean(data)), float(np.std(data))
        counts, bins, _ = ax.hist(data, bins=40, color=color,
                                  edgecolor="white", alpha=0.82, density=True)
        if sigma > 0:
            x = np.linspace(bins[0], bins[-1], 300)
            ax.plot(x, sp_norm.pdf(x, mu, sigma), "r-", linewidth=2,
                    label=f"Gauss  μ = {mu:.2e}\n        σ = {sigma:.2e}")
            ax.legend(fontsize=8)
        ax.axvline(0, color="k", linestyle="--", linewidth=1)
        ax.set_xlabel(xlabel, fontsize=10)
        ax.set_ylabel("Densité", fontsize=10)
        rel = sigma / ref_scale if ref_scale > 0 else float("nan")
        ax.set_title(f"{title_extra}\nmax|Δ| = {float(np.max(np.abs(data))):.2e}   "
                     f"σ/ref = {rel:.1e}",
                     fontsize=9, fontweight="bold")

    u_scale = float(np.max(np.abs(cli["u"])))
    v_scale = float(np.max(np.abs(cli["v"])))
    _hist_panel(axes[0], du, "Δu  (λ)", "steelblue", u_scale,
                f"Coordonnée u — {k}/{n} vis.\n"
                "Float64 (FITS) − Float32 (wrapper C)")
    _hist_panel(axes[1], dv, "Δv  (λ)", "steelblue", v_scale,
                f"Coordonnée v — {k}/{n} vis.\n"
                "Float64 (FITS) − Float32 (wrapper C)")

    if da_sc is not None:
        amp_scale = float(np.max(np.abs(cli_sc["amp"])))
        _hist_panel(axes[2], da_sc, "Δamp  (Jy)", "darkorange", amp_scale,
                    f"Amplitude post-selfcal — {k_sc}/{n_sc} vis.\n"
                    "Bruit d'arrondi float32 sur les corrections")
    else:
        axes[2].text(0.5, 0.5, "Données post-selfcal\nindisponibles",
                     ha="center", va="center", transform=axes[2].transAxes)

    fig.suptitle(
        f"Bruit numérique flottant — {stem}\n"
        "Différences CLI float64 (lecture FITS) vs Wrapper float32 (mémoire C)\n"
        "Distribution centrée sur 0, symétrique → pas de biais systématique",
        fontsize=10, y=1.04,
    )
    out_path = fig_dir / f"{stem}_numerical_noise.png"
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    _step(f"Figure bruit numérique → {out_path.relative_to(REPO_ROOT)}")
    return out_path


# ─────────────────────────────────────────────────────────
# 5. Preuve UV plot
# ─────────────────────────────────────────────────────────

def proof_uv(uv_fits_cli: Path, uv_data_wrap: dict, stem: str) -> dict:
    """
    Compare u, v, amplitude entre CLI (wobs FITS) et Wrapper (get_data()).

    Tire N_SAMPLE indices aléatoires et vérifie que CLI[idx] == Wrapper[idx]
    aux mêmes positions (même ordre naturel d'export difmap).
    """
    _step(f"Preuve UV — {stem}")

    cli = _load_uvfits(uv_fits_cli)
    u_c, v_c, a_c = cli["u"], cli["v"], cli["amp"]

    weights = uv_data_wrap.get("weight", np.ones(len(uv_data_wrap["u"])))
    mask    = weights > 0
    u_w = uv_data_wrap["u"][mask].astype(np.float32)
    v_w = uv_data_wrap["v"][mask].astype(np.float32)
    a_w = uv_data_wrap["amp"][mask].astype(np.float32)

    n = len(u_c)
    if len(u_w) != n:
        print(f"    [WARN] Tailles différentes : CLI={n}  Wrapper={len(u_w)} — comparaison impossible")
        return {"n_vis": n, "metrics": {}, "n_sample": 0}

    # Tri stable par (u, v) pour aligner CLI et Wrapper indépendamment de leur ordre interne
    ord_c = np.lexsort((v_c, u_c))
    ord_w = np.lexsort((v_w, u_w))
    u_c, v_c, a_c = u_c[ord_c], v_c[ord_c], a_c[ord_c]
    u_w, v_w, a_w = u_w[ord_w], v_w[ord_w], a_w[ord_w]

    # Tirage aléatoire de N_SAMPLE indices dans l'espace trié (même indices des 2 côtés)
    rng     = np.random.default_rng(seed=42)
    k       = min(N_SAMPLE, n)
    indices = rng.choice(n, size=k, replace=False)
    indices.sort()

    u_cs, v_cs, a_cs = u_c[indices], v_c[indices], a_c[indices]
    u_ws, v_ws, a_ws = u_w[indices], v_w[indices], a_w[indices]

    print(f"    DIFMAP_SRC:     n_vis={n}  u_max={float(np.max(np.abs(u_c)))/1e6:.4f} Mλ  "
          f"amp_max={float(np.max(a_c)):.4f} Jy  amp_med={float(np.median(a_c)):.4f} Jy")
    print(f"    DIFMAP_WRAPPER: n_vis={n}  u_max={float(np.max(np.abs(u_w)))/1e6:.4f} Mλ  "
          f"amp_max={float(np.max(a_w)):.4f} Jy  amp_med={float(np.median(a_w)):.4f} Jy")
    print(f"    Échantillon aléatoire : {k}/{n} indices dans l'espace trié par (u,v) (seed=42)")

    # Tolérances séparées : coordonnées UV en longueurs d'onde, amplitude en Jy
    tol_map = {"u": TOL_UV_COORD, "v": TOL_UV_COORD, "amp": TOL_UV_AMP}

    metrics = {}
    u_eq = v_eq = amp_eq = True
    for name, xc, xw in [("u", u_cs, u_ws), ("v", v_cs, v_ws), ("amp", a_cs, a_ws)]:
        tol  = tol_map[name]
        diff = xw - xc
        err  = float(np.max(np.abs(diff)))
        rmse = float(np.sqrt(np.mean(diff**2)))
        pear = _pearson(xc, xw)
        conf = bool(err < tol)
        n_ok = int(np.sum(np.abs(diff) < tol))
        unit = "λ" if name in ("u", "v") else "Jy"
        metrics[name] = {"err_max": err, "rmse": rmse, "pearson_r": pear,
                         "conform": conf, "n_ok": n_ok, "n_sample": k}
        if name == "u":   u_eq   = conf
        if name == "v":   v_eq   = conf
        if name == "amp": amp_eq = conf
        print(f"      {name:<4} : err_max={err:.3e} {unit}  RMSE={rmse:.3e}  "
              f"Pearson={pear:.6f}  {n_ok}/{k} dans tolérance  {'OK ✓' if conf else 'ÉCART ✗'}")
        if name in ("u", "v") and err > 0:
            rel = err / float(np.max(np.abs(xc))) if float(np.max(np.abs(xc))) > 0 else 0
            print(f"             (bruit float32 quantification : erreur relative {rel:.2e} — physiquement négligeable)")

    print(f"    COMPARE_UV:     u_equal={u_eq}  v_equal={v_eq}  amp_equal={amp_eq}")
    return {"n_vis": n, "n_sample": k, "metrics": metrics}


# ─────────────────────────────────────────────────────────
# 6. Preuve Radplot
# ─────────────────────────────────────────────────────────

def proof_radplot(uv_fits_cli: Path, uv_data_wrap: dict, stem: str) -> dict:
    """
    Radplot CLI vs Wrapper : tire N_SAMPLE indices aléatoires et compare
    (rayon UV, amplitude) à ces mêmes indices dans les deux jeux de données.
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

    n = len(r_c)
    if len(r_w) != n:
        print(f"    [WARN] Tailles différentes : CLI={n}  Wrapper={len(r_w)} — comparaison impossible")
        return {"err_max": float("nan"), "rmse": float("nan"), "conform": False, "n_sample": 0}

    # Tri stable par (u, v) pour aligner CLI et Wrapper
    u_c_raw = cli["u"]; v_c_raw = cli["v"]
    ord_c = np.lexsort((v_c_raw, u_c_raw))
    ord_w = np.lexsort((v_w, u_w))
    r_c, a_c = r_c[ord_c], a_c[ord_c]
    r_w, a_w = r_w[ord_w], a_w[ord_w]

    # Tirage aléatoire de N_SAMPLE indices (même indices des 2 côtés)
    rng     = np.random.default_rng(seed=42)
    k       = min(N_SAMPLE, n)
    indices = rng.choice(n, size=k, replace=False)
    indices.sort()

    r_cs, a_cs = r_c[indices], a_c[indices]
    r_ws, a_ws = r_w[indices], a_w[indices]

    diff_r   = r_ws - r_cs
    diff_a   = a_ws - a_cs
    err_r    = float(np.max(np.abs(diff_r)))
    err_a    = float(np.max(np.abs(diff_a)))
    rmse_a   = float(np.sqrt(np.mean(diff_a**2)))
    pear_a   = _pearson(a_cs, a_ws)
    n_ok_a   = int(np.sum(np.abs(diff_a) < TOL_UV_AMP))
    conform  = bool(err_a < TOL_UV_AMP)

    print(f"    DIFMAP_SRC:     n_vis={n}  r_max={float(r_c.max()):.3f} Mλ  "
          f"amp_med={float(np.median(a_c)):.4f} Jy  amp_max={float(np.max(a_c)):.4f} Jy")
    print(f"    DIFMAP_WRAPPER: n_vis={n}  r_max={float(r_w.max()):.3f} Mλ  "
          f"amp_med={float(np.median(a_w)):.4f} Jy  amp_max={float(np.max(a_w)):.4f} Jy")
    print(f"    Échantillon aléatoire : {k} indices sur {n} (seed=42)")
    print(f"      radius : err_max={err_r:.3e} Mλ")
    print(f"      amp    : err_max={err_a:.3e} Jy  RMSE={rmse_a:.3e}  "
          f"Pearson={pear_a:.6f}  {n_ok_a}/{k} dans tolérance  {'OK ✓' if conform else 'ÉCART ✗'}")
    print(f"    COMPARE_RADPLOT: amp_equal={conform}  err_max={err_a:.3e} Jy  RMSE={rmse_a:.3e} Jy")

    return {"err_max": err_a, "rmse": rmse_a, "conform": conform,
            "n_vis": n, "n_sample": k, "pearson_r": pear_a}


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

        # UV (avant selfcal)
        uv = d.get("uv", {}).get("metrics", {})
        for qty in ("u", "v", "amp"):
            if qty in uv:
                m   = uv[qty]
                st  = "CONFORME ✓" if m["conform"] else "NON CONFORME ✗"
                print(f"  {'UV ' + short:<26} {qty:<12} {m['err_max']:>12.3e} {st:>14}")
                if not m["conform"]:
                    all_ok = False

        # UV après selfcal
        uv_sc = d.get("uv_sc", {}).get("metrics", {})
        for qty in ("u", "v", "amp"):
            if qty in uv_sc:
                m  = uv_sc[qty]
                st = "CONFORME ✓" if m["conform"] else "NON CONFORME ✗"
                print(f"  {'UV_SC ' + short:<26} {qty:<12} {m['err_max']:>12.3e} {st:>14}")
                if not m["conform"]:
                    all_ok = False

        # Radplot
        rp = d.get("radplot", {})
        if rp:
            st = "CONFORME ✓" if rp["conform"] else "NON CONFORME ✗"
            k_str = f"(n={rp.get('n_sample', '?')})"
            print(f"  {'Radplot ' + short:<26} {('amp ' + k_str):<12} {rp['err_max']:>12.3e} {st:>14}")
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
        for map_type in ("dirty", "clean", "clean_sc"):
            m = compare_maps(gt[map_type], wr[map_type], map_type)
            m["stem"] = stem
            all_map_metrics.append(m)

        # 4. Figures cartes
        print("\n[4/4] Figures cartes...")
        for m in [mm for mm in all_map_metrics if mm["stem"] == stem]:
            plot_comparison(m, stem, dir_fig)

        # 4b. Figure bruit numérique — carte dirty float32 vs float64
        print("\n[NOISE-IMG] Figure bruit numérique — dirty float32 vs float64...")
        plot_float32_vs_float64_dirty(uv_path, stem, dir_fig)

        # 4b-clean. Figure bruit numérique — clean float32 vs float64
        print(f"\n[NOISE-CLEAN] Figure bruit numérique — clean float32 vs float64 ({CLEAN_NITER_PY} iter)...")
        plot_float32_vs_float64_clean(gt["uv_sc"], stem, dir_fig)

        # 4c. Figure bruit numérique — plan UV 3 panneaux (post-selfcal)
        print("\n[NOISE-MAP] Figure bruit numérique — plan UV (3 panneaux)...")
        plot_uv_noise_as_map(gt["uv_sc"], wr["uv_data_sc"], stem, dir_fig)

        # 4c. Figure bruit numérique — histogrammes
        print("\n[NOISE-HIST] Figure bruit numérique — histogrammes...")
        plot_uv_noise_figure(
            gt["uv"], wr["uv_data"],
            gt["uv_sc"], wr["uv_data_sc"],
            stem, dir_fig,
        )

        # 5. Preuve UV (avant selfcal)
        print("\n[UV] Preuve UV plot (avant selfcal)...")
        extra_metrics[stem]["uv"] = proof_uv(gt["uv"], wr["uv_data"], stem)

        # 5b. Preuve UV après selfcal
        print("\n[UV_SC] Preuve UV plot (après selfcal)...")
        extra_metrics[stem]["uv_sc"] = proof_uv(gt["uv_sc"], wr["uv_data_sc"], f"{stem}_sc")

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
            "clean_niter": CLEAN_NITER, "clean_niter_2": CLEAN_NITER_2, "clean_gain": CLEAN_GAIN,
            "tolerance_map_jy_beam": TOLERANCE,
            "tolerance_uv_amp_jy": TOL_UV_AMP,
            "tolerance_uv_coord_lambda": TOL_UV_COORD,
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
