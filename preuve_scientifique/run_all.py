from __future__ import annotations

from pathlib import Path

from .config import default_config
from .difmap_src import generate_difmap_src_outputs
from .difmap_wrapper import generate_difmap_wrapper_outputs
from .compare import compare_outputs
from .utils import list_uv_inputs


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    cfg = default_config(repo_root)

    uv_paths = list_uv_inputs(cfg.test_data_dir)

    print(f"RUN_ALL: datasets={len(uv_paths)}")

    src_workdir = generate_difmap_src_outputs(cfg, uv_paths)
    wrapper_workdir = generate_difmap_wrapper_outputs(cfg, uv_paths)

    compare_outputs(cfg, src_workdir, wrapper_workdir)

    print(f"RUN_ALL: done. See {cfg.out_dir}")


if __name__ == "__main__":
    main()
