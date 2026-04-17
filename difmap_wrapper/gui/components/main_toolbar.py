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
    if _HAS_QTA:
        try: return qta.icon(name, color=color)
        except Exception: pass
    return None

class MainToolbar(QToolBar):
    def __init__(self, title="Main Toolbar", parent=None):
        super().__init__(title, parent)
        self.setMovable(False)
        self.setIconSize(QSize(18, 18))
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)

    def add_standard_actions(self, window):
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

        self.action_inspect = act("Nearest (s)", "fa5s.info-circle", "Show info for nearest point [s]")
        self.addAction(self.action_inspect)

        # ── SÉPARATEUR EXTENSIBLE ────────────────────────────────
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.addWidget(spacer)

        self.action_terminal = act("Terminal", "fa5s.terminal", "Show / hide the log terminal")
        self.addAction(self.action_terminal)