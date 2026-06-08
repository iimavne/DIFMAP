from __future__ import annotations

import re
from pathlib import Path

import numpy as np
from astropy.io import fits

import difmap_native
from difmap_wrapper import DifmapSession
from difmap_wrapper import standardizer

from .config import default_config
from .utils import ensure_dir, list_uv_inputs, run_subprocess, write_json


_READING_RE = re.compile(r"Reading\s+(\d+)\s+visibilities\.")


def _count_vis_from_cli_output(stdout: str) -> int:
    matches = _READING_RE.findall(stdout or "")
    if not matches:
        raise RuntimeError("Impossible de trouver la ligne 'Reading N visibilities.' dans la sortie DIFMAP_SRC")
    return int(matches[-1])


def _count_vis_wrapper(uv_path: Path, pol: str) -> int:
    with DifmapSession() as session:
        print(f"DIFMAP_WRAPPER: observe {uv_path}")
        session.observe(str(uv_path))
        session.obs.select(pol=pol)
        data = session.obs.get_data()
        w = data.get("weight")
        if w is None:
            return int(len(data.get("u", [])))
        return int((w > 0).sum())


def _count_vis_wrapper_raw(uv_path: Path, pol: str) -> int:
    """Compteur brut, analogue à 'Reading N visibilities.' côté CLI.

    DIFMAP_SRC l'affiche au moment de la lecture UVFITS (uvf_read.c) comme :

        GCOUNT * NCHAN * NIF * NPOL

    Ici on reproduit exactement ce calcul en lisant le fichier UVFITS d'origine.
    """
    with fits.open(uv_path) as hdul:
        hdr = hdul[0].header
        d = hdul[0].data

        gcount = int(hdr.get("GCOUNT", 0))
        if gcount <= 0:
            # Fallback : certains dialectes peuvent ne pas avoir GCOUNT utilisable
            # → on se rabat sur le nombre de groupes dans la table.
            gcount = int(len(d))

        # On infère NCHAN/NIF/NPOL à partir de la forme du champ DATA.
        # Dernier axe = (Re, Im, Wt).
        d_sq = d["DATA"]
        shape = d_sq.shape
        if len(shape) < 2:
            raise RuntimeError(f"UVFITS inattendu: DATA.shape={shape}")

        # Produit des dimensions après l'axe groupe et avant l'axe (Re,Im,Wt)
        per_group = int(np.prod(shape[1:-1])) if len(shape) > 2 else 1
        return int(gcount * per_group)


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    cfg = default_config(repo_root)

    out_dir = cfg.out_compare / "visibility_count"
    ensure_dir(out_dir)

    uv_paths = list_uv_inputs(cfg.test_data_dir)

    report: dict[str, dict] = {}

    for uv in uv_paths:
        stem = uv.name
        workdir = out_dir / stem
        ensure_dir(workdir)

        # 1) DIFMAP_SRC : on exporte les UV sélectionnés via wobs.
        # Cela permet d'obtenir un compteur comparable à ce que manipule le wrapper
        # (visibilités actives, poids > 0).
        uv_out = workdir / "src_uv.fits"
        script = "\n".join(
            [
                f"observe {uv}",
                f"select {cfg.pol}",
                f"wobs {uv_out.name}",
                "quit",
            ]
        ) + "\n"

        cmd_path = workdir / "script.cmd"
        cmd_path.write_text(script, encoding="utf-8")

        proc = run_subprocess(
            argv=["bash", "-lc", f"{cfg.difmap_executable} < {cmd_path.name}"],
            cwd=workdir,
            env=None,
            timeout_s=900,
            label="DIFMAP_SRC",
        )

        # Compteur brut DIFMAP (informatif) : "Reading N visibilities.".
        # Attention : ce chiffre inclut des visibilités qui peuvent ensuite être
        # rendues inactives (poids<=0) par le pipeline AIPS/flags.
        n_src_raw = _count_vis_from_cli_output(proc.stdout)

        # Compteur comparable : visibilités actives exportées dans le UVFITS.
        data_src = standardizer.extract_uvfits_standardized(str(uv_out))
        n_src_active = int(len(data_src.get("u", [])))

        n_wrap_active = _count_vis_wrapper(uv, cfg.pol)
        n_wrap_raw = _count_vis_wrapper_raw(uv, cfg.pol)
        ok_active = n_src_active == n_wrap_active
        ok_raw = n_src_raw == n_wrap_raw

        print(f"DIFMAP_SRC: file={stem} n_vis_raw={n_src_raw} n_vis_active={n_src_active}")
        print(f"DIFMAP_WRAPPER: file={stem} n_vis_raw={n_wrap_raw} n_vis_active={n_wrap_active}")
        print(f"COMPARE_VIS_COUNT: raw_equal={ok_raw} active_equal={ok_active}")

        report[stem] = {
            "difmap_src": {
                "n_vis_raw": n_src_raw,
                "n_vis_active": n_src_active,
            },
            "difmap_wrapper": {
                "n_vis_raw": n_wrap_raw,
                "n_vis_active": n_wrap_active,
            },
            "raw_equal": ok_raw,
            "active_equal": ok_active,
        }

    write_json(out_dir / "visibility_count_report.json", report)


if __name__ == "__main__":
    main()
