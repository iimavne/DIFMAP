# difmap_wrapper/gui/components/main_toolbar.py
from PyQt6.QtWidgets import QToolBar, QComboBox, QLabel, QSizePolicy, QWidget
from PyQt6.QtGui import QAction

class MainToolbar(QToolBar):
    def __init__(self, title="Main Toolbar", parent=None):
        super().__init__(title, parent)
        self.setMovable(False)

    def add_standard_actions(self, window):
        # --- GROUPE 1 : ACTIONS DE FICHIER ---
        self.action_load = QAction("LOAD FITS", window)
        self.addAction(self.action_load)
        
        self.action_save = QAction("SAVE WOBS", window) # <--- RÉPARÉ
        self.addAction(self.action_save)
        
        self.addSeparator()

        # --- GROUPE 2 : NAVIGATION ---
        self.action_home = QAction("RESET VIEW", window) # <--- RÉPARÉ
        self.addAction(self.action_home)
        
        self.action_undo = QAction("UNDO", window) # <--- RÉPARÉ
        self.addAction(self.action_undo)

        self.addSeparator()

        # --- GROUPE 3 : MENU DES OUTILS (Épuré) ---
        self.addWidget(QLabel("  Tool: "))
        self.combo_tools = QComboBox(window)
        self.combo_tools.setMinimumWidth(140)
        self.combo_tools.addItems(["None (Inspect)", "Pan (Move)", "Zoom Box", "Zoom X (UV)", "Cut Box", "Stats Box"])
        self.addWidget(self.combo_tools)

        # Espace flexible pour pousser le refresh à droite
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.addWidget(spacer)

        self.action_refresh = QAction("REFRESH", window) # <--- RÉPARÉ
        self.addAction(self.action_refresh)