# difmap_wrapper/gui/components/control_panel.py
from PyQt6.QtWidgets import (QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QComboBox, QLineEdit, QCheckBox,
                             QScrollArea, QSlider, QPushButton, QMessageBox,
                             QColorDialog, QSpinBox)
from PyQt6.QtGui import QColor
from PyQt6.QtCore import pyqtSignal
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

class _IFRangeBar(QWidget):
    """Barre horizontale indiquant visuellement la plage d'IFs sélectionnée."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(10)
        self._beg = 1
        self._end = 1
        self._total = 1

    def update_range(self, beg: int, end: int, total: int):
        self._beg   = beg
        self._end   = end
        self._total = max(1, total)
        self.update()

    def paintEvent(self, event):
        from PyQt6.QtGui import QPainter, QColor, QPen
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Fond
        p.fillRect(0, 0, w, h, QColor(D.ASTRAL_DEEP))

        # Zone sélectionnée
        x1 = int((self._beg - 1) / self._total * w)
        x2 = int(self._end        / self._total * w)
        p.fillRect(x1, 1, max(2, x2 - x1), h - 2, QColor(D.ASTRAL_ACCENT))

        # Bordure
        pen = QPen(QColor(D.ASTRAL_BORDER))
        pen.setWidth(1)
        p.setPen(pen)
        p.drawRect(0, 0, w - 1, h - 1)
        p.end()


class CollapsibleSection(QWidget):
    """
    Section accordéon déroulante remplaçant le ``QGroupBox`` standard.

    Le bouton d'en-tête affiche une flèche indiquant l'état ouvert/fermé.
    """

    def __init__(self, title, parent=None):
        """
        Parameters
        ----------
        title : str
            Titre affiché dans le bouton d'en-tête.
        parent : QWidget, optional
            Widget parent Qt.
        """
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
        """Bascule la visibilité de la zone de contenu et met à jour la flèche (▼/▶)."""
        is_checked = self.toggle_button.isChecked()
        self.content_area.setVisible(is_checked)
        arrow = "▼" if is_checked else "▶"
        title = self.toggle_button.text()[3:] # Garde le titre pur
        self.toggle_button.setText(f"{arrow}  {title}")


class ControlPanel(QDockWidget):
    """Panneau de contrôle gauche de DIFMAP Modern."""

    data_color_changed = pyqtSignal(str)
    ifs_range_changed  = pyqtSignal(int, int)   # (if_beg, if_end) — 1-indexed, 0=last

    def __init__(self, session, title="Controls", parent=None):
        """
        Parameters
        ----------
        session : DifmapSession
            Session principale donnant accès à ``obs`` et ``imager``.
        title : str, optional
            Titre du dock widget affiché dans la barre de titre.
        parent : QWidget, optional
            Widget parent Qt.
        """
        super().__init__(title, parent)
        self.session = session # <-- SAUVEGARDE de la session
        self.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea)
        self.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        self.container = QWidget()
        self.main_layout = QVBoxLayout(self.container)
        self.main_layout.setSpacing(12)
        self.main_layout.setContentsMargins(8, 8, 8, 8)
        self.container.setStyleSheet(_QSS)

        self._build_data_selection()
        self._build_telescope_focus()
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
        """Construit la section « 1. DATA SELECTION » avec polarisation et plage d'IFs."""
        self.group_data_selection = CollapsibleSection("1. DATA SELECTION")
        layout = self.group_data_selection.content_layout

        layout.addWidget(QLabel("Polarization:"))
        self.combo_pol = QComboBox()
        self.combo_pol.addItems(["I", "RR", "LL", "RL", "LR"])
        layout.addWidget(self.combo_pol)

        # --- Séparateur ---
        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {D.ASTRAL_BORDER}; margin: 2px 0;")
        layout.addWidget(sep)

        # --- Sélecteur de plage d'IFs ---
        spin_style = f"""
            QSpinBox {{
                background-color: {D.ASTRAL_SURFACE};
                border: 1px solid {D.ASTRAL_BORDER};
                border-radius: {D.RADIUS_SM};
                padding: 2px 4px;
                color: {D.ASTRAL_TEXT};
                font-size: {D.FONT_SIZE_BASE};
                min-height: 20px;
            }}
            QSpinBox:focus {{ border: 1px solid {D.ASTRAL_ACCENT}; }}
            QSpinBox::up-button, QSpinBox::down-button {{
                width: 14px;
                background-color: {D.ASTRAL_DEEP};
                border: none;
            }}
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
                background-color: {D.ASTRAL_HOVER};
            }}
        """
        btn_all_style = f"""
            QPushButton {{
                background-color: {D.ASTRAL_SURFACE};
                border: 1px solid {D.ASTRAL_BORDER};
                border-radius: 3px;
                color: {D.ASTRAL_DIM};
                font-size: 9px;
                padding: 2px 6px;
            }}
            QPushButton:hover {{ background-color: {D.ASTRAL_HOVER}; color: {D.ASTRAL_TEXT}; }}
        """

        # Ligne "IFs:   [1] → [4]   [All]"
        h_ifs = QHBoxLayout()
        h_ifs.setSpacing(4)
        h_ifs.addWidget(QLabel("IFs:"))

        self.spin_if_start = QSpinBox()
        self.spin_if_start.setMinimum(1)
        self.spin_if_start.setMaximum(1)
        self.spin_if_start.setValue(1)
        self.spin_if_start.setEnabled(False)
        self.spin_if_start.setStyleSheet(spin_style)
        self.spin_if_start.setFixedWidth(46)
        self.spin_if_start.setToolTip("Premier IF (1 = début)")

        lbl_arrow = QLabel("→")
        lbl_arrow.setStyleSheet(f"color: {D.ASTRAL_MUTED}; font-size: 11px;")
        lbl_arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.spin_if_end = QSpinBox()
        self.spin_if_end.setMinimum(1)
        self.spin_if_end.setMaximum(1)
        self.spin_if_end.setValue(1)
        self.spin_if_end.setEnabled(False)
        self.spin_if_end.setStyleSheet(spin_style)
        self.spin_if_end.setFixedWidth(46)
        self.spin_if_end.setToolTip("Dernier IF")

        self._btn_ifs_all = QPushButton("All")
        self._btn_ifs_all.setFixedWidth(36)
        self._btn_ifs_all.setFixedHeight(22)
        self._btn_ifs_all.setEnabled(False)
        self._btn_ifs_all.setStyleSheet(btn_all_style)
        self._btn_ifs_all.setToolTip("Sélectionner tous les IFs")

        h_ifs.addWidget(self.spin_if_start)
        h_ifs.addWidget(lbl_arrow)
        h_ifs.addWidget(self.spin_if_end)
        h_ifs.addStretch()
        h_ifs.addWidget(self._btn_ifs_all)
        layout.addLayout(h_ifs)

        # Barre de progression visuelle indiquant la plage sélectionnée
        self._if_range_bar = _IFRangeBar()
        layout.addWidget(self._if_range_bar)

        self._n_ifs_total = 1

        self.spin_if_start.valueChanged.connect(self._on_if_spin_changed)
        self.spin_if_end  .valueChanged.connect(self._on_if_spin_changed)
        self._btn_ifs_all .clicked.connect(self._select_all_ifs)

        self.main_layout.addWidget(self.group_data_selection)
        # NB : combo_pol est géré exclusivement par MainWindow._change_polarization
        # (pas de double connexion ici pour éviter les doubles appels obs.select)

    def set_if_range(self, n_ifs: int) -> None:
        """
        Configure le sélecteur pour *n_ifs* IFs disponibles et remet à all.

        Parameters
        ----------
        n_ifs : int
            Nombre total d'IFs dans l'observation (≥ 1).
        """
        self._n_ifs_total = max(1, n_ifs)
        for spin in (self.spin_if_start, self.spin_if_end):
            spin.blockSignals(True)
            spin.setMinimum(1)
            spin.setMaximum(self._n_ifs_total)
            spin.blockSignals(False)
        self.spin_if_start.blockSignals(True)
        self.spin_if_start.setValue(1)
        self.spin_if_start.blockSignals(False)
        self.spin_if_end.blockSignals(True)
        self.spin_if_end.setValue(self._n_ifs_total)
        self.spin_if_end.blockSignals(False)

        for w in (self.spin_if_start, self.spin_if_end, self._btn_ifs_all):
            w.setEnabled(True)

        self._if_range_bar.update_range(1, self._n_ifs_total, self._n_ifs_total)

    def get_if_range(self) -> tuple[int, int]:
        """Retourne ``(if_beg, if_end)`` prêt pour ``obs.select(ifs=...)``.

        Retourne ``(1, 0)`` si tout est sélectionné (convention difmap = all).
        """
        beg = self.spin_if_start.value()
        end = self.spin_if_end.value()
        if beg == 1 and end == self._n_ifs_total:
            return (1, 0)
        return (beg, end)

    def _select_all_ifs(self):
        self.spin_if_start.blockSignals(True)
        self.spin_if_end  .blockSignals(True)
        self.spin_if_start.setValue(1)
        self.spin_if_end  .setValue(self._n_ifs_total)
        self.spin_if_start.blockSignals(False)
        self.spin_if_end  .blockSignals(False)
        self._if_range_bar.update_range(1, self._n_ifs_total, self._n_ifs_total)
        self.ifs_range_changed.emit(1, 0)

    def _on_if_spin_changed(self):
        beg = self.spin_if_start.value()
        end = self.spin_if_end.value()
        # Contrainte : beg ≤ end
        if beg > end:
            sender = self.sender()
            if sender is self.spin_if_start:
                self.spin_if_end.blockSignals(True)
                self.spin_if_end.setValue(beg)
                self.spin_if_end.blockSignals(False)
                end = beg
            else:
                self.spin_if_start.blockSignals(True)
                self.spin_if_start.setValue(end)
                self.spin_if_start.blockSignals(False)
                beg = end
        self._if_range_bar.update_range(beg, end, self._n_ifs_total)
        if_beg, if_end = (1, 0) if (beg == 1 and end == self._n_ifs_total) else (beg, end)
        self.ifs_range_changed.emit(if_beg, if_end)
        
    def on_polarization_changed(self, requested_pol: str):
        """
        Gère le changement de polarisation demandé via le combo.

        Si le moteur C ne dispose pas de la polarisation demandée, effectue
        un fallback sur la polarisation disponible et informe l'utilisateur.

        Parameters
        ----------
        requested_pol : str
            Code de polarisation demandé (ex. ``'I'``, ``'RR'``, ``'LL'``).
        """
        try:
            # 1. On passe l'ordre et on récupère la VRAIE polarisation
            actual_pol = self.session.obs.select(pol=requested_pol)
            
            # 2. Si le moteur C a fait un "Fallback"
            if actual_pol != requested_pol:
                self.combo_pol.blockSignals(True)
                self.combo_pol.setCurrentText(actual_pol)
                self.combo_pol.blockSignals(False)
                
                QMessageBox.information(
                    self, 
                    "Polarisation indisponible", 
                    f"La polarisation '{requested_pol}' n'existe pas.\n\n"
                    f"Difmap a basculé sur '{actual_pol}'."
                )
            
            # 3. On rafraîchit les graphiques
            self.session.obs.notify_data_changed()
            
        except Exception as e:
            QMessageBox.critical(self, "Erreur de sélection", str(e))
            
    def _build_telescope_focus(self):
        """
        Construit la section « 2. TELESCOPE FOCUS ».

        Crée le champ de recherche de télescope et les boutons de navigation
        antenne (n/p) et sous-réseau (N/P).
        """
        self.group_telescope = CollapsibleSection("2. TELESCOPE FOCUS")
        layout = self.group_telescope.content_layout

        h = QHBoxLayout()
        self.input_search_tel = QLineEdit()
        self.input_search_tel.setPlaceholderText("e.g. 1:BR  [T]")
        self.btn_search_tel = SecondaryButton("Search")
        self.btn_clear_focus = SecondaryButton("Reset focus")
        self.btn_clear_focus.setToolTip("Remove telescope focus / no highlight")
        h.addWidget(self.input_search_tel); h.addWidget(self.btn_search_tel); h.addWidget(self.btn_clear_focus)
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

    def _build_display_options(self):
        """
        Construit la section « 4. DISPLAY OPTIONS ».

        Crée le sélecteur de mode Radplot, les checkboxes d'affichage
        (modèle, résidus, crosshair, erreurs, conjuguées) et le slider de taille.
        """
        self.group_display = CollapsibleSection("3. DISPLAY OPTIONS")
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
        self.chk_conjugate.setChecked(True)
        self.chk_model      = QCheckBox("Model overlay  [M]")
        self.chk_residuals  = QCheckBox("Residuals (Data − Model)  [−]")
        self.chk_crosshair  = QCheckBox("Full-screen crosshair  [+]")
        self.chk_errors     = QCheckBox("Error plot (1/√w)  [E]")

        for chk in (self.chk_conjugate, self.chk_model, self.chk_residuals, self.chk_crosshair, self.chk_errors):
            layout.addWidget(chk)

        # Taille des marqueurs
        h_size = QHBoxLayout()
        self.lbl_slider_size = QLabel("Marker size  [.]:")
        self.lbl_slider_size_val = QLabel("10 %")
        self.lbl_slider_size_val.setAlignment(Qt.AlignmentFlag.AlignRight)
        h_size.addWidget(self.lbl_slider_size)
        h_size.addWidget(self.lbl_slider_size_val)
        layout.addLayout(h_size)
        self.slider_size = QSlider(Qt.Orientation.Horizontal)
        self.slider_size.setMinimum(1)
        self.slider_size.setMaximum(100)
        self.slider_size.setValue(10)
        self.slider_size.setToolTip("Marker size (1–100 %)")
        self.slider_size.valueChanged.connect(
            lambda v: self.lbl_slider_size_val.setText(f"{v} %")
        )
        layout.addWidget(self.slider_size)

        # Transparence des points
        layout.addWidget(QLabel("Opacity:"))
        self.slider_alpha = QSlider(Qt.Orientation.Horizontal)
        self.slider_alpha.setMinimum(10)
        self.slider_alpha.setMaximum(100)
        self.slider_alpha.setValue(50)
        self.slider_alpha.setToolTip("Point opacity (10–100 %)")
        layout.addWidget(self.slider_alpha)

        # Couleur des points
        h_color = QHBoxLayout()
        h_color.addWidget(QLabel("Data color:"))
        self.btn_data_color = QPushButton()
        self.btn_data_color.setFixedHeight(22)
        self.btn_data_color.setToolTip("Pick data point color")
        self._current_data_color = "#1565C0"
        self.btn_data_color.setStyleSheet(
            f"background-color: {self._current_data_color}; border: 1px solid #555;"
        )
        h_color.addWidget(self.btn_data_color)

        def _pick_color():
            color = QColorDialog.getColor(
                QColor(self._current_data_color), None, "Choose data point color"
            )
            if color.isValid():
                self._current_data_color = color.name()
                self.btn_data_color.setStyleSheet(
                    f"background-color: {self._current_data_color}; border: 1px solid #555;"
                )
                self.data_color_changed.emit(self._current_data_color)

        self.btn_data_color.clicked.connect(_pick_color)
        layout.addLayout(h_color)

        self.main_layout.addWidget(self.group_display)

    def _build_imaging(self):
        """
        Construit la section « 5. IMAGING ENGINE ».

        Crée les champs mapsize, cellsize, la pondération UV, le taper gaussien
        et le bouton « Compute Dirty Map ».
        """
        self.group_imaging = CollapsibleSection("4. IMAGING")
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