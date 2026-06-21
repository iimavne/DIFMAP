# difmap_wrapper/gui/components/control_panel.py
from PyQt6.QtWidgets import (QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QComboBox, QLineEdit, QCheckBox,
                             QScrollArea, QSlider, QPushButton, QMessageBox,
                             QColorDialog, QSpinBox, QFrame, QProgressBar,
                             QGridLayout, QToolButton)
from PyQt6.QtGui import QColor, QPainter, QBrush, QPen
from PyQt6.QtCore import pyqtSignal, QRect
from PyQt6.QtCore import Qt
import qtawesome as qta
from .styled_buttons import PrimaryButton, SecondaryButton
from difmap_wrapper.gui.styles import DesignSystem
from difmap_wrapper.enums import POLARIZATIONS

D = DesignSystem

# Style de base pour les éléments classiques
_QSS = D.get_panel_qss()
_TOGGLE_QSS = D.get_panel_toggle_button_qss()
_FIELD_QSS = D.get_panel_field_qss()

class RangeSlider(QWidget):
    """Slider double-poignée (min / max) sur une même piste.

    invert=True : axe visuel inversé (droite→gauche), comme l'axe U du plan UV.
    Les valeurs émises restent toujours (lo, hi) en unités réelles.
    """

    range_changed = pyqtSignal(float, float)  # (lo, hi) en unités réelles

    _HANDLE = 10
    _TRACK_H = 4

    def __init__(self, minimum=0.0, maximum=1000.0, invert=False, parent=None):
        super().__init__(parent)
        self.setFixedHeight(28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._min    = float(minimum)
        self._max    = float(maximum)
        self._lo     = float(minimum)
        self._hi     = float(maximum)
        self._invert = invert
        self._drag   = None   # 'lo' | 'hi' | None

    # ── API publique ──────────────────────────────────────────────
    def set_data_range(self, minimum: float, maximum: float) -> None:
        self._min = float(minimum)
        self._max = float(maximum)
        self._lo  = float(minimum)
        self._hi  = float(maximum)
        self.update()

    def set_values(self, lo: float, hi: float) -> None:
        self._lo = max(self._min, min(float(lo), self._max))
        self._hi = max(self._min, min(float(hi), self._max))
        self.update()

    def values(self) -> tuple[float, float]:
        return (self._lo, self._hi)

    # ── Coordonnées ───────────────────────────────────────────────
    def _x_for(self, val: float) -> int:
        r = self._max - self._min
        t = self._track_rect()
        if r == 0:
            return t.left()
        frac = (val - self._min) / r
        if self._invert:
            frac = 1.0 - frac
        return int(t.left() + frac * t.width())

    def _val_for(self, x: float) -> float:
        t = self._track_rect()
        frac = max(0.0, min(1.0, (x - t.left()) / max(1, t.width())))
        if self._invert:
            frac = 1.0 - frac
        return self._min + frac * (self._max - self._min)

    def _track_rect(self) -> QRect:
        h = self._HANDLE
        return QRect(h // 2, (self.height() - self._TRACK_H) // 2,
                     self.width() - h, self._TRACK_H)

    # ── Rendu ─────────────────────────────────────────────────────
    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        t = self._track_rect()
        h = self._HANDLE

        p.setBrush(QBrush(QColor(D.ASTRAL_SURFACE)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(t, 2, 2)

        x_lo = self._x_for(self._lo)
        x_hi = self._x_for(self._hi)
        # Zone sélectionnée entre les deux poignées (quelle que soit l'inversion)
        x_left  = min(x_lo, x_hi)
        x_right = max(x_lo, x_hi)
        sel = QRect(x_left, t.top(), max(2, x_right - x_left), t.height())
        p.setBrush(QBrush(QColor(D.ASTRAL_ACCENT)))
        p.drawRect(sel)

        for x in (x_lo, x_hi):
            p.setBrush(QBrush(QColor("#FFFFFF")))
            p.setPen(QPen(QColor(D.ASTRAL_ACCENT), 2))
            p.drawEllipse(x - h // 2, (self.height() - h) // 2, h, h)

        p.end()

    # ── Interactions ──────────────────────────────────────────────
    def mousePressEvent(self, ev):
        if ev.button() != Qt.MouseButton.LeftButton:
            return
        x = ev.position().x()
        x_lo = self._x_for(self._lo)
        x_hi = self._x_for(self._hi)
        self._drag = 'lo' if abs(x - x_lo) <= abs(x - x_hi) else 'hi'
        self._move_drag(x)

    def mouseMoveEvent(self, ev):
        if self._drag:
            self._move_drag(ev.position().x())

    def mouseReleaseEvent(self, _ev):
        self._drag = None

    def _move_drag(self, x: float) -> None:
        val = self._val_for(x)
        if self._drag == 'lo':
            self._lo = max(self._min, min(val, self._hi))
        else:
            self._hi = min(self._max, max(val, self._lo))
        self.update()
        self.range_changed.emit(self._lo, self._hi)


class _IFRangeBar(QWidget):
    """Barre horizontale indiquant visuellement les IFs sélectionnés (contigus ou non)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(10)
        self._total = 1
        self._selected: list[int] = []  # liste 1-indexed des IFs sélectionnés

    def update_range(self, beg: int, end: int, total: int):
        """Mise à jour mode plage contigüe."""
        self._total = max(1, total)
        self._selected = list(range(beg, end + 1))
        self.update()

    def update_list(self, if_list: list[int], total: int):
        """Mise à jour mode liste non-contigüe."""
        self._total = max(1, total)
        self._selected = list(if_list)
        self.update()

    def paintEvent(self, event):
        from PyQt6.QtGui import QPainter, QColor, QPen
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        p.fillRect(0, 0, w, h, QColor(D.ASTRAL_DEEP))

        cell_w = w / self._total
        for cif in self._selected:
            if 1 <= cif <= self._total:
                x = int((cif - 1) * cell_w)
                bw = max(1, int(cell_w) - 1)
                p.fillRect(x, 1, bw, h - 2, QColor(D.ASTRAL_ACCENT))

        pen = QPen(QColor(D.ASTRAL_BORDER))
        pen.setWidth(1)
        p.setPen(pen)
        p.drawRect(0, 0, w - 1, h - 1)
        p.end()


class ToggleSwitch(QPushButton):
    """Interrupteur iOS-style (ovale coloré + cercle blanc glissant)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(44, 24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggled.connect(self._refresh)
        self._refresh(False)

    def _refresh(self, checked: bool):
        bg = D.ASTRAL_ACCENT if checked else D.ASTRAL_MUTED
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                border-radius: 12px;
                border: none;
            }}
        """)
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        from PyQt6.QtGui import QPainter, QBrush, QColor
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor("#FFFFFF")))
        margin = 4
        size = self.height() - 2 * margin
        x = self.width() - size - margin if self.isChecked() else margin
        p.drawEllipse(x, margin, size, size)
        p.end()


class LabeledToggle(QWidget):
    """Switch iOS-style avec label intégré — label à gauche, switch à droite.

    Drop-in replacement de QCheckBox pour les lignes autonomes.
    setVisible / setEnabled / blockSignals / setChecked / isChecked / toggled
    se comportent exactement comme sur QCheckBox.
    """
    toggled = pyqtSignal(bool)

    def __init__(self, label_text, parent=None):
        super().__init__(parent)
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 2, 0, 2)
        h.setSpacing(8)
        self._lbl = QLabel(label_text)
        self._lbl.setStyleSheet(
            f"color: {D.ASTRAL_TEXT}; font-size: {D.FONT_SIZE_BASE}; background: transparent;"
        )
        self._sw = ToggleSwitch()
        self._sw.toggled.connect(self.toggled)
        h.addWidget(self._lbl)
        h.addStretch()
        h.addWidget(self._sw)

    def setChecked(self, v: bool) -> None:
        self._sw.setChecked(v)

    def isChecked(self) -> bool:
        return self._sw.isChecked()

    def setToolTip(self, text: str) -> None:
        super().setToolTip(text)
        self._sw.setToolTip(text)


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
                border-radius: {D.RADIUS_MD};
                padding: 10px 9px;
                text-align: left;
                font-weight: bold;
                font-size: {D.FONT_SIZE_BASE};
                min-width: 150px;
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
                border-bottom-left-radius: {D.RADIUS_MD};
                border-bottom-right-radius: {D.RADIUS_MD};
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
    if_select_syntax_changed = pyqtSignal(str)   # syntaxe difmap brute
    chan_select_syntax_changed = pyqtSignal(str)  # syntaxe canaux brute
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
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.container = QWidget()
        self.main_layout = QVBoxLayout(self.container)
        self.main_layout.setSpacing(14)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.container.setStyleSheet(_QSS)

        self._build_data_selection()
        self._build_telescope_focus()
        self._build_display_options()
        self._build_imaging()

        self.main_layout.addStretch()

        lbl = QLabel("Press H for keyboard shortcuts")
        lbl.setStyleSheet(f"color: {D.ASTRAL_DIM}; font-size: {D.FONT_SIZE_XS}; font-style: italic;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(lbl)

        scroll.setWidget(self.container)
        self.setWidget(scroll)

    def set_uv_data_range(self, umin: float, umax: float, vmin: float, vmax: float) -> None:
        """Cale les sliders UV et affiche les vraies valeurs comme placeholder."""
        self._slider_u.set_data_range(umin, umax)
        self._slider_v.set_data_range(vmin, vmax)
        def _f(v): return f"{v:.2f}"
        # U inversé : inp_umin ↔ positif (umax), inp_umax ↔ négatif (umin)
        self.input_umin.setPlaceholderText(_f(umax))
        self.input_umax.setPlaceholderText(_f(umin))
        self.input_vmin_uv.setPlaceholderText(_f(vmin))
        self.input_vmax_uv.setPlaceholderText(_f(vmax))

    def set_rad_data_range(self, uv_max: float, amp_max: float) -> None:
        """Cale les sliders Radplot et affiche les vraies valeurs comme placeholder."""
        self._slider_rad_uv.set_data_range(0.0, uv_max)
        self._slider_rad_amp.set_data_range(0.0, amp_max)
        def _f(v): return f"{v:.2f}"
        self.input_rad_uvmin.setPlaceholderText(_f(0.0))
        self.input_rad_uvmax.setPlaceholderText(_f(uv_max))
        self.input_rad_ampmin.setPlaceholderText(_f(0.0))
        self.input_rad_ampmax.setPlaceholderText(_f(amp_max))
        self.input_rad_phsmin.setPlaceholderText("-180.00")
        self.input_rad_phsmax.setPlaceholderText("180.00")
        # Phase : toujours −180 / +180

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

        # --- Sélecteur d'IFs (syntaxe difmap) ---
        btn_all_style = f"""
            QPushButton {{
                background-color: {D.ASTRAL_SURFACE};
                border: 1px solid {D.ASTRAL_BORDER};
                border-radius: {D.RADIUS_MD};
                color: {D.ASTRAL_TEXT};
                font-size: {D.FONT_SIZE_XS};
                padding: 3px 7px;
            }}
            QPushButton:hover {{ background-color: {D.ASTRAL_HOVER}; color: {D.ASTRAL_TEXT}; }}
        """

        h_ifs = QHBoxLayout()
        h_ifs.setSpacing(4)
        h_ifs.addWidget(QLabel("IFs:"))

        self.input_if_select = QLineEdit()
        self.input_if_select.setPlaceholderText("e.g. 1-3  or  1,3,5  or  2:5-10")
        self.input_if_select.setEnabled(False)
        self.input_if_select.setStyleSheet(_QSS)
        self.input_if_select.setToolTip(
            "Syntaxe difmap :\n"
            "  1-3       → IFs 1 à 3\n"
            "  1,3,5     → IFs 1, 3 et 5\n"
            "  2:5-10    → IF 2, canaux locaux 5–10\n"
            "  1,3:2-5   → IFs 1 et 3, canaux 2–5\n"
            "  (vide)    → tous les IFs"
        )

        self._btn_ifs_all = QPushButton("All")
        self._btn_ifs_all.setFixedWidth(36)
        self._btn_ifs_all.setFixedHeight(22)
        self._btn_ifs_all.setEnabled(False)
        self._btn_ifs_all.setStyleSheet(btn_all_style)
        self._btn_ifs_all.setToolTip("Sélectionner tous les IFs")

        h_ifs.addWidget(self.input_if_select)
        h_ifs.addWidget(self._btn_ifs_all)
        layout.addLayout(h_ifs)

        # Label d'erreur de syntaxe (caché par défaut)
        self._lbl_if_syntax_err = QLabel("")
        self._lbl_if_syntax_err.setStyleSheet(
            f"color: #FF6B6B; font-size: {D.FONT_SIZE_XS}; padding: 0px;"
        )
        self._lbl_if_syntax_err.setVisible(False)
        layout.addWidget(self._lbl_if_syntax_err)

        # Barre visuelle des IFs sélectionnés
        self._if_range_bar = _IFRangeBar()
        layout.addWidget(self._if_range_bar)

        # Label d'info : "N IFs · M ch/IF"
        self._lbl_if_info = QLabel("—")
        self._lbl_if_info.setStyleSheet(
            f"color: {D.ASTRAL_DIM}; font-size: {D.FONT_SIZE_XS}; padding: 0px;"
        )
        layout.addWidget(self._lbl_if_info)

        # --- Sélecteur de canaux (restriction) ---
        h_ch = QHBoxLayout()
        h_ch.setSpacing(4)
        h_ch.addWidget(QLabel("Channels:"))

        self._btn_mapping_info = QPushButton("Info")
        self._btn_mapping_info.setFixedWidth(44)
        self._btn_mapping_info.setFixedHeight(22)
        self._btn_mapping_info.setEnabled(False)
        self._btn_mapping_info.setStyleSheet(btn_all_style)
        self._btn_mapping_info.setToolTip("Afficher le mapping IF → canaux globaux")
        h_ch.addWidget(self._btn_mapping_info)

        self.input_chan_select = QLineEdit()
        self.input_chan_select.setPlaceholderText("e.g. 2:5-10  or  20-25,47-65  or  nif*nchan")
        self.input_chan_select.setEnabled(False)
        self.input_chan_select.setStyleSheet(_QSS)

        self._btn_ch_all = QPushButton("All")
        self._btn_ch_all.setFixedWidth(36)
        self._btn_ch_all.setFixedHeight(22)
        self._btn_ch_all.setEnabled(False)
        self._btn_ch_all.setStyleSheet(btn_all_style)
        self._btn_ch_all.setToolTip("Sélectionner tous les canaux")

        h_ch.addWidget(self.input_chan_select)
        h_ch.addWidget(self._btn_ch_all)
        layout.addLayout(h_ch)

        self._lbl_chan_syntax_err = QLabel("")
        self._lbl_chan_syntax_err.setStyleSheet(
            f"color: #FF6B6B; font-size: {D.FONT_SIZE_XS}; padding: 0px;"
        )
        self._lbl_chan_syntax_err.setVisible(False)
        layout.addWidget(self._lbl_chan_syntax_err)

        self._lbl_chan_info = QLabel("—")
        self._lbl_chan_info.setStyleSheet(
            f"color: {D.ASTRAL_DIM}; font-size: {D.FONT_SIZE_XS}; padding: 0px;"
        )
        layout.addWidget(self._lbl_chan_info)

        self._mapping_dialog_text = ""

        self._n_ifs_total = 1
        self._n_chan_total = 0
        self._if_selecting = False   # garde anti-ré-entrant
        self._chan_selecting = False

        # Un seul signal — editingFinished couvre Entrée ET perte de focus.
        # returnPressed est volontairement absent pour éviter le double déclenchement.
        self.input_if_select.editingFinished.connect(self._on_if_syntax_entered)
        self._btn_ifs_all.clicked.connect(self._select_all_ifs)

        self.input_chan_select.editingFinished.connect(self._on_chan_syntax_entered)
        self._btn_ch_all.clicked.connect(self._select_all_channels)
        self._btn_mapping_info.clicked.connect(self._show_mapping_info)

        self.main_layout.addWidget(self.group_data_selection)
        # NB : combo_pol est géré exclusivement par MainWindow._change_polarization
        # (pas de double connexion ici pour éviter les doubles appels obs.select)

    def set_if_range(self, n_ifs: int, nchan: int = 0) -> None:
        """Configure le sélecteur pour *n_ifs* IFs et remet la sélection à tous."""
        self._n_ifs_total = max(1, n_ifs)
        self._n_chan_total = max(0, nchan)
        self.input_if_select.blockSignals(True)
        self.input_if_select.clear()
        self.input_if_select.blockSignals(False)
        self.input_chan_select.blockSignals(True)
        self.input_chan_select.clear()
        self.input_chan_select.blockSignals(False)

        for w in (self.input_if_select, self._btn_ifs_all, self.input_chan_select, self._btn_ch_all, self._btn_mapping_info):
            w.setEnabled(True)
        self._lbl_if_syntax_err.setVisible(False)
        self._lbl_chan_syntax_err.setVisible(False)
        self._if_range_bar.update_range(1, self._n_ifs_total, self._n_ifs_total)

        # Mettre à jour le label d'info et le placeholder avec les vraies valeurs
        nc = max(1, nchan)
        total = n_ifs * nc
        if nchan > 1:
            self._lbl_if_info.setText(
                f"{n_ifs} IFs  ·  {nchan} ch/IF  ·  {total} canaux total"
            )
            self._lbl_chan_info.setText(
                f"Syntaxe locale: IF:canal1-canal2  |  Syntaxe globale: 1..{total}  |  nif*nchan={total}"
            )
            self.input_if_select.setPlaceholderText("e.g. 1-3  or  1,3,5  (empty = all IFs)")
        else:
            self._lbl_if_info.setText(f"{n_ifs} IFs  ·  {total} canaux total")
            self.input_if_select.setPlaceholderText("e.g. 1-3  or  1,3,5  (empty = all IFs)")

        # Tooltip : mapping IF → plage de canaux globaux (info), et tooltip IFs = IFs only
        lines = ["Channels per IF (global indices):", ""]
        for cif in range(1, n_ifs + 1):
            bch = (cif - 1) * nc + 1
            ech = cif * nc
            if nc == 1:
                lines.append(f"  IF {cif:2d}  →  ch {bch}")
            else:
                lines.append(f"  IF {cif:2d}  →  ch {bch} – {ech}")
        lines += ["", "Global channels range: 1..nif*nchan"]
        self._lbl_if_info.setToolTip("\n".join(lines))

        self._mapping_dialog_text = "\n".join(lines)

        self._lbl_chan_info.setToolTip("\n".join(lines))
        self.input_if_select.setToolTip(
            "IF selection:\n"
            "  1-3     → IFs 1 to 3\n"
            "  1,3,5   → IFs 1, 3 and 5\n"
            "  Empty   → all IFs"
        )

        self.input_chan_select.setToolTip(
            "Channels restriction:\n"
            "  Local:  2:5-10   or   1,3:2-5\n"
            "  Global: 20-25,47-65   or   20,25,47,65\n"
            "  Vars: nif, nchan, nif*nchan\n"
            "  Empty = all channels"
        )

    def _select_all_ifs(self):
        self.input_if_select.blockSignals(True)
        self.input_if_select.clear()
        self.input_if_select.blockSignals(False)
        self._lbl_if_syntax_err.setVisible(False)
        self._if_range_bar.update_range(1, self._n_ifs_total, self._n_ifs_total)
        self.if_select_syntax_changed.emit("")

    def _select_all_channels(self):
        self.input_chan_select.blockSignals(True)
        self.input_chan_select.clear()
        self.input_chan_select.blockSignals(False)
        self._lbl_chan_syntax_err.setVisible(False)
        self.chan_select_syntax_changed.emit("")

    def _on_if_syntax_entered(self):
        if self._if_selecting:
            return
        self._if_selecting = True
        try:
            text = self.input_if_select.text().strip()
            self._lbl_if_syntax_err.setVisible(False)
            self.if_select_syntax_changed.emit(text)
        finally:
            self._if_selecting = False

    def _on_chan_syntax_entered(self):
        if self._chan_selecting:
            return
        self._chan_selecting = True
        try:
            text = self.input_chan_select.text().strip()
            self._lbl_chan_syntax_err.setVisible(False)
            self.chan_select_syntax_changed.emit(text)
        finally:
            self._chan_selecting = False

    def update_if_bar(self, selected_ifs: list[int]) -> None:
        """Met à jour la barre visuelle avec la liste (1-indexed) des IFs sélectionnés."""
        self._if_range_bar.update_list(selected_ifs, self._n_ifs_total)

    def show_if_syntax_error(self, msg: str) -> None:
        self._lbl_if_syntax_err.setText(msg)
        self._lbl_if_syntax_err.setVisible(True)

    def show_chan_syntax_error(self, msg: str) -> None:
        self._lbl_chan_syntax_err.setText(msg)
        self._lbl_chan_syntax_err.setVisible(True)

    def _show_mapping_info(self) -> None:
        QMessageBox.information(self, "IF ↔ Channels mapping", self._mapping_dialog_text or "—")
        
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
        self.chk_conjugate = LabeledToggle("Conjugate points  [%]")
        self.chk_conjugate.setChecked(True)
        self.chk_model     = LabeledToggle("Model overlay  [M]")
        self.chk_residuals = LabeledToggle("Residuals (Data − Model)  [−]")
        self.chk_crosshair = QCheckBox("Full-screen crosshair  [+]")
        self.chk_errors    = LabeledToggle("Error plot (1/√w)  [E]")

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

        toggle_style = _TOGGLE_QSS
        field_style = _FIELD_QSS

        h_uv_hdr = QHBoxLayout()
        lbl_uv = QLabel("Limite plan UV")
        lbl_uv.setStyleSheet(f"color: {D.ASTRAL_TEXT}; font-size: {D.FONT_SIZE_BASE}; font-weight: 600;")
        self.chk_uv_limit = ToggleSwitch()
        self.chk_uv_limit.setToolTip("Activer les limites manuelles du plan UV")
        h_uv_hdr.addWidget(lbl_uv)
        h_uv_hdr.addStretch()
        h_uv_hdr.addWidget(self.chk_uv_limit)
        _uv_sec.addLayout(h_uv_hdr)

        self._uv_limit_box = QWidget()
        grid = QVBoxLayout(self._uv_limit_box)
        grid.setContentsMargins(0, 4, 0, 0)
        grid.setSpacing(6)

        def _make_uv_axis(axis: str, invert: bool = False):
            """Retourne (slider, inp_min, inp_max, reset_btn) pour un axe U ou V."""
            h_ax = QHBoxLayout(); h_ax.setContentsMargins(0, 0, 0, 0); h_ax.setSpacing(0)
            lbl_ax = QLabel(f"{axis}  (Mλ)")
            lbl_ax.setStyleSheet(f"color: {D.ASTRAL_DIM}; font-size: {D.FONT_SIZE_XS};")
            h_ax.addWidget(lbl_ax)
            if invert:
                lbl_orient = QLabel("  ← +   − →")
                lbl_orient.setStyleSheet(f"color: {D.ASTRAL_DIM}; font-size: {D.FONT_SIZE_XS}; font-style: italic;")
                h_ax.addStretch(); h_ax.addWidget(lbl_orient)
            grid.addLayout(h_ax)

            rs = RangeSlider(-1000.0, 1000.0, invert=invert)
            rs.setEnabled(False)
            grid.addWidget(rs)

            inp_min = QLineEdit(); inp_min.setPlaceholderText("—"); inp_min.setStyleSheet(field_style); inp_min.setEnabled(False)
            inp_min.setToolTip(f"Limite {axis} minimum (Mλ)")
            inp_max = QLineEdit(); inp_max.setPlaceholderText("—"); inp_max.setStyleSheet(field_style); inp_max.setEnabled(False)
            inp_max.setToolTip(f"Limite {axis} maximum (Mλ)")

            rst = QToolButton(); rst.setText("↺"); rst.setFixedWidth(32)
            rst.setToolTip(f"Réinitialiser l'axe {axis}")
            rst.setEnabled(False)
            rst.clicked.connect(lambda checked=False, _rs=rs, _a=inp_min, _b=inp_max: [
                _a.setText(""), _b.setText(""),
                _rs.set_values(_rs._min, _rs._max),
                _emit_uv_limits_checked()
            ])

            row = QHBoxLayout(); row.setSpacing(4)
            lbl_l = QLabel("min"); lbl_l.setStyleSheet(f"color: {D.ASTRAL_DIM}; font-size: {D.FONT_SIZE_XS};"); lbl_l.setFixedWidth(22)
            lbl_r = QLabel("max"); lbl_r.setStyleSheet(f"color: {D.ASTRAL_DIM}; font-size: {D.FONT_SIZE_XS};"); lbl_r.setFixedWidth(22)
            row.addWidget(lbl_l); row.addWidget(inp_min)
            row.addSpacing(4)
            row.addWidget(lbl_r); row.addWidget(inp_max)
            row.addWidget(rst)
            grid.addLayout(row)
            return rs, inp_min, inp_max, rst

        self._slider_u, self.input_umin, self.input_umax, self._rst_u = _make_uv_axis("U", invert=True)
        self._slider_v, self.input_vmin_uv, self.input_vmax_uv, self._rst_v = _make_uv_axis("V")

        rst_all_uv = QToolButton(); rst_all_uv.setText("↺  Reset all")
        rst_all_uv.setEnabled(False)
        def _reset_all_uv():
            for f in (self.input_umin, self.input_umax,
                      self.input_vmin_uv, self.input_vmax_uv):
                f.setText("")
            self._slider_u.set_values(self._slider_u._min, self._slider_u._max)
            self._slider_v.set_values(self._slider_v._min, self._slider_v._max)
            self._emit_uv_limits()
        rst_all_uv.clicked.connect(_reset_all_uv)
        self._rst_all_uv = rst_all_uv
        row_rst = QHBoxLayout(); row_rst.addStretch(); row_rst.addWidget(rst_all_uv)
        grid.addLayout(row_rst)

        _uv_sec.addWidget(self._uv_limit_box)
        layout.addWidget(self._uv_limits_section)

        def _parse_uv(field):
            t = field.text().strip()
            try:
                return float(t) if t and t.lower() != "auto" else None
            except ValueError:
                return None

        def _fmt(v: float) -> str:
            return f"{v:.1f}" if v != int(v) else str(int(v))

        def _emit_uv_limits_checked():
            if self.chk_uv_limit.isChecked():
                self._emit_uv_limits()

        self._emit_uv_limits = lambda: self.uv_limits_changed.emit(
            _parse_uv(self.input_umin), _parse_uv(self.input_umax),
            _parse_uv(self.input_vmin_uv), _parse_uv(self.input_vmax_uv),
        )

        def _on_slider_u(lo, hi):
            # U inversé : hi (positif) → champ "min" (gauche plot), lo (négatif) → champ "max" (droite plot)
            self.input_umin.blockSignals(True); self.input_umax.blockSignals(True)
            self.input_umin.setText(_fmt(hi)); self.input_umax.setText(_fmt(lo))
            self.input_umin.blockSignals(False); self.input_umax.blockSignals(False)
            _emit_uv_limits_checked()

        def _on_slider_v(lo, hi):
            self.input_vmin_uv.blockSignals(True); self.input_vmax_uv.blockSignals(True)
            self.input_vmin_uv.setText(_fmt(lo)); self.input_vmax_uv.setText(_fmt(hi))
            self.input_vmin_uv.blockSignals(False); self.input_vmax_uv.blockSignals(False)
            _emit_uv_limits_checked()

        def _on_field_u():
            # input_umin contient le positif (hi), input_umax contient le négatif (lo)
            hi = _parse_uv(self.input_umin); lo = _parse_uv(self.input_umax)
            mn, mx = self._slider_u._min, self._slider_u._max
            self._slider_u.set_values(lo if lo is not None else mn, hi if hi is not None else mx)
            _emit_uv_limits_checked()

        def _on_field_v():
            lo = _parse_uv(self.input_vmin_uv); hi = _parse_uv(self.input_vmax_uv)
            mn, mx = self._slider_v._min, self._slider_v._max
            self._slider_v.set_values(lo if lo is not None else mn, hi if hi is not None else mx)
            _emit_uv_limits_checked()

        self._slider_u.range_changed.connect(_on_slider_u)
        self._slider_v.range_changed.connect(_on_slider_v)
        self.input_umin.editingFinished.connect(_on_field_u)
        self.input_umax.editingFinished.connect(_on_field_u)
        self.input_vmin_uv.editingFinished.connect(_on_field_v)
        self.input_vmax_uv.editingFinished.connect(_on_field_v)

        def _on_uv_toggle(checked):
            for w in (self.input_umin, self.input_umax, self.input_vmin_uv, self.input_vmax_uv,
                      self._slider_u, self._slider_v,
                      self._rst_u, self._rst_v, self._rst_all_uv):
                w.setEnabled(checked)
            self._emit_uv_limits()

        self.chk_uv_limit.toggled.connect(_on_uv_toggle)

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
        lbl_rad_lim.setStyleSheet(f"color: {D.ASTRAL_TEXT}; font-size: {D.FONT_SIZE_BASE}; font-weight: 600;")
        self.chk_rad_limit = ToggleSwitch()
        self.chk_rad_limit.setToolTip("Activer les limites manuelles du Radplot")
        h_rad_hdr.addWidget(lbl_rad_lim)
        h_rad_hdr.addStretch()
        h_rad_hdr.addWidget(self.chk_rad_limit)
        _rad_sec.addLayout(h_rad_hdr)

        self._rad_limit_box = QWidget()
        _rlb = QVBoxLayout(self._rad_limit_box)
        _rlb.setContentsMargins(0, 4, 0, 0)
        _rlb.setSpacing(6)

        _rad_sliders: list = []
        _rad_fields_list: list = []
        _rad_rst_btns: list = []

        def _fmt_r(v: float) -> str:
            return f"{v:.2f}" if v != int(v) else str(int(v))

        def _parse_rad(field):
            t = field.text().strip()
            try:
                return float(t) if t and t.lower() != "auto" else None
            except ValueError:
                return None

        def _make_rad_block(parent_layout, title: str, sl_min: float, sl_max: float,
                            tip_min: str, tip_max: str, invert: bool = False):
            """Crée label + RangeSlider + champs min/max + reset. Retourne (slider, inp_min, inp_max, reset_btn)."""
            lbl = QLabel(title)
            lbl.setStyleSheet(f"color: {D.ASTRAL_DIM}; font-size: {D.FONT_SIZE_XS}; font-weight: bold;")
            parent_layout.addWidget(lbl)

            rs = RangeSlider(sl_min, sl_max, invert=invert)
            rs.setEnabled(False)
            parent_layout.addWidget(rs)
            _rad_sliders.append(rs)

            row = QHBoxLayout(); row.setSpacing(4)
            la = QLabel("min"); la.setStyleSheet(f"color: {D.ASTRAL_DIM}; font-size: {D.FONT_SIZE_XS};"); la.setFixedWidth(24)
            ia = QLineEdit(); ia.setPlaceholderText("—"); ia.setStyleSheet(field_style); ia.setToolTip(tip_min); ia.setEnabled(False)
            lb = QLabel("max"); lb.setStyleSheet(f"color: {D.ASTRAL_DIM}; font-size: {D.FONT_SIZE_XS};"); lb.setFixedWidth(24)
            ib = QLineEdit(); ib.setPlaceholderText("—"); ib.setStyleSheet(field_style); ib.setToolTip(tip_max); ib.setEnabled(False)

            rst = QToolButton(); rst.setText("↺"); rst.setFixedWidth(32)
            rst.setToolTip(f"Réinitialiser {title}")
            rst.setEnabled(False)
            rst.clicked.connect(lambda checked=False, _rs=rs, _a=ia, _b=ib: [
                _a.setText(""), _b.setText(""),
                _rs.set_values(_rs._min, _rs._max),
                self._emit_rad_limits() if self.chk_rad_limit.isChecked() else None
            ])

            row.addWidget(la); row.addWidget(ia); row.addSpacing(4); row.addWidget(lb); row.addWidget(ib)
            row.addWidget(rst)
            parent_layout.addLayout(row)
            _rad_fields_list.extend([ia, ib])
            _rad_rst_btns.append(rst)

            def _on_slider(lo, hi, _ia=ia, _ib=ib):
                _ia.blockSignals(True); _ib.blockSignals(True)
                _ia.setText(_fmt_r(lo)); _ib.setText(_fmt_r(hi))
                _ia.blockSignals(False); _ib.blockSignals(False)
                if self.chk_rad_limit.isChecked():
                    self._emit_rad_limits()

            def _on_fields(_rs=rs, _ia=ia, _ib=ib):
                lo = _parse_rad(_ia); hi = _parse_rad(_ib)
                _rs.set_values(lo if lo is not None else _rs._min,
                               hi if hi is not None else _rs._max)
                if self.chk_rad_limit.isChecked():
                    self._emit_rad_limits()

            rs.range_changed.connect(_on_slider)
            ia.editingFinished.connect(_on_fields)
            ib.editingFinished.connect(_on_fields)
            return rs, ia, ib, rst

        # ── UV Radius (toujours visible) ──────────────────────────
        self._slider_rad_uv, self.input_rad_uvmin, self.input_rad_uvmax, _ = _make_rad_block(
            _rlb, "UV Radius (Mλ)", 0.0, 1000.0, "UV radius minimum (Mλ)", "UV radius maximum (Mλ)")

        # ── Amplitude (mode 1 ou 3) ───────────────────────────────
        self._rad_amp_box = QWidget()
        _amp_l = QVBoxLayout(self._rad_amp_box); _amp_l.setContentsMargins(0, 0, 0, 0); _amp_l.setSpacing(4)
        self._slider_rad_amp, self.input_rad_ampmin, self.input_rad_ampmax, _ = _make_rad_block(
            _amp_l, "Amplitude (Jy)", 0.0, 2.0, "Amplitude minimum (Jy)", "Amplitude maximum (Jy)")
        _rlb.addWidget(self._rad_amp_box)

        # ── Phase (mode 2 ou 3) ───────────────────────────────────
        self._rad_phs_box = QWidget()
        _phs_l = QVBoxLayout(self._rad_phs_box); _phs_l.setContentsMargins(0, 0, 0, 0); _phs_l.setSpacing(4)
        self._slider_rad_phs, self.input_rad_phsmin, self.input_rad_phsmax, _ = _make_rad_block(
            _phs_l, "Phase (°)", -180.0, 180.0, "Phase minimum (°)", "Phase maximum (°)")
        _rlb.addWidget(self._rad_phs_box)

        rst_all_rad = QToolButton(); rst_all_rad.setText("↺  Reset all")
        rst_all_rad.setEnabled(False)
        def _reset_all_rad():
            for f in _rad_fields_list:
                f.setText("")
            for rs in _rad_sliders:
                rs.set_values(rs._min, rs._max)
            self._emit_rad_limits()
        rst_all_rad.clicked.connect(_reset_all_rad)
        self._rst_all_rad = rst_all_rad
        row_rst_rad = QHBoxLayout(); row_rst_rad.addStretch(); row_rst_rad.addWidget(rst_all_rad)
        _rlb.addLayout(row_rst_rad)

        _rad_sec.addWidget(self._rad_limit_box)
        layout.addWidget(self._rad_limits_section)

        def _emit_rad_limits_checked():
            if self.chk_rad_limit.isChecked():
                self._emit_rad_limits()

        self._emit_rad_limits = lambda: self.rad_limits_changed.emit(
            _parse_rad(self.input_rad_uvmin),  _parse_rad(self.input_rad_uvmax),
            _parse_rad(self.input_rad_ampmin), _parse_rad(self.input_rad_ampmax),
            _parse_rad(self.input_rad_phsmin), _parse_rad(self.input_rad_phsmax),
        )

        def _sync_rad_boxes(mode_index: int = -1) -> None:
            if mode_index < 0:
                mode_index = self.combo_rad_mode.currentIndex()
            show_amp = mode_index in (0, 2)
            show_phs = mode_index in (1, 2)
            self._rad_amp_box.setVisible(show_amp)
            self._rad_phs_box.setVisible(show_phs)

        self.combo_rad_mode.currentIndexChanged.connect(_sync_rad_boxes)
        _sync_rad_boxes()

        def _on_rad_toggle(checked):
            for w in _rad_fields_list:
                w.setEnabled(checked)
            for rs in _rad_sliders:
                rs.setEnabled(checked)
            for rb in _rad_rst_btns:
                rb.setEnabled(checked)
            self._rst_all_rad.setEnabled(checked)
            self._emit_rad_limits()

        self.chk_rad_limit.toggled.connect(_on_rad_toggle)

        # ── Marker box ────────────────────────────────────────────
        sep2 = QWidget()
        sep2.setFixedHeight(1)
        sep2.setStyleSheet(f"background-color: {D.ASTRAL_BORDER}; margin: 4px 0;")
        layout.addWidget(sep2)

        marker_frame = QFrame()
        marker_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {D.ASTRAL_DEEPEST};
                border: 1px solid {D.ASTRAL_BORDER};
                border-radius: 4px;
            }}
        """)
        mbox = QVBoxLayout(marker_frame)
        mbox.setContentsMargins(8, 6, 8, 8)
        mbox.setSpacing(6)

        lbl_marker_hdr = QLabel("Marker")
        lbl_marker_hdr.setStyleSheet(f"""
            color: {D.ASTRAL_TEXT};
            font-size: {D.FONT_SIZE_XS};
            font-weight: bold;
            letter-spacing: 1px;
            background: transparent;
            border: none;
        """)
        mbox.addWidget(lbl_marker_hdr)

        # Size
        h_size = QHBoxLayout(); h_size.setSpacing(4)
        lbl_size = QLabel("Size  [.]")
        lbl_size.setStyleSheet(f"color: {D.ASTRAL_DIM}; font-size: {D.FONT_SIZE_XS}; background: transparent; border: none;")
        lbl_size.setFixedWidth(52)
        self.lbl_slider_size = lbl_size
        self.lbl_slider_size_val = QLabel("40 %")
        self.lbl_slider_size_val.setStyleSheet(f"color: {D.ASTRAL_DIM}; font-size: {D.FONT_SIZE_XS}; background: transparent; border: none;")
        self.lbl_slider_size_val.setAlignment(Qt.AlignmentFlag.AlignRight)
        h_size.addWidget(lbl_size)
        h_size.addStretch()
        h_size.addWidget(self.lbl_slider_size_val)
        mbox.addLayout(h_size)
        self.slider_size = QSlider(Qt.Orientation.Horizontal)
        self.slider_size.setMinimum(1)
        self.slider_size.setMaximum(100)
        self.slider_size.setValue(40)
        self.slider_size.setToolTip("Marker size (1–100 %)")
        self.slider_size.valueChanged.connect(
            lambda v: self.lbl_slider_size_val.setText(f"{v} %")
        )
        mbox.addWidget(self.slider_size)

        # Opacity
        h_alpha_hdr = QHBoxLayout(); h_alpha_hdr.setSpacing(4)
        lbl_alpha = QLabel("Opacity")
        lbl_alpha.setStyleSheet(f"color: {D.ASTRAL_DIM}; font-size: {D.FONT_SIZE_XS}; background: transparent; border: none;")
        lbl_alpha.setFixedWidth(52)
        self.lbl_slider_alpha_val = QLabel("50 %")
        self.lbl_slider_alpha_val.setStyleSheet(f"color: {D.ASTRAL_DIM}; font-size: {D.FONT_SIZE_XS}; background: transparent; border: none;")
        self.lbl_slider_alpha_val.setAlignment(Qt.AlignmentFlag.AlignRight)
        h_alpha_hdr.addWidget(lbl_alpha)
        h_alpha_hdr.addStretch()
        h_alpha_hdr.addWidget(self.lbl_slider_alpha_val)
        mbox.addLayout(h_alpha_hdr)
        self.slider_alpha = QSlider(Qt.Orientation.Horizontal)
        self.slider_alpha.setMinimum(10)
        self.slider_alpha.setMaximum(100)
        self.slider_alpha.setValue(50)
        self.slider_alpha.setToolTip("Point opacity (10–100 %)")
        self.slider_alpha.valueChanged.connect(
            lambda v: self.lbl_slider_alpha_val.setText(f"{v} %")
        )
        mbox.addWidget(self.slider_alpha)

        # Colour
        h_color = QHBoxLayout(); h_color.setSpacing(6)
        lbl_color = QLabel("Colour")
        lbl_color.setStyleSheet(f"color: {D.ASTRAL_DIM}; font-size: {D.FONT_SIZE_XS}; background: transparent; border: none;")
        self.btn_data_color = QPushButton()
        self.btn_data_color.setFixedHeight(22)
        self.btn_data_color.setToolTip("Pick data point color")
        self._current_data_color = "#1565C0"
        self.btn_data_color.setStyleSheet(
            f"background-color: {self._current_data_color}; border: 1px solid #555; border-radius: 3px;"
        )
        h_color.addWidget(lbl_color)
        h_color.addStretch()
        h_color.addWidget(self.btn_data_color)
        mbox.addLayout(h_color)

        def _pick_color():
            color = QColorDialog.getColor(
                QColor(self._current_data_color), None, "Choose data point color"
            )
            if color.isValid():
                self._current_data_color = color.name()
                self.btn_data_color.setStyleSheet(
                    f"background-color: {self._current_data_color}; border: 1px solid #555; border-radius: 3px;"
                )
                self.data_color_changed.emit(self._current_data_color)

        self.btn_data_color.clicked.connect(_pick_color)
        layout.addWidget(marker_frame)

        self.main_layout.addWidget(self.group_display)

    # ─────────────────────────────────────────────────────────────
    # Helpers visuels
    # ─────────────────────────────────────────────────────────────

    def _subsection_header(self, text: str) -> QLabel:
        """En-tête de sous-section — ligne colorée avec texte en majuscules."""
        lbl = QLabel(text.upper())
        lbl.setStyleSheet(f"""
            color: {D.ASTRAL_ACCENT};
            font-size: {D.FONT_SIZE_XS};
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
        sep.setStyleSheet(f"background-color: {D.ASTRAL_BORDER}; margin: 3px 0;")
        return sep

    def _row(self, *items) -> QHBoxLayout:
        """Crée un QHBoxLayout peuplé des widgets/labels fournis."""
        h = QHBoxLayout()
        h.setSpacing(6)
        for item in items:
            if isinstance(item, str):
                lbl = QLabel(item)
                lbl.setStyleSheet(f"color: {D.ASTRAL_DIM}; font-size: {D.FONT_SIZE_SM};")
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
        toggle_style = _TOGGLE_QSS
        field_s = _FIELD_QSS

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
        h_grid.addWidget(QLabel("Size (px):")); h_grid.addWidget(self.input_mapsize)
        h_grid.addWidget(QLabel("Cell (mas):")); h_grid.addWidget(self.input_cellsize)
        h_grid.addStretch()
        ip.addLayout(h_grid)

        h_wt = QHBoxLayout(); h_wt.setSpacing(6)
        h_wt.addWidget(QLabel("Weighting:"))
        self.combo_weight = QComboBox()
        self.combo_weight.addItems(["Uniform  (bin=2, err=0)", "Natural  (bin=0, err=−2)", "Custom"])
        self.combo_weight.setToolTip(
            "Pondération des visibilités UV (commande uvweight de Difmap)\n"
            "  Uniform  : uvweight 2,0   (résolution maximale — défaut Difmap)\n"
            "  Natural  : uvweight 0,-2  (1/σ² — meilleure sensibilité)\n"
            "  Custom   : bin et errpow personnalisés"
        )
        h_wt.addWidget(self.combo_weight)
        ip.addLayout(h_wt)

        self.custom_weight_widget = QWidget()
        h_cw = QHBoxLayout(self.custom_weight_widget); h_cw.setContentsMargins(0, 0, 0, 0); h_cw.setSpacing(6)
        h_cw.addWidget(QLabel("Bin:"))
        self.input_weight_bin = QLineEdit("2.0")
        self.input_weight_bin.setFixedWidth(52)
        self.input_weight_bin.setToolTip("uvweight bin (≥0 ; 0=natural, 2=uniform)")
        h_cw.addWidget(self.input_weight_bin)
        h_cw.addWidget(QLabel("ErrPow:"))
        self.input_weight_err = QLineEdit("0.0")
        self.input_weight_err.setFixedWidth(52)
        self.input_weight_err.setToolTip("uvweight errpow (≤0 ; 0=uniform, -2=natural)")
        h_cw.addWidget(self.input_weight_err)
        h_cw.addStretch()
        self.custom_weight_widget.setVisible(False)
        ip.addWidget(self.custom_weight_widget)
        self.combo_weight.currentTextChanged.connect(
            lambda t: self.custom_weight_widget.setVisible(t.startswith("Custom"))
        )

        h_uvf_hdr = QHBoxLayout(); h_uvf_hdr.setSpacing(6)
        lbl_uvf = QLabel("UV Filtering")
        lbl_uvf.setStyleSheet(f"color: {D.ASTRAL_TEXT}; font-size: {D.FONT_SIZE_BASE}; font-weight: 600;")
        self.chk_uv_filter = ToggleSwitch()
        self.chk_uv_filter.setToolTip("Activer le filtre de plage UV (uvrange) en Mλ")
        h_uvf_hdr.addWidget(lbl_uvf); h_uvf_hdr.addStretch(); h_uvf_hdr.addWidget(self.chk_uv_filter)
        ip.addLayout(h_uvf_hdr)

        self._uv_filter_box = QWidget()
        h_uvf = QHBoxLayout(self._uv_filter_box)
        h_uvf.setContentsMargins(0, 0, 0, 0); h_uvf.setSpacing(6)
        lbl_uvfmin = QLabel("UV min (Mλ)"); lbl_uvfmin.setFixedWidth(64)
        self.input_uvfilter_min = QLineEdit(); self.input_uvfilter_min.setPlaceholderText("0")
        self.input_uvfilter_min.setStyleSheet(field_s); self.input_uvfilter_min.setEnabled(False)
        self.input_uvfilter_min.setToolTip(
            "Rayon UV minimum en Méga-lambdas\n"
            "Correspond au 1er argument de la commande uvrange de Difmap"
        )
        lbl_uvfmax = QLabel("UV max (Mλ)"); lbl_uvfmax.setFixedWidth(64)
        self.input_uvfilter_max = QLineEdit(); self.input_uvfilter_max.setPlaceholderText("0")
        self.input_uvfilter_max.setStyleSheet(field_s); self.input_uvfilter_max.setEnabled(False)
        self.input_uvfilter_max.setToolTip(
            "Rayon UV maximum en Méga-lambdas\n"
            "Correspond au 2e argument de la commande uvrange de Difmap"
        )
        h_uvf.addWidget(lbl_uvfmin); h_uvf.addWidget(self.input_uvfilter_min)
        h_uvf.addWidget(lbl_uvfmax); h_uvf.addWidget(self.input_uvfilter_max)
        ip.addWidget(self._uv_filter_box)

        lbl_taper_hdr = QLabel("Taper gaussien")
        lbl_taper_hdr.setStyleSheet(f"color: {D.ASTRAL_TEXT}; font-size: {D.FONT_SIZE_BASE}; font-weight: 600;")
        lbl_taper_hdr.setToolTip(
            "uvtaper (invert) : pondère les visibilités pour produire la carte.\n"
            "Différent du selfcal taper (staper) qui n'affecte pas la carte."
        )
        ip.addWidget(lbl_taper_hdr)

        h_tap = QHBoxLayout(); h_tap.setSpacing(6)
        col_tap_val = QVBoxLayout(); col_tap_val.setSpacing(2)
        lbl_tap_val = QLabel("Valeur")
        lbl_tap_val.setStyleSheet(f"color: {D.ASTRAL_DIM}; font-size: {D.FONT_SIZE_XS};")
        col_tap_val.addWidget(lbl_tap_val)
        self.input_taper_amp = QLineEdit("")
        self.input_taper_amp.setFixedWidth(64)
        self.input_taper_amp.setFixedHeight(34)
        self.input_taper_amp.setPlaceholderText("0")
        self.input_taper_amp.setToolTip(
            "Amplitude du taper au rayon (]0, 1[)\n"
            "Laisser vide ou 0 = aucun taper"
        )
        col_tap_val.addWidget(self.input_taper_amp)
        h_tap.addLayout(col_tap_val)

        col_tap_rad = QVBoxLayout(); col_tap_rad.setSpacing(2)
        lbl_tap_rad = QLabel("Rayon (Mλ)")
        lbl_tap_rad.setStyleSheet(f"color: {D.ASTRAL_DIM}; font-size: {D.FONT_SIZE_XS};")
        col_tap_rad.addWidget(lbl_tap_rad)
        self.input_taper = QLineEdit("")
        self.input_taper.setFixedWidth(72)
        self.input_taper.setFixedHeight(34)
        self.input_taper.setPlaceholderText("0")
        self.input_taper.setToolTip(
            "Rayon du taper gaussien en Méga-lambdas — laisser vide ou 0 = aucun taper\n"
            "(uvtaper : affecte la carte)"
        )
        col_tap_rad.addWidget(self.input_taper)
        h_tap.addLayout(col_tap_rad)

        self.btn_reset_taper = QPushButton("Reset")
        self.btn_reset_taper.setFixedWidth(64)
        self.btn_reset_taper.setFixedHeight(34)
        self.btn_reset_taper.setToolTip("Effacer les valeurs du taper (désactivé)")
        self.btn_reset_taper.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_reset_taper.setStyleSheet(D.get_panel_action_button_qss("secondary"))
        self.btn_reset_taper.clicked.connect(lambda: (
            self.input_taper.setText(""),
            self.input_taper_amp.setText(""),
        ))
        h_tap.addWidget(self.btn_reset_taper)
        h_tap.setAlignment(self.btn_reset_taper, Qt.AlignmentFlag.AlignBottom)
        h_tap.addStretch()
        ip.addLayout(h_tap)

        self.btn_apply_imaging = QPushButton("⊞  Apply")
        self.btn_apply_imaging.setToolTip(
            "Appliquer les paramètres d'imagerie au moteur sans recalculer de carte.\n"
            "(La plupart des actions Invert/CLEAN appliquent déjà les paramètres automatiquement.)"
        )
        self.btn_apply_imaging.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_apply_imaging.setStyleSheet(D.get_panel_action_button_qss("secondary"))
        self.btn_apply_imaging.setVisible(False)
        ip.addWidget(self.btn_apply_imaging)

        layout.addWidget(self._imaging_params_section)

        # ══════════════════════════════════════════════════════════
        # DIRTY MAP BUTTON — onglet Dirty Map uniquement
        # ══════════════════════════════════════════════════════════
        self._dirty_btn_section = QWidget()
        db = QVBoxLayout(self._dirty_btn_section)
        db.setContentsMargins(0, 0, 0, 0); db.setSpacing(4)
        self.btn_compute = QPushButton("  Make Dirty Map")
        self.btn_compute.setIcon(qta.icon("fa5s.play", color="white"))
        self.btn_compute.setToolTip(
            "Invert → calcule la Dirty Map.\n"
            "Tu n'as PAS besoin de faire ça avant Start CLEAN (Start CLEAN fait aussi un invert)."
        )
        self.btn_compute.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_compute.setStyleSheet(D.get_panel_action_button_qss("success"))
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
        lbl_params.setStyleSheet(f"color: {D.ASTRAL_TEXT}; font-size: {D.FONT_SIZE_BASE}; font-weight: 600;")
        cc.addWidget(lbl_params)

        # Ligne 1 : Total Niter | Loop Gain côte à côte
        h_row1 = QHBoxLayout(); h_row1.setSpacing(8)
        col_niter = QVBoxLayout(); col_niter.setSpacing(2)
        lbl_niter = QLabel("Niter")
        lbl_niter.setStyleSheet(f"color: {D.ASTRAL_DIM}; font-size: {D.FONT_SIZE_XS};")
        col_niter.addWidget(lbl_niter)
        self.input_niter = QLineEdit("1000")
        self.input_niter.setToolTip("Nombre d'itérations CLEAN à effectuer")
        col_niter.addWidget(self.input_niter)
        h_row1.addLayout(col_niter)

        col_gain = QVBoxLayout(); col_gain.setSpacing(2)
        lbl_gain = QLabel("Loop Gain")
        lbl_gain.setStyleSheet(f"color: {D.ASTRAL_DIM}; font-size: {D.FONT_SIZE_XS};")
        col_gain.addWidget(lbl_gain)
        self.input_gain = QLineEdit("0.05")
        self.input_gain.setToolTip("Gain de boucle CLEAN (0–1)")
        col_gain.addWidget(self.input_gain)
        h_row1.addLayout(col_gain)
        cc.addLayout(h_row1)

        # Cutoff pleine largeur, label au-dessus
        lbl_cutoff = QLabel("Cutoff (Jy/beam)")
        lbl_cutoff.setStyleSheet(f"color: {D.ASTRAL_DIM}; font-size: {D.FONT_SIZE_XS};")
        cc.addWidget(lbl_cutoff)
        self.input_cutoff = QLineEdit("0.001")
        self.input_cutoff.setToolTip(
            "Seuil de flux résiduel en Jy/beam\n"
            "Le CLEAN s'arrête quand le pic résiduel passe en-dessous de ce seuil.\n"
            "0 = pas de limite (le CLEAN tourne jusqu'à Niter itérations)"
        )
        cc.addWidget(self.input_cutoff)

        h_bp_hdr = QHBoxLayout(); h_bp_hdr.setSpacing(6)
        lbl_bp = QLabel("Conditional Breakpoints")
        lbl_bp.setStyleSheet(f"color: {D.ASTRAL_TEXT}; font-size: {D.FONT_SIZE_BASE};")
        self.chk_conditional_bp = ToggleSwitch()
        self.chk_conditional_bp.setChecked(False)
        self.chk_conditional_bp.setToolTip("Pause automatique après X itérations")
        h_bp_hdr.addWidget(lbl_bp); h_bp_hdr.addStretch(); h_bp_hdr.addWidget(self.chk_conditional_bp)
        cc.addLayout(h_bp_hdr)

        self._bp_box = QWidget()
        h_bp = QHBoxLayout(self._bp_box)
        h_bp.setContentsMargins(0, 0, 0, 0); h_bp.setSpacing(6)
        h_bp.addWidget(QLabel("Pause after"))
        self.input_pause_after = QLineEdit("100"); self.input_pause_after.setFixedWidth(52)
        self.input_pause_after.setStyleSheet(field_s); self.input_pause_after.setEnabled(False)
        self.input_pause_after.setToolTip("Nombre d'itérations (iters) entre deux pauses automatiques")
        h_bp.addWidget(self.input_pause_after)
        h_bp.addWidget(QLabel("iters")); h_bp.addStretch()
        cc.addWidget(self._bp_box)

        h_prog = QHBoxLayout(); h_prog.setSpacing(4)
        lbl_prog_title = QLabel("Progress")
        lbl_prog_title.setStyleSheet(f"color: {D.ASTRAL_DIM}; font-size: {D.FONT_SIZE_XS};")
        h_prog.addWidget(lbl_prog_title)
        h_prog.addStretch()
        self.lbl_progress = QLabel("0 / 0")
        self.lbl_progress.setStyleSheet(f"color: {D.ASTRAL_DIM}; font-size: {D.FONT_SIZE_XS};")
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
            QProgressBar::chunk {{ background-color: #2F7D4A; border-radius: 4px; }}
        """)
        cc.addWidget(self.progress_bar)

        # Start CLEAN + Restore sur la même ligne
        h_clean_row = QHBoxLayout(); h_clean_row.setSpacing(6)
        self.btn_compute_clean = QPushButton("▶  Start CLEAN")
        self.btn_compute_clean.setToolTip(
            "Invert + CLEAN — sans restore.\n"
            "Utilise 'Restore' quand la boucle selfcal est terminée.\n"
            "(Pas besoin de faire 'Make Dirty Map' avant.)"
        )
        self.btn_compute_clean.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_compute_clean.setStyleSheet(D.get_panel_action_button_qss("success"))
        h_clean_row.addWidget(self.btn_compute_clean)

        self.btn_restore = QPushButton("Restore")
        self.btn_restore.setToolTip(
            "Convolue le modèle CLEAN avec le beam pour produire la carte finale.\n"
            "À appliquer après la dernière itération CLEAN / selfcal."
        )
        self.btn_restore.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_restore.setStyleSheet(D.get_panel_action_button_qss("secondary"))
        self.btn_restore.setFixedWidth(80)
        h_clean_row.addWidget(self.btn_restore)
        cc.addLayout(h_clean_row)

        # ── Show Windows — visible uniquement sous CLEAN ──────────
        cc.addWidget(self._thin_sep())
        self.chk_show_windows = LabeledToggle("Show Windows  [W]")
        self.chk_show_windows.setChecked(True)
        self.chk_show_windows.setToolTip(
            "Afficher les rectangles des fenêtres CLEAN sur la carte résiduelle"
        )
        cc.addWidget(self.chk_show_windows)

        self.chk_show_model_map = LabeledToggle("Show Model Components  [M]")
        self.chk_show_model_map.setToolTip("Afficher les composantes CLEAN sur la carte")
        self.chk_show_model_map.setChecked(False)
        cc.addWidget(self.chk_show_model_map)
        layout.addWidget(self._clean_controls_section)

        # ══════════════════════════════════════════════════════════
        # SELFCAL — un bloc par commande difmap
        # ══════════════════════════════════════════════════════════
        self._selfcal_section = QWidget()
        sc = QVBoxLayout(self._selfcal_section)
        sc.setContentsMargins(0, 0, 0, 0); sc.setSpacing(6)
        sc.addWidget(self._thin_sep())
        sc.addWidget(self._subsection_header("Selfcal"))

        self.lbl_selfcal_status = QLabel("Aucun modèle — lancez CLEAN d'abord")
        self.lbl_selfcal_status.setStyleSheet(
            f"color: {D.ASTRAL_DIM}; font-size: {D.FONT_SIZE_XS}; font-style: italic;"
        )
        sc.addWidget(self.lbl_selfcal_status)

        def _cmd_frame(cmd_name: str, start_open: bool = True) -> tuple:
            """Retourne (CollapsibleSection, inner_layout) avec header monospace cmd_name."""
            sec = CollapsibleSection(cmd_name)
            sec.toggle_button.setStyleSheet(f"""
                QPushButton {{
                    background-color: {D.ASTRAL_DEEPEST};
                    color: {D.ASTRAL_ACCENT};
                    border: 1px solid {D.ASTRAL_BORDER};
                    border-left: 3px solid {D.ASTRAL_ACCENT};
                    border-radius: 4px;
                    padding: 6px 9px;
                    text-align: left;
                    font-family: monospace;
                    font-size: {D.FONT_SIZE_XS};
                    font-weight: bold;
                    letter-spacing: 1px;
                }}
                QPushButton:hover {{ background-color: {D.ASTRAL_HOVER}; }}
                QPushButton:checked {{
                    border-bottom-left-radius: 0px;
                    border-bottom-right-radius: 0px;
                }}
            """)
            sec.toggle_button.setChecked(start_open)
            sec.content_area.setVisible(start_open)
            arrow = "▼" if start_open else "▶"
            sec.toggle_button.setText(f"{arrow}  {cmd_name}")
            return sec, sec.content_layout

        # ── selfcal : doamp, dofloat, solint ─────────────────────
        frm_sc, vsc = _cmd_frame("selfcal", start_open=True)

        h_mode = QHBoxLayout(); h_mode.setSpacing(6)
        lbl_doamp = QLabel("doamp")
        lbl_doamp.setStyleSheet(f"color: {D.ASTRAL_DIM}; font-size: {D.FONT_SIZE_XS}; background: transparent; border: none;")
        self.combo_sc_mode = QComboBox()
        self.combo_sc_mode.addItem("Phase seule", False)
        self.combo_sc_mode.addItem("Amplitude + Phase", True)
        self.combo_sc_mode.setToolTip(
            "doamp=False : calibration de phase seule (plus sûr, à faire en premier)\n"
            "doamp=True  : calibration amplitude + phase (nécessite un bon modèle)"
        )
        h_mode.addWidget(lbl_doamp)
        h_mode.addWidget(self.combo_sc_mode, 1)
        vsc.addLayout(h_mode)

        h_sol_float = QHBoxLayout(); h_sol_float.setSpacing(6)
        lbl_solint = QLabel("solint")
        lbl_solint.setStyleSheet(f"color: {D.ASTRAL_DIM}; font-size: {D.FONT_SIZE_XS}; background: transparent; border: none;")
        self.input_sc_solint = QLineEdit("0")
        self.input_sc_solint.setFixedWidth(52)
        self.input_sc_solint.setToolTip("Intervalle de solution en minutes — 0 = une solution par intégration")
        lbl_solint_unit = QLabel("min")
        lbl_solint_unit.setStyleSheet(f"color: {D.ASTRAL_DIM}; font-size: {D.FONT_SIZE_XS}; background: transparent; border: none;")
        lbl_dofloat = QLabel("dofloat")
        lbl_dofloat.setStyleSheet(
            f"color: {D.ASTRAL_DIM}; font-size: {D.FONT_SIZE_XS}; background: transparent; border: none;"
        )
        self.chk_sc_float_amp = ToggleSwitch()
        self.chk_sc_float_amp.setToolTip(
            "Corrections d'amplitude non contraintes (flottantes)\n"
            "Disponible uniquement en mode Amplitude + Phase"
        )
        self.chk_sc_float_amp.setEnabled(False)
        def _update_float_enabled() -> None:
            try:
                doamp = bool(self.combo_sc_mode.currentData())
            except Exception:
                doamp = (self.combo_sc_mode.currentText().strip() == "Amplitude + Phase")
            self.chk_sc_float_amp.setEnabled(doamp)
            if not doamp:
                self.chk_sc_float_amp.setChecked(False)

        self.combo_sc_mode.currentIndexChanged.connect(_update_float_enabled)
        _update_float_enabled()
        h_sol_float.addWidget(lbl_solint)
        h_sol_float.addWidget(self.input_sc_solint)
        h_sol_float.addWidget(lbl_solint_unit)
        h_sol_float.addStretch()
        h_sol_float.addWidget(lbl_dofloat)
        h_sol_float.addWidget(self.chk_sc_float_amp)
        vsc.addLayout(h_sol_float)
        sc.addWidget(frm_sc)

        # ── selfflag : doflag, p_mintel, a_mintel ────────────────
        frm_sf, vsf = _cmd_frame("selfflag", start_open=False)

        h_doflag = QHBoxLayout(); h_doflag.setSpacing(6)
        lbl_doflag_text = QLabel("doflag")
        lbl_doflag_text.setStyleSheet(
            f"color: {D.ASTRAL_DIM}; font-size: {D.FONT_SIZE_XS}; background: transparent; border: none;"
        )
        self.chk_sc_doflag = ToggleSwitch()
        self.chk_sc_doflag.setChecked(True)
        self.chk_sc_doflag.setToolTip("Flaguer automatiquement les solutions jugées mauvaises")
        h_doflag.addWidget(lbl_doflag_text)
        h_doflag.addWidget(self.chk_sc_doflag)
        h_doflag.addStretch()
        vsf.addLayout(h_doflag)

        h_mintel = QHBoxLayout(); h_mintel.setSpacing(8)
        lbl_p = QLabel("p_mintel")
        lbl_p.setStyleSheet(f"color: {D.ASTRAL_DIM}; font-size: {D.FONT_SIZE_XS}; background: transparent; border: none;")
        self.spin_sc_p_mintel = QSpinBox()
        self.spin_sc_p_mintel.setRange(3, 99)
        self.spin_sc_p_mintel.setValue(3)
        self.spin_sc_p_mintel.setFixedWidth(56)
        self.spin_sc_p_mintel.setToolTip(
            "Nb min d'antennes pour une solution de phase.\n"
            "Difmap défaut = 3 (valeurs < 3 ramenées à 0 en interactif)"
        )
        lbl_a = QLabel("a_mintel")
        lbl_a.setStyleSheet(f"color: {D.ASTRAL_DIM}; font-size: {D.FONT_SIZE_XS}; background: transparent; border: none;")
        self.spin_sc_a_mintel = QSpinBox()
        self.spin_sc_a_mintel.setRange(4, 99)
        self.spin_sc_a_mintel.setValue(4)
        self.spin_sc_a_mintel.setFixedWidth(56)
        self.spin_sc_a_mintel.setToolTip(
            "Nb min d'antennes pour une solution d'amplitude.\n"
            "Difmap défaut = 4 — actif seulement si doamp=True"
        )
        h_mintel.addWidget(lbl_p)
        h_mintel.addWidget(self.spin_sc_p_mintel)
        h_mintel.addSpacing(4)
        h_mintel.addWidget(lbl_a)
        h_mintel.addWidget(self.spin_sc_a_mintel)
        h_mintel.addStretch()
        vsf.addLayout(h_mintel)
        sc.addWidget(frm_sf)

        # ── selflims : maxphs, maxamp, clip ───────────────────────
        frm_sl, vsl = _cmd_frame("selflims", start_open=False)

        h_lims = QHBoxLayout(); h_lims.setSpacing(8)
        lbl_maxphs = QLabel("maxphs (°)")
        lbl_maxphs.setStyleSheet(f"color: {D.ASTRAL_DIM}; font-size: {D.FONT_SIZE_XS}; background: transparent; border: none;")
        self.input_sc_maxphs = QLineEdit("")
        self.input_sc_maxphs.setPlaceholderText("0 = ∞")
        self.input_sc_maxphs.setFixedWidth(62)
        self.input_sc_maxphs.setToolTip("Correction de phase max en degrés — 0 = illimitée")
        lbl_maxamp = QLabel("maxamp")
        lbl_maxamp.setStyleSheet(f"color: {D.ASTRAL_DIM}; font-size: {D.FONT_SIZE_XS}; background: transparent; border: none;")
        self.input_sc_maxamp = QLineEdit("")
        self.input_sc_maxamp.setPlaceholderText("0 = ∞")
        self.input_sc_maxamp.setFixedWidth(62)
        self.input_sc_maxamp.setToolTip(
            "Ratio max de correction d'amplitude (≥ 1, ex: 2.0 = max ×2)\n"
            "0 = illimité — actif seulement si doamp=True"
        )
        h_lims.addWidget(lbl_maxphs)
        h_lims.addWidget(self.input_sc_maxphs)
        h_lims.addSpacing(4)
        h_lims.addWidget(lbl_maxamp)
        h_lims.addWidget(self.input_sc_maxamp)
        h_lims.addStretch()
        vsl.addLayout(h_lims)

        h_clip = QHBoxLayout(); h_clip.setSpacing(6)
        lbl_clip_text = QLabel("clip")
        lbl_clip_text.setStyleSheet(
            f"color: {D.ASTRAL_DIM}; font-size: {D.FONT_SIZE_XS}; background: transparent; border: none;"
        )
        self.chk_sc_clip = ToggleSwitch()
        self.chk_sc_clip.setToolTip(
            "Clipper les solutions hors limites (maxphs / maxamp)\n"
            "Actif uniquement si maxphs > 0 ou maxamp > 0"
        )
        h_clip.addWidget(lbl_clip_text)
        h_clip.addWidget(self.chk_sc_clip)
        h_clip.addStretch()
        vsl.addLayout(h_clip)
        sc.addWidget(frm_sl)

        # ── selftaper : gauval, gaurad ────────────────────────────
        frm_st, vst = _cmd_frame("selftaper", start_open=False)
        lbl_st_hint = QLabel("Taper UV pour selfcal uniquement — n'affecte pas la carte")
        lbl_st_hint.setStyleSheet(f"color: {D.ASTRAL_DIM}; font-size: {D.FONT_SIZE_XS}; font-style: italic; background: transparent; border: none;")
        lbl_st_hint.setWordWrap(True)
        vst.addWidget(lbl_st_hint)

        h_st = QHBoxLayout(); h_st.setSpacing(8)
        lbl_gauval = QLabel("gauval")
        lbl_gauval.setStyleSheet(f"color: {D.ASTRAL_DIM}; font-size: {D.FONT_SIZE_XS}; background: transparent; border: none;")
        self.input_sc_taper_amp = QLineEdit("")
        self.input_sc_taper_amp.setPlaceholderText("0")
        self.input_sc_taper_amp.setFixedWidth(56)
        self.input_sc_taper_amp.setToolTip("Amplitude ]0, 0.99[ — vide/0 = aucun taper")
        lbl_gaurad = QLabel("gaurad (Mλ)")
        lbl_gaurad.setStyleSheet(f"color: {D.ASTRAL_DIM}; font-size: {D.FONT_SIZE_XS}; background: transparent; border: none;")
        self.input_sc_taper_rad = QLineEdit("")
        self.input_sc_taper_rad.setPlaceholderText("0")
        self.input_sc_taper_rad.setFixedWidth(56)
        self.input_sc_taper_rad.setToolTip("Rayon en Mλ — vide/0 = aucun taper")
        h_st.addWidget(lbl_gauval)
        h_st.addWidget(self.input_sc_taper_amp)
        h_st.addSpacing(4)
        h_st.addWidget(lbl_gaurad)
        h_st.addWidget(self.input_sc_taper_rad)
        h_st.addStretch()
        vst.addLayout(h_st)
        sc.addWidget(frm_st)

        # ── Ergonomie : activer/désactiver selon les valeurs ──────
        def _sync_sc() -> None:
            is_amp = (self.combo_sc_mode.currentIndex() == 1)
            doflag = self.chk_sc_doflag.isChecked()
            has_maxphs = bool(self.input_sc_maxphs.text().strip()
                              and self.input_sc_maxphs.text().strip() not in ("0", "0.0"))
            has_maxamp = bool(self.input_sc_maxamp.text().strip()
                              and self.input_sc_maxamp.text().strip() not in ("0", "0.0"))

            self.chk_sc_float_amp.setEnabled(is_amp)
            if not is_amp:
                self.chk_sc_float_amp.setChecked(False)

            self.spin_sc_p_mintel.setEnabled(doflag)
            self.spin_sc_a_mintel.setEnabled(is_amp and doflag)
            self.input_sc_maxamp.setEnabled(is_amp)
            self.chk_sc_clip.setEnabled(has_maxphs or has_maxamp)
            if not (has_maxphs or has_maxamp):
                self.chk_sc_clip.setChecked(False)

        self.combo_sc_mode.currentIndexChanged.connect(lambda _: _sync_sc())
        self.chk_sc_doflag.toggled.connect(lambda _: _sync_sc())
        self.input_sc_maxphs.textChanged.connect(lambda _: _sync_sc())
        self.input_sc_maxamp.textChanged.connect(lambda _: _sync_sc())
        _sync_sc()

        # ── Bouton Run Selfcal ────────────────────────────────────
        self.btn_run_selfcal = QPushButton("⊞  Run Selfcal")
        self.btn_run_selfcal.setToolTip(
            "Lancer l'auto-calibration avec le modèle CLEAN courant\n"
            "Un invert() sera relancé automatiquement après"
        )
        self.btn_run_selfcal.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_run_selfcal.setStyleSheet(D.get_panel_action_button_qss("primary"))
        sc.addWidget(self.btn_run_selfcal)

        layout.addWidget(self._selfcal_section)

        # ══════════════════════════════════════════════════════════
        # MAP DISPLAY — tous les onglets carte
        # ══════════════════════════════════════════════════════════
        self._map_display_section = QWidget()
        md = QVBoxLayout(self._map_display_section)
        md.setContentsMargins(0, 0, 0, 0); md.setSpacing(4)
        md.addWidget(self._thin_sep())
        md.addWidget(self._subsection_header("Map Display"))

        h_cmap = QHBoxLayout(); h_cmap.setSpacing(6)
        h_cmap.addWidget(QLabel("Colormap:"))
        self.combo_colormap = QComboBox()
        self.combo_colormap.addItems(["inferno", "viridis", "cividis", "gray", "hot", "plasma", "jet"])
        self.combo_colormap.setToolTip(
            "inferno : pseudo-color (proche du défaut Difmap)\n"
            "viridis : colorblind-friendly\n"
            "cividis : colorblind-friendly, perceptuellement uniforme\n"
            "gray    : niveaux de gris (G natif Difmap)\n"
            "hot     : chaud\n"
            "plasma  : alternative vibrante\n"
            "jet     : arc-en-ciel classique"
        )
        h_cmap.addWidget(self.combo_colormap)
        md.addLayout(h_cmap)
        layout.addWidget(self._map_display_section)

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
        h_range.addWidget(QLabel("Min (Jy/beam):"))
        self.input_vmin = QLineEdit(); self.input_vmin.setPlaceholderText("auto")
        self.input_vmin.setToolTip("Limite minimale de l'échelle couleur (Jy/beam)")
        h_range.addWidget(self.input_vmin)
        h_range.addWidget(QLabel("Max (Jy/beam):"))
        self.input_vmax = QLineEdit(); self.input_vmax.setPlaceholderText("auto")
        self.input_vmax.setToolTip("Limite maximale de l'échelle couleur (Jy/beam)")
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
        self.input_absmin.setToolTip("Niveau minimum en % du pic")
        h_log.addWidget(self.input_absmin)
        h_log.addWidget(QLabel("Max%:"))
        self.input_absmax = QLineEdit("100"); self.input_absmax.setFixedWidth(38)
        self.input_absmax.setToolTip("Niveau maximum en % du pic")
        h_log.addWidget(self.input_absmax)
        h_log.addWidget(QLabel("×:"))
        self.input_factor = QLineEdit("2"); self.input_factor.setFixedWidth(34)
        self.input_factor.setToolTip("Facteur multiplicatif entre niveaux")
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

        layout.addWidget(self._display_clean_section)

        # ── Connexions internes ───────────────────────────────────
        def _on_uvf_toggle(checked):
            for w in (self.input_uvfilter_min, self.input_uvfilter_max):
                w.setEnabled(checked)

        def _on_bp_toggle(checked):
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
