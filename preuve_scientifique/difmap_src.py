from __future__ import annotations

from pathlib import Path

from .config import ProofConfig
from .utils import clean_dir, copy_inputs_to_workdir, ensure_dir, run_subprocess


def _difmap_script_lines(
    *,
    uv_filename: str,
    pol: str,
    mapsize: int,
    cellsize: float,
    clean_niter: int,
    clean_gain: float,
    output_prefix: str,
    windows: list[tuple[float, float, float, float]],
) -> list[str]:
    lines: list[str] = []

    lines.append(f"observe {uv_filename}")
    lines.append(f"select {pol}")
    lines.append(f"mapsize {mapsize},{cellsize}")

    # Dirty map
    lines.append("invert")
    lines.append(f"wdmap {output_prefix}_dirty.fits")
    lines.append(f"wbeam {output_prefix}_beam.fits")

    # Fenêtres
    lines.append("delwin")
    for xa, xb, ya, yb in windows:
        # difmap accepte classiquement addwin xa,xb,ya,yb
        lines.append(f"addwin {xa},{xb},{ya},{yb}")

    # Sauvegarder l'état (inclut un .win)
    lines.append(f"save {output_prefix}_state")

    # CLEAN en deux temps pour capturer le résiduel avant restore()
    lines.append(f"clean {clean_niter},{clean_gain}")
    lines.append(f"wdmap {output_prefix}_residual.fits")

    lines.append("restore")
    lines.append(f"wmap {output_prefix}_clean.fits")

    # UV export : utile pour uvplot/radplot
    lines.append(f"wobs {output_prefix}_uv.fits")

    lines.append("quit")
    return lines


def generate_difmap_src_outputs(cfg: ProofConfig, uv_paths: list[Path]) -> Path:
    """Génère tous les artefacts DIFMAP_SRC dans cfg.out_src."""
    clean_dir(cfg.out_src)

    workdir = cfg.out_src / "work"
    ensure_dir(workdir)
    copied = copy_inputs_to_workdir(uv_paths, workdir)

    print(f"DIFMAP_SRC: difmap executable = {cfg.difmap_executable}")

    # Fenêtres fixes (mas). Le but est de comparer le fichier .win et l'effet sur CLEAN.
    windows = [
        (-2.0, 2.0, -2.0, 2.0),
        (-10.0, -6.0, 4.0, 8.0),
    ]

    for uv in copied:
        stem = uv.name.replace(".uvfits", "").replace(".UVFITS", "")
        prefix = f"{stem}_{cfg.pol}"

        script_lines = _difmap_script_lines(
            uv_filename=uv.name,
            pol=cfg.pol,
            mapsize=cfg.mapsize,
            cellsize=cfg.cellsize,
            clean_niter=cfg.clean_niter,
            clean_gain=cfg.clean_gain,
            output_prefix=prefix,
            windows=windows,
        )
        script = "\n".join(script_lines) + "\n"

        # Exécution avec script injecté via stdin.
        # On évite les pipes complexes : on écrit le script dans un fichier.
        cmd_path = workdir / f"{prefix}.cmd"
        cmd_path.write_text(script, encoding="utf-8")

        run_subprocess(
            argv=["bash", "-lc", f"{cfg.difmap_executable} < {cmd_path.name}"],
            cwd=workdir,
            env=None,
            timeout_s=900,
            label="DIFMAP_SRC",
        )

    return workdir
