from __future__ import annotations

from pathlib import Path

import numpy as np
from astropy.io import fits
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from difmap_wrapper import standardizer

from .config import ProofConfig
from .utils import ensure_dir, parse_win_file, write_json


def _read_fits_image(path: Path) -> np.ndarray:
    with fits.open(path) as hdul:
        return hdul[0].data.squeeze().astype(np.float32)


def _save_uvplot_png(fig_dir: Path, base: str, data_src: dict, data_wrap: dict, uv_metrics: dict) -> None:
    u_src = data_src["u"] / 1e6
    v_src = data_src["v"] / 1e6
    u_w = data_wrap["u"] / 1e6
    v_w = data_wrap["v"] / 1e6
    diff_u = uv_metrics["diff_u"]

    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    fig.suptitle(f"UVPLOT (GEOMETRIE) : {base}", fontsize=14)

    axes[0].scatter(u_src, v_src, s=0.3, color="black", alpha=0.5)
    axes[0].set_title("DIFMAP_SRC")

    axes[1].scatter(u_w, v_w, s=0.3, color="blue", alpha=0.5)
    axes[1].set_title("DIFMAP_WRAPPER")

    sc = axes[2].scatter(u_w, diff_u, s=2, c=diff_u, cmap="coolwarm")
    axes[2].set_title("Résidus ΔU (λ brutes)")
    fig.colorbar(sc, ax=axes[2], label="ΔU")

    for i, ax in enumerate(axes):
        ax.grid(True, linestyle=":", alpha=0.6)
        ax.set_xlabel(r"U (M$\lambda$)")
        if i < 2:
            ax.set_ylabel(r"V (M$\lambda$)")
            ax.axis("equal")
            ax.invert_xaxis()

    plt.tight_layout()
    fig.savefig(fig_dir / f"{base}__uvplot.png", dpi=150)
    plt.close(fig)


def _save_radplot_png(fig_dir: Path, base: str, data_src: dict, data_wrap: dict, uv_metrics: dict) -> None:
    r_src = data_src["uv_radius"]
    amp_src = data_src["amp"]
    r_w = data_wrap["uv_radius"]
    amp_w = data_wrap["amp"]
    diff_amp = uv_metrics["diff_amp"]

    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    fig.suptitle(f"RADPLOT (AMPLITUDE) : {base}", fontsize=14)

    axes[0].scatter(r_src, amp_src, s=0.5, color="black", alpha=0.5)
    axes[0].set_title("DIFMAP_SRC")
    axes[0].set_ylabel("Amplitude (Jy)")

    axes[1].scatter(r_w, amp_w, s=0.5, color="blue", alpha=0.5)
    axes[1].set_title("DIFMAP_WRAPPER")

    sc = axes[2].scatter(r_w, diff_amp, s=2, c=diff_amp, cmap="coolwarm")
    axes[2].set_title("Résidus ΔAmp (Jy)")
    axes[2].axhline(0.0, color="black", linestyle="--", linewidth=0.8)
    fig.colorbar(sc, ax=axes[2], label="ΔAmp")

    for ax in axes:
        ax.grid(True, linestyle=":", alpha=0.6)
        ax.set_xlabel(r"Rayon UV (M$\lambda$)")

    plt.tight_layout()
    fig.savefig(fig_dir / f"{base}__radplot.png", dpi=150)
    plt.close(fig)


def _save_map_png(fig_dir: Path, base: str, kind: str, img_src: np.ndarray, img_wrap: np.ndarray, metrics: dict) -> None:
    diff = metrics["diff_map"]
    vmax = float(np.nanmax(np.abs(diff))) if diff.size else 0.0

    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    fig.suptitle(f"{kind.upper()} MAP : {base}", fontsize=14)

    im0 = axes[0].imshow(img_src, origin="lower", cmap="inferno")
    axes[0].set_title("DIFMAP_SRC")
    fig.colorbar(im0, ax=axes[0], fraction=0.046, pad=0.04)

    im1 = axes[1].imshow(img_wrap, origin="lower", cmap="inferno")
    axes[1].set_title("DIFMAP_WRAPPER")
    fig.colorbar(im1, ax=axes[1], fraction=0.046, pad=0.04)

    im2 = axes[2].imshow(diff, origin="lower", cmap="coolwarm", vmin=-vmax, vmax=vmax)
    axes[2].set_title(f"DIFF (WRAPPER - SRC)\nerr_max={metrics['err_max']:.2e}")
    fig.colorbar(im2, ax=axes[2], fraction=0.046, pad=0.04)

    for ax in axes:
        ax.set_xticks([])
        ax.set_yticks([])

    plt.tight_layout()
    fig.savefig(fig_dir / f"{base}__{kind}.png", dpi=150)
    plt.close(fig)


def compare_outputs(cfg: ProofConfig, src_workdir: Path, wrapper_workdir: Path) -> None:
    ensure_dir(cfg.out_compare)
    fig_dir = cfg.out_compare / "figures"
    ensure_dir(fig_dir)

    # Compare sur tous les couples de fichiers présents (basé sur les FITS wrapper).
    wrapper_fits = sorted(wrapper_workdir.glob("*_uv.fits"))
    if not wrapper_fits:
        raise FileNotFoundError(f"Aucun *_uv.fits trouvé dans {wrapper_workdir}")

    summary: dict[str, dict] = {}

    for w_uv in wrapper_fits:
        base = w_uv.name.replace("_uv.fits", "")

        s_uv = src_workdir / f"{base}_uv.fits"
        w_dirty = wrapper_workdir / f"{base}_dirty.fits"
        s_dirty = src_workdir / f"{base}_dirty.fits"
        w_res = wrapper_workdir / f"{base}_residual.fits"
        s_res = src_workdir / f"{base}_residual.fits"
        w_clean = wrapper_workdir / f"{base}_clean.fits"
        s_clean = src_workdir / f"{base}_clean.fits"

        w_win = wrapper_workdir / f"{base}_state.win"
        s_win = src_workdir / f"{base}_state.win"

        print(f"COMPARE: dataset={base}")

        # ------------------------------------------------------------------
        # UVPLOT + RADPLOT via UVFITS
        # ------------------------------------------------------------------
        print(f"DIFMAP_SRC: uv_export={s_uv.name}")
        data_src = standardizer.extract_uvfits_standardized(str(s_uv))
        print(f"DIFMAP_WRAPPER: uv_export={w_uv.name}")
        data_wrap = standardizer.extract_uvfits_standardized(str(w_uv))

        uv_metrics = standardizer.compare_uv_datasets(data_src, data_wrap)

        # ------------------------------------------------------------------
        # Images pixel-à-pixel
        # ------------------------------------------------------------------
        img_dirty_src = _read_fits_image(s_dirty)
        img_dirty_wrap = _read_fits_image(w_dirty)
        dirty_metrics = standardizer.compare_images(img_dirty_src, img_dirty_wrap)

        img_res_src = _read_fits_image(s_res)
        img_res_wrap = _read_fits_image(w_res)
        res_metrics = standardizer.compare_images(img_res_src, img_res_wrap)

        img_clean_src = _read_fits_image(s_clean)
        img_clean_wrap = _read_fits_image(w_clean)
        clean_metrics = standardizer.compare_images(img_clean_src, img_clean_wrap)

        _save_uvplot_png(fig_dir, base, data_src, data_wrap, uv_metrics)
        _save_radplot_png(fig_dir, base, data_src, data_wrap, uv_metrics)
        _save_map_png(fig_dir, base, "dirty", img_dirty_src, img_dirty_wrap, dirty_metrics)
        _save_map_png(fig_dir, base, "residual", img_res_src, img_res_wrap, res_metrics)
        _save_map_png(fig_dir, base, "clean", img_clean_src, img_clean_wrap, clean_metrics)

        # ------------------------------------------------------------------
        # Fenêtres
        # ------------------------------------------------------------------
        win_src = parse_win_file(s_win)
        win_wrap = parse_win_file(w_win)

        windows_ok = win_src == win_wrap

        uv_part = (
            f"ΔUmax={uv_metrics['delta_u_max']:.2e} λ, "
            f"ΔVmax={uv_metrics['delta_v_max']:.2e} λ, "
            f"ΔAmpmax={uv_metrics['delta_amp_max']:.2e} Jy, "
            f"amp_rmse={uv_metrics['amp_rmse']:.2e} Jy"
        )
        img_part = (
            f"dirty_err_max={dirty_metrics['err_max']:.2e}, "
            f"residual_err_max={res_metrics['err_max']:.2e}, "
            f"clean_err_max={clean_metrics['err_max']:.2e}"
        )
        win_part = f"windows_count={len(win_src)} equal={windows_ok}"

        # On imprime volontairement les mêmes champs des deux côtés.
        # Les métriques sont *des comparaisons* (SRC vs WRAPPER) mais on les affiche
        # sous les deux préfixes pour que la lecture soit symétrique.
        print(f"DIFMAP_SRC: {uv_part}")
        print(f"DIFMAP_SRC: {img_part}")
        print(f"DIFMAP_SRC: {win_part}")

        print(f"DIFMAP_WRAPPER: {uv_part}")
        print(f"DIFMAP_WRAPPER: {img_part}")
        print(f"DIFMAP_WRAPPER: {win_part}")

        summary[base] = {
            "uv": {k: float(uv_metrics[k]) for k in ("delta_u_max", "delta_v_max", "delta_amp_max", "amp_rmse")},
            "dirty": {k: float(dirty_metrics[k]) for k in ("err_max", "rmse", "std_err")},
            "residual": {k: float(res_metrics[k]) for k in ("err_max", "rmse", "std_err")},
            "clean": {k: float(clean_metrics[k]) for k in ("err_max", "rmse", "std_err")},
            "windows": {
                "src_count": len(win_src),
                "wrapper_count": len(win_wrap),
                "equal": bool(windows_ok),
            },
        }

    write_json(cfg.out_compare / "summary.json", summary)
