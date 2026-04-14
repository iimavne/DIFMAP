# difmap_wrapper/gui/components/control_panel.py
from PyQt6.QtWidgets import (QDockWidget, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QComboBox, QLineEdit, QCheckBox,
                             QGroupBox, QScrollArea, QSlider)
from PyQt6.QtCore import Qt
from difmap_wrapper.gui.components.styled_buttons import (
    PrimaryButton, SecondaryButton
)

class ControlPanel(QDockWidget):
    def __init__(self, title="SmartEditor Controls", parent=None):
        super().__init__(title, parent)
        self.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea)
        self.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        
        # Scroll Area pour que ça rentre même sur les petits écrans
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        
        self.container = QWidget()
        self.layout = QVBoxLayout(self.container)
        self.layout.setSpacing(10)
        self.layout.setContentsMargins(10, 10, 10, 10)

        # Style QSS Global (Pro, Sombre, Contraste)

        # Construction des modules
        self._build_data_selection()
        self._build_telescope_focus()   # <-- Nouveau !
        self._build_flagging_options()  # <-- Nouveau !
        self._build_display_options()   # <-- Nouveau !
        self._build_imaging()

        self.layout.addStretch()
        
        # Astuce UI : Rappel pour l'inspection
        lbl_hint = QLabel("💡 Hint: Hover a point and press 'S' to inspect.")
        self.btn_compute.setStyleSheet("background-color: #3b82f6; color: white; border: none; padding: 6px 12px; border-radius: 3px; font-weight: bold;")
        self.layout.addWidget(lbl_hint)

        scroll.setWidget(self.container)
        self.setWidget(scroll)

    def _build_data_selection(self):
        group = QGroupBox("1. DATA SELECTION")
        layout = QVBoxLayout(group)
        
        layout.addWidget(QLabel("Polarization"))
        self.combo_pol = QComboBox()
        self.combo_pol.addItems(["Stokes I", "RR", "LL", "XX", "YY"])
        layout.addWidget(self.combo_pol)
        
        self.layout.addWidget(group)

    def _build_telescope_focus(self):
        """Remplace les raccourcis n, p, N, P, T"""
        self.group_telescope = QGroupBox("2. TELESCOPE FOCUS")
        layout = QVBoxLayout(self.group_telescope)
        
        # Recherche spécifique (Touche T)
        h_search = QHBoxLayout()
        self.input_search_tel = QLineEdit()
        self.input_search_tel.setPlaceholderText("ex: 1:BR")
        self.btn_search_tel = SecondaryButton("Search")
        h_search.addWidget(self.input_search_tel)
        h_search.addWidget(self.btn_search_tel)
        layout.addLayout(h_search)

        # Navigation Subarrays (Touches N, P)
        layout.addWidget(QLabel("Subarray Navigation (N/P):"))
        h_sub = QHBoxLayout()
        self.btn_prev_sub = SecondaryButton("◀ Prev Sub")
        self.btn_next_sub = SecondaryButton("Next Sub ▶")
        h_sub.addWidget(self.btn_prev_sub)
        h_sub.addWidget(self.btn_next_sub)
        layout.addLayout(h_sub)

        # Navigation Antennes (Touches n, p)
        layout.addWidget(QLabel("Antenna Navigation (n/p):"))
        h_ant = QHBoxLayout()
        self.btn_prev_ant = SecondaryButton("◀ Prev Ant")
        self.btn_next_ant = SecondaryButton("Next Ant ▶")
        h_ant.addWidget(self.btn_prev_ant)
        h_ant.addWidget(self.btn_next_ant)
        layout.addLayout(h_ant)

        self.layout.addWidget(self.group_telescope)

    def _build_flagging_options(self):
        """Remplace le raccourci W"""
        self.group_flagging = QGroupBox("3. FLAGGING PREFERENCES")
        layout = QVBoxLayout(self.group_flagging)
        
        self.chk_all_channels = QCheckBox("Flag ALL Channels in IF (Shortcut: W)")
        self.chk_all_channels.setToolTip("If unchecked, flags only selected channels.")
        layout.addWidget(self.chk_all_channels)
        
        self.layout.addWidget(self.group_flagging)

    def _build_display_options(self):
        """Remplace les raccourcis ., +, %"""
        self.group_display = QGroupBox("4. DISPLAY OPTIONS")
        layout = QVBoxLayout(self.group_display)
        
        self.chk_conjugate = QCheckBox("Show Conjugate Points (-U, -V) [%]")
        layout.addWidget(self.chk_conjugate)

        self.chk_crosshair = QCheckBox("Full-screen Crosshair [+]")
        layout.addWidget(self.chk_crosshair)

        layout.addWidget(QLabel("Marker Size [.]"))
        self.slider_size = QSlider(Qt.Orientation.Horizontal)
        self.slider_size.setMinimum(1)
        self.slider_size.setMaximum(5)
        self.slider_size.setValue(1)
        layout.addWidget(self.slider_size)

        self.layout.addWidget(self.group_display)

    def _build_imaging(self):
        self.group_imaging = QGroupBox("5. IMAGING ENGINE")
        layout = QVBoxLayout(self.group_imaging)
        
        # 1. Mapsize et Cellsize
        h_map = QHBoxLayout()
        self.input_mapsize = QLineEdit("1024")
        self.input_cellsize = QLineEdit("0.05")
        h_map.addWidget(QLabel("Size:"))
        h_map.addWidget(self.input_mapsize)
        h_map.addWidget(QLabel("Cell:"))
        h_map.addWidget(self.input_cellsize)
        layout.addLayout(h_map)

        # 2. UV Weighting (C'ÉTAIT ÇA QUI MANQUAIT !)
        layout.addWidget(QLabel("UV Weighting:"))
        self.combo_weight = QComboBox()
        self.combo_weight.addItems(["Natural", "Uniform", "Briggs"])
        layout.addWidget(self.combo_weight)

        # 3. Gaussian Taper
        layout.addWidget(QLabel("Gaussian Taper (Mλ):"))
        self.input_taper = QLineEdit("2.5")
        layout.addWidget(self.input_taper)

        # 4. Le bouton d'action
        self.btn_compute = PrimaryButton(" Compute Dirty Map")
        layout.addWidget(self.btn_compute)

        self.layout.addWidget(self.group_imaging)