import numpy as np
import matplotlib.pyplot as plt
from .base import BasePlotEditor
from difmap_wrapper.gui.styles.design_system import DesignSystem

class UVPlotEditor(BasePlotEditor):
    """
    Éditeur spécifique aux Visibilités dans le plan U/V.
    """

    def __init__(self, observation, fig, ax, data, scat_main, scat_conj, base_color, info_callback=None, save_callback=None, sync_callback=None):
        super().__init__(observation, fig, ax, data, info_callback, save_callback, sync_callback)
        self.scat_main = scat_main
        self.scat_conj = scat_conj
        self.base_color = base_color

        # Ajout du raccourci purement UVPlot (Points conjugués)
        self.raccourcis_autorises["%"] = self.action_toggle_conjugate

    def apply_cut(self, x1, y1, x2, y2):
        """Flagge les points dans la boîte (u1,v1) à (u2,v2)."""
        u_min, u_max = min(x1, x2), max(x1, x2)
        v_min, v_max = min(y1, y2), max(y1, y2)
        
        u_data = self.data["u"] / 1e6
        v_data = self.data["v"] / 1e6
        
        # Trouver points dans la boîte - plein ET conjugués
        mask_main = (u_data >= u_min) & (u_data <= u_max) & (v_data >= v_min) & (v_data <= v_max)
        mask_conj = (-u_data >= u_min) & (-u_data <= u_max) & (-v_data >= v_min) & (-v_data <= v_max)
        mask_box = mask_main | mask_conj
        
        # Ne pas reflagge points déjà flaggés
        masque_final = mask_box & (~self.masque_flagges)
        indices_a_supprimer = np.where(masque_final)[0]
        
        if len(indices_a_supprimer) > 0:
            print(f"[CUT] {len(indices_a_supprimer)} visibilités flaggées (UV plot)")
            self._flag_indices(indices_a_supprimer)

    def update_marker_size(self, size):
        """Met à jour la taille des points en temps réel via le slider."""
        # On met la taille au carré pour que le slider ait un vrai impact visuel (1 à 25)
        real_size = size ** 2
        self.scat_main.set_sizes([real_size])
        self.scat_conj.set_sizes([real_size])
        self.fig.canvas.draw_idle() # <-- IL MANQUAIT ÇA POUR RAFRAÎCHIR L'IMAGE !

    def set_conjugate_visible(self, visible: bool):
        """Affiche ou masque les points symétriques en suivant la Checkbox."""
        self.scat_conj.set_visible(visible)
        etat = "affichés" if visible else "masqués"
        msg = f"Points conjugués {etat}." # <--- Balise supprimée
        if self.info_callback:
            self.info_callback(msg, level='info')
        self.fig.canvas.draw_idle()

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
            vrai_nom = self.noms_antennes.get(ant_cible, f"Ant {ant_cible}")
            m = (self.data["subarray"] == sub_actif) & ((self.data["tel_a"] == ant_cible) | (self.data["tel_b"] == ant_cible))
            
            # Simple changement de couleur, la taille reste identique (s=1)
            couleurs[m] = DesignSystem.PLOT_FOCUS
            self.ax.set_title(f"FOCUS : {sub_actif}:{vrai_nom}", color=DesignSystem.PLOT_FOCUS, fontsize=10)
        else:
            self.ax.set_title(f"EXPLORATION : SUBARRAY {sub_actif}", color=DesignSystem.PLOT_TITLE_INACTIVE, fontsize=10)

        # Cacher les flaggés
        off_m = np.column_stack((self.data["u"] / 1e6, self.data["v"] / 1e6))
        off_c = np.column_stack((-self.data["u"] / 1e6, -self.data["v"] / 1e6))
        off_m[self.masque_flagges] = [np.nan, np.nan]
        off_c[self.masque_flagges] = [np.nan, np.nan]

        self.scat_main.set_offsets(off_m)
        self.scat_conj.set_offsets(off_c)
        
        # Application des couleurs homogènes
        self.scat_main.set_color(couleurs)
        self.scat_conj.set_color(couleurs)
        
        self.fig.canvas.draw_idle()
        
    def action_show_info(self, event):
        """Récupère l'information exacte (Touche S ou Clic Gauche)."""
        if event.xdata is None or event.ydata is None: return

        u_s, v_s = event.xdata, event.ydata
        u_d, v_d = self.data["u"] / 1e6, self.data["v"] / 1e6
        tolerance_sq = ((self.ax.get_xlim()[1] - self.ax.get_xlim()[0]) * 0.015) ** 2

        dist_main = (u_d - u_s) ** 2 + (v_d - v_s) ** 2
        dist_conj = (-u_d - u_s) ** 2 + (-v_d - v_s) ** 2

        min_m, min_c = np.min(dist_main), np.min(dist_conj)
        if min(min_m, min_c) > tolerance_sq: return

        idx = np.argmin(dist_main) if min_m < min_c else np.argmin(dist_conj)
        if self.masque_flagges[idx]: return

        # BLINDAGE ANTI-CRASH (utilisation de .get())
        sub = self.data.get("subarray", [0]*len(u_d))[idx]
        t_a = self.data.get("tel_a", [0]*len(u_d))[idx]
        t_b = self.data.get("tel_b", [0]*len(u_d))[idx]
        nom_a = self.noms_antennes.get(t_a, f"An{t_a}")
        nom_b = self.noms_antennes.get(t_b, f"An{t_b}")
        
        if_no = self.data.get("if_no", [1]*len(u_d))[idx]
        ut_raw = self.data.get("time", np.zeros(len(u_d)))[idx]
        flux = self.data.get("amp", np.zeros(len(u_d)))[idx]

        doy = int(ut_raw // 86400)
        hh, mm, ss = int((ut_raw % 86400) // 3600), int((ut_raw % 3600) // 60), int(ut_raw % 60)

        # Création du bloc multilignes avec un alignement (:) parfait
        info_text = (
            f"--- Quick Inspect (S) ---\n"
            f"Antennas : {sub}:{nom_a}-{nom_b}\n"
            f"Time UT  : {doy:03d}-{hh:02d}:{mm:02d}:{ss:02d}\n"
            f"Flux     : {flux:.4f} Jy\n"
            f"IF Band  : {if_no}\n"
            f"-------------------------"
        )
        
        if self.info_callback:
            # On utilise le nouveau niveau 'inspect' pour la couleur bleue !
            self.info_callback(info_text, level='inspect')
            
    def apply_external_cut(self, indices):
        """Reçoit une demande de flagging depuis un autre widget (ex: Radplot)."""
        if len(indices) == 0: return
        
        # Filtre pour ne pas re-flagger des points déjà supprimés
        indices_valides = [i for i in indices if not self.masque_flagges[i]]
        if not indices_valides: return
        
        indices_np = np.array(indices_valides, dtype=np.int32)
        
        # Le Cerveau fait le travail (Moteur C, Masque, et Historique d'Undo)
        self.obs.flag_data(indices_np)
        self.masque_flagges[indices_np] = True
        self.historique_coupes.append(indices_np)
        
        # Met à jour l'écran 1 (Plan UV)
        self._update_colors()
        print(f"{len(indices_np)} visibilites flaggees depuis le Radplot.")
        
        # Met à jour l'écran 2 (Radplot) via l'alarme
        if hasattr(self, 'sync_callback') and self.sync_callback:
            self.sync_callback()
            
    