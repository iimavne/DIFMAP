# difmap_wrapper/gui/components/main_toolbar.py
from PyQt6.QtWidgets import QToolBar, QLabel, QSizePolicy, QWidget, QComboBox
from PyQt6.QtGui import QAction
from PyQt6.QtCore import QSize, Qt

try:
    import qtawesome as qta
    _HAS_QTA = True
except ImportError:
    _HAS_QTA = False

def _icon(name, color="#4A6A8A"):
    """
    Crée une icône QtAwesome si la bibliothèque est disponible.

    Parameters
    ----------
    name : str
        Nom de l'icône FontAwesome (ex. ``'fa5s.save'``).
    color : str, optional
        Couleur hexadécimale de l'icône.

    Returns
    -------
    QIcon or None
        Icône créée, ou ``None`` si ``qtawesome`` n'est pas installé.
    """
    if _HAS_QTA:
        try: return qta.icon(name, color=color)
        except Exception: pass
    return None

class MainToolbar(QToolBar):
    """
    Barre d'outils principale de DIFMAP Modern.

    Contient les actions fichier (Load/Save), vue (Undo/Refresh/Reset),
    le sélecteur d'outil actif, l'inspecteur et le bouton terminal.
    """

    def __init__(self, title="Main Toolbar", parent=None):
        """
        Parameters
        ----------
        title : str, optional
            Titre interne de la toolbar (utilisé par Qt).
        parent : QWidget, optional
            Widget parent Qt.
        """
        super().__init__(title, parent)
        self.setMovable(False)
        self.setIconSize(QSize(18, 18))
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)

    def add_standard_actions(self, window):
        """
        Crée et ajoute toutes les actions standard à la toolbar.

        Attributs créés : ``action_load``, ``action_save``, ``action_undo``,
        ``action_refresh``, ``action_home``, ``lbl_tools``, ``combo_tools``,
        ``action_inspect``, ``action_terminal``.

        Parameters
        ----------
        window : QMainWindow
            Fenêtre parent utilisée comme owner des ``QAction``.
        """
        def act(label, icon_name=None, tooltip=None):
            a = QAction(label, window)
            if icon_name and _icon(icon_name):
                a.setIcon(_icon(icon_name))
            if tooltip:
                a.setToolTip(tooltip)
            return a

        # ── FICHIER ──────────────────────────────────────────────
        self.action_load = act("Load", "fa5s.folder-open", "Load a FITS observation file")
        self.addAction(self.action_load)
        self.action_save = act("Save", "fa5s.save", "Save visibilities as FITS [Ctrl+S]")
        self.addAction(self.action_save)
        self.addSeparator()

        # ── ACTIONS VUE ──────────────────────────────────────────
        self.action_undo = act("Undo", "fa5s.undo", "Undo last flagging operation [U]")
        self.addAction(self.action_undo)
        self.action_refresh = act("Refresh", "fa5s.sync", "Refresh display [L]")
        self.addAction(self.action_refresh)
        self.action_home = act("Reset", "fa5s.home", "Reset plot view [R]")
        self.addAction(self.action_home)
        self.addSeparator()

        # ── OUTILS (Menu Déroulant Compact) ──────────────────────
        self.lbl_tools = QLabel("  Tool: ")
        self.lbl_tools.setStyleSheet("font-weight: bold; color: #4A6A8A;")
        self.addWidget(self.lbl_tools)

        self.combo_tools = QComboBox()
        self.combo_tools.setMinimumWidth(160)
        self.combo_tools.setToolTip("Select the active mouse tool")
        self.addWidget(self.combo_tools)

        self.action_inspect = act("Inspect (s)", "fa5s.info-circle", "Toggle inspect mode — click a point to see its info [s]")
        self.action_inspect.setCheckable(True)
        self.addAction(self.action_inspect)

        # ── SÉPARATEUR EXTENSIBLE ────────────────────────────────
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.addWidget(spacer)

        self.action_terminal = act("Terminal", "fa5s.terminal", "Show / hide the log terminal")
        self.addAction(self.action_terminal)