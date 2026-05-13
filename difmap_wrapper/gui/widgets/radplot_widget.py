# difmap_wrapper/gui/radplot_widget.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from matplotlib.collections import PathCollection
from PyQt6.QtCore import QSize
from PyQt6.QtCore import Qt as _Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QMenu, QPushButton, QToolButton, QWidget
try:
    import qtawesome as qta
    _HAS_QTA = True
except ImportError:
    _HAS_QTA = False

from .base_plot_widget import BasePlotWidget
from difmap_wrapper.gui.editors.rad_editor import RadPlotEditor
from difmap_wrapper.gui.utils import MatplotlibStyler
from difmap_wrapper.gui.styles import DesignSystem
from difmap_wrapper.types import DisplayMode

D = DesignSystem

# Teinte accent légère pour l'état actif (fond bleu pâle, texte bleu, bordure bleue)
_TOOLBAR_QSS = f"""
QWidget#PlotToolbar {{
    background-color: {D.BACKGROUND};
    border-bottom: 1px solid {D.BORDER};
    padding: 5px 8px;
}}
/* ── Pills (même style que UV plot) ── */
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
/* ── Sélecteur déroulant : même pill mais plus large ── */
QToolButton {{
    background-color: {D.SURFACE};
    color: {D.TEXT_SECONDARY};
    border: 1px solid {D.BORDER};
    border-radius: 12px;
    padding: 3px 12px;
    font-size: 10px;
    font-family: {D.FONT_FAMILY};
    font-weight: 500;
    min-height: 22px;
    min-width: 110px;
}}
QToolButton:hover {{
    background-color: {D.SURFACE_ALT};
    border-color: {D.ASTRAL_ACCENT};
    color: {D.TEXT};
}}
QToolButton:checked {{
    background-color: {D.ASTRAL_BG};
    color: #FFFFFF;
    border-color: {D.ASTRAL_BG};
    font-weight: 600;
}}
QToolButton:pressed {{
    background-color: {D.ASTRAL_HOVER};
    color: #FFFFFF;
}}
QToolButton::menu-indicator {{ image: none; width: 0; }}
/* ── Menu déroulant ── */
QMenu {{
    background-color: {D.SURFACE};
    border: 1px solid {D.BORDER};
    border-radius: 8px;
    padding: 4px;
    font-family: {D.FONT_FAMILY};
    font-size: 10px;
}}
QMenu::item {{
    padding: 5px 14px 5px 10px;
    border-radius: 5px;
    color: {D.TEXT};
    min-width: 150px;
}}
QMenu::item:selected {{
    background-color: {D.ASTRAL_BG};
    color: #FFFFFF;
}}
QMenu::item:checked {{
    color: {D.ASTRAL_ACCENT};
    font-weight: 600;
}}
"""


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
    sep.setFixedHeight(20)
    sep.setStyleSheet(f"background-color: {D.BORDER};")
    return sep


def _make_dropdown(group_label: str, items: list,
                   tool_buttons: dict, on_mode_click) -> QToolButton:
    """
    Crée un QToolButton avec menu déroulant pour sélection de mode.
    items: [(label, mode, icon_name, shortcut, tooltip), ...]
    """
    btn = QToolButton()
    btn.setCheckable(True)
    btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
    btn.setToolButtonStyle(_Qt.ToolButtonStyle.ToolButtonTextOnly)

    menu = QMenu(btn)
    first_item = items[0]

    for label, mode, icon_name, shortcut, tip in items:
        display = f"{label}    {shortcut}" if shortcut else label
        act = QAction(display, btn)
        act.setCheckable(True)
        act.setData(mode)
        act.setToolTip(tip)
        act.triggered.connect(
            lambda checked, m=mode, l=label, b=btn: _dropdown_select(b, l, m, on_mode_click))
        menu.addAction(act)
        tool_buttons[mode] = btn

    btn.setMenu(menu)
    _dropdown_label(btn, first_item[0], first_item[1])
    return btn


def _dropdown_label(btn: QToolButton, label: str, mode: str) -> None:
    """Met à jour le label et la coche du menu sans déclencher l'éditeur."""
    btn.setText(f"{label}  ▾")
    btn.setProperty("activeMode", mode)
    if btn.menu():
        for act in btn.menu().actions():
            act.setChecked(act.data() == mode)


def _dropdown_select(btn: QToolButton, label: str, mode: str, on_mode_click) -> None:
    """Met à jour le label ET déclenche le changement de mode dans l'éditeur."""
    _dropdown_label(btn, label, mode)
    if on_mode_click:
        on_mode_click(mode, btn)


@dataclass
class RadScatters:
    """
    S3 — Remplace le dict à clés magic strings {"amp": None, "phs": None, ...}.

    Les attributs sont typés et nommés explicitement.
    Plus de .get("m_amp") fragile → accès direct .model_amp.
    """
    amp:       Optional[PathCollection] = field(default=None)
    phase:     Optional[PathCollection] = field(default=None)
    model_amp: Optional[PathCollection] = field(default=None)
    model_phs: Optional[PathCollection] = field(default=None)
    err:       Optional[PathCollection] = field(default=None)


class RadPlotWidget(BasePlotWidget):
    """
    Widget PyQt6 encapsulant les graphiques Radplot (Amplitude/Phase/Erreur).
    """

    def __init__(self, parent=None, sync_callback=None):
        """
        Parameters
        ----------
        parent : QWidget, optional
            Widget parent Qt.
        sync_callback : callable, optional
            Fonction appelée pour synchroniser l'état éditeur → MainWindow.
        """
        # Attributs initialisés AVANT super().__init__() car _setup_axes()
        # est appelée par BasePlotWidget.__init__() et en a besoin.
        self.display_mode: int  = DisplayMode.AMP_ONLY
        self.show_errors:  bool = False
        self.ax_phase = None
        self.ax_err   = None
        self.data     = None
        self.editor: Optional[RadPlotEditor] = None
        self._sync_callback = sync_callback
        super().__init__(parent=parent, figsize=(8, 6), layout_type='constrained')
        self._build_local_toolbar()

    # =========================================================
    # TOOLBAR LOCALE
    # =========================================================

    # (label, mode, icon_name, shortcut_display, tooltip)
    # Note : dans RadPlot, m/M est overridé par "toggle model" → Pan n'a pas de raccourci clavier
    _RAD_NAVIGATE = [
        ("Pan",     "PAN",     "fa5s.arrows-alt",  "G", "Naviguer / déplacer la vue"),
        ("Inspect", "INSPECT", "fa5s.info-circle", "s", "Inspecter le point le plus proche"),
    ]
    # Z=zoom libre (base), U (Shift+u)=Zoom Radius, Y=Zoom amp/phs
    _RAD_ZOOM = [
        ("Zoom Box",     "ZOOM",   "fa5s.search-plus",  "Z",       "Zoom rectangle (libre)"),
        ("Zoom Radius",  "ZOOM_X", "fa5s.arrows-alt-h", "Shift+u", "Zoom plage UV radius (axe X)"),
        ("Zoom Amp/Phs", "ZOOM_Y", "fa5s.arrows-alt-v", "Y",       "Zoom axe Amplitude / Phase"),
    ]
    _RAD_FLAG = [
        ("Flag Box", "CUT", "fa5s.ban", "C", "Flaguer un rectangle"),
    ]
    _RAD_STATS = [
        ("Amp / Phase", "STATS",   "fa5s.chart-bar",  "S", "Statistiques scalaires (Amp, Phase)"),
        ("Re / Im",     "STATS_V", "fa5s.chart-line", "V", "Statistiques vectorielles (Re, Im)"),
    ]

    def _build_local_toolbar(self) -> None:
        """
        Deux lignes de toolbar :
        - Ligne 1 (haut)  : boutons d'action (Dezoom, Reset, Undo, Refresh, Crosshair)
        - Ligne 2 (bas)   : sélecteurs déroulants de mode (Navigate, Zoom, Flag, Stats)
        """
        self._tool_buttons: dict[str, QToolButton] = {}

        # ── Ligne 1 : actions ─────────────────────────────────
        row1 = self.plot_toolbar_row
        row1.setObjectName("PlotToolbar")
        row1.setStyleSheet(_TOOLBAR_QSS)
        row1.setVisible(True)
        lay1 = self.plot_toolbar_layout

        _actions = [
            ("Dezoom",     "fa5s.search-minus", "O", "Dézoomer de 50 %",           False, None),
            ("Reset View", "fa5s.home",         "R", "Réinitialiser la vue",        False, None),
            ("Undo Flag",  "fa5s.undo",         "u",  "Annuler le dernier flagging  (distinct de Shift+u = Zoom Radius)", False, None),
            ("Refresh",    "fa5s.sync-alt",     "L", "Rafraîchir l'affichage",      False, None),
            ("Crosshair",  "fa5s.crosshairs",   "+", "Crosshair plein écran",       True,  "XHAIR"),
        ]
        for label, icon_name, shortcut, tip, checkable, mode in _actions:
            btn = QPushButton(f"{label} [{shortcut}]")
            btn.setCheckable(checkable)
            btn.setToolTip(f"{tip}  [{shortcut}]")
            ico = _icon(icon_name)
            if ico:
                btn.setIcon(ico)
                btn.setIconSize(QSize(14, 14))
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
            elif label == "Refresh":
                btn.clicked.connect(
                    lambda: self._on_button_click(
                        self.editor.action_redisplay, None) if self.editor else None)
            lay1.addWidget(btn)
        lay1.addStretch()

        # ── Ligne 2 : outils de mode ──────────────────────────
        row2 = QWidget()
        row2.setObjectName("PlotToolbar")
        row2.setStyleSheet(_TOOLBAR_QSS)
        lay2 = QHBoxLayout(row2)
        lay2.setContentsMargins(10, 4, 10, 4)
        lay2.setSpacing(8)

        # Pan et Inspect : pills indépendantes
        for label, mode, icon_name, shortcut, tip in self._RAD_NAVIGATE:
            btn = QPushButton(f"{label} [{shortcut}]")
            btn.setCheckable(True)
            btn.setToolTip(f"{tip}  [{shortcut}]")
            ico = _icon(icon_name)
            if ico:
                btn.setIcon(ico)
                btn.setIconSize(QSize(14, 14))
            btn.clicked.connect(
                lambda checked, m=mode, b=btn: self._on_tool_btn(m, b))
            self._tool_buttons[mode] = btn
            lay2.addWidget(btn)

        lay2.addWidget(_make_separator())

        # Zoom : dropdown (Zoom Box / Zoom X / Zoom Y)
        dd_zoom = _make_dropdown("Zoom", self._RAD_ZOOM,
                                 self._tool_buttons, self._on_tool_btn)
        lay2.addWidget(dd_zoom)

        lay2.addWidget(_make_separator())

        # Flag Box : pill toggle simple
        flag_def = self._RAD_FLAG[0]  # ("Flag Box", "CUT", icon, shortcut, tip)
        btn_flag = QPushButton(f"{flag_def[0]} [{flag_def[3]}]")
        btn_flag.setCheckable(True)
        btn_flag.setToolTip(f"{flag_def[4]}  [{flag_def[3]}]")
        ico = _icon(flag_def[2])
        if ico:
            btn_flag.setIcon(ico)
            btn_flag.setIconSize(QSize(14, 14))
        btn_flag.clicked.connect(
            lambda checked, m=flag_def[1], b=btn_flag: self._on_tool_btn(m, b))
        self._tool_buttons[flag_def[1]] = btn_flag
        lay2.addWidget(btn_flag)

        lay2.addWidget(_make_separator())

        # Statistics : dropdown (Amp/Phase / Re/Im)
        dd_stats = _make_dropdown("Statistics", self._RAD_STATS,
                                  self._tool_buttons, self._on_tool_btn)
        lay2.addWidget(dd_stats)

        lay2.addStretch()

        # Insérer row2 juste après row1 dans le layout vertical du widget
        self.layout.insertWidget(1, row2)

    # ── Gestion des boutons ──────────────────────────────────────

    def _update_btn_visuals(self, mode: str) -> None:
        """
        Met à jour UNIQUEMENT l'état visuel des boutons (checked + label dropdown).
        N'appelle PAS l'éditeur — évite toute récursion depuis sync_*.
        """
        if not hasattr(self, '_tool_buttons'):
            return
        seen_dropdowns: set = set()
        for m, b in self._tool_buttons.items():
            if m == "XHAIR":
                continue
            if isinstance(b, QToolButton) and b.menu() and id(b) not in seen_dropdowns:
                seen_dropdowns.add(id(b))
                owns = any(a.data() == mode for a in b.menu().actions())
                b.blockSignals(True)
                b.setChecked(owns)
                if owns:
                    for a in b.menu().actions():
                        a.setChecked(a.data() == mode)
                        if a.data() == mode:
                            raw = a.text().split("   ")[0].strip()
                            b.setText(f"{raw}  ▾")
                            b.setProperty("activeMode", mode)
                b.blockSignals(False)
            elif not isinstance(b, QToolButton):
                b.blockSignals(True)
                b.setChecked(m == mode)
                b.blockSignals(False)

    def _on_tool_btn(self, mode: str, btn) -> None:
        """Appelé par interaction utilisateur : met à jour l'UI puis l'éditeur."""
        self._update_btn_visuals(mode)
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
        if self.editor:
            self.editor.action_toggle_crosshair(None)
        self.canvas.setFocus()

    def _on_button_click(self, func, arg=None):
        if func:
            func(arg)
        self.canvas.setFocus()

    # ── Synchronisation UI ← éditeur / clavier (pas d'appel éditeur) ──

    def sync_inspect_state(self, active: bool) -> None:
        """Met à jour l'UI uniquement — PAS l'éditeur (évite récursion)."""
        if active:
            self._update_btn_visuals("INSPECT")
        else:
            if not hasattr(self, '_tool_buttons'):
                return
            seen: set = set()
            for m, b in self._tool_buttons.items():
                if m == "XHAIR" or id(b) in seen:
                    continue
                seen.add(id(b))
                b.blockSignals(True)
                b.setChecked(False)
                b.blockSignals(False)

    def sync_tool_state(self, tool: str) -> None:
        """Met à jour l'UI uniquement — PAS l'éditeur (évite récursion)."""
        if not hasattr(self, '_tool_buttons') or not tool:
            return
        self._update_btn_visuals(tool)

    def sync_crosshair_btn(self, active: bool) -> None:
        btn = self._tool_buttons.get("XHAIR")
        if btn:
            btn.blockSignals(True)
            btn.setChecked(active)
            btn.blockSignals(False)

    # =========================================================
    # API publique
    # =========================================================

    def set_display_mode(self, mode_index: int) -> None:
        """
        Change le mode d'affichage du Radplot.

        Parameters
        ----------
        mode_index : int
            Index combo (0 = Amplitude, 1 = Phase, 2 = Amplitude & Phase).
            Converti en interne en :class:`DisplayMode` (valeurs 1/2/3).
        """
        self.display_mode = mode_index + 1
        if self.data is not None:
            self._refresh_layout()

    def set_show_errors(self, visible: bool) -> None:
        """
        Active ou désactive le sous-graphique d'erreurs théoriques (1/√w).

        Déclenché par la touche ``E``, la checkbox ou le ``sync_callback`` de l'éditeur.

        Parameters
        ----------
        visible : bool
            ``True`` pour afficher le panneau d'erreurs, ``False`` pour le masquer.
        """
        self.show_errors = visible
        if self.data is not None:
            self._refresh_layout()

    def set_rad_limits(self, uvmin, uvmax, ampmin, ampmax, phsmin, phsmax) -> None:
        """Applique les limites d'affichage Radplot (équivalent uvradplt r_setrange)."""
        try:
            all_none = all(v is None for v in (uvmin, uvmax, ampmin, ampmax, phsmin, phsmax))
            if self.ax:
                if uvmin is None and uvmax is None:
                    if not all_none and self.editor and self.editor.original_limits:
                        self.ax.set_xlim(self.editor.original_limits[0])
                else:
                    xl = self.ax.get_xlim()
                    self.ax.set_xlim(
                        uvmin if uvmin is not None else xl[0],
                        uvmax if uvmax is not None else xl[1],
                    )
                if ampmin is None and ampmax is None:
                    pass
                else:
                    yl = self.ax.get_ylim()
                    self.ax.set_ylim(
                        ampmin if ampmin is not None else yl[0],
                        ampmax if ampmax is not None else yl[1],
                    )
            if self.ax_phase:
                if phsmin is None and phsmax is None:
                    pass
                else:
                    yl = self.ax_phase.get_ylim()
                    self.ax_phase.set_ylim(
                        phsmin if phsmin is not None else yl[0],
                        phsmax if phsmax is not None else yl[1],
                    )
            self.fig.canvas.draw_idle()
        except Exception:
            pass

    def _refresh_layout(self) -> None:
        """
        Recrée les axes et l'éditeur en préservant le masque de l'Observation (C3).
        
        Sauvegarde et restaure l'état du crosshair.
        """
        if self.editor and self.data is not None:
            crosshair_was_active = getattr(self.editor, 'cursor_active', False)
            saved_size_pct = getattr(self.editor, 'marker_size_pct', 10)

            self.plot_data(self.data, observation=self.editor.obs)

            # Restaurer la taille des marqueurs
            if self.editor:
                self.editor.update_marker_size(saved_size_pct)

            # Restaurer le crosshair
            if crosshair_was_active and self.editor and hasattr(self.editor, 'cursor_active'):
                if not self.editor.cursor_active:
                    self.editor.action_toggle_crosshair(None)

    # =========================================================
    # M4 : plot_data() décomposé en sous-méthodes
    # =========================================================

    def plot_data(self, data: dict, observation=None) -> None:
        """
        Point d'entrée principal : configure les axes, scatter plots et éditeur.

        C3 — Le masque de flagging vit exclusivement dans ``Observation`` ;
        ``shared_mask`` / ``shared_history`` ont été supprimés.

        Parameters
        ----------
        data : dict
            Données UV (clés : ``'u'``, ``'v'``, ``'amp'``, ``'phase'``,
            ``'weight'``, ``'modamp'``, ``'modphs'``).
        observation : Observation, optional
            Si fourni, instancie un :class:`RadPlotEditor` sur les données.
        """
        self.data = data
        self._setup_axes()

        if data is None or len(data.get('u', [])) == 0:
            self.draw()
            return

        scats = self._create_scatters(data)

        if observation is not None:
            self._create_editor(observation, scats)

        self.fig.canvas.draw_idle()

    def _setup_axes(self) -> None:
        """
        M4 — Crée dynamiquement les axes selon display_mode et show_errors.
        Appelée par BasePlotWidget.__init__() (sans données) et par plot_data().
        """
        self.fig.clear()

        active = []
        if self.display_mode in [DisplayMode.AMP_ONLY, DisplayMode.BOTH]:
            active.append('AMP')
        if self.display_mode in [DisplayMode.PHASE_ONLY, DisplayMode.BOTH]:
            active.append('PHS')
        if self.show_errors:
            active.append('ERR')

        if not active:
            active = ['AMP']

        self.ax_phase = None
        self.ax_err   = None
        self.ax       = None

        main_ax = None
        for i, ptype in enumerate(active):
            ax = self.fig.add_subplot(len(active), 1, i + 1, sharex=main_ax)
            if i == 0:
                main_ax = ax
                self.ax = ax

            if ptype == 'AMP':
                MatplotlibStyler.setup_axes(ax, title_text="Amplitude",
                                            xlabel="", ylabel="Amp (Jy)")
            elif ptype == 'PHS':
                self.ax_phase = ax
                MatplotlibStyler.setup_axes(ax, title_text="Phase",
                                            xlabel="", ylabel="Phase (°)")
            elif ptype == 'ERR':
                self.ax_err = ax
                MatplotlibStyler.setup_axes(ax, title_text="Theoretical Error",
                                            xlabel="UV Radius (Mλ)", ylabel="1/√w (Jy)")

        if self.fig.axes:
            self.fig.axes[-1].set_xlabel("UV Radius (Mλ)")

    def _create_scatters(self, data: dict) -> RadScatters:
        """
        Crée les objets ``PathCollection`` (scatter) pour chaque type de données.

        Parameters
        ----------
        data : dict
            Données UV avec clés ``'u'``, ``'v'``, ``'amp'``, ``'phase'``,
            ``'weight'``, ``'modamp'``, ``'modphs'``.

        Returns
        -------
        RadScatters
            Dataclass regroupant tous les scatter plots créés sur les axes actifs.
        """
        uv_radius  = np.sqrt(data['u']**2 + data['v']**2) / 1e6
        weight     = data.get('weight', np.ones_like(uv_radius))
        error_data = np.where(weight != 0, 1.0 / np.sqrt(np.fabs(weight)), 0.0)

        scats = RadScatters()
        kw = dict(s=1, alpha=0.5, edgecolors='none', zorder=2)
        kw_model = dict(s=1, alpha=0.8, edgecolors='none', zorder=3, visible=False)

        zeros = np.zeros_like(uv_radius)

        if self.ax:
            if self.display_mode in [DisplayMode.AMP_ONLY, DisplayMode.BOTH]:
                scats.amp = self.ax.scatter(
                    uv_radius, data['amp'], color=DesignSystem.PLOT_DATA, **kw)
                scats.model_amp = self.ax.scatter(
                    uv_radius, data.get('modamp', zeros),
                    color=DesignSystem.PLOT_MODEL, **kw_model)
            elif self.display_mode == DisplayMode.PHASE_ONLY:
                scats.phase = self.ax.scatter(
                    uv_radius, data['phase'], color=DesignSystem.PLOT_DATA, **kw)
                scats.model_phs = self.ax.scatter(
                    uv_radius, data.get('modphs', zeros),
                    color=DesignSystem.PLOT_MODEL, **kw_model)

        if self.ax_phase and self.display_mode == DisplayMode.BOTH:
            scats.phase = self.ax_phase.scatter(
                uv_radius, data['phase'], color=DesignSystem.PLOT_DATA, **kw)
            scats.model_phs = self.ax_phase.scatter(
                uv_radius, data.get('modphs', zeros),
                color=DesignSystem.PLOT_MODEL, **kw_model)

        if self.ax_err:
            scats.err = self.ax_err.scatter(
                uv_radius, error_data, color=DesignSystem.PLOT_ERROR, **kw)
            valid = weight[weight != 0]
            if len(valid) > 0:
                wtmin   = np.min(np.fabs(valid))
                err_max = 1.0 / np.sqrt(wtmin) if wtmin > 0 else 1.0
                self.ax_err.set_ylim([0.0, err_max * 1.1])

        return scats

    def _create_editor(self, observation, scats: RadScatters) -> None:
        """
        Instancie un :class:`RadPlotEditor` sur les axes et scatters courants.

        Parameters
        ----------
        observation : Observation
            Objet fournissant le masque de flagging et les métadonnées.
        scats : RadScatters
            Scatter plots déjà tracés sur les axes actifs.
        """
        # Déconnecter les handlers de l'ancien éditeur pour éviter les fuites mémoire
        if self.editor is not None:
            self.editor.cleanup()

        ax_phase_arg = self.ax_phase if self.display_mode == DisplayMode.BOTH else None

        self.editor = RadPlotEditor(
            observation=observation,
            fig=self.fig,
            ax=self.ax,
            ax_phase=ax_phase_arg,
            ax_err=self.ax_err,
            data=self.data,
            scats=scats,
            base_color=DesignSystem.PLOT_DATA,
            sync_callback=self._sync_callback,
        )
        self.editor.show_errors  = self.show_errors
        self.editor.display_mode = self.display_mode
        self.editor._update_colors()
        # Appliquer le mode courant des boutons au nouvel éditeur
        if hasattr(self, '_tool_buttons'):
            for mode, btn in self._tool_buttons.items():
                if mode != "XHAIR" and btn.isChecked():
                    self._on_tool_btn(mode, btn)
                    break
