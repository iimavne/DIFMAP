from PyQt6.QtWidgets import QToolBar
from PyQt6.QtGui import QAction, QActionGroup

class MainToolbar(QToolBar):
    def __init__(self, title="Main Toolbar", parent=None):
        super().__init__(title, parent)
        self.setMovable(False)

    def add_standard_actions(self, window):
        # --- GROUPE 1 : FICHIERS ---
        self.action_load = QAction("LOAD FITS", window)
        self.addAction(self.action_load)
        
        self.action_save = QAction("SAVE WOBS", window)
        self.addAction(self.action_save)
        
        self.addSeparator()

        # --- GROUPE 2 : NAVIGATION (EXCLUSIFS) ---
        self.action_home = QAction("RESET VIEW", window)
        self.addAction(self.action_home)

        self.action_pan = QAction("PAN (MOVE)", window)
        self.action_pan.setCheckable(True)
        self.addAction(self.action_pan)

        self.action_zoom = QAction("ZOOM", window)
        self.action_zoom.setCheckable(True)
        self.addAction(self.action_zoom)

        self.action_cut = QAction("CUT FLAG", window)
        self.action_cut.setCheckable(True)
        self.addAction(self.action_cut)

        # On crée un groupe pour qu'un seul outil soit actif à la fois
        self.tools_group = QActionGroup(window)
        self.tools_group.addAction(self.action_pan)
        self.tools_group.addAction(self.action_zoom)
        self.tools_group.addAction(self.action_cut)
        self.tools_group.setExclusionPolicy(QActionGroup.ExclusionPolicy.ExclusiveOptional)
        
        self.addSeparator()

        # --- GROUPE 3 : ACTIONS ---
        self.action_undo = QAction("UNDO", window)
        self.addAction(self.action_undo)

        self.action_refresh = QAction("REFRESH", window)
        self.addAction(self.action_refresh)