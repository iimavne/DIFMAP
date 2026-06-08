from __future__ import annotations

from pathlib import Path

import numpy as np

import difmap_native
from difmap_wrapper import DifmapSession

from .config import ProofConfig
from .utils import clean_dir, ensure_dir


def generate_difmap_wrapper_outputs(cfg: ProofConfig, uv_paths: list[Path]) -> Path:
    """Génère tous les artefacts DIFMAP_WRAPPER dans cfg.out_wrapper."""
    clean_dir(cfg.out_wrapper)

    workdir = cfg.out_wrapper / "work"
    ensure_dir(workdir)

    print("DIFMAP_WRAPPER: start generation")

    windows = [
        (-2.0, 2.0, -2.0, 2.0),
        (-10.0, -6.0, 4.0, 8.0),
    ]

    for uv in uv_paths:
        stem = uv.name.replace(".uvfits", "").replace(".UVFITS", "")
        prefix = f"{stem}_{cfg.pol}"

        with DifmapSession() as session:
            print(f"DIFMAP_WRAPPER: observe {uv}")
            session.observe(str(uv))
            session.obs.select(pol=cfg.pol)

            session.imager.mapsize(cfg.mapsize, cfg.cellsize)
            session.imager.invert()

            # Dirty map
            difmap_native.wdmap(str(workdir / f"{prefix}_dirty.fits"))
            difmap_native.wbeam(str(workdir / f"{prefix}_beam.fits"))

            # Fenêtres
            difmap_native.delwin()
            for xa, xb, ya, yb in windows:
                difmap_native.addwin(float(xa), float(xb), float(ya), float(yb))

            # Sauvegarde état (produit .win, .par, etc.)
            session.save(str(workdir / f"{prefix}_state"))

            # CLEAN : capturer le résiduel avant restore()
            session.imager.clean(niter=cfg.clean_niter, gain=cfg.clean_gain)
            difmap_native.wdmap(str(workdir / f"{prefix}_residual.fits"))

            session.imager.restore()
            difmap_native.wmap(str(workdir / f"{prefix}_clean.fits"))

            # UV export
            difmap_native.wfits(str(workdir / f"{prefix}_uv.fits"))

            # Sanity prints
            try:
                win_list = difmap_native.get_windows()
            except Exception:
                win_list = []
            print(f"DIFMAP_WRAPPER: windows_count={len(win_list)}")

    return workdir
