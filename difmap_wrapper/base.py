import re
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Cursor, RectangleSelector

class BasePlotEditor:
    """
    Éditeur de base universel pour les visibilités.
    """

    def __init__(self, observation, fig, ax, data):
        # Blindage anti-erreur (gère Observation, Session ou Visualizer)
        if hasattr(observation, 'flag_data'):
            self.obs = observation
        elif hasattr(observation, '_session'):
            self.obs = observation._session.obs
        elif hasattr(observation, 'obs'):
            self.obs = observation.obs
        else:
            self.obs = observation

        self.fig = fig
        self.ax = ax
        self.data = data

        self.masque_flagges = np.zeros(len(data["u"]), dtype=bool)
        self.historique_coupes = []
        self.flag_all_channels = False 

        # --- Regroupement des antennes par sous-réseau ---
        self.antennes_par_subarray = {}
        for sub in np.unique(data["subarray"]):
            masque = data["subarray"] == sub
            self.antennes_par_subarray[sub] = list(np.unique(np.concatenate([data["tel_a"][masque], data["tel_b"][masque]])))

        self.liste_subarrays = list(self.antennes_par_subarray.keys())
        self.index_subarray_actuel = 0
        self.index_antenne_actuelle = -1

        self.noms_antennes = {num: self.obs._native.get_telescope_name(0, num) 
                              for num in np.unique(np.concatenate([data["tel_a"], data["tel_b"]]))}

        # --- Protection des raccourcis Matplotlib ---
        touches_protegees = [
            "s", "S", "p", "P", "c", "C", "h", "H", "l", "L", 
            "n", "N", "z", "Z", "a", "A", "d", "D", "w", "W", 
            "q", "Q", "x", "X", "t", "T", "u", ".", "+", "%",
            "ctrl+s", "ctrl+z"
        ]
        for key in ["save", "pan", "zoom", "home", "back", "forward", "xscale", "yscale", "quit"]:
            config_key = f"keymap.{key}"
            if config_key in plt.rcParams:
                plt.rcParams[config_key] = [k for k in plt.rcParams[config_key] if k not in touches_protegees]

        self.mode = None
        self.first_corner = None
        self.original_limits = (self.ax.get_xlim(), self.ax.get_ylim())
        self.current_size_idx = 0
        self.marker_sizes = [1.0, 3.0, 5.0]

        self.rs = RectangleSelector(
            self.ax, self.on_select, useblit=True, button=[1],
            minspanx=5, minspany=5, spancoords="pixels", interactive=False,
        )
        self.rs.set_active(False)
        self.cursor_widget = Cursor(self.ax, useblit=True, color='gray', linewidth=0.8)
        self.cursor_widget.active = False

        self.raccourcis_autorises = {
            "x": self.action_quit, "X": self.action_quit,
            "q": self.action_quit, "Q": self.action_quit,
            "h": self.action_help, "H": self.action_help,
            "l": self.action_redisplay, "L": self.action_redisplay,
            "z": self.action_toggle_zoom, "Z": self.action_toggle_zoom,
            "a": self.action_select_vertex, "A": self.action_select_vertex,
            "d": self.action_cancel_selection, "D": self.action_cancel_selection,
            ".": self.action_toggle_marker_size,
            "+": self.action_toggle_crosshair,
            "c": self.action_toggle_cut, "C": self.action_toggle_cut,
            "w": self.action_toggle_channels, "W": self.action_toggle_channels,
            "u": self.action_undo, "ctrl+z": self.action_undo,
            "ctrl+s": self.action_save,
            "n": self.action_next_telescope, "p": self.action_prev_telescope,
            "N": self.action_next_subarray, "P": self.action_prev_subarray,
            "t": self.action_specific_telescope, "T": self.action_specific_telescope,
            "s": self.action_show_info, "S": self.action_show_info,
        }

        self.cid_keypress = self.fig.canvas.mpl_connect("key_press_event", self.on_key_press)
        self.cid_mouseclick = self.fig.canvas.mpl_connect("button_press_event", self.on_mouse_click)

    def on_key_press(self, event):
        if event.key in self.raccourcis_autorises:
            self.raccourcis_autorises[event.key](event)

    def on_mouse_click(self, event):
        if self.mode not in ["ZOOM", "CUT"] or event.xdata is None: return
        if event.button in [2, 3]:  self.action_cancel_selection(event)

    def on_select(self, eclick, erelease):
        if self.mode not in ["ZOOM", "CUT"]: return
        
        dx = abs(eclick.xdata - erelease.xdata)
        dy = abs(eclick.ydata - erelease.ydata)
        x_span = self.ax.get_xlim()[1] - self.ax.get_xlim()[0]
        y_span = self.ax.get_ylim()[1] - self.ax.get_ylim()[0]
        
        if dx < (x_span * 0.01) and dy < (y_span * 0.01):
            self.action_select_vertex(erelease)
            return

        u1, v1, u2, v2 = eclick.xdata, eclick.ydata, erelease.xdata, erelease.ydata
        if self.mode == "ZOOM":
            if abs(u1 - u2) > 1e-10 and abs(v1 - v2) > 1e-10:
                self.ax.set_xlim(min(u1, u2), max(u1, u2))
                self.ax.set_ylim(min(v1, v2), max(v1, v2))
                self.fig.canvas.draw_idle()
                print("[ZOOM] Zone appliquee par rectangle.")
            self.first_corner = None
        elif self.mode == "CUT":
            self.apply_cut(u1, v1, u2, v2)
            self.first_corner = None

    def _set_mode(self, new_mode):
        if new_mode is None or self.mode == new_mode:
            old_mode = self.mode
            self.mode = None
            self.first_corner = None
            self.rs.set_active(False)
            if old_mode:
                print(f"[MODE] {old_mode} desactive.")
            return

        if self.mode is not None:
            print(f"[MODE] Fermeture de {self.mode} pour passer a {new_mode}...")
        
        self.mode = new_mode
        self.first_corner = None
        self.rs.set_active(True)
        print(f"[MODE] {new_mode} active : Utilisez A (ou Clic Gauche) pour placer 2 sommets, ou dessinez un rectangle.")

    def action_toggle_zoom(self, event):
        if self.mode == "ZOOM":
            self.ax.set_xlim(self.original_limits[0])
            self.ax.set_ylim(self.original_limits[1])
            self.fig.canvas.draw_idle()
            self._set_mode(None)
            print("[VIEW] Vue reinitialisee a l'origine.")
        else:
            self._set_mode("ZOOM")

    def action_toggle_cut(self, event): self._set_mode("CUT")

    def action_select_vertex(self, event):
        if self.mode not in ["ZOOM", "CUT"] or event.xdata is None: return
        if self.first_corner is None:
            self.first_corner = (event.xdata, event.ydata)
            print(f"[{self.mode}] 1er sommet : U={event.xdata:.2f}, V={event.ydata:.2f}")
        else:
            u1, v1 = self.first_corner
            u2, v2 = event.xdata, event.ydata
            if self.mode == "ZOOM":
                if abs(u1 - u2) > 1e-10 and abs(v1 - v2) > 1e-10:
                    self.ax.set_xlim(min(u1, u2), max(u1, u2))
                    self.ax.set_ylim(min(v1, v2), max(v1, v2))
                    print("[ZOOM] Zone appliquee.")
            elif self.mode == "CUT":
                self.apply_cut(u1, v1, u2, v2)
            self.first_corner = None
            self.fig.canvas.draw_idle()

    def action_cancel_selection(self, event): 
        if self.first_corner is not None:
            self.first_corner = None
            print(f"[{self.mode}] Selection annulee. Re-selectionnez le 1er sommet (A ou Clic).")
        else:
            print(f"Mode {self.mode} actif. En attente d'une action.")

    def action_redisplay(self, event): 
        self.fig.canvas.draw_idle()

    def action_toggle_crosshair(self, event):
        self.cursor_widget.active = not self.cursor_widget.active
        etat = "activé" if self.cursor_widget.active else "désactivé"
        print(f"[VIEW] Reticule {etat}.")
        self.fig.canvas.draw_idle()

    def action_toggle_channels(self, event): 
        self.flag_all_channels = not self.flag_all_channels
        etat = "TOUS LES CANAUX de l'IF source" if self.flag_all_channels else "UNIQUEMENT LES CANAUX SÉLECTIONNÉS"
        print(f"[SCOPE] Portee du flagging modifiee : {etat}.")

    def action_toggle_marker_size(self, event):
        self.current_size_idx = (self.current_size_idx + 1) % len(self.marker_sizes)
        nouvelle_taille = self.marker_sizes[self.current_size_idx]
        self.update_marker_size(nouvelle_taille) 
        print(f"[VIEW] Taille des marqueurs : {nouvelle_taille}")
        self.fig.canvas.draw_idle()

    # --- Gestion de l'historique d'édition ---
    def action_undo(self, event):
        if not self.historique_coupes: 
            print("Aucune opération à annuler.")
            return
        derniers_morts = self.historique_coupes.pop()
        self.obs.unflag_data(derniers_morts)
        self.masque_flagges[derniers_morts] = False
        self._update_colors()
        print(f"Restauration de {len(derniers_morts)} visibilites.")

    def action_save(self, event):
        path_origine = getattr(self.obs, 'filepath', None)
        nom_affiche = path_origine.split('/')[-1] if path_origine else "le fichier actuel"

        print(f"\n[SAVE] Sauvegarde des visibilites (wobs).")
        prompt = (
            f"--- Fichier actuel : {nom_affiche} ---\n"
            f"1. Saisissez un NOUVEAU NOM de fichier (ex: data_clean.fits)\n"
            f"2. Tapez 'E' pour ÉCRASER le fichier actuel\n"
            f"3. Appuyez sur [Entrée] pour ANNULER la sauvegarde\n"
            f"Votre choix : "
        )
        
        reponse = input(prompt).strip()

        if not reponse:
            print("Sauvegarde annulee.")
            return

        if reponse.upper() == 'E':
            if not path_origine:
                print("Erreur : Chemin d'origine introuvable.")
                return
            nom_final = path_origine
            confirm = input(f"Voulez-vous vraiment ECRASER {nom_affiche} ? (o/N) : ").strip().lower()
            if confirm != 'o':
                print("Sauvegarde annulee.")
                return
        else:
            nom_final = reponse if reponse.lower().endswith(".fits") else reponse + ".fits"

        try:
            print(f"Ecriture en cours...")
            self.obs.save_wobs(nom_final)
            print(f"Succes ! Fichier enregistre sous : {nom_final}")
        except Exception as e:
            print(f"Echec de la sauvegarde : {e}")

    def action_quit(self, event):
        if self.historique_coupes:
            print("\nMODIFICATIONS NON SAUVEGARDÉES !")
            reponse = input("Voulez-vous enregistrer (Ctrl+S) avant de quitter ? (O/n/a) [O] : ").strip().lower()
            if reponse == 'a':
                print("Fermeture annulée. Retour à l'éditeur.")
                return 
            elif reponse == 'o' or reponse == '':
                self.action_save(event)
        else:
            confirm = input("\nQuitter la session interactive UVPlot ? (O/n) [O] : ").strip().lower()
            if confirm == 'n':
                return

        print("Fermeture et retour à l'invite.")
        plt.close(self.fig)

    # --- Navigation Télescopes ---
    def action_next_telescope(self, event):
        sub_id = self.liste_subarrays[self.index_subarray_actuel]
        nb_ant_dans_sub = len(self.antennes_par_subarray[sub_id])
        self.index_antenne_actuelle += 1
        if self.index_antenne_actuelle >= nb_ant_dans_sub:
            self.index_subarray_actuel = (self.index_subarray_actuel + 1) % len(self.liste_subarrays)
            self.index_antenne_actuelle = 0
        self._update_colors()

    def action_prev_telescope(self, event):
        self.index_antenne_actuelle -= 1
        if self.index_antenne_actuelle < 0:
            self.index_subarray_actuel = (self.index_subarray_actuel - 1) % len(self.liste_subarrays)
            sub_id = self.liste_subarrays[self.index_subarray_actuel]
            self.index_antenne_actuelle = len(self.antennes_par_subarray[sub_id]) - 1
        self._update_colors()

    def action_next_subarray(self, event):
        nom_actuel = ""
        if self.index_antenne_actuelle >= 0:
            sub_id_vieux = self.liste_subarrays[self.index_subarray_actuel]
            id_ant_vieux = self.antennes_par_subarray[sub_id_vieux][self.index_antenne_actuelle]
            nom_actuel = self.noms_antennes.get(id_ant_vieux, "")

        self.index_subarray_actuel = (self.index_subarray_actuel + 1) % len(self.liste_subarrays)
        sub_id_nouveau = self.liste_subarrays[self.index_subarray_actuel]

        self.index_antenne_actuelle = 0
        if nom_actuel:
            for idx, id_ant in enumerate(self.antennes_par_subarray[sub_id_nouveau]):
                if self.noms_antennes.get(id_ant) == nom_actuel:
                    self.index_antenne_actuelle = idx
                    break
        self._update_colors()

    def action_prev_subarray(self, event):
        nom_actuel = ""
        if self.index_antenne_actuelle >= 0:
            sub_id_vieux = self.liste_subarrays[self.index_subarray_actuel]
            id_ant_vieux = self.antennes_par_subarray[sub_id_vieux][self.index_antenne_actuelle]
            nom_actuel = self.noms_antennes.get(id_ant_vieux, "")

        self.index_subarray_actuel = (self.index_subarray_actuel - 1) % len(self.liste_subarrays)
        sub_id_nouveau = self.liste_subarrays[self.index_subarray_actuel]

        self.index_antenne_actuelle = 0
        if nom_actuel:
            for idx, id_ant in enumerate(self.antennes_par_subarray[sub_id_nouveau]):
                if self.noms_antennes.get(id_ant) == nom_actuel:
                    self.index_antenne_actuelle = idx
                    break
        self._update_colors()

    def action_specific_telescope(self, event):
        recherche = input("Nom cible (ex: BR, 1:BR, 1BR) : ").strip().upper()
        if not recherche:
            return

        target_sub, target_ant = None, recherche
        if ":" in recherche:
            parts = recherche.split(":", 1)
            target_sub, target_ant = parts[0], parts[1]
        elif recherche[0].isdigit():
            match = re.match(r"([0-9]+)([A-Z0-9]+)$", recherche)
            if match:
                target_sub, target_ant = match.group(1), match.group(2)

        found = False
        for s_idx, sub_id in enumerate(self.liste_subarrays):
            if target_sub is not None and str(sub_id) != target_sub:
                continue
            for a_idx, ant_id in enumerate(self.antennes_par_subarray[sub_id]):
                if target_ant in (self.noms_antennes.get(ant_id, "").upper(), str(ant_id)):
                    self.index_subarray_actuel = s_idx
                    self.index_antenne_actuelle = a_idx
                    found = True
                    break
            if found: break

        if found:
            sub_id = self.liste_subarrays[self.index_subarray_actuel]
            nom = self.noms_antennes.get(self.antennes_par_subarray[sub_id][self.index_antenne_actuelle])
            print(f"Focus sur {sub_id}:{nom}.")
            self._update_colors()
        else:
            print(f"Antenne introuvable : '{recherche}'.")

    def action_help(self, event):
        help_text = """
MANUEL DES RACCOURCIS - UVPLOT EDITOR

QUITTER ET AIDE
  X, Q      : Quitte la session interactive (retour à l'invite).
  H         : Affiche ce manuel d'aide.

GESTION DE L'AFFICHAGE ET DU ZOOM
  L         : Réaffiche (rafraîchit) le graphique.
  Z         : Mode ZOOM. 2 sommets (A/Clic-G), annuler (D). Ré-appuyer sur
              Z pour réinitialiser la vue à l'origine.

MISE EN ÉVIDENCE DES TÉLESCOPES (Highlighting)
  n / p     : Télescope Suivant / Précédent dans le sous-réseau.
  N / P     : Sous-réseau Suivant / Précédent.
  T         : Rechercher un télescope spécifique (ex: BR ou 1:BR).

INFORMATIONS SUR LES DONNÉES
  S         : Affiche les infos de la visibilité sous le curseur.

ÉDITION ET FLAGGING
  C         : Mode CUT (flagging). 2 sommets (A/Clic-G), annuler (D).
  W         : Bascule la portée du flagging (Tous canaux / Sélec.).
  U, Ctrl+Z : Annuler le dernier flagging (Undo).
  Ctrl+S    : Sauvegarder les données modifiées (wobs).

OPTIONS COSMÉTIQUES
  . (point) : Bascule la taille des marqueurs de visibilités.
  + (plus)  : Alterne l'affichage du réticule (crosshair).
  %         : Bascule l'affichage des points conjugués (-U, -V).
        """
        print(help_text)

    # =======================================================
    # MÉTHODES "VIRTUELLES"
    # =======================================================
    def apply_cut(self, x1, y1, x2, y2): pass
    def update_marker_size(self, size): pass
    def _update_colors(self): pass
    def action_show_info(self, event): pass