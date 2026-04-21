# difmap_wrapper/enums.py
"""
Constantes typées pour les états des éditeurs et de l'interface.

Implémentées comme classes simples (pas d'Enum) pour rester 100%
compatibles avec les comparaisons string/int existantes dans tout le code.
Exemples : EditorMode.ZOOM == "ZOOM" → True, TabIndex.UV == 0 → True.
"""


class EditorMode:
    """Modes d'interaction de l'éditeur graphique (souris/clavier)."""
    INSPECT         = None           # Mode par défaut : inspecter au clic
    ZOOM            = "ZOOM"
    CUT             = "CUT"
    PAN             = "PAN"
    STATS           = "STATS"
    STATS_V         = "STATS_V"
    ZOOM_X          = "ZOOM_X"
    INTERACTIVE_FLAG = "INTERACTIVE_FLAG"  # Nouveau : flagging souris (gauche=flag, droit=unflag)

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
    UV      = 0
    RADPLOT = 1
    MAP     = 2
