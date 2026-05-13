# difmap_wrapper/gui/components/control_panel.py
from PyQt6.QtWidgets import (QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QComboBox, QLineEdit, QCheckBox,
                             QScrollArea, QSlider, QPushButton, QMessageBox,
                             QColorDialog, QSpinBox, QFrame, QProgressBar)
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

    data_color_changed   = pyqtSignal(str)
    ifs_range_changed    = pyqtSignal(int, int)
    uv_limits_changed    = pyqtSignal(object, object, object, object)
    rad_limits_changed   = pyqtSignal(object, object, object, object, object, object)
    colormap_changed     = pyqtSignal(str)
    show_windows_changed = pyqtSignal(bool)

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
        """Construit la section « 3. AFFICHAGE OPTIONS »."""
        self.group_display = CollapsibleSection("3. AFFICHAGE OPTIONS")
        layout = self.group_display.content_layout

        # ── Radplot mode (masqué hors Radplot) ────────────────────
        self.lbl_rad_mode = QLabel("Radplot mode  [1 / 2 / 3]:")
        layout.addWidget(self.lbl_rad_mode)
        self.combo_rad_mode = QComboBox()
        self.combo_rad_mode.addItems(["1 – Amplitude only", "2 – Phase only", "3 – Amplitude & Phase"])
        layout.addWidget(self.combo_rad_mode)

        self.sep_display = QWidget()
        self.sep_display.setFixedHeight(1)
        self.sep_display.setStyleSheet(f"background-color: {D.ASTRAL_BORDER}; margin: 4px 0;")
        layout.addWidget(self.sep_display)

        # ── Checkboxes UV / Radplot ────────────────────────────────
        self.chk_conjugate = QCheckBox("Conjugate points  [%]")
        self.chk_conjugate.setChecked(True)
        self.chk_model     = QCheckBox("Model overlay  [M]")
        self.chk_residuals = QCheckBox("Residuals (Data − Model)  [−]")
        self.chk_crosshair = QCheckBox("Full-screen crosshair  [+]")
        self.chk_errors    = QCheckBox("Error plot (1/√w)  [E]")

        # chk_crosshair existe (pour les liaisons internes) mais n'est plus dans le panel —
        # il est remplacé par le bouton Crosshair [+] de la toolbar UV.
        for chk in (self.chk_conjugate, self.chk_model, self.chk_residuals, self.chk_errors):
            layout.addWidget(chk)

        # ── Limite plan UV ─────────────────────────────────────────
        self._uv_limits_section = QWidget()
        _uv_sec = QVBoxLayout(self._uv_limits_section)
        _uv_sec.setContentsMargins(0, 0, 0, 0)
        _uv_sec.setSpacing(4)

        sep_uv = QWidget()
        sep_uv.setFixedHeight(1)
        sep_uv.setStyleSheet(f"background-color: {D.ASTRAL_BORDER}; margin: 4px 0;")
        _uv_sec.addWidget(sep_uv)

        toggle_style = f"""
            QPushButton {{
                background-color: {D.ASTRAL_MUTED};
                color: {D.ASTRAL_TEXT};
                border: none;
                border-radius: 9px;
                padding: 2px 8px;
                font-size: 9px;
                font-weight: bold;
                min-width: 38px;
                max-width: 38px;
                min-height: 18px;
            }}
            QPushButton:checked {{
                background-color: {D.ASTRAL_ACCENT};
                color: #FFFFFF;
            }}
        """
        field_style = f"""
            QLineEdit {{
                background-color: {D.ASTRAL_SURFACE};
                border: 1px solid {D.ASTRAL_BORDER};
                border-radius: 3px;
                padding: 3px 5px;
                color: {D.ASTRAL_TEXT};
                font-size: 10px;
                min-height: 20px;
            }}
            QLineEdit:focus {{ border: 1px solid {D.ASTRAL_ACCENT}; }}
            QLineEdit:disabled {{
                background-color: {D.ASTRAL_DEEP};
                color: {D.ASTRAL_MUTED};
            }}
        """

        h_uv_hdr = QHBoxLayout()
        lbl_uv = QLabel("Limite plan UV")
        lbl_uv.setStyleSheet(f"color: {D.ASTRAL_TEXT}; font-size: 10px; font-weight: 500;")
        self.chk_uv_limit = QPushButton("OFF")
        self.chk_uv_limit.setCheckable(True)
        self.chk_uv_limit.setChecked(False)
        self.chk_uv_limit.setStyleSheet(toggle_style)
        self.chk_uv_limit.setToolTip("Activer les limites manuelles du plan UV")
        h_uv_hdr.addWidget(lbl_uv)
        h_uv_hdr.addStretch()
        h_uv_hdr.addWidget(self.chk_uv_limit)
        _uv_sec.addLayout(h_uv_hdr)

        # Grille U min / U max / V min / V max
        self._uv_limit_box = QWidget()
        grid = QVBoxLayout(self._uv_limit_box)
        grid.setContentsMargins(0, 4, 0, 0)
        grid.setSpacing(4)

        row_u = QHBoxLayout()
        row_u.setSpacing(6)
        lbl_umin = QLabel("U min")
        lbl_umin.setFixedWidth(34)
        self.input_umin = QLineEdit()
        self.input_umin.setPlaceholderText("auto")
        self.input_umin.setStyleSheet(field_style)
        lbl_umax = QLabel("U max")
        lbl_umax.setFixedWidth(34)
        self.input_umax = QLineEdit()
        self.input_umax.setPlaceholderText("auto")
        self.input_umax.setStyleSheet(field_style)
        row_u.addWidget(lbl_umin); row_u.addWidget(self.input_umin)
        row_u.addWidget(lbl_umax); row_u.addWidget(self.input_umax)
        grid.addLayout(row_u)

        row_v = QHBoxLayout()
        row_v.setSpacing(6)
        lbl_vmin = QLabel("V min")
        lbl_vmin.setFixedWidth(34)
        self.input_vmin_uv = QLineEdit()
        self.input_vmin_uv.setPlaceholderText("auto")
        self.input_vmin_uv.setStyleSheet(field_style)
        lbl_vmax = QLabel("V max")
        lbl_vmax.setFixedWidth(34)
        self.input_vmax_uv = QLineEdit()
        self.input_vmax_uv.setPlaceholderText("auto")
        self.input_vmax_uv.setStyleSheet(field_style)
        row_v.addWidget(lbl_vmin); row_v.addWidget(self.input_vmin_uv)
        row_v.addWidget(lbl_vmax); row_v.addWidget(self.input_vmax_uv)
        grid.addLayout(row_v)

        _uv_sec.addWidget(self._uv_limit_box)
        layout.addWidget(self._uv_limits_section)

        # Désactiver les champs par défaut (toggle OFF)
        for w in (self.input_umin, self.input_umax, self.input_vmin_uv, self.input_vmax_uv):
            w.setEnabled(False)

        def _on_uv_toggle(checked):
            self.chk_uv_limit.setText("ON" if checked else "OFF")
            for w in (self.input_umin, self.input_umax, self.input_vmin_uv, self.input_vmax_uv):
                w.setEnabled(checked)
            self._emit_uv_limits()

        def _parse_uv(field):
            t = field.text().strip()
            try:
                return float(t) if t and t.lower() != "auto" else None
            except ValueError:
                return None

        def _emit_uv_limits_checked():
            if self.chk_uv_limit.isChecked():
                self._emit_uv_limits()

        self._emit_uv_limits = lambda: self.uv_limits_changed.emit(
            _parse_uv(self.input_umin), _parse_uv(self.input_umax),
            _parse_uv(self.input_vmin_uv), _parse_uv(self.input_vmax_uv),
        )

        self.chk_uv_limit.toggled.connect(_on_uv_toggle)
        for w in (self.input_umin, self.input_umax, self.input_vmin_uv, self.input_vmax_uv):
            w.editingFinished.connect(_emit_uv_limits_checked)

        # ── Limite Radplot ─────────────────────────────────────────
        self._rad_limits_section = QWidget()
        _rad_sec = QVBoxLayout(self._rad_limits_section)
        _rad_sec.setContentsMargins(0, 0, 0, 0)
        _rad_sec.setSpacing(4)

        sep_rad = QWidget()
        sep_rad.setFixedHeight(1)
        sep_rad.setStyleSheet(f"background-color: {D.ASTRAL_BORDER}; margin: 4px 0;")
        _rad_sec.addWidget(sep_rad)

        h_rad_hdr = QHBoxLayout()
        lbl_rad_lim = QLabel("Limite Radplot")
        lbl_rad_lim.setStyleSheet(f"color: {D.ASTRAL_TEXT}; font-size: 10px; font-weight: 500;")
        self.chk_rad_limit = QPushButton("OFF")
        self.chk_rad_limit.setCheckable(True)
        self.chk_rad_limit.setChecked(False)
        self.chk_rad_limit.setStyleSheet(toggle_style)
        self.chk_rad_limit.setToolTip("Activer les limites manuelles du Radplot")
        h_rad_hdr.addWidget(lbl_rad_lim)
        h_rad_hdr.addStretch()
        h_rad_hdr.addWidget(self.chk_rad_limit)
        _rad_sec.addLayout(h_rad_hdr)

        self._rad_limit_box = QWidget()
        grid_rad = QVBoxLayout(self._rad_limit_box)
        grid_rad.setContentsMargins(0, 4, 0, 0)
        grid_rad.setSpacing(4)

        def _make_rad_row(lbl_a, lbl_b):
            row = QHBoxLayout()
            row.setSpacing(6)
            la = QLabel(lbl_a); la.setFixedWidth(40)
            ia = QLineEdit(); ia.setPlaceholderText("auto"); ia.setStyleSheet(field_style)
            lb = QLabel(lbl_b); lb.setFixedWidth(40)
            ib = QLineEdit(); ib.setPlaceholderText("auto"); ib.setStyleSheet(field_style)
            row.addWidget(la); row.addWidget(ia)
            row.addWidget(lb); row.addWidget(ib)
            grid_rad.addLayout(row)
            return ia, ib

        lbl_uvr = QLabel("UV Radius (Mλ)")
        lbl_uvr.setStyleSheet(f"color: {D.ASTRAL_DIM}; font-size: 9px;")
        grid_rad.addWidget(lbl_uvr)
        self.input_rad_uvmin, self.input_rad_uvmax = _make_rad_row("UV min", "UV max")

        lbl_amp = QLabel("Amplitude (Jy)")
        lbl_amp.setStyleSheet(f"color: {D.ASTRAL_DIM}; font-size: 9px;")
        grid_rad.addWidget(lbl_amp)
        self.input_rad_ampmin, self.input_rad_ampmax = _make_rad_row("Amp min", "Amp max")

        lbl_phs = QLabel("Phase (°)")
        lbl_phs.setStyleSheet(f"color: {D.ASTRAL_DIM}; font-size: 9px;")
        grid_rad.addWidget(lbl_phs)
        self.input_rad_phsmin, self.input_rad_phsmax = _make_rad_row("Phs min", "Phs max")

        _rad_sec.addWidget(self._rad_limit_box)
        layout.addWidget(self._rad_limits_section)

        _rad_fields = (self.input_rad_uvmin, self.input_rad_uvmax,
                       self.input_rad_ampmin, self.input_rad_ampmax,
                       self.input_rad_phsmin, self.input_rad_phsmax)

        for w in _rad_fields:
            w.setEnabled(False)

        def _on_rad_toggle(checked):
            self.chk_rad_limit.setText("ON" if checked else "OFF")
            for w in _rad_fields:
                w.setEnabled(checked)
            self._emit_rad_limits()

        def _parse_rad(field):
            t = field.text().strip()
            try:
                return float(t) if t and t.lower() != "auto" else None
            except ValueError:
                return None

        def _emit_rad_limits_checked():
            if self.chk_rad_limit.isChecked():
                self._emit_rad_limits()

        self._emit_rad_limits = lambda: self.rad_limits_changed.emit(
            _parse_rad(self.input_rad_uvmin),  _parse_rad(self.input_rad_uvmax),
            _parse_rad(self.input_rad_ampmin), _parse_rad(self.input_rad_ampmax),
            _parse_rad(self.input_rad_phsmin), _parse_rad(self.input_rad_phsmax),
        )

        self.chk_rad_limit.toggled.connect(_on_rad_toggle)
        for w in _rad_fields:
            w.editingFinished.connect(_emit_rad_limits_checked)

        # ── Taille des marqueurs ───────────────────────────────────
        sep2 = QWidget()
        sep2.setFixedHeight(1)
        sep2.setStyleSheet(f"background-color: {D.ASTRAL_BORDER}; margin: 4px 0;")
        layout.addWidget(sep2)

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

        # ── Opacité ────────────────────────────────────────────────
        layout.addWidget(QLabel("Opacity:"))
        self.slider_alpha = QSlider(Qt.Orientation.Horizontal)
        self.slider_alpha.setMinimum(10)
        self.slider_alpha.setMaximum(100)
        self.slider_alpha.setValue(50)
        self.slider_alpha.setToolTip("Point opacity (10–100 %)")
        layout.addWidget(self.slider_alpha)

        # ── Couleur des points ─────────────────────────────────────
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

        # ── Styles locaux ────────────────────────────────────────
        toggle_style = f"""
            QPushButton {{
                background-color: {D.ASTRAL_MUTED}; color: {D.ASTRAL_TEXT};
                border: none; border-radius: 9px; padding: 2px 8px;
                font-size: 9px; font-weight: bold;
                min-width: 38px; max-width: 38px; min-height: 18px;
            }}
            QPushButton:checked {{ background-color: {D.ASTRAL_ACCENT}; color: #FFFFFF; }}
        """
        field_s = f"""
            QLineEdit {{
                background-color: {D.ASTRAL_SURFACE}; border: 1px solid {D.ASTRAL_BORDER};
                border-radius: 3px; padding: 3px 5px;
                color: {D.ASTRAL_TEXT}; font-size: 10px; min-height: 20px;
            }}
            QLineEdit:focus {{ border: 1px solid {D.ASTRAL_ACCENT}; }}
            QLineEdit:disabled {{ background-color: {D.ASTRAL_DEEP}; color: {D.ASTRAL_MUTED}; }}
        """

        # ══════════════════════════════════════════════════════════
        # IMAGING PARAMS — tous les onglets carte
        # ══════════════════════════════════════════════════════════
        self._imaging_params_section = QWidget()
        ip = QVBoxLayout(self._imaging_params_section)
        ip.setContentsMargins(0, 0, 0, 0); ip.setSpacing(4)

        ip.addWidget(self._subsection_header("Grid"))
        h_grid = QHBoxLayout(); h_grid.setSpacing(6)
        self.input_mapsize = QLineEdit("512"); self.input_mapsize.setFixedWidth(52)
        self.input_mapsize.setToolTip("Taille de la grille FFT (puissance de 2 recommandée)")
        self.input_cellsize = QLineEdit("0.1"); self.input_cellsize.setFixedWidth(52)
        self.input_cellsize.setToolTip("Taille du pixel en mas")
        h_grid.addWidget(QLabel("Size:")); h_grid.addWidget(self.input_mapsize)
        h_grid.addWidget(QLabel("Cell (mas):")); h_grid.addWidget(self.input_cellsize)
        h_grid.addStretch()
        ip.addLayout(h_grid)

        h_uvf_hdr = QHBoxLayout(); h_uvf_hdr.setSpacing(6)
        lbl_uvf = QLabel("UV Filtering")
        lbl_uvf.setStyleSheet(f"color: {D.ASTRAL_TEXT}; font-size: 10px; font-weight: 500;")
        self.chk_uv_filter = QPushButton("OFF")
        self.chk_uv_filter.setCheckable(True); self.chk_uv_filter.setChecked(False)
        self.chk_uv_filter.setStyleSheet(toggle_style)
        self.chk_uv_filter.setToolTip("Activer le filtre de plage UV (uvrange) en Mλ")
        h_uvf_hdr.addWidget(lbl_uvf); h_uvf_hdr.addStretch(); h_uvf_hdr.addWidget(self.chk_uv_filter)
        ip.addLayout(h_uvf_hdr)

        self._uv_filter_box = QWidget()
        h_uvf = QHBoxLayout(self._uv_filter_box)
        h_uvf.setContentsMargins(0, 0, 0, 0); h_uvf.setSpacing(6)
        lbl_uvfmin = QLabel("UV min"); lbl_uvfmin.setFixedWidth(40)
        self.input_uvfilter_min = QLineEdit(); self.input_uvfilter_min.setPlaceholderText("0")
        self.input_uvfilter_min.setStyleSheet(field_s); self.input_uvfilter_min.setEnabled(False)
        self.input_uvfilter_min.setToolTip("Rayon UV minimum (Mλ)")
        lbl_uvfmax = QLabel("UV max"); lbl_uvfmax.setFixedWidth(40)
        self.input_uvfilter_max = QLineEdit(); self.input_uvfilter_max.setPlaceholderText("0")
        self.input_uvfilter_max.setStyleSheet(field_s); self.input_uvfilter_max.setEnabled(False)
        self.input_uvfilter_max.setToolTip("Rayon UV maximum (Mλ)")
        h_uvf.addWidget(lbl_uvfmin); h_uvf.addWidget(self.input_uvfilter_min)
        h_uvf.addWidget(lbl_uvfmax); h_uvf.addWidget(self.input_uvfilter_max)
        ip.addWidget(self._uv_filter_box)

        h_wt = QHBoxLayout(); h_wt.setSpacing(6)
        h_wt.addWidget(QLabel("Weighting:"))
        self.combo_weight = QComboBox()
        self.combo_weight.addItems(["None", "Natural", "Uniform"])
        self.combo_weight.setToolTip(
            "Pondération des baselines UV\n"
            "  None     : paramètres par défaut Difmap (bin=2, errpow=0)\n"
            "  Natural  : uvweight 0,-2  (1/σ² — meilleure sensibilité)\n"
            "  Uniform  : uvweight 2,0   (résolution maximale)"
        )
        h_wt.addWidget(self.combo_weight)
        ip.addLayout(h_wt)

        h_tap = QHBoxLayout(); h_tap.setSpacing(6)
        h_tap.addWidget(QLabel("Taper (Mλ):"))
        self.input_taper = QLineEdit("0"); self.input_taper.setFixedWidth(52)
        self.input_taper.setToolTip("Taper gaussien — 0 = aucun")
        h_tap.addWidget(self.input_taper); h_tap.addStretch()
        ip.addLayout(h_tap)

        self.btn_apply_imaging = SecondaryButton("Apply")
        self.btn_apply_imaging.setToolTip("Appliquer les paramètres d'imagerie au moteur")
        ip.addWidget(self.btn_apply_imaging)

        layout.addWidget(self._imaging_params_section)

        # ══════════════════════════════════════════════════════════
        # DIRTY MAP BUTTON — onglet Dirty Map uniquement
        # ══════════════════════════════════════════════════════════
        self._dirty_btn_section = QWidget()
        db = QVBoxLayout(self._dirty_btn_section)
        db.setContentsMargins(0, 0, 0, 0); db.setSpacing(4)
        self.btn_compute = PrimaryButton("⊞  Make Dirty Map")
        self.btn_compute.setToolTip("Calculer la Dirty Map (invert)")
        db.addWidget(self.btn_compute)
        layout.addWidget(self._dirty_btn_section)

        # ══════════════════════════════════════════════════════════
        # CLEAN CONTROLS — Residual + Clean Map
        # ══════════════════════════════════════════════════════════
        self._clean_controls_section = QWidget()
        cc = QVBoxLayout(self._clean_controls_section)
        cc.setContentsMargins(0, 0, 0, 0); cc.setSpacing(4)
        cc.addWidget(self._thin_sep())
        cc.addWidget(self._subsection_header("Clean"))

        lbl_params = QLabel("Parameters")
        lbl_params.setStyleSheet(f"color: {D.ASTRAL_DIM}; font-size: 9px;")
        cc.addWidget(lbl_params)

        h_nc = QHBoxLayout(); h_nc.setSpacing(6)
        h_nc.addWidget(QLabel("Total Niter:"))
        self.input_niter = QLineEdit("1000"); self.input_niter.setFixedWidth(60)
        self.input_niter.setToolTip("Nombre total d'itérations CLEAN")
        h_nc.addWidget(self.input_niter); h_nc.addStretch()
        cc.addLayout(h_nc)

        h_gain = QHBoxLayout(); h_gain.setSpacing(6)
        h_gain.addWidget(QLabel("Loop Gain:"))
        self.input_gain = QLineEdit("0.05"); self.input_gain.setFixedWidth(60)
        self.input_gain.setToolTip("Gain de boucle CLEAN (0–1)")
        h_gain.addWidget(self.input_gain); h_gain.addStretch()
        cc.addLayout(h_gain)

        h_cutoff = QHBoxLayout(); h_cutoff.setSpacing(6)
        h_cutoff.addWidget(QLabel("Cutoff (Jy/bm):"))
        self.input_cutoff = QLineEdit("0.001"); self.input_cutoff.setFixedWidth(60)
        self.input_cutoff.setToolTip("Seuil de flux résiduel (Jy/beam) — 0 = pas de limite")
        h_cutoff.addWidget(self.input_cutoff); h_cutoff.addStretch()
        cc.addLayout(h_cutoff)

        h_bp_hdr = QHBoxLayout(); h_bp_hdr.setSpacing(6)
        lbl_bp = QLabel("Conditional Breakpoints")
        lbl_bp.setStyleSheet(f"color: {D.ASTRAL_TEXT}; font-size: 10px;")
        self.chk_conditional_bp = QPushButton("OFF")
        self.chk_conditional_bp.setCheckable(True); self.chk_conditional_bp.setChecked(False)
        self.chk_conditional_bp.setStyleSheet(toggle_style)
        self.chk_conditional_bp.setToolTip("Pause automatique après X itérations")
        h_bp_hdr.addWidget(lbl_bp); h_bp_hdr.addStretch(); h_bp_hdr.addWidget(self.chk_conditional_bp)
        cc.addLayout(h_bp_hdr)

        self._bp_box = QWidget()
        h_bp = QHBoxLayout(self._bp_box)
        h_bp.setContentsMargins(0, 0, 0, 0); h_bp.setSpacing(6)
        h_bp.addWidget(QLabel("Pause after"))
        self.input_pause_after = QLineEdit("100"); self.input_pause_after.setFixedWidth(52)
        self.input_pause_after.setStyleSheet(field_s); self.input_pause_after.setEnabled(False)
        h_bp.addWidget(self.input_pause_after)
        h_bp.addWidget(QLabel("iters")); h_bp.addStretch()
        cc.addWidget(self._bp_box)

        h_prog = QHBoxLayout(); h_prog.setSpacing(4)
        h_prog.addWidget(QLabel("Progress"))
        self.lbl_progress = QLabel("0 / 0")
        self.lbl_progress.setStyleSheet(f"color: {D.ASTRAL_DIM}; font-size: 10px;")
        self.lbl_progress.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        h_prog.addWidget(self.lbl_progress)
        cc.addLayout(h_prog)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0); self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0); self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {D.ASTRAL_SURFACE}; border: 1px solid {D.ASTRAL_BORDER};
                border-radius: 4px;
            }}
            QProgressBar::chunk {{ background-color: {D.ASTRAL_ACCENT}; border-radius: 4px; }}
        """)
        cc.addWidget(self.progress_bar)

        h_sp = QHBoxLayout(); h_sp.setSpacing(6)
        self.btn_compute_clean = PrimaryButton("▶  Start")
        self.btn_compute_clean.setToolTip("Lancer invert + CLEAN + restore")
        self.btn_pause_clean = QPushButton("⏸  Pause")
        self.btn_pause_clean.setEnabled(False)
        self.btn_pause_clean.setToolTip("Suspendre / reprendre le CLEAN")
        self.btn_pause_clean.setStyleSheet(f"""
            QPushButton {{
                background-color: {D.ASTRAL_SURFACE}; color: {D.ASTRAL_MUTED};
                border: 1px solid {D.ASTRAL_BORDER}; border-radius: 4px;
                padding: 6px 10px; font-size: 11px;
            }}
            QPushButton:enabled {{
                background-color: #8B2222; color: #FFFFFF; border-color: #8B2222;
            }}
            QPushButton:enabled:hover {{ background-color: #A03030; }}
        """)
        h_sp.addWidget(self.btn_compute_clean); h_sp.addWidget(self.btn_pause_clean)
        cc.addLayout(h_sp)
        layout.addWidget(self._clean_controls_section)

        # ══════════════════════════════════════════════════════════
        # MAP DISPLAY — tous les onglets carte
        # ══════════════════════════════════════════════════════════
        self._map_display_section = QWidget()
        md = QVBoxLayout(self._map_display_section)
        md.setContentsMargins(0, 0, 0, 0); md.setSpacing(4)
        md.addWidget(self._thin_sep())
        md.addWidget(self._subsection_header("Map Display"))

        h_cmap = QHBoxLayout(); h_cmap.setSpacing(6)
        h_cmap.addWidget(QLabel("Color Map:"))
        self.combo_colormap = QComboBox()
        self.combo_colormap.addItems(["inferno", "viridis", "gray", "hot", "plasma"])
        self.combo_colormap.setToolTip(
            "inferno : pseudo-color (proche du défaut difmap)\n"
            "viridis : colorblind-friendly\n"
            "gray    : niveaux de gris (G natif difmap)\n"
            "hot     : chaud\n"
            "plasma  : alternative vibrante"
        )
        h_cmap.addWidget(self.combo_colormap)
        md.addLayout(h_cmap)
        layout.addWidget(self._map_display_section)

        # ── Show Windows — Residual + Clean ──────────────────────
        self._display_windows_section = QWidget()
        dw = QVBoxLayout(self._display_windows_section)
        dw.setContentsMargins(0, 0, 0, 0); dw.setSpacing(2)
        self.chk_show_windows = QCheckBox("Show Windows  [W]")
        self.chk_show_windows.setChecked(True)
        self.chk_show_windows.setToolTip("Afficher les rectangles des fenêtres CLEAN")
        dw.addWidget(self.chk_show_windows)
        layout.addWidget(self._display_windows_section)

        # ── Affichage avancé — Clean Map uniquement ───────────────
        self._display_clean_section = QWidget()
        dc = QVBoxLayout(self._display_clean_section)
        dc.setContentsMargins(0, 0, 0, 0); dc.setSpacing(4)

        h_sc = QHBoxLayout(); h_sc.setSpacing(6)
        h_sc.addWidget(QLabel("Scale:"))
        self.combo_scale = QComboBox()
        self.combo_scale.addItems(["Linear", "Log", "Sqrt"])
        self.combo_scale.setToolTip("Échelle de couleur (mapfunc)")
        h_sc.addWidget(self.combo_scale)
        dc.addLayout(h_sc)

        h_range = QHBoxLayout(); h_range.setSpacing(6)
        h_range.addWidget(QLabel("Min:"))
        self.input_vmin = QLineEdit(); self.input_vmin.setPlaceholderText("auto")
        h_range.addWidget(self.input_vmin)
        h_range.addWidget(QLabel("Max:"))
        self.input_vmax = QLineEdit(); self.input_vmax.setPlaceholderText("auto")
        h_range.addWidget(self.input_vmax)
        dc.addLayout(h_range)

        h_ctr = QHBoxLayout(); h_ctr.setSpacing(6)
        h_ctr.addWidget(QLabel("Contours:"))
        self.combo_contour_mode = QComboBox()
        self.combo_contour_mode.addItems(["Standard %", "Log", "Custom"])
        self.combo_contour_mode.setToolTip("levs / loglevs / niveaux personnalisés")
        h_ctr.addWidget(self.combo_contour_mode)
        dc.addLayout(h_ctr)

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
        dc.addWidget(self._widget_log_params)

        self._widget_custom_levels = QWidget()
        v_custom = QVBoxLayout(self._widget_custom_levels)
        v_custom.setContentsMargins(0, 0, 0, 0); v_custom.setSpacing(2)
        v_custom.addWidget(QLabel("Levels (% of peak):"))
        self.input_custom_levels = QLineEdit()
        self.input_custom_levels.setPlaceholderText("ex: -1 1 2 4 8 16 32 64 | 1:64:*2")
        v_custom.addWidget(self.input_custom_levels)
        self._widget_custom_levels.setVisible(False)
        dc.addWidget(self._widget_custom_levels)

        self.chk_show_model_map = QCheckBox("Show Model Components  [M]")
        self.chk_show_model_map.setToolTip("Afficher les composantes CLEAN sur la carte")
        self.chk_show_model_map.setChecked(False)
        dc.addWidget(self.chk_show_model_map)

        self.btn_refresh_view = SecondaryButton("↻  Refresh View")
        self.btn_refresh_view.setToolTip("Appliquer l'affichage sans recalculer la carte")
        dc.addWidget(self.btn_refresh_view)
        layout.addWidget(self._display_clean_section)

        # ── Connexions internes ───────────────────────────────────
        def _on_uvf_toggle(checked):
            self.chk_uv_filter.setText("ON" if checked else "OFF")
            for w in (self.input_uvfilter_min, self.input_uvfilter_max):
                w.setEnabled(checked)

        def _on_bp_toggle(checked):
            self.chk_conditional_bp.setText("ON" if checked else "OFF")
            self.input_pause_after.setEnabled(checked)

        self.chk_uv_filter.toggled.connect(_on_uvf_toggle)
        self.chk_conditional_bp.toggled.connect(_on_bp_toggle)
        self.combo_contour_mode.currentIndexChanged.connect(self._on_contour_mode_changed)
        self.combo_colormap.currentTextChanged.connect(lambda t: self.colormap_changed.emit(t))
        self.chk_show_windows.toggled.connect(lambda v: self.show_windows_changed.emit(v))

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
