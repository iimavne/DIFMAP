# difmap_wrapper/gui/plot_widget.py
import numpy as np
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import QLabel, QPushButton, QHBoxLayout, QWidget
try:
    import qtawesome as qta
    _HAS_QTA = True
except ImportError:
    _HAS_QTA = False

from .base_plot_widget import BasePlotWidget
from difmap_wrapper.gui.editors.uv_editor import UVPlotEditor
from difmap_wrapper.gui.utils import MatplotlibStyler
from difmap_wrapper.gui.styles import DesignSystem

D = DesignSystem

_TOOLBAR_QSS = f"""
QWidget#PlotToolbar {{
    background-color: {D.BACKGROUND};
    border-bottom: 1px solid {D.BORDER};
    padding: 5px 8px;
}}
QLabel#ToolsLabel {{
    color: {D.TEXT_MUTED};
    font-size: 10px;
    font-weight: bold;
    background: transparent;
    padding-right: 4px;
}}
QPushButton {{
    background-color: {D.SURFACE};
    color: {D.TEXT_SECONDARY};
    border: 1px solid {D.BORDER};
    border-radius: 12px;
    padding: 3px 12px;
    font-size: 10px;
    font-family: {D.FONT_FAMILY};
    font-weight: 500;
    min-height: 22px;
    min-width: 60px;
}}
QPushButton:hover {{
    background-color: {D.SURFACE_ALT};
    border-color: {D.ASTRAL_ACCENT};
    color: {D.TEXT};
}}
QPushButton:checked {{
    background-color: {D.ASTRAL_BG};
    color: #FFFFFF;
    border-color: {D.ASTRAL_BG};
    font-weight: 600;
}}
QPushButton:pressed {{
    background-color: {D.ASTRAL_HOVER};
    color: #FFFFFF;
}}
"""


def _icon(name: str, color: str = "#4A6A8A"):
    if not _HAS_QTA:
        return None
    try:
        return qta.icon(name, color=color)
    except Exception:
        return None


def _make_tool_btn(label: str, checkable: bool = True, icon_name: str = None,
                   tooltip: str = None) -> QPushButton:
    btn = QPushButton(label)
    btn.setCheckable(checkable)
    if icon_name:
        ico = _icon(icon_name)
        if ico:
            btn.setIcon(ico)
            btn.setIconSize(QSize(12, 12))
    if tooltip:
        btn.setToolTip(tooltip)
    return btn


class UVPlotWidget(BasePlotWidget):
    """
    Widget PyQt6 encapsulant un graphique Matplotlib interactif pour le plan UV.

    M3 — reload_data() permet de réutiliser le widget sans détruire l'onglet.
         Les callbacks sont stockés à l'init pour être réutilisés lors du reload.
    """

    # (label, editor_mode, checkable, icon, shortcut_hint, tooltip)
    _UV_TOOLS = [
        ("Navigate",  "PAN",     True,  "fa5s.arrows-alt",   "[M]", "Mode navigation / déplacement"),
        ("Zoom",      "ZOOM",    True,  "fa5s.search-plus",  "[Z]", "Zoom rectangle"),
        ("Flag",      "CUT",     True,  "fa5s.ban",          "[C]", "Flaguer rectangle"),
        ("Info",      "INSPECT", True,  "fa5s.info-circle",  "[S]", "Inspecter baseline / temps"),
    ]
    _UV_ACTIONS = [
        ("Dezoom",     None,       False, "fa5s.search-minus", "[O]", "Dézoomer de 50 %"),
        ("Reset View", None,       False, "fa5s.home",         "[R]", "Réinitialiser la vue complète"),
        ("Undo Flag",  None,       False, "fa5s.undo",         "[U]", "Annuler le dernier flagging"),
        ("Crosshair",  "XHAIR",   True,  "fa5s.crosshairs",   "[+]", "Crosshair plein écran"),
    ]

    def __init__(self, observation, data, parent=None,
                 save_callback=None, sync_callback=None):
        # layout_type=None : évite que le moteur de layout contraint recalcule la
        # géométrie de l'axe à chaque draw() (sinon adjustable='box' + crosshair
        # provoque un zoom parasite). Les marges sont gérées via subplots_adjust.
        super().__init__(parent=parent, figsize=(8, 8), layout_type=None)

        self._save_callback = save_callback
        self._sync_callback = sync_callback

        self.observation = observation
        self.data        = data

        self._build_local_toolbar()
        self._draw_and_create_editor()

    # =========================================================
    # TOOLBAR LOCALE
    # =========================================================

    def _build_local_toolbar(self) -> None:
        """Crée la mini-toolbar pills au-dessus du canvas UV."""
        row = self.plot_toolbar_row
        row.setObjectName("PlotToolbar")
        row.setStyleSheet(_TOOLBAR_QSS)
        row.setVisible(True)
        lay = self.plot_toolbar_layout

        lbl = QLabel("Tools:")
        lbl.setObjectName("ToolsLabel")
        lay.addWidget(lbl)

        # ── Boutons de mode (exclusifs) ────────────────────────
        self._tool_buttons: dict[str, QPushButton] = {}
        for label, mode, checkable, icon, shortcut, tip in self._UV_TOOLS:
            btn = _make_tool_btn(f"{label} {shortcut}", checkable, icon, tip)
            btn.setProperty("editorMode", mode)
            btn.clicked.connect(lambda checked, m=mode, b=btn: self._on_tool_btn(m, b))
            self._tool_buttons[mode] = btn
            lay.addWidget(btn)

        # Séparateur visuel entre modes et actions
        sep = QWidget()
        sep.setFixedWidth(1)
        sep.setFixedHeight(20)
        sep.setStyleSheet(f"background-color: {D.BORDER};")
        lay.addWidget(sep)

        # ── Boutons d'action ──────────────────────────────────
        for label, mode, checkable, icon, shortcut, tip in self._UV_ACTIONS:
            btn = _make_tool_btn(f"{label} {shortcut}", checkable, icon, tip)
            btn.setProperty("editorMode", mode)
            if mode == "XHAIR":
                btn.clicked.connect(lambda checked, b=btn: self._on_crosshair_btn(b))
                self._tool_buttons["XHAIR"] = btn
            elif label == "Dezoom":
                btn.clicked.connect(
                    lambda: self._on_button_click(
                        self.editor.action_dezoom, None) if self.editor else None)
            elif label == "Reset View":
                btn.clicked.connect(
                    lambda: self._on_button_click(
                        self.editor.action_home, None) if self.editor else None)
            elif label == "Undo Flag":
                btn.clicked.connect(
                    lambda: self._on_button_click(
                        self.editor.action_undo, None) if self.editor else None)
            lay.addWidget(btn)

        lay.addStretch()

        # Sélectionner Navigate par défaut
        self._set_active_tool_btn("PAN")

    def _on_tool_btn(self, mode: str, btn: QPushButton) -> None:
        """Exclusif : active le mode et désélectionne les autres boutons de mode."""
        for m, b in self._tool_buttons.items():
            if m != "XHAIR":
                b.setChecked(m == mode)
        if not self.editor:
            return
        if mode == "INSPECT":
            self.editor.inspect_active = True
            self.editor._set_mode(None)
        else:
            self.editor.inspect_active = False
            self.editor._set_mode(mode)
        self.canvas.setFocus()

    def _on_crosshair_btn(self, btn: QPushButton) -> None:
        """Toggle indépendant pour le crosshair."""
        if self.editor:
            self.editor.action_toggle_crosshair(None)
        self.canvas.setFocus()

    def _set_active_tool_btn(self, mode: str) -> None:
        for m, b in self._tool_buttons.items():
            if m != "XHAIR":
                b.setChecked(m == mode)

    def _on_button_click(self, func, arg=None):
        if func:
            func(arg)
        self.canvas.setFocus()

    def sync_inspect_state(self, active: bool) -> None:
        if active:
            self._set_active_tool_btn("INSPECT")
        else:
            for m, b in self._tool_buttons.items():
                if m != "XHAIR":
                    b.blockSignals(True)
                    b.setChecked(False)
                    b.blockSignals(False)

    def sync_tool_state(self, tool: str) -> None:
        if tool and tool in self._tool_buttons:
            self._set_active_tool_btn(tool)

    def sync_crosshair_btn(self, active: bool) -> None:
        """Met à jour l'état visuel du bouton Crosshair depuis un événement clavier."""
        btn = self._tool_buttons.get("XHAIR")
        if btn:
            btn.blockSignals(True)
            btn.setChecked(active)
            btn.blockSignals(False)

    # =========================================================
    # CANVAS & ÉDITEUR
    # =========================================================

    def _draw_and_create_editor(self) -> None:
        self.ax.clear()
        self._setup_axes()

        self.editor = UVPlotEditor(
            observation=self.observation,
            fig=self.fig,
            ax=self.ax,
            data=self.data,
            base_color=D.PLOT_DATA,
            save_callback=self._save_callback,
            sync_callback=self._sync_callback,
        )
        self.editor.update_marker_size(self.editor.marker_size_pct)
        # Appliquer le mode actif au nouvel éditeur
        for mode, btn in self._tool_buttons.items():
            if mode != "XHAIR" and btn.isChecked():
                self._on_tool_btn(mode, btn)
                break

    def reload_data(self, data, observation=None) -> None:
        if observation is not None:
            self.observation = observation
        self.data = data

        crosshair_was_active = False
        if self.editor and hasattr(self.editor, 'cursor_active'):
            crosshair_was_active = self.editor.cursor_active

        if self.editor:
            self.editor.cleanup()

        self._draw_and_create_editor()

        if crosshair_was_active and self.editor and hasattr(self.editor, 'cursor_active'):
            if not self.editor.cursor_active:
                self.editor.action_toggle_crosshair(None)

        self.fig.canvas.draw()

    def set_uv_limits(self, umin, umax, vmin, vmax) -> None:
        """Applique les limites d'axe UV (équivalent umax/vmax difmap)."""
        try:
            if umin is None and umax is None and vmin is None and vmax is None:
                self.ax.set_xlim(self.editor.original_limits[0])
                self.ax.set_ylim(self.editor.original_limits[1])
            else:
                if umin is not None and umax is not None:
                    self.ax.set_xlim(umin, umax)
                if vmin is not None and vmax is not None:
                    self.ax.set_ylim(vmin, vmax)
            self.fig.canvas.draw_idle()
        except Exception:
            pass

    def _setup_axes(self):
        MatplotlibStyler.setup_axes(
            self.ax,
            title_text="UV Coverage",
            xlabel=r"U ($M\lambda$)",
            ylabel=r"V ($M\lambda$)"
        )
        self.ax.invert_xaxis()
        self.ax.set_aspect('equal', adjustable='box')
        self.fig.subplots_adjust(left=0.12, bottom=0.09, right=0.97, top=0.93)
