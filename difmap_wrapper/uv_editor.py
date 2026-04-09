import numpy as np
import matplotlib.pyplot as plt
from .base import BasePlotEditor

class UVPlotEditor(BasePlotEditor):
    """
    Éditeur spécifique aux Visibilités dans le plan U/V.
    """

    def __init__(self, observation, fig, ax, data, scat_main, scat_conj, base_color):
        super().__init__(observation, fig, ax, data)

        self.scat_main = scat_main
        self.scat_conj = scat_conj
        self.base_color = base_color

        # Ajout du raccourci purement UVPlot (Points conjugués)
        self.raccourcis_autorises["%"] = self.action_toggle_conjugate

    def update_marker_size(self, size):
        self.scat_main.set_sizes([size])
        self.scat_conj.set_sizes([size])

    def action_toggle_conjugate(self, event):
        is_visible = self.scat_conj.get_visible()
        self.scat_conj.set_visible(not is_visible)
        etat = "affichés" if not is_visible else "masqués"
        print(f"[VIEW] Points conjugues {etat}.")
        self.fig.canvas.draw_idle()

    def action_redisplay(self, event):
        print("[VIEW] Rafraichissement complet du graphique...")
        vis_m = self.scat_main.get_visible()
        vis_c = self.scat_conj.get_visible()
        self.scat_main.set_visible(False)
        self.scat_conj.set_visible(False)
        
        self.fig.canvas.draw()
        plt.pause(0.05) # Effet de clignotement pour prouver le refresh
        
        self.scat_main.set_visible(vis_m)
        self.scat_conj.set_visible(vis_c)
        self._update_colors()

    def _update_colors(self):
        couleurs = np.full(len(self.data["u"]), self.base_color, dtype=object)
        sub_actif = self.liste_subarrays[self.index_subarray_actuel]
        
        if self.index_antenne_actuelle >= 0:
            ant_cible = self.antennes_par_subarray[sub_actif][self.index_antenne_actuelle]
            vrai_nom = self.noms_antennes.get(ant_cible, f"Antenne {ant_cible}")
            m = (self.data["subarray"] == sub_actif) & ((self.data["tel_a"] == ant_cible) | (self.data["tel_b"] == ant_cible))
            couleurs[m] = "red"
            self.ax.set_title(f"Focus : {sub_actif}:{vrai_nom}", color="red", fontweight="bold")
        else:
            self.ax.set_title(f"Mode exploration (sous-réseau {sub_actif})", color="black")

        off_m = np.column_stack((self.data["u"] / 1e6, self.data["v"] / 1e6))
        off_c = np.column_stack((-self.data["u"] / 1e6, -self.data["v"] / 1e6))
        
        off_m[self.masque_flagges] = [np.nan, np.nan]
        off_c[self.masque_flagges] = [np.nan, np.nan]

        self.scat_main.set_offsets(off_m)
        self.scat_conj.set_offsets(off_c)
        self.scat_main.set_color(couleurs)
        self.scat_conj.set_color(couleurs)
        self.fig.canvas.draw_idle()

    def apply_cut(self, u1, v1, u2, v2):
        u_min, u_max = min(u1, u2), max(u1, u2)
        v_min, v_max = min(v1, v2), max(v1, v2)
        u_d, v_d = self.data["u"] / 1e6, self.data["v"] / 1e6

        m_main = (u_d >= u_min) & (u_d <= u_max) & (v_d >= v_min) & (v_d <= v_max)
        m_conj = (-u_d >= u_min) & (-u_d <= u_max) & (-v_d >= v_min) & (-v_d <= v_max)
        masque_final = (m_main | m_conj) & (~self.masque_flagges)
        
        indices_a_supprimer = np.where(masque_final)[0].astype(np.int32)

        if len(indices_a_supprimer) == 0:
            print("Aucun point valide dans la zone.")
            return

        self.obs.flag_data(indices_a_supprimer)
        self.masque_flagges[indices_a_supprimer] = True
        self.historique_coupes.append(indices_a_supprimer)
        self._update_colors()
        print(f"{len(indices_a_supprimer)} visibilites flaggees.")

    def action_show_info(self, event):
        """Récupère l'information exacte, y compris l'IF et l'heure (Touche S)."""
        if event.xdata is None or event.ydata is None:
            return

        u_s, v_s = event.xdata, event.ydata
        u_d, v_d = self.data["u"] / 1e6, self.data["v"] / 1e6
        tolerance_sq = ((self.ax.get_xlim()[1] - self.ax.get_xlim()[0]) * 0.015) ** 2

        dist_main = (u_d - u_s) ** 2 + (v_d - v_s) ** 2
        dist_conj = (-u_d - u_s) ** 2 + (-v_d - v_s) ** 2

        min_m, min_c = np.min(dist_main), np.min(dist_conj)
        if min(min_m, min_c) > tolerance_sq:
            print("Aucune visibilité proche du curseur.")
            return

        idx = np.argmin(dist_main) if min_m < min_c else np.argmin(dist_conj)
        if self.masque_flagges[idx]:
            print("Point sélectionné déjà flaggé.")
            return

        sub = self.data["subarray"][idx]
        t_a, t_b = self.data["tel_a"][idx], self.data["tel_b"][idx]
        nom_a = self.noms_antennes.get(t_a, f"An{t_a}")
        nom_b = self.noms_antennes.get(t_b, f"An{t_b}")
        
        if_no = self.data.get("if_no", [1]*len(u_d))[idx]
        ut_raw = self.data["time"][idx]
        flux = self.data["amp"][idx]

        doy = int(ut_raw // 86400)
        hh, mm, ss = int((ut_raw % 86400) // 3600), int((ut_raw % 3600) // 60), int(ut_raw % 60)

        print(f"Visibility: {sub}:{nom_a}-{nom_b} (IF {if_no}) UT {doy}/{hh:02d}:{mm:02d}:{ss:02d} | Flux {flux:.3f} Jy")