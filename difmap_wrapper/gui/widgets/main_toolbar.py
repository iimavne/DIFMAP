# difmap_wrapper/gui/widgets/main_toolbar.py
from PyQt6.QtWidgets import QToolBar, QSizePolicy, QWidget
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
    """Barre unique fusionnant menu et actions principales."""

    def __init__(self, title="Main Toolbar", parent=None):
        super().__init__(title, parent)
        self.setMovable(False)
        self.setIconSize(QSize(15, 15))
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)

    def add_standard_actions(self, window):
        """
        Construit la barre unique : Load · Save · | · Help · Exit · spacer → Terminal.
        Attributs publics : action_load, action_save, action_help, action_exit, action_terminal.
        """
        def act(label, icon_name=None, tooltip=None, color="#4A6A8A"):
            a = QAction(label, window)
            ico = _icon(icon_name, color) if icon_name else None
            if ico:
                a.setIcon(ico)
            if tooltip:
                a.setToolTip(tooltip)
            return a

        # ── Fichier ───────────────────────────────────────────────
        self.action_load = act("Load", "fa5s.folder-open", "Ouvrir un fichier FITS")
        self.addAction(self.action_load)

        self.action_save = act("Save", "fa5s.save", "Sauvegarder les visibilités [Ctrl+S]")
        self.addAction(self.action_save)

        self.addSeparator()

        # ── Aide & Quitter ────────────────────────────────────────
        self.action_help = act("Help", "fa5s.keyboard", "Raccourcis clavier [H]")
        self.addAction(self.action_help)

        self.action_exit = act("Exit", "fa5s.times-circle",
                               "Quitter l'application", color="#C62828")
        self.addAction(self.action_exit)

        # ── Espaceur extensible ───────────────────────────────────
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.addWidget(spacer)

        # ── Terminal ──────────────────────────────────────────────
        self.action_terminal = act("Terminal", "fa5s.terminal",
                                   "Afficher / masquer le terminal")
        self.addAction(self.action_terminal)

        # ── Export logs ───────────────────────────────────────────
        self.action_export_logs = act("Export Logs", "fa5s.file-export",
                                      "Exporter les logs dans un fichier texte")
        self.addAction(self.action_export_logs)
