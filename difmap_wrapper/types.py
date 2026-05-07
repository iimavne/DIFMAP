# difmap_wrapper/enums.py
"""
Constantes typées pour les états des éditeurs et de l'interface.

Implémentées comme classes simples (pas d'Enum) pour rester 100%
compatibles avec les comparaisons string/int existantes dans tout le code.
Exemples : EditorMode.ZOOM == "ZOOM" → True, TabIndex.UV == 0 → True.
"""
from typing import Literal

# ---------------------------------------------------------------------------
# Polarisation — liste exhaustive issue de difmap_src/stokes.c (Stokes_table)
# Stokes  : I  Q  U  V
# Circulaire : RR  LL  RL  LR
# Linéaire   : XX  YY  XY  YX
# Pseudo-I   : PI  (moyenne des mains parallèles, (RR+LL)/2 ou (XX+YY)/2)
# ---------------------------------------------------------------------------
Polarization = Literal[
    "I",  "Q",  "U",  "V",
    "RR", "LL", "RL", "LR",
    "XX", "YY", "XY", "YX",
    "PI",
]

# Toutes les valeurs valides comme tuple (utile pour les validations runtime)
POLARIZATIONS: tuple[str, ...] = (
    "I",  "Q",  "U",  "V",
    "RR", "LL", "RL", "LR",
    "XX", "YY", "XY", "YX",
    "PI",
)

# ---------------------------------------------------------------------------
# Unités UV — le wrapper utilise toujours les Mega-longueurs d'onde (Mλ).
# La valeur 1e6 est utilisée pour convertir les coordonnées u,v (en λ) vers Mλ.
# Centraliser ici permet de changer l'unité en un seul endroit si nécessaire.
# ---------------------------------------------------------------------------
UV_UNIT_SCALE: float = 1e6   # λ → Mλ
UV_UNIT_LABEL: str   = "Mλ"


class EditorMode:
    """Modes d'interaction de l'éditeur graphique (souris/clavier)."""
    INSPECT         = None           # Mode par défaut : inspecter au clic
    ZOOM            = "ZOOM"
    CUT             = "CUT"
    PAN             = "PAN"
    STATS           = "STATS"
    STATS_V         = "STATS_V"
    ZOOM_X          = "ZOOM_X"
    INTERACTIVE_FLAG = "INTERACTIVE_FLAG"  # flagging souris (gauche=flag, droit=unflag)
    ZOOM_Y           = "ZOOM_Y"            # zoom vertical axe Y (radplot)

    # Ensemble des modes qui activent le RectangleSelector
    ALL_RECT = frozenset(["ZOOM", "CUT", "STATS", "STATS_V"])


class DisplayMode:
    """Modes d'affichage du Radplot (entiers pour compatibilité avec le code existant)."""
    AMP_ONLY   = 1
    PHASE_ONLY = 2
    BOTH       = 3


class TabIndex:
    """
    Indices des onglets dans QTabWidget.
    """
    UV       = 0
    RADPLOT  = 1
    MAP      = 2   # Dirty Map
    CLEAN    = 3   # Clean Map (restaurée)
    RESIDUAL = 4   # Residual Map (après clean(), avant restore())
    HEADER   = 5
