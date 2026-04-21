# difmap_wrapper/gui/radplot_widget.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from matplotlib.collections import PathCollection

from difmap_wrapper.gui.widgets.base_plot_widget import BasePlotWidget
from difmap_wrapper.editors.rad_editor import RadPlotEditor
from difmap_wrapper.gui.utils import MatplotlibStyler
from difmap_wrapper.gui.styles.design_system import DesignSystem
from difmap_wrapper.enums import DisplayMode


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
            # Sauvegarder l'état du crosshair
            crosshair_was_active = getattr(self.editor, 'cursor_active', False)
            
            # Recrée l'éditeur avec les mêmes données et observation
            self.plot_data(self.data, observation=self.editor.obs)
            
            # Restaurer l'état du crosshair si nécessaire
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
