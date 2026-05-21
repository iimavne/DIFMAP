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
    INSPECT          = None
    ZOOM             = "ZOOM"
    CUT              = "CUT"
    PAN              = "PAN"
    STATS            = "STATS"
    STATS_V          = "STATS_V"
    ZOOM_X           = "ZOOM_X"
    INTERACTIVE_FLAG = "INTERACTIVE_FLAG"
    ZOOM_Y           = "ZOOM_Y"

    ALL_RECT = frozenset(["ZOOM", "CUT", "STATS", "STATS_V"])


class DisplayMode:
    """Modes d'affichage du Radplot (entiers pour compatibilité avec le code existant)."""
    AMP_ONLY   = 1
    PHASE_ONLY = 2
    BOTH       = 3


class TabIndex:
    """
    Indices logiques des onglets (flat, indépendants de la hiérarchie UI).

    Outer (super-onglets) :
        OUTER_HEADER     = 0  → Header
        OUTER_GRAPHIQUES = 1  → Graphiques
        OUTER_IMAGERIE   = 2  → Imagerie

    Inner Graphiques :
        UV      = 0  (inner index 0)
        RADPLOT = 1  (inner index 1)

    Inner Imagerie :
        MAP      = 2  (inner index 0)
        RESIDUAL = 4  (inner index 1)
        CLEAN    = 3  (inner index 2)
        ALL_MAPS = 6  (inner index 3)

    HEADER = 5 reste le code logique renvoyé par _get_logical_tab().
    """
    UV       = 0
    RADPLOT  = 1
    MAP      = 2
    CLEAN    = 3
    RESIDUAL = 4
    HEADER   = 5
    ALL_MAPS = 6

    OUTER_HEADER     = 0
    OUTER_GRAPHIQUES = 1
    OUTER_IMAGERIE   = 2
