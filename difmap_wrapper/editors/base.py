import re
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Cursor, RectangleSelector

class BasePlotEditor:
    """Éditeur de base universel pour les visibilités."""

    def __init__(self, observation, fig, ax, data, info_callback=None, save_callback=None, sync_callback=None, shared_mask=None, shared_history=None):
        # Blindage anti-erreur pour récupérer l'objet observation
        if hasattr(observation, 'flag_data'): self.obs = observation
        elif hasattr(observation, '_session'): self.obs = observation._session.obs
        elif hasattr(observation, 'obs'): self.obs = observation.obs
        else: self.obs = observation

        self.fig = fig
        self.ax = ax
        self.data = data
        self.info_callback = info_callback
        self.save_callback = save_callback
        self.sync_callback = sync_callback
        
        # Partage de la mémoire entre les onglets
        self.masque_flagges = shared_mask if shared_mask is not None else np.zeros(len(data["u"]), dtype=bool)
        self.historique_coupes = shared_history if shared_history is not None else []
        self.flag_all_channels = False 

        # --- Regroupement des antennes par sous-réseau ---
        self.antennes_par_subarray = {}
        for sub in np.unique(data["subarray"]):
            masque = data["subarray"] == sub
            self.antennes_par_subarray[sub] = list(np.unique(np.concatenate([data["tel_a"][masque], data["tel_b"][masque]])))

        self.liste_subarrays = list(self.antennes_par_subarray.keys())
        self.index_subarray_actuel = 0
        self.index_antenne_actuelle = -1

        # Récupération des noms depuis le moteur C
        self.noms_antennes = {num: self.obs._native.get_telescope_name(0, num) 
                              for num in np.unique(np.concatenate([data["tel_a"], data["tel_b"]]))}

        # --- Variables de la Super-Souris ---
        self.mode = None
        self.press_info = None  # Position du clic pour le Smart Click
        self.pan_start = None   # Départ du glissement pour le mode Pan
        self.original_limits = (self.ax.get_xlim(), self.ax.get_ylim())
        self.current_size_idx = 0
        self.marker_sizes = [1.0, 3.0, 5.0]

        # --- Outils Matplotlib ---
        self.rs = RectangleSelector(
            self.ax, self.on_select, useblit=True, button=[1],
            minspanx=5, minspany=5, spancoords="pixels", interactive=False,
        )
        self.rs.set_active(False)
        
        self.cursor_widget = Cursor(self.ax, useblit=True, color='gray', linewidth=0.8)
        self.cursor_widget.active = False

        # --- Raccourcis Clavier ---
        self.raccourcis_autorises = {
            "r": self.action_home,
            "x": self.action_quit, "X": self.action_quit,
            "q": self.action_quit, "Q": self.action_quit,
            "h": self.action_help, "H": self.action_help,
            "l": self.action_redisplay, "L": self.action_redisplay,
            "z": self.action_toggle_zoom, "Z": self.action_toggle_zoom,
            "m": self.action_toggle_pan, "M": self.action_toggle_pan,
            "c": self.action_toggle_cut, "C": self.action_toggle_cut,
            ".": self.action_toggle_marker_size,
            "+": self.action_toggle_crosshair,
            "w": self.action_toggle_channels, "W": self.action_toggle_channels,
            "u": self.action_undo, "ctrl+z": self.action_undo,
            "ctrl+s": self.action_save,
            "n": self.action_next_telescope, "p": self.action_prev_telescope,
            "N": self.action_next_subarray, "P": self.action_prev_subarray,
            "t": self.action_specific_telescope, "T": self.action_specific_telescope,
            "s": self.action_show_info, "S": self.action_show_info,
        }

        # Connexion des événements
        self.fig.canvas.mpl_connect("key_press_event", self.on_key_press)
        self.fig.canvas.mpl_connect("button_press_event", self.on_mouse_press)
        self.fig.canvas.mpl_connect("button_release_event", self.on_mouse_release)
        self.fig.canvas.mpl_connect("motion_notify_event", self.on_mouse_motion)

    # =======================================================
    # LOGIQUE DE LA SOURIS (Smart Click, Pan, Drag)
    # =======================================================
    def on_mouse_press(self, event):
        if event.inaxes != self.ax or event.button != 1: return
        self.press_info = (event.x, event.y)
        
        if self.mode == "PAN":
            # On mémorise les PIXELS (event.x/y) et les LIMITES au moment précis du clic
            self.pan_start = (event.x, event.y, self.ax.get_xlim(), self.ax.get_ylim())

    def on_mouse_motion(self, event):
        if self.mode == "PAN" and self.pan_start is not None and event.x is not None:
            px_start, py_start, xlim0, ylim0 = self.pan_start
            
            # 1. Calcul du déplacement en PIXELS (fixe par rapport à l'écran)
            dx_pix = event.x - px_start
            dy_pix = event.y - py_start
            
            # 2. Conversion PIXELS -> DATA (Unités du graphique)
            # On calcule combien d'unités de données il y a par pixel
            width, height = self.ax.bbox.width, self.ax.bbox.height
            ux = (xlim0[1] - xlim0[0]) / width
            uy = (ylim0[1] - ylim0[0]) / height
            
            dx_data = dx_pix * ux
            dy_data = dy_pix * uy
            
            # 3. On applique le décalage aux limites d'origine (xlim0)
            self.ax.set_xlim(xlim0[0] - dx_data, xlim0[1] - dx_data)
            self.ax.set_ylim(ylim0[0] - dy_data, ylim0[1] - dy_data)
            
            self.fig.canvas.draw_idle()

    def on_mouse_release(self, event):
        self.pan_start = None
        if not self.press_info or event.button != 1: return
        
        # SMART CLICK : Moins de 5 pixels = Inspection
        dist = np.sqrt((event.x - self.press_info[0])**2 + (event.y - self.press_info[1])**2)
        if dist < 5.0 and event.xdata is not None:
            self.action_show_info(event)
        
        self.press_info = None
        
    def on_select(self, eclick, erelease):
        if self.mode not in ["ZOOM", "CUT"]: return
        u1, v1 = eclick.xdata, eclick.ydata
        u2, v2 = erelease.xdata, erelease.ydata
        
        if self.mode == "ZOOM":
            self.ax.set_xlim(min(u1, u2), max(u1, u2))
            self.ax.set_ylim(min(v1, v2), max(v1, v2))
            self.fig.canvas.draw_idle()
            if self.info_callback: self.info_callback("Zoom appliqué.", level='info')
        elif self.mode == "CUT":
            self.apply_cut(u1, v1, u2, v2)

    def on_key_press(self, event):
        if event.key in self.raccourcis_autorises:
            self.raccourcis_autorises[event.key](event)

    # =======================================================
    # GESTION DES MODES
    # =======================================================
    def _set_mode(self, new_mode):
        if self.mode == new_mode:
            new_mode = None 
            
        self.mode = new_mode
        self.rs.set_active(self.mode in ["ZOOM", "CUT"])
        
        etat = self.mode if self.mode else "Désactivé (Inspection Rapide)"
        if hasattr(self, 'info_callback') and self.info_callback:
            self.info_callback(f"Outil actif : {etat}", level='info')

    def action_toggle_zoom(self, event=None): self._set_mode("ZOOM")
    def action_toggle_cut(self, event=None): self._set_mode("CUT")
    def action_toggle_pan(self, event=None): self._set_mode("PAN")

    def action_home(self, event=None):
        """Réinitialise la vue globale."""
        if self.original_limits:
            self.ax.set_xlim(self.original_limits[0])
            self.ax.set_ylim(self.original_limits[1])
            self._set_mode(None) 
            self.fig.canvas.draw_idle()
            if self.info_callback:
                self.info_callback("Vue réinitialisée à l'origine.", level='success')

    # =======================================================
    # ACTIONS SECONDAIRES ET COSMÉTIQUES
    # =======================================================
    def action_redisplay(self, event): 
        self.fig.canvas.draw_idle()

    def action_toggle_crosshair(self, event):
        self.cursor_widget.active = not self.cursor_widget.active
        self.fig.canvas.draw_idle()

    def action_toggle_channels(self, event): 
        self.flag_all_channels = not self.flag_all_channels
        etat = "TOUS LES CANAUX" if self.flag_all_channels else "CANAUX SÉLECTIONNÉS"
        if self.info_callback: self.info_callback(f"Portée du flagging : {etat}", level='warning')

    def action_toggle_marker_size(self, event):
        self.current_size_idx = (self.current_size_idx + 1) % len(self.marker_sizes)
        self.update_marker_size(self.marker_sizes[self.current_size_idx]) 

    def set_crosshair_visible(self, visible: bool):
        self.cursor_widget.active = visible
        self.fig.canvas.draw_idle()

    def set_flag_all_channels(self, flag: bool):
        self.flag_all_channels = flag
        etat = "TOUS LES CANAUX" if flag else "CANAUX SÉLECTIONNÉS"
        if self.info_callback: self.info_callback(f"Portée du flagging : {etat}", level='warning')

    def action_undo(self, event=None):
        if not self.historique_coupes: 
            if self.info_callback: self.info_callback("Aucune opération à annuler.", level='warning')
            return
        derniers_morts = self.historique_coupes.pop()
        self.obs.unflag_data(derniers_morts)
        self.masque_flagges[derniers_morts] = False
        self._update_colors()
        if self.info_callback: self.info_callback(f"Restauration de {len(derniers_morts)} visibilités.", level='success')
        if self.sync_callback: self.sync_callback()

    def action_save(self, event=None):
        path_origine = getattr(self.obs, 'filepath', "data.fits")
        if hasattr(self, 'save_callback') and self.save_callback:
            nom_final = self.save_callback(path_origine)
            if not nom_final: return 
        else:
            nom_final = input("Nom du fichier de sauvegarde : ").strip()
            if not nom_final: return

        try:
            self.obs.save_wobs(nom_final)
            if self.info_callback: self.info_callback(f"Fichier enregistré : {nom_final}", level='success')
        except Exception as e:
            if self.info_callback: self.info_callback(f"Échec sauvegarde : {e}", level='error')

    def action_quit(self, event):
        plt.close(self.fig)

    # =======================================================
    # NAVIGATION TÉLESCOPES
    # =======================================================
    def action_next_telescope(self, event=None):
        sub_id = self.liste_subarrays[self.index_subarray_actuel]
        nb_ant_dans_sub = len(self.antennes_par_subarray[sub_id])
        self.index_antenne_actuelle += 1
        if self.index_antenne_actuelle >= nb_ant_dans_sub:
            self.index_subarray_actuel = (self.index_subarray_actuel + 1) % len(self.liste_subarrays)
            self.index_antenne_actuelle = 0
        self._update_colors()

    def action_prev_telescope(self, event=None):
        self.index_antenne_actuelle -= 1
        if self.index_antenne_actuelle < 0:
            self.index_subarray_actuel = (self.index_subarray_actuel - 1) % len(self.liste_subarrays)
            sub_id = self.liste_subarrays[self.index_subarray_actuel]
            self.index_antenne_actuelle = len(self.antennes_par_subarray[sub_id]) - 1
        self._update_colors()

    def action_next_subarray(self, event=None):
        self.index_subarray_actuel = (self.index_subarray_actuel + 1) % len(self.liste_subarrays)
        self.index_antenne_actuelle = 0
        self._update_colors()

    def action_prev_subarray(self, event=None):
        self.index_subarray_actuel = (self.index_subarray_actuel - 1) % len(self.liste_subarrays)
        self.index_antenne_actuelle = 0
        self._update_colors()

    def action_specific_telescope(self, event=None, target_name=None):
        recherche = str(target_name).strip().upper() if target_name else ""
        if not recherche: return

        found = False
        for s_idx, sub_id in enumerate(self.liste_subarrays):
            for a_idx, ant_id in enumerate(self.antennes_par_subarray[sub_id]):
                if recherche in (self.noms_antennes.get(ant_id, "").upper(), str(ant_id)):
                    self.index_subarray_actuel, self.index_antenne_actuelle = s_idx, a_idx
                    found = True; break
            if found: break

        if found:
            sub_id = self.liste_subarrays[self.index_subarray_actuel]
            nom = self.noms_antennes.get(self.antennes_par_subarray[sub_id][self.index_antenne_actuelle])
            if self.info_callback: self.info_callback(f"Focus sur {sub_id}:{nom}.", level='info')
            self._update_colors()

    def action_help(self, event):
        if self.info_callback: self.info_callback("Consultez le menu Help pour les raccourcis.", level='info')

    # =======================================================
    # MÉTHODES VIRTUELLES ET UTILITAIRES
    # =======================================================
    def apply_cut(self, x1, y1, x2, y2): pass
    def update_marker_size(self, size): pass
    def set_conjugate_visible(self, visible: bool): pass
    def _update_colors(self): pass
    def action_show_info(self, event): pass
    
    def _flag_indices(self, indices):
        if len(indices) == 0: return
        indices_np = np.array(indices, dtype=np.int32)
        self.obs.flag_data(indices_np)
        self.masque_flagges[indices_np] = True
        self.historique_coupes.append(indices_np)
        self._update_colors()
        if self.sync_callback: self.sync_callback()