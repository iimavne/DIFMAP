# difmap_wrapper/gui/components/control_panel.py
from PyQt6.QtWidgets import (QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QComboBox, QLineEdit, QCheckBox,
                             QScrollArea, QSlider, QPushButton)
from PyQt6.QtCore import Qt
from difmap_wrapper.gui.components.styled_buttons import PrimaryButton, SecondaryButton
from difmap_wrapper.gui.styles.design_system import DesignSystem

D = DesignSystem

# Style de base pour les éléments classiques
_QSS = f"""
QWidget {{
    background-color: {D.ASTRAL_BG};
    color: {D.ASTRAL_TEXT};
    font-family: {D.FONT_FAMILY};
    font-size: {D.FONT_SIZE_BASE};
}}
QDockWidget::title {{
    background-color: {D.ASTRAL_DEEPEST};
    color: {D.ASTRAL_TEXT};
    padding: 5px 10px;
    font-weight: bold;
    font-size: 10px;
    text-transform: uppercase;
}}
QCheckBox {{
    color: {D.ASTRAL_TEXT};
    spacing: 6px;
    padding: 2px 0;
}}
QCheckBox:disabled {{ color: {D.ASTRAL_MUTED}; }}
QCheckBox::indicator {{
    width: 14px; height: 14px;
    border-radius: 3px;
    border: 1px solid {D.ASTRAL_BORDER};
    background-color: {D.ASTRAL_DEEP};
}}
QCheckBox::indicator:checked {{
    background-color: {D.ASTRAL_ACCENT};
    border-color: {D.ASTRAL_ACCENT};
}}
QLabel {{
    color: {D.ASTRAL_DIM};
    font-size: 10px;
}}
QLabel:disabled {{ color: {D.ASTRAL_MUTED}; }}
QComboBox {{
    background-color: {D.ASTRAL_SURFACE};
    border: 1px solid {D.ASTRAL_BORDER};
    border-radius: {D.RADIUS_SM};
    padding: 4px 8px;
    color: {D.ASTRAL_TEXT};
    font-size: {D.FONT_SIZE_BASE};
    min-height: 22px;
}}
QComboBox:hover {{ border: 1px solid {D.ASTRAL_ACCENT}; }}
QComboBox::drop-down {{ border: none; width: 18px; }}
QLineEdit {{
    background-color: {D.ASTRAL_SURFACE};
    border: 1px solid {D.ASTRAL_BORDER};
    border-radius: {D.RADIUS_SM};
    padding: 4px 6px;
    color: {D.ASTRAL_TEXT};
    font-size: {D.FONT_SIZE_BASE};
    min-height: 20px;
}}
QLineEdit:focus {{ border: 1px solid {D.ASTRAL_ACCENT}; }}
QSlider::groove:horizontal {{
    border: 1px solid {D.ASTRAL_BORDER};
    height: 4px;
    background: {D.ASTRAL_SURFACE};
    border-radius: 2px;
    margin: 0 4px;
}}
QSlider::handle:horizontal {{
    background: {D.ASTRAL_ACCENT};
    border: 1px solid {D.PRIMARY_HOVER};
    width: 12px; height: 12px;
    border-radius: 6px;
    margin: -5px 0;
}}
QSlider::handle:horizontal:hover {{ background: {D.PRIMARY_HOVER}; }}
QScrollArea {{ border: none; background-color: {D.ASTRAL_BG}; }}
"""

class CollapsibleSection(QWidget):
    """Un accordéon déroulant remplaçant le QGroupBox standard"""
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # Le bouton d'en-tête cliquable
        self.toggle_button = QPushButton(f"▼  {title}")
        self.toggle_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {D.ASTRAL_DEEPEST};
                color: {D.ASTRAL_TEXT};
                border: 1px solid {D.ASTRAL_BORDER};
                border-radius: 4px;
                padding: 8px;
                text-align: left;
                font-weight: bold;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: {D.ASTRAL_HOVER};
            }}
            QPushButton:checked {{
                border-bottom-left-radius: 0px;
                border-bottom-right-radius: 0px;
            }}
        """)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(True)
        self.toggle_button.clicked.connect(self.toggle)

        # La zone de contenu cachable
        self.content_area = QWidget()
        self.content_area.setObjectName("ContentArea")
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(8, 8, 8, 8)
        self.content_layout.setSpacing(6)
        self.content_area.setStyleSheet(f"""
            QWidget#ContentArea {{
                background-color: {D.ASTRAL_BG};
                border: 1px solid {D.ASTRAL_BORDER};
                border-top: none;
                border-bottom-left-radius: 4px;
                border-bottom-right-radius: 4px;
            }}
        """)

        self.layout.addWidget(self.toggle_button)
        self.layout.addWidget(self.content_area)

    def toggle(self):
        is_checked = self.toggle_button.isChecked()
        self.content_area.setVisible(is_checked)
        arrow = "▼" if is_checked else "▶"
        title = self.toggle_button.text()[3:] # Garde le titre pur
        self.toggle_button.setText(f"{arrow}  {title}")


class ControlPanel(QDockWidget):
    def __init__(self, title="Controls", parent=None):
        super().__init__(title, parent)
        self.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea)
        self.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        self.container = QWidget()
        self.main_layout = QVBoxLayout(self.container)
        self.main_layout.setSpacing(12) # Plus d'espace entre les accordéons
        self.main_layout.setContentsMargins(8, 8, 8, 8)
        self.container.setStyleSheet(_QSS)

        self._build_data_selection()
        self._build_telescope_focus()
        self._build_flagging_options()
        self._build_display_options()
        self._build_imaging()

        self.main_layout.addStretch()

        lbl = QLabel("Press H for keyboard shortcuts")
        lbl.setStyleSheet(f"color: {D.ASTRAL_MUTED}; font-size: 9px; font-style: italic;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(lbl)

        scroll.setWidget(self.container)
        self.setWidget(scroll)

    def _build_data_selection(self):
        self.group_data_selection = CollapsibleSection("1. DATA SELECTION")
        layout = self.group_data_selection.content_layout
        layout.addWidget(QLabel("Polarization:"))
        self.combo_pol = QComboBox()
        self.combo_pol.addItems(["Stokes I", "RR", "LL", "XX", "YY"])
        layout.addWidget(self.combo_pol)
        self.main_layout.addWidget(self.group_data_selection)

    def _build_telescope_focus(self):
        self.group_telescope = CollapsibleSection("2. TELESCOPE FOCUS")
        layout = self.group_telescope.content_layout

        h = QHBoxLayout()
        self.input_search_tel = QLineEdit()
        self.input_search_tel.setPlaceholderText("e.g. 1:BR  [T]")
        self.btn_search_tel = SecondaryButton("Search")
        h.addWidget(self.input_search_tel); h.addWidget(self.btn_search_tel)
        layout.addLayout(h)

        layout.addWidget(QLabel("Subarray  [N / P]:"))
        h2 = QHBoxLayout()
        self.btn_prev_sub = SecondaryButton("◀ Prev")
        self.btn_next_sub = SecondaryButton("Next ▶")
        h2.addWidget(self.btn_prev_sub); h2.addWidget(self.btn_next_sub)
        layout.addLayout(h2)

        layout.addWidget(QLabel("Antenna  [n / p]:"))
        h3 = QHBoxLayout()
        self.btn_prev_ant = SecondaryButton("◀ Prev")
        self.btn_next_ant = SecondaryButton("Next ▶")
        h3.addWidget(self.btn_prev_ant); h3.addWidget(self.btn_next_ant)
        layout.addLayout(h3)

        self.main_layout.addWidget(self.group_telescope)

    def _build_flagging_options(self):
        self.group_flagging = CollapsibleSection("3. FLAGGING")
        layout = self.group_flagging.content_layout
        self.chk_all_channels = QCheckBox("Flag ALL channels in IF  [W]")
        layout.addWidget(self.chk_all_channels)
        self.main_layout.addWidget(self.group_flagging)

    def _build_display_options(self):
        self.group_display = CollapsibleSection("4. DISPLAY OPTIONS")
        layout = self.group_display.content_layout

        # On sauve le Label pour pouvoir le cacher
        self.lbl_rad_mode = QLabel("Radplot mode  [1 / 2 / 3]:")
        layout.addWidget(self.lbl_rad_mode)
        self.combo_rad_mode = QComboBox()
        self.combo_rad_mode.addItems(["1 – Amplitude only", "2 – Phase only", "3 – Amplitude & Phase"])
        layout.addWidget(self.combo_rad_mode)

        # On sauve le séparateur pour pouvoir le cacher
        self.sep_display = QWidget()
        self.sep_display.setFixedHeight(1)
        self.sep_display.setStyleSheet(f"background-color: {D.ASTRAL_BORDER}; margin: 4px 0;")
        layout.addWidget(self.sep_display)

        self.chk_conjugate  = QCheckBox("Conjugate points  [%]")
        self.chk_model      = QCheckBox("Model overlay  [M]")
        self.chk_residuals  = QCheckBox("Residuals (Data − Model)  [−]")
        self.chk_crosshair  = QCheckBox("Full-screen crosshair  [+]")
        self.chk_errors     = QCheckBox("Error plot (1/√w)  [E]")

        for chk in (self.chk_conjugate, self.chk_model, self.chk_residuals, self.chk_crosshair, self.chk_errors):
            layout.addWidget(chk)

        # On sauve le Label pour pouvoir le cacher
        self.lbl_slider_size = QLabel("Marker size  [.]:")
        layout.addWidget(self.lbl_slider_size)
        self.slider_size = QSlider(Qt.Orientation.Horizontal)
        self.slider_size.setMinimum(1)
        self.slider_size.setMaximum(3)
        self.slider_size.setValue(1)
        self.slider_size.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.slider_size.setTickInterval(1)
        layout.addWidget(self.slider_size)

        self.main_layout.addWidget(self.group_display)

    def _build_imaging(self):
        self.group_imaging = CollapsibleSection("5. IMAGING ENGINE")
        layout = self.group_imaging.content_layout

        h = QHBoxLayout()
        self.input_mapsize  = QLineEdit("1024")
        self.input_cellsize = QLineEdit("0.05")
        h.addWidget(QLabel("Size:")); h.addWidget(self.input_mapsize)
        h.addWidget(QLabel("Cell:")); h.addWidget(self.input_cellsize)
        layout.addLayout(h)

        layout.addWidget(QLabel("UV Weighting:"))
        self.combo_weight = QComboBox()
        self.combo_weight.addItems(["Natural", "Uniform", "Briggs"])
        layout.addWidget(self.combo_weight)

        layout.addWidget(QLabel("Gaussian Taper (Mλ):"))
        self.input_taper = QLineEdit("2.5")
        layout.addWidget(self.input_taper)

        self.btn_compute = PrimaryButton("Compute Dirty Map")
        layout.addWidget(self.btn_compute)

        self.main_layout.addWidget(self.group_imaging)