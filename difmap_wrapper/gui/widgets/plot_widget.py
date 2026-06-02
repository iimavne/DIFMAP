# difmap_wrapper/gui/plot_widget.py
import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtCore import Qt as _Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QCheckBox, QLabel, QHBoxLayout, QMenu, QToolButton, QWidget
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
    for label, mode, checkable, _icon_name, shortcut, tip in items:
        act = QAction(f"{label} {shortcut}", btn)
        act.setCheckable(bool(checkable))
        act.setData(mode)
        act.setToolTip(tip)
        act.triggered.connect(
            lambda checked, m=mode, l=label, b=btn: _select_mode_dropdown(b, l, m, on_mode_click)
        )
        menu.addAction(act)
        if checkable:
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
        ("Pan",      "PAN",     True,  "fa5s.arrows-alt",   "[G]", "Naviguer / déplacer la vue"),
        ("Inspect",  "INSPECT", True,  "fa5s.info-circle",  "[S]", "Inspecter baseline / temps"),
    ]
    _UV_EDIT = [
        ("Edit Off", None,  True, "fa5s.times", "[D]", "Désactiver les outils d'édition"),
        ("Flag",     "CUT", True, "fa5s.ban",   "[C]", "Flaguer rectangle"),
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

        self._nav_mode = "PAN"
        self._edit_mode = None

        lay.addWidget(QLabel("Tool:"))
        tool_menu = _make_mode_dropdown(self._UV_TOOLS, self._tool_buttons, self._on_nav_tool_btn)
        lay.addWidget(tool_menu)

        lay.addWidget(_make_separator())

        lay.addWidget(QLabel("Edit:"))
        edit_menu = _make_mode_dropdown(self._UV_EDIT, self._tool_buttons, self._on_edit_tool_btn)
        lay.addWidget(edit_menu)

        undo_btn = QToolButton()
        undo_btn.setText("Undo [u]")
        undo_btn.setToolButtonStyle(_Qt.ToolButtonStyle.ToolButtonTextOnly)
        undo_btn.setToolTip("Annuler le dernier flag (u / Ctrl+Z)")
        undo_btn.clicked.connect(
            lambda checked=False: self._on_button_click(
                self.editor.action_undo, None) if self.editor else None
        )
        lay.addWidget(undo_btn)

        redo_btn = QToolButton()
        redo_btn.setText("Redo [Ctrl+Y]")
        redo_btn.setToolButtonStyle(_Qt.ToolButtonStyle.ToolButtonTextOnly)
        redo_btn.setToolTip("Refaire le dernier undo flag (Ctrl+Y)")
        redo_btn.clicked.connect(
            lambda checked=False: self._on_button_click(
                self.editor.action_redo, None) if self.editor else None
        )
        lay.addWidget(redo_btn)

        lay.addWidget(_make_separator())

        lay.addWidget(QLabel("Zoom:"))
        zoom_in_btn = QToolButton()
        zoom_in_btn.setText("+")
        zoom_in_btn.setToolButtonStyle(_Qt.ToolButtonStyle.ToolButtonTextOnly)
        zoom_in_btn.setToolTip("Zoom-in (centré sur la souris)")
        zoom_in_btn.clicked.connect(
            lambda checked=False: self._on_button_click(
                self.editor.action_zoom_in, None) if self.editor else None
        )
        lay.addWidget(zoom_in_btn)

        zoom_out_btn = QToolButton()
        zoom_out_btn.setText("-")
        zoom_out_btn.setToolButtonStyle(_Qt.ToolButtonStyle.ToolButtonTextOnly)
        zoom_out_btn.setToolTip("Dézoomer de 50 %")
        zoom_out_btn.clicked.connect(
            lambda checked=False: self._on_button_click(
                self.editor.action_dezoom, None) if self.editor else None
        )
        lay.addWidget(zoom_out_btn)

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

        self._crosshair_chk = QCheckBox("Crosshair")
        self._crosshair_chk.setToolTip("Crosshair plein écran")
        self._crosshair_chk.stateChanged.connect(
            lambda _state: self._on_crosshair_chk(bool(self._crosshair_chk.isChecked()))
        )
        lay.addWidget(self._crosshair_chk)

        lay.addWidget(_make_separator())

        lay.addStretch()

        lay.addWidget(_make_separator())
        _export_btn = QToolButton()
        _export_btn.setText("Export PNG")
        _export_btn.setToolButtonStyle(_Qt.ToolButtonStyle.ToolButtonTextOnly)
        _export_btn.setToolTip("Exporter la couverture UV en PNG")
        _export_btn.clicked.connect(lambda checked=False: self._export_png("uv_coverage.png"))
        lay.addWidget(_export_btn)

        # Sélectionner Pan par défaut (Tool), Edit Off pour l'édition
        self._set_active_tool_btn("PAN")
        self._set_active_edit_btn(None)

    def _on_nav_tool_btn(self, mode: str, btn) -> None:
        """Outil de visualisation local (non synchronisé)."""
        self._nav_mode = mode
        self._set_active_tool_btn(mode)
        if not self.editor:
            return
        # Si un outil d'édition est actif, il reste prioritaire.
        if self._edit_mode is not None:
            self.editor.inspect_active = False
            self.editor._set_mode(self._edit_mode)
            self.canvas.setFocus()
            return
        if mode == "INSPECT":
            self.editor.inspect_active = True
            self.editor._set_mode(None)
        else:
            self.editor.inspect_active = False
            self.editor._set_mode(mode)
        self.canvas.setFocus()

    def _on_edit_tool_btn(self, mode: str | None, btn) -> None:
        """Outil d'édition synchronisé entre graphiques."""
        self._set_edit_tool(mode, emit_sync=True)

    def _set_edit_tool(self, mode: str | None, emit_sync: bool) -> None:
        self._edit_mode = mode
        self._set_active_edit_btn(mode)
        if self.editor:
            if mode is None:
                # Retour au mode de visualisation local
                self._on_nav_tool_btn(self._nav_mode, None)
            else:
                self.editor.inspect_active = False
                self.editor._set_mode(mode)
        if emit_sync and self._sync_callback:
            self._sync_callback({'edit_tool': mode})
        self.canvas.setFocus()

    def _on_crosshair_chk(self, checked: bool) -> None:
        """Active/désactive explicitement le crosshair."""
        if self.editor:
            self.editor.set_crosshair_visible(bool(checked))
        self.canvas.setFocus()

    def _set_active_tool_btn(self, mode: str) -> None:
        for m, b in self._tool_buttons.items():
            if m == "XHAIR":
                continue
            if m in ("CUT", None):
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

    def _set_active_edit_btn(self, mode: str | None) -> None:
        """Met à jour l'état visuel du dropdown Edit sans modifier l'éditeur."""
        if not hasattr(self, '_tool_buttons'):
            return
        for m, b in self._tool_buttons.items():
            if m not in (None, "CUT"):
                continue
            if not isinstance(b, QToolButton) or not b.menu():
                continue
            owns = any(a.data() == mode for a in b.menu().actions())
            b.blockSignals(True)
            b.setChecked(owns)
            if owns:
                for action in b.menu().actions():
                    action.setChecked(action.data() == mode)
                    if action.data() == mode:
                        b.setText(action.text().split("[")[0].strip() + " ▾")
                        b.setProperty("activeMode", mode)
            b.blockSignals(False)

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

    def sync_edit_tool_state(self, tool: str | None) -> None:
        """Synchronise l'outil d'édition sans reboucler vers MainWindow."""
        self._set_edit_tool(tool, emit_sync=False)

    def sync_crosshair_btn(self, active: bool) -> None:
        """Met à jour l'état visuel du crosshair depuis un événement clavier."""
        chk = getattr(self, '_crosshair_chk', None)
        if chk:
            chk.blockSignals(True)
            chk.setChecked(bool(active))
            chk.blockSignals(False)

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
        # Appliquer l'état courant au nouvel éditeur
        if self._edit_mode is not None:
            self._set_edit_tool(self._edit_mode, emit_sync=False)
        else:
            self._on_nav_tool_btn(self._nav_mode, None)

    def reload_data(self, data, observation=None) -> None:
        if observation is not None:
            self.observation = observation
        self.data = data

        crosshair_was_active = False
        if self.editor and hasattr(self.editor, 'cursor_active'):
            crosshair_was_active = self.editor.cursor_active

        saved_focus = None
        if self.editor is not None:
            try:
                saved_focus = (
                    getattr(self.editor, 'index_subarray_actuel', 0),
                    getattr(self.editor, 'index_antenne_actuelle', -1),
                    getattr(self.editor, '_nom_antenne_courante', ""),
                    getattr(self.editor, 'inspect_active', False),
                )
            except Exception:
                saved_focus = None

        if self.editor:
            self.editor.cleanup()

        self._draw_and_create_editor()

        if crosshair_was_active and self.editor and hasattr(self.editor, 'cursor_active'):
            self.editor.set_crosshair_visible(True)

        if saved_focus and self.editor is not None:
            try:
                (sub_idx, ant_idx, ant_name, inspect_active) = saved_focus
                self.editor.index_subarray_actuel = sub_idx
                self.editor.index_antenne_actuelle = ant_idx
                self.editor._nom_antenne_courante = ant_name
                self.editor.inspect_active = inspect_active
                self.editor._update_colors()
            except Exception:
                pass

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
