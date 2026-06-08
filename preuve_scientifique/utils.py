from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import asdict
from pathlib import Path
from typing import Iterable


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def clean_dir(p: Path) -> None:
    if p.exists():
        shutil.rmtree(p)
    p.mkdir(parents=True, exist_ok=True)


def run_subprocess(
    *,
    argv: list[str],
    cwd: Path,
    env: dict[str, str] | None = None,
    timeout_s: int = 600,
    label: str,
) -> subprocess.CompletedProcess:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)

    print(f"{label}: RUN {' '.join(argv)}")
    proc = subprocess.run(
        argv,
        cwd=str(cwd),
        env=merged_env,
        text=True,
        capture_output=True,
        timeout=timeout_s,
    )

    if proc.returncode != 0:
        tail_out = (proc.stdout or "")[-4000:]
        tail_err = (proc.stderr or "")[-4000:]
        raise RuntimeError(
            f"{label}: subprocess failed (rc={proc.returncode})\n"
            f"STDOUT (tail):\n{tail_out}\n\nSTDERR (tail):\n{tail_err}"
        )

    return proc


def write_json(path: Path, payload: dict) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def list_uv_inputs(test_data_dir: Path) -> list[Path]:
    # Jeux utilisés dans la suite de tests.
    patterns = ["*_X.SPLIT.1", "*.uvfits", "*.UVFITS"]
    found: list[Path] = []
    for pat in patterns:
        found.extend(sorted(test_data_dir.glob(pat)))
    # Dédupliquer en gardant l'ordre.
    uniq: list[Path] = []
    seen: set[Path] = set()
    for p in found:
        rp = p.resolve()
        if rp not in seen and p.is_file():
            seen.add(rp)
            uniq.append(p)
    if not uniq:
        raise FileNotFoundError(f"Aucun dataset trouvé dans {test_data_dir}")
    return uniq


def copy_inputs_to_workdir(inputs: Iterable[Path], workdir: Path) -> list[Path]:
    ensure_dir(workdir)
    copied = []
    for p in inputs:
        dst = workdir / p.name
        shutil.copy(p, dst)
        copied.append(dst)
    return copied


def parse_win_file(path: Path) -> list[tuple[float, float, float, float]]:
    """Parse très simple des fichiers .win exportés par difmap.

    On vise une comparaison robuste : extraire uniquement les 4 nombres des
    fenêtres rectangulaires quand ils apparaissent dans une ligne.
    """
    windows: list[tuple[float, float, float, float]] = []
    if not path.exists():
        return windows

    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line:
            continue
        # Extraire tous les floats sur la ligne.
        toks = []
        for t in line.replace(",", " ").split():
            try:
                toks.append(float(t))
            except ValueError:
                continue
        if len(toks) >= 4:
            xa, xb, ya, yb = toks[:4]
            windows.append((min(xa, xb), max(xa, xb), min(ya, yb), max(ya, yb)))

    return windows
