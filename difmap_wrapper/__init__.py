# difmap_wrapper/__init__.py

# 1. On importe les classes pour l'API publique (accès direct)
from .session import DifmapSession
from .observation import Observation
from .imaging import DifmapImager
from .visualizer import Visualizer
from .manager import DifmapBatchManager
from .exceptions import DifmapError, DifmapStateError

# 2. On importe AUSSI les modules sous-jacents pour que Quartodoc
#    puisse remonter à la source et lire les docstrings
from . import session
from . import observation
from . import imaging
from . import visualizer
from . import manager
from . import exceptions

# 3. On déclare tout ce petit monde comme public
__all__ = [
    # API publique
    "DifmapSession",
    "Observation",
    "DifmapImager",
    "Visualizer",
    "DifmapBatchManager",
    "DifmapError",
    "DifmapStateError",
    
    # Autorisation pour Quartodoc
    "session",
    "observation",
    "imaging",
    "visualizer",
    "manager",
    "exceptions"
]
