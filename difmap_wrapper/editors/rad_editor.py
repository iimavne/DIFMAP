import numpy as np
from .base import BasePlotEditor
from difmap_wrapper.gui.styles.design_system import DesignSystem

class RadPlotEditor(BasePlotEditor):
    def __init__(self, observation, fig, ax, data, scat_main, base_color, info_callback=None, save_callback=None, sync_callback=None, shared_mask=None, shared_history=None):
        super().__init__(observation, fig, ax, data, info_callback, save_callback, sync_callback, shared_mask, shared_history)
        self.scat_main = scat_main
        self.base_color = base_color
        self.uv_radius = np.sqrt(self.data["u"]**2 + self.data["v"]**2) / 1e6
        
        self.raccourcis_autorises["%"] = self.action_toggle_conjugate
 

    def apply_cut(self, x1, y1, x2, y2):
        xmin, xmax = min(x1, x2), max(x1, x2)
        ymin, ymax = min(y1, y2), max(y1, y2)
        amp = self.data["amp"]
        
        mask_box = (self.uv_radius >= xmin) & (self.uv_radius <= xmax) & (amp >= ymin) & (amp <= ymax)
        masque_final = mask_box & (~self.masque_flagges)
        indices_a_supprimer = np.where(masque_final)[0]
        
        if len(indices_a_supprimer) > 0:
            print(f"[CUT] {len(indices_a_supprimer)} visibilités flaggées (Radplot)")
            self._flag_indices(indices_a_supprimer)

    def _update_colors(self):
        couleurs = np.full(len(self.data["u"]), self.base_color, dtype=object)
        sub_actif = self.liste_subarrays[self.index_subarray_actuel]
        
        if self.index_antenne_actuelle >= 0:
            ant_cible = self.antennes_par_subarray[sub_actif][self.index_antenne_actuelle]
            vrai_nom = self.noms_antennes.get(ant_cible, f"An{ant_cible}")
            m = (self.data["subarray"] == sub_actif) & ((self.data["tel_a"] == ant_cible) | (self.data["tel_b"] == ant_cible))
            
            couleurs[m] = DesignSystem.PLOT_FOCUS
            self.ax.set_title(f"FOCUS : {sub_actif}:{vrai_nom}", color=DesignSystem.PLOT_FOCUS, fontsize=10)
        else:
            self.ax.set_title(f"EXPLORATION : SUBARRAY {sub_actif}", color=DesignSystem.PLOT_TITLE_INACTIVE, fontsize=10)

        # Cacher les flaggés via offsets
        off_m = np.column_stack((self.uv_radius, self.data["amp"]))
        off_m[self.masque_flagges] = [np.nan, np.nan]

        self.scat_main.set_offsets(off_m)
        self.scat_main.set_color(couleurs)
        self.fig.canvas.draw_idle()


    def update_marker_size(self, size):
        """Met à jour la taille des points en temps réel via le slider."""
        # RadPlotEditor n'a que scat_main (pas de conjugués comme UV plot)
        real_size = size ** 2
        self.scat_main.set_sizes([real_size])
        self.fig.canvas.draw_idle()

    def set_conjugate_visible(self, visible: bool):
        """RadPlotEditor n'a pas de points conjugués - action inopérante."""
        msg = "Les points conjugués ne s'appliquent pas au Radplot."
        if self.info_callback:
            self.info_callback(msg, level='warning')

    def action_toggle_conjugate(self, event):
        """RadPlotEditor n'a pas de conjugués - action inopérante."""
        msg = "Les points conjugués ne s'appliquent pas au Radplot."
        if self.info_callback:
            self.info_callback(msg, level='warning')
        
    def action_show_info(self, event):
        if event.xdata is None or event.ydata is None: return
        x_s, y_s = event.xdata, event.ydata
        
        x_span = self.ax.get_xlim()[1] - self.ax.get_xlim()[0]
        y_span = self.ax.get_ylim()[1] - self.ax.get_ylim()[0]
        
        norm_dx = (self.uv_radius - x_s) / x_span
        norm_dy = (self.data["amp"] - y_s) / y_span
        dist_sq = norm_dx**2 + norm_dy**2
        
        idx = np.argmin(dist_sq)
        if dist_sq[idx] > (0.015**2) or self.masque_flagges[idx]: return
            
        # BLINDAGE ANTI-CRASH
        sub = self.data.get("subarray", [0]*len(self.uv_radius))[idx]
        t_a = self.data.get("tel_a", [0]*len(self.uv_radius))[idx]
        t_b = self.data.get("tel_b", [0]*len(self.uv_radius))[idx]
        
        nom_a = self.noms_antennes.get(t_a, str(t_a))
        nom_b = self.noms_antennes.get(t_b, str(t_b))
        
        flux_val = self.data.get('amp', np.zeros(len(self.uv_radius)))[idx]
        
        msg = (
            f"--- Quick Inspect (S) ---\n"
            f"Antennas : {sub}:{nom_a}-{nom_b}\n"
            f"Radius   : {self.uv_radius[idx]:.2f} Mλ\n"
            f"Flux     : {flux_val:.4f} Jy\n"
            f"-------------------------"
        )
        
        if self.info_callback: 
            self.info_callback(msg, level='inspect')