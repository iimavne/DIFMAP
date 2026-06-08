from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProofConfig:
    repo_root: Path
    test_data_dir: Path
    out_dir: Path
    out_src: Path
    out_wrapper: Path
    out_compare: Path
    out_benchmark: Path

    difmap_executable: str = "difmap"

    pol: str = "RR"
    mapsize: int = 512
    cellsize: float = 0.1

    clean_niter: int = 100
    clean_gain: float = 0.05


def default_config(repo_root: Path) -> ProofConfig:
    out_dir = repo_root / "preuve_scientifique" / "out"
    return ProofConfig(
        repo_root=repo_root,
        test_data_dir=repo_root / "tests" / "test_data",
        out_dir=out_dir,
        out_src=out_dir / "difmap_src",
        out_wrapper=out_dir / "difmap_wrapper",
        out_compare=out_dir / "compare",
        out_benchmark=out_dir / "benchmark",
    )
