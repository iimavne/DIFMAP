# difmap_wrapper/__init__.py
import sys
import importlib

import difmap_native
from .core.session import DifmapSession
from .core.observation import Observation
from .core.imaging import DifmapImager
from .core.visualizer import Visualizer
from .core.manager import DifmapBatchManager
from .utils.exceptions import DifmapError, DifmapStateError

from . import core
from . import utils

__all__ = [
    "DifmapSession",
    "Observation",
    "DifmapImager",
    "Visualizer",
    "DifmapBatchManager",
    "DifmapError",
    "DifmapStateError",
    "core",
    "utils",
]


def _alias_module(name: str, attrs: dict) -> None:
    std_types = importlib.import_module("types")
    mod = std_types.ModuleType(name)
    mod.__dict__.update(attrs)
    sys.modules[name] = mod


# ---------------------------------------------------------------------------
# Compatibility aliases
#
# In editable installs via meson-python, the package __path__ can point to an
# overlay location that doesn't automatically expose new root-level modules.
# We publish legacy import paths explicitly so tests and user code can do:
#   from difmap_wrapper.session import DifmapSession
# ---------------------------------------------------------------------------

_alias_module(__name__ + ".session", {"DifmapSession": DifmapSession})
_alias_module(__name__ + ".manager", {"DifmapBatchManager": DifmapBatchManager})
_alias_module(__name__ + ".visualizer", {"Visualizer": Visualizer})
_alias_module(__name__ + ".observation", {"Observation": Observation})
_alias_module(__name__ + ".imaging", {"DifmapImager": DifmapImager})
_alias_module(
    __name__ + ".exceptions",
    {"DifmapError": DifmapError, "DifmapStateError": DifmapStateError},
)

session = sys.modules[__name__ + ".session"]
manager = sys.modules[__name__ + ".manager"]
visualizer = sys.modules[__name__ + ".visualizer"]
observation = sys.modules[__name__ + ".observation"]
imaging = sys.modules[__name__ + ".imaging"]
exceptions = sys.modules[__name__ + ".exceptions"]

from .utils.map_geometry import DifmapMapGeometry, get_difmap_contour_levels
from .utils import standardizer as _standardizer

_alias_module(
    __name__ + ".map_geometry",
    {
        "DifmapMapGeometry": DifmapMapGeometry,
        "get_difmap_contour_levels": get_difmap_contour_levels,
    },
)

map_geometry = sys.modules[__name__ + ".map_geometry"]

_alias_module(__name__ + ".standardizer", _standardizer.__dict__)
standardizer = sys.modules[__name__ + ".standardizer"]

editors_mod_name = __name__ + ".editors"
if editors_mod_name not in sys.modules:
    _alias_module(editors_mod_name, {})
try:
    from .gui.editors.rad_editor import RadPlotEditor

    _alias_module(editors_mod_name + ".rad_editor", {"RadPlotEditor": RadPlotEditor})
except Exception:
    # L'import GUI peut échouer en environnement headless; on laisse le module
    # indisponible plutôt que de casser l'import de base du package.
    pass
