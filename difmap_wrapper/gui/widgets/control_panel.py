# difmap_wrapper/gui/components/control_panel.py
from PyQt6.QtWidgets import (QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QComboBox, QLineEdit, QCheckBox,
                             QScrollArea, QSlider, QPushButton, QMessageBox,
                             QColorDialog, QSpinBox)
from PyQt6.QtGui import QColor
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtCore import Qt
from .styled_buttons import PrimaryButton, SecondaryButton
from difmap_wrapper.gui.styles import DesignSystem
from difmap_wrapper.types import POLARIZATIONS

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

    def set_available_polarizations(self, polarizations: list[str], current: str | None = None) -> None:
        """Met à jour le combo avec les seules polarisations proposées par le fichier."""
        values = [pol for pol in polarizations if pol]
        if not values:
            values = list(POLARIZATIONS)

        self.combo_pol.blockSignals(True)
        self.combo_pol.clear()
        self.combo_pol.addItems(values)
        self.combo_pol.setCurrentText(current if current in values else values[0])
        self.combo_pol.blockSignals(False)

    def _build_data_selection(self):
        """Construit la section « 1. DATA SELECTION » avec polarisation et plage d'IFs."""
        self.group_data_selection = CollapsibleSection("1. DATA SELECTION")
        layout = self.group_data_selection.content_layout

        layout.addWidget(QLabel("Polarization:"))
        self.combo_pol = QComboBox()
        self.combo_pol.addItems(list(POLARIZATIONS))
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

    # ─────────────────────────────────────────────────────────────
    # Helpers visuels
    # ─────────────────────────────────────────────────────────────

    def _subsection_header(self, text: str) -> QLabel:
        """En-tête de sous-section — ligne colorée avec texte en majuscules."""
        lbl = QLabel(text.upper())
        lbl.setStyleSheet(f"""
            color: {D.ASTRAL_ACCENT};
            font-size: 9px;
            font-weight: bold;
            letter-spacing: 1.5px;
            padding: 6px 0 2px 0;
            background: transparent;
        """)
        return lbl

    def _thin_sep(self) -> QWidget:
        """Ligne de séparation fine entre sous-sections."""
        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {D.ASTRAL_MUTED}; margin: 2px 0;")
        return sep

    def _row(self, *items) -> QHBoxLayout:
        """Crée un QHBoxLayout peuplé des widgets/labels fournis."""
        h = QHBoxLayout()
        h.setSpacing(6)
        for item in items:
            if isinstance(item, str):
                lbl = QLabel(item)
                lbl.setStyleSheet(f"color: {D.ASTRAL_DIM}; font-size: 10px;")
                h.addWidget(lbl)
            else:
                h.addWidget(item)
        return h

    # ─────────────────────────────────────────────────────────────
    # Section Imaging
    # ─────────────────────────────────────────────────────────────

    def _build_imaging(self):
        self.group_imaging = CollapsibleSection("4. IMAGING")
        layout = self.group_imaging.content_layout
        layout.setSpacing(4)

        # ── GRID ─────────────────────────────────────────────────
        layout.addWidget(self._subsection_header("Grid"))

        h_grid = QHBoxLayout()
        h_grid.setSpacing(6)
        self.input_mapsize = QLineEdit("512")
        self.input_mapsize.setFixedWidth(52)
        self.input_mapsize.setToolTip("Taille de la grille FFT (puissance de 2 recommandée)")
        self.input_cellsize = QLineEdit("0.1")
        self.input_cellsize.setFixedWidth(52)
        self.input_cellsize.setToolTip("Taille du pixel en mas")
        h_grid.addWidget(QLabel("Size:")); h_grid.addWidget(self.input_mapsize)
        h_grid.addWidget(QLabel("Cell (mas):")); h_grid.addWidget(self.input_cellsize)
        h_grid.addStretch()
        layout.addLayout(h_grid)

        h_wt = QHBoxLayout()
        h_wt.setSpacing(6)
        h_wt.addWidget(QLabel("Weighting:"))
        self.combo_weight = QComboBox()
        self.combo_weight.addItems(["None", "Natural", "Uniform", "Briggs"])
        self.combo_weight.setToolTip("Pondération des baselines UV")
        h_wt.addWidget(self.combo_weight)
        layout.addLayout(h_wt)

        h_tap = QHBoxLayout()
        h_tap.setSpacing(6)
        h_tap.addWidget(QLabel("Taper (Mλ):"))
        self.input_taper = QLineEdit("0")
        self.input_taper.setFixedWidth(52)
        self.input_taper.setToolTip("Taper gaussien — 0 = aucun")
        h_tap.addWidget(self.input_taper)
        h_tap.addStretch()
        layout.addLayout(h_tap)

        self.btn_compute = PrimaryButton("⊞  Dirty Map")
        self.btn_compute.setToolTip("Calculer la Dirty Map (invert)")
        layout.addWidget(self.btn_compute)

        # ── CLEAN ─────────────────────────────────────────────────
        layout.addWidget(self._thin_sep())
        layout.addWidget(self._subsection_header("Clean"))

        # Ligne 1: Niter et Gain
        h_nc = QHBoxLayout()
        h_nc.setSpacing(6)
        h_nc.addWidget(QLabel("Niter:"))
        self.input_niter = QLineEdit("100")
        self.input_niter.setFixedWidth(52)
        self.input_niter.setToolTip("Nombre d'itérations CLEAN\n(si négatif: arrêt au 1er composant négatif)")
        h_nc.addWidget(self.input_niter)
        h_nc.addWidget(QLabel("Gain:"))
        self.input_gain = QLineEdit("0.05")
        self.input_gain.setFixedWidth(46)
        self.input_gain.setToolTip("Gain de boucle CLEAN (0–1)")
        h_nc.addWidget(self.input_gain)
        h_nc.addStretch()
        layout.addLayout(h_nc)

        # Ligne 2: Cutoff
        h_cutoff = QHBoxLayout()
        h_cutoff.setSpacing(6)
        h_cutoff.addWidget(QLabel("Cutoff:"))
        self.input_cutoff = QLineEdit("0.0")
        self.input_cutoff.setFixedWidth(60)
        self.input_cutoff.setToolTip("Seuil de flux résiduel (Jy/beam)\n0 = pas de limite")
        h_cutoff.addWidget(self.input_cutoff)
        h_cutoff.addWidget(QLabel("Jy/bm"))
        h_cutoff.addStretch()
        layout.addLayout(h_cutoff)

        self.btn_compute_clean = PrimaryButton("▶  Clean Map")
        self.btn_compute_clean.setToolTip("Calculer la Clean Map (invert → clean → restore)")
        layout.addWidget(self.btn_compute_clean)

        # ── DISPLAY ───────────────────────────────────────────────
        layout.addWidget(self._thin_sep())
        layout.addWidget(self._subsection_header("Display"))

        h_sc = QHBoxLayout(); h_sc.setSpacing(6)
        h_sc.addWidget(QLabel("Scale:"))
        self.combo_scale = QComboBox()
        self.combo_scale.addItems(["Linear", "Log", "Sqrt"])
        self.combo_scale.setToolTip("Échelle de couleur (mapfunc)")
        h_sc.addWidget(self.combo_scale)
        layout.addLayout(h_sc)

        h_range = QHBoxLayout(); h_range.setSpacing(6)
        h_range.addWidget(QLabel("Min:"))
        self.input_vmin = QLineEdit(); self.input_vmin.setPlaceholderText("auto")
        h_range.addWidget(self.input_vmin)
        h_range.addWidget(QLabel("Max:"))
        self.input_vmax = QLineEdit(); self.input_vmax.setPlaceholderText("auto")
        h_range.addWidget(self.input_vmax)
        layout.addLayout(h_range)

        # Contours
        h_ctr = QHBoxLayout(); h_ctr.setSpacing(6)
        h_ctr.addWidget(QLabel("Contours:"))
        self.combo_contour_mode = QComboBox()
        self.combo_contour_mode.addItems(["Standard %", "Log", "Custom"])
        self.combo_contour_mode.setToolTip("levs / loglevs / niveaux personnalisés")
        h_ctr.addWidget(self.combo_contour_mode)
        layout.addLayout(h_ctr)

        self._widget_log_params = QWidget()
        h_log = QHBoxLayout(self._widget_log_params)
        h_log.setContentsMargins(0, 0, 0, 0); h_log.setSpacing(4)
        h_log.addWidget(QLabel("Min%:"))
        self.input_absmin = QLineEdit("1"); self.input_absmin.setFixedWidth(38)
        h_log.addWidget(self.input_absmin)
        h_log.addWidget(QLabel("Max%:"))
        self.input_absmax = QLineEdit("100"); self.input_absmax.setFixedWidth(38)
        h_log.addWidget(self.input_absmax)
        h_log.addWidget(QLabel("×:"))
        self.input_factor = QLineEdit("2"); self.input_factor.setFixedWidth(34)
        h_log.addWidget(self.input_factor)
        self._widget_log_params.setVisible(False)
        layout.addWidget(self._widget_log_params)

        self._widget_custom_levels = QWidget()
        v_custom = QVBoxLayout(self._widget_custom_levels)
        v_custom.setContentsMargins(0, 0, 0, 0); v_custom.setSpacing(2)
        v_custom.addWidget(QLabel("Levels (% of peak):"))
        self.input_custom_levels = QLineEdit()
        self.input_custom_levels.setPlaceholderText("ex: -1 1 2 4 8 16 32 64 | 1:64:*2")
        v_custom.addWidget(self.input_custom_levels)
        self._widget_custom_levels.setVisible(False)
        layout.addWidget(self._widget_custom_levels)

        # Checkbox Show Model pour les cartes (comme PGPLOT 'M')
        self.chk_show_model_map = QCheckBox("Show Model Components  [M]")
        self.chk_show_model_map.setToolTip("Afficher les composantes CLEAN sur la carte")
        self.chk_show_model_map.setChecked(False)
        layout.addWidget(self.chk_show_model_map)

        self.btn_refresh_view = SecondaryButton("↻  Refresh View")
        self.btn_refresh_view.setToolTip("Appliquer l'affichage sans recalculer la carte")
        layout.addWidget(self.btn_refresh_view)

        self.combo_contour_mode.currentIndexChanged.connect(self._on_contour_mode_changed)
        self.main_layout.addWidget(self.group_imaging)

    def _on_contour_mode_changed(self, index: int) -> None:
        """Affiche/masque les champs de paramètres selon le mode de contours."""
        self._widget_log_params.setVisible(index == 1)    # Log levels
        self._widget_custom_levels.setVisible(index == 2)  # Custom

    def get_scale_params(self) -> tuple:
        """
        Retourne ``(scale, vmin, vmax)`` depuis les contrôles d'échelle de couleur.

        Returns
        -------
        tuple
            ``scale`` : ``'linear'``, ``'log'`` ou ``'sqrt'``.
            ``vmin``, ``vmax`` : float ou ``None`` (automatique).
        """
        scale = self.combo_scale.currentText().lower()
        try:
            vmin = float(self.input_vmin.text()) if self.input_vmin.text().strip() else None
        except ValueError:
            vmin = None
        try:
            vmax = float(self.input_vmax.text()) if self.input_vmax.text().strip() else None
        except ValueError:
            vmax = None
        return scale, vmin, vmax

    def get_contour_params(self) -> tuple:
        """
        Retourne ``(mode, absmin, absmax, factor, custom_list)`` depuis les contrôles
        de niveaux de contours.

        Returns
        -------
        tuple
            ``mode`` : ``'pct'``, ``'log'`` ou ``'custom'``.
            ``absmin``, ``absmax``, ``factor`` : float (pour mode ``'log'``).
            ``custom_list`` : list[float] ou ``None``.
        """
        idx = self.combo_contour_mode.currentIndex()
        if idx == 1:  # Log levels
            try:
                absmin = float(self.input_absmin.text() or "1")
            except ValueError:
                absmin = 1.0
            try:
                absmax = float(self.input_absmax.text() or "100")
            except ValueError:
                absmax = 100.0
            try:
                factor = float(self.input_factor.text() or "2")
            except ValueError:
                factor = 2.0
            return 'log', absmin, absmax, factor, None
        if idx == 2:  # Custom
            raw = self.input_custom_levels.text().strip()

            def _parse_custom_levels(text: str) -> list[float]:
                if not text:
                    return []
                txt = text.replace('..', ':').replace(';', ' ')
                parts = [p for p in re.split(r"[\s,]+", txt) if p]
                out: list[float] = []
                for p in parts:
                    if ':' in p:
                        segs = [s for s in p.split(':') if s]
                        if len(segs) < 2:
                            continue
                        try:
                            start = float(segs[0])
                            stop = float(segs[1])
                        except ValueError:
                            continue
                        if len(segs) == 2:
                            out.extend([start, stop])
                            continue
                        third = segs[2].strip()
                        try:
                            if third.startswith('*'):
                                factor = float(third[1:])
                                if factor <= 1:
                                    continue
                                v = start
                                if start <= 0 or stop <= 0:
                                    continue
                                while v <= stop:
                                    out.append(v)
                                    v *= factor
                            else:
                                step = float(third)
                                if step == 0:
                                    continue
                                v = start
                                if (stop - start) * step < 0:
                                    step = -step
                                if step > 0:
                                    while v <= stop:
                                        out.append(v)
                                        v += step
                                else:
                                    while v >= stop:
                                        out.append(v)
                                        v += step
                        except ValueError:
                            continue
                        continue
                    try:
                        out.append(float(p))
                    except ValueError:
                        continue
                return out

            custom = _parse_custom_levels(raw)
            return 'custom', 1.0, 100.0, 2.0, custom or None
        # Standard %
        return 'pct', 1.0, 100.0, 2.0, None
