import numpy as np
from difmap_wrapper.gui.widgets.base_plot_widget import BasePlotWidget
from difmap_wrapper.editors.rad_editor import RadPlotEditor
from difmap_wrapper.gui.utils import MatplotlibStyler
from difmap_wrapper.gui.styles.design_system import DesignSystem

class RadPlotWidget(BasePlotWidget):
    def __init__(self, parent=None, info_callback=None, sync_callback=None):
        self.display_mode = 1 # 1: Amp, 2: Phase, 3: Both
        self.show_errors = False
        self.ax_phase = None  
        self.ax_err = None
        self.data = None
        self.editor = None
        self.info_callback = info_callback
        self.sync_callback = sync_callback
        super().__init__(parent=parent, figsize=(8, 6), layout_type='constrained')

    def set_display_mode(self, mode_index):
        self.display_mode = mode_index + 1
        if self.data is not None: self._refresh_layout()

    def set_show_errors(self, visible):
        """Action déclenchée par la touche E ou la checkbox."""
        self.show_errors = visible
        if self.data is not None: self._refresh_layout()

    def _refresh_layout(self):
        """Re-calcule tout le plot pour changer la géométrie (1, 2 ou 3 axes)."""
        if self.editor and self.data is not None:
            self.plot_data(self.data, self.editor.masque_flagges, self.editor.historique_coupes, self.editor.obs)

    def _setup_axes(self):
        self.fig.clear()
        
        # Détermination des axes nécessaires
        active_plots = []
        if self.display_mode in [1, 3]: active_plots.append('AMP')
        if self.display_mode in [2, 3]: active_plots.append('PHS')
        if self.show_errors: active_plots.append('ERR')
        
        n_rows = len(active_plots)
        self.ax_phase = None
        self.ax_err = None
        self.ax = None  # Réinitialiser avant création

        # Création dynamique avec sharex correct
        main_ax = None
        for i, ptype in enumerate(active_plots):
            # Tous partagent le même axe X (le premier)
            ax = self.fig.add_subplot(n_rows, 1, i+1, sharex=main_ax)
            if i == 0: 
                main_ax = ax
                self.ax = ax
            
            if ptype == 'AMP':
                MatplotlibStyler.setup_axes(ax, title_text="Amplitude", xlabel="", ylabel="Amp (Jy)")
            elif ptype == 'PHS':
                self.ax_phase = ax
                MatplotlibStyler.setup_axes(ax, title_text="Phase", xlabel="", ylabel="Phase (°)")
            elif ptype == 'ERR':
                self.ax_err = ax
                MatplotlibStyler.setup_axes(ax, title_text="Theoretical Error", xlabel="UV Radius (Mλ)", ylabel="1/√w (Jy)")
        
        # Ajustement du dernier axe pour le label X
        if self.fig.axes:
            self.fig.axes[-1].set_xlabel("UV Radius (Mλ)")

    def plot_data(self, data, shared_mask=None, shared_history=None, observation=None):
        self.data = data
        self._setup_axes()
        if data is None or len(data.get('u', [])) == 0:
            self.draw(); return

        uv_radius = np.sqrt(data['u']**2 + data['v']**2) / 1e6
        
        # Calcul de l'erreur théorique (1/sqrt(|weight|)) - match C source: 1.0/sqrt(fabs(wt))
        weight = data.get('weight', np.ones_like(uv_radius))
        error_data = np.where(weight != 0, 1.0 / np.sqrt(np.fabs(weight)), 0.0)

        # Dictionnaire pour stocker proprement les objets graphiques
        scats = {"amp": None, "phs": None, "m_amp": None, "m_phs": None, "err": None}

        # On remplit les graphiques en fonction des axes qui ont été créés
        if self.ax: 
            if self.display_mode in [1, 3]:
                scats["amp"] = self.ax.scatter(uv_radius, data['amp'], s=1, color=DesignSystem.PLOT_DATA, alpha=0.5, edgecolors='none', zorder=2)
                scats["m_amp"] = self.ax.scatter(uv_radius, data.get('modamp', np.zeros_like(uv_radius)), s=1, color='red', alpha=0.8, edgecolors='none', zorder=3, visible=False)
            elif self.display_mode == 2:
                # Si on n'affiche que la phase, elle prend l'axe principal
                scats["phs"] = self.ax.scatter(uv_radius, data['phase'], s=1, color=DesignSystem.PLOT_DATA, alpha=0.5, edgecolors='none', zorder=2)
                scats["m_phs"] = self.ax.scatter(uv_radius, data.get('modphs', np.zeros_like(uv_radius)), s=1, color='red', alpha=0.8, edgecolors='none', zorder=3, visible=False)
        
        if self.ax_phase and self.display_mode == 3:
            scats["phs"] = self.ax_phase.scatter(uv_radius, data['phase'], s=1, color=DesignSystem.PLOT_DATA, alpha=0.5, edgecolors='none', zorder=2)
            scats["m_phs"] = self.ax_phase.scatter(uv_radius, data.get('modphs', np.zeros_like(uv_radius)), s=1, color='red', alpha=0.8, edgecolors='none', zorder=3, visible=False)

        if self.ax_err:
            scats["err"] = self.ax_err.scatter(uv_radius, error_data, s=1, color='cyan', alpha=0.5, edgecolors='none', zorder=2)
            # Auto-scale error axis: errmin=0, errmax=1/sqrt(|wtmin|)
            valid_weights = weight[weight != 0]
            if len(valid_weights) > 0:
                wtmin = np.min(np.fabs(valid_weights))
                err_max = 1.0 / np.sqrt(wtmin) if wtmin > 0 else 1.0
                self.ax_err.set_ylim([0.0, err_max * 1.1])  # Add 10% margin

        if observation:
            # Déterminer correctement les axes selon le mode
            # Mode 1: Amp only -> ax_phase=None
            # Mode 2: Phase only -> ax_phase=None (la phase est dans self.ax)
            # Mode 3: Amp+Phase -> ax_phase est le deuxième axe
            passed_ax_phase = None
            if self.display_mode == 3:
                passed_ax_phase = self.ax_phase
            # En mode 1 ou 2, ax_phase reste None - c'est correct
            
            # Création de l'éditeur en lui passant tous les objets proprement
            self.editor = RadPlotEditor(
                observation=observation, fig=self.fig, ax=self.ax,
                ax_phase=passed_ax_phase,
                ax_err=self.ax_err, data=self.data, scats=scats,
                base_color=DesignSystem.PLOT_DATA, info_callback=self.info_callback, 
                sync_callback=self.sync_callback, shared_mask=shared_mask, shared_history=shared_history
            )
            # ✅ Synchroniser l'état d'affichage des erreurs
            self.editor.show_errors = self.show_errors
            self.editor._update_colors()
            
        # ✅ Force un redraw complet (pas juste draw_idle) pour que les nouveaux axes s'affichent
        self.fig.canvas.draw()
        self.refresh()