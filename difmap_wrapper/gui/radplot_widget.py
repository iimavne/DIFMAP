# difmap_wrapper/gui/radplot_widget.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from matplotlib.collections import PathCollection
from PyQt6.QtCore import QSize
from PyQt6.QtWidgets import QLabel, QComboBox, QPushButton
try:
    import qtawesome as qta
    _HAS_QTA = True
except ImportError:
    _HAS_QTA = False

from difmap_wrapper.gui.widgets.base_plot_widget import BasePlotWidget
from difmap_wrapper.editors.rad_editor import RadPlotEditor
from difmap_wrapper.gui.utils import MatplotlibStyler
from difmap_wrapper.gui.styles.design_system import DesignSystem
from difmap_wrapper.enums import DisplayMode

_TOOLBAR_QSS = f"""
QWidget#PlotToolbar {{
    background-color: {DesignSystem.SURFACE_ALT};
    border-bottom: 1px solid {DesignSystem.BORDER};
    padding: 4px 0;
    height: 32px;
}}
QPushButton {{
    background-color: {DesignSystem.SURFACE};
    color: {DesignSystem.TEXT};
    border: 1px solid {DesignSystem.BORDER};
    border-radius: 5px;
    padding: 4px 10px;
    font-size: 10px;
    min-height: 26px;
    min-width: 70px;
}}
QPushButton:hover  {{
    background-color: {DesignSystem.SURFACE_ALT};
    border-color: {DesignSystem.PRIMARY};
    color: {DesignSystem.TEXT};
}}
QPushButton:pressed {{
    background-color: {DesignSystem.BORDER_LIGHT};
    border-color: {DesignSystem.PRIMARY_ACTIVE};
    color: {DesignSystem.TEXT};
}}
QLabel {{
    color: {DesignSystem.TEXT_MUTED};
    font-size: 10px;
    font-weight: bold;
    background: transparent;
    padding-left: 4px;
}}
QComboBox {{
    background-color: {DesignSystem.SURFACE};
    color: {DesignSystem.TEXT};
    border: 1px solid {DesignSystem.BORDER};
    border-radius: 5px;
    padding: 3px 8px;
    font-size: 10px;
    min-width: 180px;
    min-height: 26px;
}}
QComboBox:hover {{ border-color: {DesignSystem.PRIMARY}; }}
QComboBox::drop-down {{ border: none; width: 18px; }}
QComboBox::down-arrow {{ width: 10px; height: 10px; }}
"""


def _icon(name: str, color: str = "#C8DCF0"):
    if not _HAS_QTA:
        return None
    try:
        return qta.icon(name, color=color)
    except Exception:
        return None


def _make_button(text: str, icon_name: str = None) -> QPushButton:
    btn = QPushButton(text)
    if icon_name:
        ico = _icon(icon_name)
        if ico:
            btn.setIcon(ico)
            btn.setIconSize(QSize(14, 14))
    return btn


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

    _RAD_TOOLS = [
        ("Inspect  [s]",            "INSPECT"),
        ("Pan  [M]",                "PAN"),
        ("Zoom Box  [Z]",           "ZOOM"),
        ("Flag Box  [C]",           "CUT"),
        ("Zoom X (UV range)  [U]",  "ZOOM_X"),
        ("Zoom Y (vertical)  [Y]",  "ZOOM_Y"),
        ("Stats Amp/Phase  [S]",    "STATS"),
        ("Stats Re/Im  [V]",        "STATS_V"),
    ]

    def _build_local_toolbar(self) -> None:
        """Crée la mini-toolbar au-dessus du canvas Radplot."""
        row = self.plot_toolbar_row
        row.setObjectName("PlotToolbar")
        row.setStyleSheet(_TOOLBAR_QSS)
        row.setFixedHeight(32)
        row.setVisible(True)
        lay = self.plot_toolbar_layout

        lay.addWidget(QLabel("  Tools:"))
        self._tool_combo = QComboBox()
        self._tool_combo.setToolTip("Tool active (Keyboard shortcut)")
        for label, data in self._RAD_TOOLS:
            self._tool_combo.addItem(label, data)
        lay.addWidget(self._tool_combo)

        lay.addSpacing(10)

        self._btn_undo    = _make_button("Undo Flag [U]",    "fa5s.undo")
        self._btn_reset   = _make_button("Reset [R]",   "fa5s.expand-arrows-alt")
        self._btn_dezoom  = _make_button("Dézoom [O]",  "fa5s.search-minus")
        self._btn_refresh = _make_button("Refresh [L]", "fa5s.sync-alt")
        for btn, tip in [
            (self._btn_undo,    "Annuler le dernier flagging"),
            (self._btn_reset,   "Réinitialiser la vue (tous les graphiques)"),
            (self._btn_dezoom,  "Dézoomer de 50 %"),
            (self._btn_refresh, "Rafraîchir l'affichage"),
        ]:
            btn.setToolTip(tip)
            lay.addWidget(btn)

        lay.addStretch()

        self._tool_combo.currentIndexChanged.connect(self._on_tool_changed)
        self._btn_undo.clicked.connect(
            lambda: self._on_button_click(self.editor.action_undo, None) if self.editor else None)
        self._btn_reset.clicked.connect(
            lambda: self._on_button_click(self.editor.action_home, None) if self.editor else None)
        self._btn_dezoom.clicked.connect(
            lambda: self._on_button_click(self.editor.action_dezoom, None) if self.editor else None)
        self._btn_refresh.clicked.connect(
            lambda: self._on_button_click(self.editor.action_redisplay, None) if self.editor else None)

    def _on_tool_changed(self, index: int) -> None:
        """Applique le mode sélectionné dans le combo à l'éditeur actif."""
        if index < 0 or not self.editor:
            return
        mode = self._tool_combo.itemData(index)
        if mode == "INSPECT":
            self.editor.inspect_active = True
            self.editor._set_mode(None)
        else:
            self.editor.inspect_active = False
            self.editor._set_mode(mode)
        self.canvas.setFocus()

    def _on_button_click(self, func, arg=None):
        """Exécute l'action du bouton et remet le focus sur le canvas pour les raccourcis clavier."""
        if func:
            func(arg)
        self.canvas.setFocus()

    def sync_inspect_state(self, active: bool) -> None:
        """Synchronise le combo quand l'état inspect change via raccourci clavier."""
        if not hasattr(self, '_tool_combo'):
            return
        if active:
            self._tool_combo.blockSignals(True)
            self._tool_combo.setCurrentIndex(0)
            self._tool_combo.blockSignals(False)

    def sync_tool_state(self, tool: str) -> None:
        """Synchronise le combo de la toolbar locale avec le mode actif de l'éditeur."""
        if not hasattr(self, '_tool_combo') or tool is None:
            return
        if tool == "INSPECT":
            target_index = 0
        else:
            target_index = next((i for i in range(self._tool_combo.count())
                                 if self._tool_combo.itemData(i) == tool), -1)
        if target_index < 0:
            return
        self._tool_combo.blockSignals(True)
        self._tool_combo.setCurrentIndex(target_index)
        self._tool_combo.blockSignals(False)

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

        self.fig.canvas.draw()
        self.refresh()

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
        self.editor.show_errors = self.show_errors
        self.editor._update_colors()
        # Appliquer le mode courant du combo au nouvel éditeur
        if hasattr(self, '_tool_combo'):
            self._on_tool_changed(self._tool_combo.currentIndex())
