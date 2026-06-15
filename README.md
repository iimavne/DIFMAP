# difmap_smartedit

Python wrapper for [Difmap](https://science.nrao.edu/facilities/vlba/docs/manuals/oss2013b/post-processing-software/difmap) — VLBI radio-interferometry imaging via a clean Python API and an optional PyQt6 GUI.

## What it does

- Load FITS/UVFITS visibility files and access raw UV data as NumPy arrays
- Full imaging pipeline: gridding (`mapsize`), weighting (`uvweight`, `uvtaper`), dirty map (`invert`), CLEAN (`clean`), self-calibration (`selfcal`), restore
- Interactive PyQt6 GUI with real-time radplot, UV-coverage, and map display
- Parallel batch processing for large datasets

## Requirements

### System (build-time)

```
gcc / gfortran
meson >= 1.0
ninja
cython >= 3.0
```

On Ubuntu/Debian:
```bash
sudo apt install build-essential gfortran meson ninja-build
```

### Python

- Python >= 3.8
- numpy >= 2.0, astropy, matplotlib, PyQt6, qtawesome

## Installation

```bash
git clone https://github.com/iimavne/DIFMAP.git
cd DIFMAP
pip install .
```

`pip` will invoke Meson automatically to compile the C/Cython binding (`difmap_native`).

> **Note:** The first install takes ~1–2 minutes because it compiles ~300 C source files.

### For development

```bash
pip install -e ".[dev]"
```

## Quick start

### Python API

```python
from difmap_wrapper.core.session import DifmapSession

with DifmapSession() as session:
    session.observe("data/source.uvfits")
    session.obs.select(pol="RR")

    data = session.obs.get_data()
    print(f"{len(data['amp'])} visibilities, mean amp = {data['amp'].mean():.3f} Jy")

    session.imager.mapsize(512, 0.1)   # 512×512 grid, 0.1 mas/pixel
    session.imager.invert()
    pkg = session.imager.get_map_package(cellsize=0.1)
    session.vis.plot_image(pkg)
```

### GUI

```bash
difmap-gui
```

Then: **File → Open** to load a UVFITS file.

### Jupyter

See [demo.ipynb](demo.ipynb) for a step-by-step walkthrough.

## Running tests

```bash
pytest tests/
```

Test data is in `tests/test_data/`.

## Project structure

```
binding/          Cython binding to the C engine (difmap_native.pyx)
difmap_src/       Original Difmap C source code
difmap_wrapper/
  core/           Python API (session, observation, imaging)
  gui/            PyQt6 interface (main window, widgets, editors)
  utils/          Shared utilities (geometry, exceptions, annotations)
  app.py          GUI entry point
tests/            pytest test suite
scripts/          Standalone analysis and benchmark scripts
docs/             Quarto documentation
demo/             Demo data and PDF
demo.ipynb        Jupyter demo notebook
```

## License

Caltech non-commercial license — see [README](README) for the original terms.
