# difmap_wrapper/gui/plot_widget.py
import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtCore import Qt as _Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QLabel, QHBoxLayout, QMenu, QToolButton, QWidget
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

_TOOLBAR_QSS = D.get_plot_toolbar_qss("PlotToolbar", with_menu=True)


def _icon(name: str, color: str = "#4A6A8A"):
    if not _HAS_QTA:
        return None
    try:
        return qta.icon(name, color=color)
    except Exception:
        return None


def _make_separator() -> QWidget:
    sep = QWidget()
    sep.setFixedWidth(1)
    sep.setFixedHeight(22)
    sep.setStyleSheet(f"background-color: {D.BORDER};")
    return sep


def _make_mode_dropdown(items: list, tool_buttons: dict, on_mode_click) -> QToolButton:
    btn = QToolButton()
    btn.setCheckable(True)
    btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
    btn.setToolButtonStyle(_Qt.ToolButtonStyle.ToolButtonTextOnly)
    menu = QMenu(btn)
    for label, mode, _checkable, _icon_name, shortcut, tip in items:
        act = QAction(f"{label} {shortcut}", btn)
        act.setCheckable(True)
        act.setData(mode)
        act.setToolTip(tip)
        act.triggered.connect(
            lambda checked, m=mode, l=label, b=btn: _select_mode_dropdown(b, l, m, on_mode_click)
        )
        menu.addAction(act)
        tool_buttons[mode] = btn
    btn.setMenu(menu)
    first = items[0]
    _set_mode_dropdown_label(btn, first[0], first[1])
    return btn


def _set_mode_dropdown_label(btn: QToolButton, label: str, mode: str) -> None:
    btn.setText(f"{label} ▾")
    btn.setProperty("activeMode", mode)
    if btn.menu():
        for act in btn.menu().actions():
            act.setChecked(act.data() == mode)


def _select_mode_dropdown(btn: QToolButton, label: str, mode: str, on_mode_click) -> None:
    _set_mode_dropdown_label(btn, label, mode)
    if on_mode_click:
        on_mode_click(mode, btn)


class UVPlotWidget(BasePlotWidget):
    """
    Widget PyQt6 encapsulant un graphique Matplotlib interactif pour le plan UV.

    M3 — reload_data() permet de réutiliser le widget sans détruire l'onglet.
         Les callbacks sont stockés à l'init pour être réutilisés lors du reload.
    """

    # (label, editor_mode, checkable, icon, shortcut_hint, tooltip)
    _UV_TOOLS = [
        ("Navigate",  "PAN",     True,  "fa5s.arrows-alt",   "[G]", "Mode navigation / déplacement"),
        ("Flag",      "CUT",     True,  "fa5s.ban",          "[C]", "Flaguer rectangle"),
        ("Info",      "INSPECT", True,  "fa5s.info-circle",  "[S]", "Inspecter baseline / temps"),
    ]
    _UV_ZOOM = [
        ("Zoom Box", "ZOOM", "fa5s.search-plus", "[Z]", "Zoom rectangle"),
        ("Dezoom", None, "fa5s.search-minus", "[O]", "Dézoomer de 50 %"),
    ]
    _UV_VIEW = [
        ("Undo Flag", None, "fa5s.undo", "[u]", "Annuler le dernier flagging"),
        ("Crosshair", "XHAIR", "fa5s.crosshairs", "[+]", "Crosshair plein écran"),
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

        lay.setContentsMargins(8, 5, 8, 5)
        lay.setSpacing(6)

        self._tool_buttons: dict[str, object] = {}

        lay.addWidget(QLabel("Tool:"))
        tool_menu = _make_mode_dropdown(self._UV_TOOLS, self._tool_buttons, self._on_tool_btn)
        lay.addWidget(tool_menu)

        lay.addWidget(_make_separator())

        lay.addWidget(QLabel("Zoom:"))
        zoom_btn = QToolButton()
        zoom_btn.setText("Zoom ▾")
        zoom_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        zoom_btn.setToolButtonStyle(_Qt.ToolButtonStyle.ToolButtonTextOnly)
        zoom_menu = QMenu(zoom_btn)
        for label, mode, _icon, shortcut, tip in self._UV_ZOOM:
            act = QAction(f"{label} {shortcut}", zoom_btn)
            act.setToolTip(tip)
            if mode == "ZOOM":
                act.setCheckable(True)
                act.setData(mode)
                act.triggered.connect(
                    lambda checked, m=mode, l=label, b=zoom_btn: self._select_zoom_mode(b, l, m)
                )
                self._tool_buttons[mode] = zoom_btn
            else:
                act.triggered.connect(
                    lambda checked=False: self._on_button_click(
                        self.editor.action_dezoom, None) if self.editor else None)
            zoom_menu.addAction(act)
        zoom_btn.setMenu(zoom_menu)
        lay.addWidget(zoom_btn)

        lay.addWidget(_make_separator())

        reset_btn = QToolButton()
        reset_btn.setText("Reset [R]")
        reset_btn.setToolButtonStyle(_Qt.ToolButtonStyle.ToolButtonTextOnly)
        reset_btn.setToolTip("Réinitialiser la vue complète")
        reset_btn.clicked.connect(
            lambda checked=False: self._on_button_click(
                self.editor.action_home, None) if self.editor else None)
        lay.addWidget(reset_btn)

        lay.addWidget(_make_separator())

        lay.addWidget(QLabel("View:"))
        view_btn = QToolButton()
        view_btn.setText("View ▾")
        view_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        view_btn.setToolButtonStyle(_Qt.ToolButtonStyle.ToolButtonTextOnly)
        view_menu = QMenu(view_btn)
        for label, mode, _icon, shortcut, tip in self._UV_VIEW:
            text = f"{label} {shortcut}"
            act = QAction(text, view_btn)
            act.setToolTip(tip)
            if label == "Crosshair":
                act.setCheckable(True)
                act.triggered.connect(lambda checked, a=act: self._on_crosshair_btn(a, checked))
                self._tool_buttons["XHAIR"] = act
            elif label == "Undo Flag":
                act.triggered.connect(
                    lambda checked=False: self._on_button_click(
                        self.editor.action_undo, None) if self.editor else None)
            view_menu.addAction(act)
        view_btn.setMenu(view_menu)
        lay.addWidget(view_btn)

        lay.addStretch()

        # Sélectionner Navigate par défaut
        self._set_active_tool_btn("PAN")

    def _select_zoom_mode(self, btn: QToolButton, label: str, mode: str) -> None:
        btn.setText(f"{label} ▾")
        btn.setProperty("activeMode", mode)
        if btn.menu():
            for action in btn.menu().actions():
                action.setChecked(action.data() == mode)
        self._on_tool_btn(mode, btn)

    def _on_tool_btn(self, mode: str, btn) -> None:
        """Exclusif : active le mode et désélectionne les autres boutons de mode."""
        for m, b in self._tool_buttons.items():
            if m == "XHAIR":
                continue
            if isinstance(b, QToolButton) and b.menu():
                owns = any(a.data() == mode for a in b.menu().actions())
                b.setChecked(owns)
                if owns:
                    for action in b.menu().actions():
                        action.setChecked(action.data() == mode)
                        if action.data() == mode:
                            b.setText(action.text().split("[")[0].strip() + " ▾")
                            b.setProperty("activeMode", mode)
            else:
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

    def _on_crosshair_btn(self, btn, checked: bool | None = None) -> None:
        """Active/désactive explicitement le crosshair."""
        if self.editor:
            visible = btn.isChecked() if checked is None else bool(checked)
            self.editor.set_crosshair_visible(visible)
        self.canvas.setFocus()

    def _set_active_tool_btn(self, mode: str) -> None:
        for m, b in self._tool_buttons.items():
            if m == "XHAIR":
                continue
            if isinstance(b, QToolButton) and b.menu():
                owns = any(a.data() == mode for a in b.menu().actions())
                b.setChecked(owns)
                if owns:
                    for action in b.menu().actions():
                        action.setChecked(action.data() == mode)
                        if action.data() == mode:
                            b.setText(action.text().split("[")[0].strip() + " ▾")
                            b.setProperty("activeMode", mode)
            else:
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
            if mode == "XHAIR":
                continue
            if isinstance(btn, QToolButton) and btn.property("activeMode") == mode:
                self._on_tool_btn(mode, btn)
                break
            if not isinstance(btn, QToolButton) and btn.isChecked():
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
            self.editor.set_crosshair_visible(True)

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
            title_text="UV Plan",
            xlabel=r"U ($M\lambda$)",
            ylabel=r"V ($M\lambda$)"
        )
        self.ax.invert_xaxis()
        self.ax.set_aspect('equal', adjustable='box')
        self.fig.subplots_adjust(left=0.12, bottom=0.09, right=0.97, top=0.93)
