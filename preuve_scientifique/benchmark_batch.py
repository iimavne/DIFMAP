from __future__ import annotations

import time
from pathlib import Path

from difmap_wrapper import DifmapBatchManager, DifmapSession

from .config import default_config
from .utils import ensure_dir, list_uv_inputs, write_json


def _worker_make_dirty_map(uv_path: str) -> dict:
    start = time.perf_counter()
    with DifmapSession() as session:
        session.observe(uv_path)
        session.obs.select(pol="RR")
        session.imager.mapsize(512, 0.1)
        session.imager.invert()
        # On force un accès pour matérialiser le coût.
        _ = session.imager.get_map()
    end = time.perf_counter()
    return {"file": uv_path, "elapsed_s": end - start}


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    cfg = default_config(repo_root)

    out_dir = cfg.out_benchmark
    ensure_dir(out_dir)

    uv_paths = [str(p) for p in list_uv_inputs(cfg.test_data_dir)]

    # Limiter pour un benchmark stable par défaut.
    uv_paths = uv_paths[:10]

    # ------------------------------------------------------------
    # Séquentiel
    # ------------------------------------------------------------
    t0 = time.perf_counter()
    seq_results = [_worker_make_dirty_map(p) for p in uv_paths]
    t1 = time.perf_counter()

    # ------------------------------------------------------------
    # Parallèle
    # ------------------------------------------------------------
    manager = DifmapBatchManager(max_workers=4)
    t2 = time.perf_counter()
    par_results = manager.run_batch(_worker_make_dirty_map, uv_paths, max_workers=4)
    t3 = time.perf_counter()

    seq_total = t1 - t0
    par_total = t3 - t2

    report = {
        "n_files": len(uv_paths),
        "sequential": {
            "total_s": seq_total,
            "per_file_s": [r["elapsed_s"] for r in seq_results],
        },
        "parallel": {
            "total_s": par_total,
            "per_file_s": [r["elapsed_s"] for r in par_results],
            "max_workers": 4,
        },
        "speedup": (seq_total / par_total) if par_total > 0 else None,
    }

    print(f"DIFMAP_WRAPPER_BATCH: sequential_total_s={seq_total:.3f}")
    print(f"DIFMAP_WRAPPER_BATCH: parallel_total_s={par_total:.3f}")
    print(f"DIFMAP_WRAPPER_BATCH: speedup={report['speedup']:.2f}x")

    write_json(out_dir / "benchmark_report.json", report)


if __name__ == "__main__":
    main()
