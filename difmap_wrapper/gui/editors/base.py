# difmap_wrapper/editors/base.py
import re
import logging
import numpy as np
from matplotlib.widgets import MultiCursor, RectangleSelector, SpanSelector
from PyQt6.QtCore import Qt

from difmap_wrapper.enums import EditorMode
from difmap_wrapper.gui.styles import DesignSystem

logger = logging.getLogger("difmap.editors")


class BasePlotEditor:
    """
    Éditeur de base universel pour les visibilités UV/Radplot.
    """

    def __init__(self, observation, fig, ax, data,
                 save_callback=None, sync_callback=None):
        """
        Parameters
        ----------
        observation : Observation
            Objet portant le masque de flagging et l'historique des coupes.
            Doit être une instance :class:`Observation`.
        fig : matplotlib.figure.Figure
            Figure Matplotlib partagée avec le widget.
        ax : matplotlib.axes.Axes
            Axe principal sur lequel les données sont tracées.
        data : dict
            Données UV brutes (clés ``'u'``, ``'v'``, ``'amp'``, ``'phase'``,
            ``'subarray'``, ``'tel_a'``, ``'tel_b'``, etc.).
        save_callback : callable, optional
            Fonction renvoyant le chemin de sauvegarde (ouvre un dialogue fichier).
        sync_callback : callable, optional
            Fonction appelée avec un ``dict`` d'état pour synchroniser l'UI.

        Raises
        ------
        TypeError
            Si ``observation`` n'est pas une instance :class:`Observation`.
        """
        from difmap_wrapper.core.observation import Observation
        if not isinstance(observation, Observation):
            raise TypeError(
                f"BasePlotEditor attend une instance Observation, reçu {type(observation).__name__}.\n"
                "Passez session.obs, pas session ou l'éditeur lui-même."
            )

        self.obs = observation
        self.fig = fig
        self.ax = ax
        self.data = data
        self.save_callback = save_callback
        self.sync_callback = sync_callback

        if self.obs.masque_flagges is None:
            self.obs.reset_flags(len(data["u"]))

        self.flag_all_channels = False

        def _header_station_names() -> list[str]:
            try:
                header_text = observation.header()
            except Exception:
                return []
            pattern = re.compile(
                r"^\s*\d+\s+([A-Za-z0-9_+\-]+)\s+[-+0-9.eE]+\s+[-+0-9.eE]+\s+[-+0-9.eE]+\s*$"
            )
            names = []
            for line in header_text.splitlines():
                match = pattern.match(line)
                if match:
                    names.append(match.group(1).strip())
            return names

        # Navigation antennes / sous-réseaux
        # Construire noms_antennes depuis le moteur C (TOUTES les antennes, y compris sans données)
        # get_telescope_name(isub, itel) retourne "INCONNU" quand itel >= sub->nstat → sentinel
        self.noms_antennes = {}
        
        # On ne demande au C que les antennes dont on est 100% sûr qu'elles
        # existent en RAM, en respectant leur sous-réseau (subarray) d'appartenance.
        if len(data["tel_a"]) > 0:
            for sub in np.unique(data["subarray"]):
                # data["subarray"] est 1-indexé dans les tableaux Python.
                c_isub = max(0, int(sub) - 1)

                # On isole les antennes de CE subarray spécifique
                mask = data["subarray"] == sub
                antennas = np.unique(np.concatenate([data["tel_a"][mask], data["tel_b"][mask]]))

                for itel in antennas:
                    c_itel = int(itel)
                    try:
                        name = observation._native.get_telescope_name(c_isub, c_itel)
                        if isinstance(name, str) and name and name != "INCONNU":
                            self.noms_antennes[c_itel] = name.strip()
                    except Exception:
                        pass
                
        # antennes_par_subarray : seuls les subarrays ayant des données, triés alphabétiquement
        self.antennes_par_subarray: dict = {}
        for sub in np.unique(data["subarray"]):
            masque = data["subarray"] == sub
            tel_ids = np.unique(np.concatenate([data["tel_a"][masque], data["tel_b"][masque]]))
            self.antennes_par_subarray[sub] = sorted(
                tel_ids.tolist(),
                key=lambda aid: str(self.noms_antennes.get(aid, aid))
            )

        # Liste globale du focus : noms de stations du fichier complet, y compris
        # celles absentes de la selection courante de visibilites.
        self.toutes_antennes_sorted = sorted(set(_header_station_names()) | set(self.noms_antennes.values()))

        # liste_subarrays : TOUS les subarrays (y compris vides) via obs.nsub()
        try:
            n_sub = observation.nsub()
            # Les subarrays difmap sont 1-indexés
            self.liste_subarrays = list(range(1, n_sub + 1))
        except Exception:
            self.liste_subarrays = list(self.antennes_par_subarray.keys())
        self.index_subarray_actuel = 0
        self.index_antenne_actuelle = -1
        # Nom de l'antenne courante — permet de retrouver la même antenne
        # dans un autre subarray (les index peuvent différer)
        self._nom_antenne_courante: str = ""

        # État souris / vue
        self.mode = None
        self.press_info = None
        self.pan_start = None
        self.original_limits = (self.ax.get_xlim(), self.ax.get_ylim())
        self.marker_size_pct = 5   # pourcentage courant (1–100)
        self._SIZE_MIN = 0.35  # pts² à 1 %
        self._SIZE_MAX = 26.0  # pts² à 100 %

        # Widgets Matplotlib
        self.rs = RectangleSelector(
            self.ax, self.on_select, useblit=True, button=[1],
            minspanx=5, minspany=5, spancoords="pixels", interactive=False,
        )
        self.rs.set_active(False)

        # RectangleSelector dédié au flagging interactif (gauche=flag, droit=unflag)
        self.rs_flag = RectangleSelector(
            self.ax, self._on_interactive_select, useblit=True, button=[1, 3],
            minspanx=5, minspany=5, spancoords="pixels", interactive=False,
        )
        self.rs_flag.set_active(False)

        self.span_x = SpanSelector(
            self.ax, self.on_span_select, 'horizontal', useblit=True,
            props=dict(alpha=0.2, facecolor=DesignSystem.PLOT_FOCUS)
        )
        self.span_x.set_active(False)

        self.axes_list = [self.ax]
        self.cursor = None
        self.cursor_active = False
        self.inspect_active = True   # True = clic gauche montre les infos de la visibilité

        self.raccourcis_autorises = {
            "r": self.action_home, "R": self.action_home,
            "x": self.action_quit, "X": self.action_quit,
            "q": self.action_quit, "Q": self.action_quit,
            "h": self.action_help, "H": self.action_help,
            "l": self.action_redisplay, "L": self.action_redisplay,
            "z": self.action_toggle_zoom, "Z": self.action_toggle_zoom,
            "g": self.action_toggle_pan, "G": self.action_toggle_pan,
            "m": self.action_toggle_pan, "M": self.action_toggle_pan,
            "c": self.action_toggle_cut, "C": self.action_toggle_cut,
            "d": self.action_cancel_cut, "D": self.action_cancel_cut,
            "f": self.action_toggle_interactive_flag, "F": self.action_toggle_interactive_flag,
            "a": self.action_flag_nearest, "A": self.action_flag_nearest,
            ".": self.action_toggle_marker_size,
            "+": self.action_toggle_crosshair,
            "o": self.action_dezoom, "O": self.action_dezoom,
            "u": self.action_undo, "ctrl+z": self.action_undo,
            "s": self.action_toggle_inspect,
            "S": self.action_toggle_stats,
            "v": self.action_toggle_stats_vec, "V": self.action_toggle_stats_vec,
            "ctrl+s": self.action_save,
            "n": self.action_next_telescope, "p": self.action_prev_telescope,
            "N": self.action_next_subarray, "P": self.action_prev_subarray,
            "t": self.action_specific_telescope, "T": self.action_specific_telescope,
        }

        self._cids = [
            self.fig.canvas.mpl_connect("key_press_event",      self.on_key_press),
            self.fig.canvas.mpl_connect("button_press_event",   self.on_mouse_press),
            self.fig.canvas.mpl_connect("button_release_event", self.on_mouse_release),
            self.fig.canvas.mpl_connect("motion_notify_event",  self.on_mouse_motion),
            self.fig.canvas.mpl_connect("figure_leave_event",   self._on_figure_leave),
            self.fig.canvas.mpl_connect("figure_enter_event",   self._on_figure_enter),
        ]

        self.obs.register_editor(self)

    @property
    def masque_flagges(self) -> np.ndarray:
        """
        Masque booléen des visibilités flaggées, délégué à :attr:`Observation.masque_flagges`.

        Returns
        -------
        numpy.ndarray
            Tableau booléen de longueur N (True = flaggé).
        """
        return self.obs.masque_flagges

    @masque_flagges.setter
    def masque_flagges(self, value: np.ndarray) -> None:
        """
        Parameters
        ----------
        value : numpy.ndarray
            Nouveau masque booléen à assigner à l'Observation.
        """
        self.obs.masque_flagges = value

    @property
    def historique_coupes(self) -> list:
        """
        Historique des indices flaggés (liste de tableaux), délégué à l'Observation.

        Returns
        -------
        list of numpy.ndarray
            Chaque entrée contient les indices d'une opération de flagging.
        """
        return self.obs.historique_coupes

    @historique_coupes.setter
    def historique_coupes(self, value: list) -> None:
        """
        Parameters
        ----------
        value : list
            Nouvel historique à assigner à l'Observation.
        """
        self.obs.historique_coupes = value

    def cleanup(self) -> None:
        """
        Déconnecte tous les écouteurs d'événements Matplotlib et se désenregistre
        de l'Observation (Observer pattern).

        À appeler avant de recréer l'éditeur sur la même figure (reload_data).
        """
        for cid in self._cids:
            try:
                self.fig.canvas.mpl_disconnect(cid)
            except Exception:
                pass
        self._cids.clear()
        self._disconnect_crosshair()
        self.obs.unregister_editor(self)

    def refresh_data(self) -> None:
        """
        Appelé par Observation.notify_data_changed() quand les données C changent.

        Re-télécharge les données, invalide le cache des noms et redessine.
        Les sous-classes (RadPlotEditor) surchargent cette méthode pour
        mettre à jour leurs tableaux intermédiaires (uv_radius, amp, phase…).
        """
        self.data = self.obs.get_data()
        self._refresh_telescope_names()
        self._update_colors()

    def _refresh_telescope_names(self) -> None:
        """
        Recharge le cache des noms de télescopes depuis le moteur C.

        Scanne toutes les stations du subarray 0 jusqu'au sentinel "INCONNU"
        pour inclure même les antennes sans visibilités dans le jeu de données.
        Construit ``self.noms_antennes`` (dict ``id → nom``).
        """
        
    def _build_focus_colors(self) -> tuple[np.ndarray, object]:
        """
        Construit le tableau de couleurs selon le focus antenne actuel.

        Utilisé par UVPlotEditor._update_colors() et RadPlotEditor._update_colors().

        Returns
        -------
        couleurs : np.ndarray of object
            Tableau de couleurs par visibilité.
        sub_actif : int
            ID du sous-réseau actif.
        """
        couleurs = np.full(len(self.data["u"]), self.base_color, dtype=object)
        sub_actif = self.liste_subarrays[self.index_subarray_actuel]

        if self.index_antenne_actuelle >= 0 and self.index_antenne_actuelle < len(self.toutes_antennes_sorted):
            nom_cible = self.toutes_antennes_sorted[self.index_antenne_actuelle]
            ant_cible = self._find_local_antenna_id(sub_actif, nom_cible)
            if ant_cible is not None:
                m = (
                    (self.data["subarray"] == sub_actif)
                    & ((self.data["tel_a"] == ant_cible) | (self.data["tel_b"] == ant_cible))
                )
                couleurs[m] = DesignSystem.PLOT_FOCUS

        return couleurs, sub_actif

    def _find_local_antenna_id(self, sub_id: int, antenna_name: str) -> int | None:
        """Retourne l'ID local de l'antenne dans ``sub_id`` a partir de son nom."""
        target = antenna_name.upper()
        for ant_id in self.antennes_par_subarray.get(sub_id, []):
            if self.noms_antennes.get(ant_id, "").upper() == target:
                return ant_id
        return None

    # =========================================================
    # LOGIQUE SOURIS
    # =========================================================

    def on_mouse_press(self, event):
        """
        Enregistre la position du clic et initialise le pan si le mode PAN est actif.

        Parameters
        ----------
        event : matplotlib.backend_bases.MouseEvent
            Événement souris Matplotlib.
        """
        if event.button != 1 or event.inaxes is None:
            return
        if event.inaxes not in self.axes_list:
            return
        self.press_info = (event.x, event.y)
        if hasattr(self, '_last_pressed_axis'):
            self._last_pressed_axis = event.inaxes
        if self.mode == EditorMode.PAN:
            self.pan_start = (event.x, event.y, self.ax.get_xlim(), self.ax.get_ylim())

    def on_mouse_motion(self, event):
        """
        Déplace la vue en mode PAN en suivant le mouvement de la souris.

        Parameters
        ----------
        event : matplotlib.backend_bases.MouseEvent
            Événement de déplacement souris.
        """
        if self.mode == EditorMode.PAN and self.pan_start is not None and event.x is not None:
            px_start, py_start, xlim0, ylim0 = self.pan_start
            dx_pix = event.x - px_start
            dy_pix = event.y - py_start
            width, height = self.ax.bbox.width, self.ax.bbox.height
            ux = (xlim0[1] - xlim0[0]) / width
            uy = (ylim0[1] - ylim0[0]) / height
            self.ax.set_xlim(xlim0[0] - dx_pix * ux, xlim0[1] - dx_pix * ux)
            self.ax.set_ylim(ylim0[0] - dy_pix * uy, ylim0[1] - dy_pix * uy)
            self.fig.canvas.draw_idle()

    def on_mouse_release(self, event):
        """
        Déclenche une inspection au clic si le déplacement est inférieur à 5 px.

        Parameters
        ----------
        event : matplotlib.backend_bases.MouseEvent
            Événement de relâchement souris.
        """
        self.pan_start = None
        if not self.press_info or event.button != 1:
            return
        dist = np.sqrt((event.x - self.press_info[0])**2 + (event.y - self.press_info[1])**2)
        if dist < 5.0 and event.xdata is not None and self.inspect_active:
            self.action_show_info(event)
        self.press_info = None

    def on_select(self, eclick, erelease):
        """
        Callback du ``RectangleSelector`` principal : dispatch selon le mode actif.

        Déclenche zoom, cut, stats scalaires ou stats vectorielles selon
        :attr:`mode` 

        Parameters
        ----------
        eclick : matplotlib.backend_bases.MouseEvent
            Événement au début de la sélection.
        erelease : matplotlib.backend_bases.MouseEvent
            Événement à la fin de la sélection.
        """
        # M2 : EditorMode.ALL_RECT remplace la liste de strings en dur
        if self.mode not in EditorMode.ALL_RECT:
            return
        if abs(erelease.x - eclick.x) < 10 and abs(erelease.y - eclick.y) < 10:
            return
        u1, v1 = eclick.xdata, eclick.ydata
        u2, v2 = erelease.xdata, erelease.ydata

        if self.mode == EditorMode.ZOOM:
            # Préserver l'orientation des axes (ex: axe X inversé dans UV plot)
            x_inv = self.ax.get_xlim()[0] > self.ax.get_xlim()[1]
            y_inv = self.ax.get_ylim()[0] > self.ax.get_ylim()[1]
            xlo, xhi = min(u1, u2), max(u1, u2)
            ylo, yhi = min(v1, v2), max(v1, v2)
            self.ax.set_xlim(xhi if x_inv else xlo, xlo if x_inv else xhi)
            self.ax.set_ylim(yhi if y_inv else ylo, ylo if y_inv else yhi)
            self.fig.canvas.draw_idle()
            logger.info("Zoom appliqué.")
        elif self.mode == EditorMode.CUT:
            self.apply_cut(u1, v1, u2, v2)
        elif self.mode == EditorMode.STATS:
            self.apply_stats(u1, v1, u2, v2)
        elif self.mode == EditorMode.STATS_V:
            self.apply_stats_vec(u1, v1, u2, v2)

    def _on_interactive_select(self, eclick, erelease):
        """
        Callback pour le flagging interactif (nouveau RectangleSelector rs_flag).
        
        Détecte le bouton de la souris :
        - Bouton 1 (clic gauche) : FLAG les points
        - Bouton 3 (clic droit) : UNFLAG les points
        
        Les sous-classes (UVPlotEditor, RadPlotEditor) surchargent cette méthode
        pour adapter la logique d'extraction des indices au type de graphique.
        """
        if abs(erelease.x - eclick.x) < 10 and abs(erelease.y - eclick.y) < 10:
            return
        
        is_flag = eclick.button == 1  # Gauche = True (flag), Droit = False (unflag)
        u1, v1 = eclick.xdata, eclick.ydata
        u2, v2 = erelease.xdata, erelease.ydata
        
        self._apply_interactive_flag(u1, v1, u2, v2, is_flag=is_flag)

    def on_key_press(self, event):
        """
        Gère les événements clavier avec normalisation des touches Shift.

        Normalise ``'shift+a'`` → ``'A'`` et ``'shift+='`` → ``'+'``,
        puis dispatch vers le raccourci correspondant dans ``raccourcis_autorises``.

        Parameters
        ----------
        event : matplotlib.backend_bases.KeyEvent
            Événement clavier Matplotlib.
        """
        key = event.key
        original_key = key
        
        if not key:
            return

        # Normalise les raccourcis de touche pour Qt/Matplotlib
        if key in ("period", "decimal"):
            key = "."
        elif key == "shift+period":
            key = ">"
        elif key.startswith('shift+'):
            base_key = key[6:]  # Enlève 'shift+'
            if base_key == '=':  # Particularité : Shift+= = +
                key = '+'
            elif len(base_key) == 1:  # Caractère simple comme 'a'
                key = base_key.upper()  # 'a' -> 'A'

        gui_event = getattr(event, 'guiEvent', None)
        if gui_event is not None:
            try:
                text = gui_event.text()
                if text:
                    key = text
                else:
                    modifiers = gui_event.modifiers()
                    if modifiers & Qt.KeyboardModifier.ShiftModifier:
                        if isinstance(key, str) and len(key) == 1 and key.isalpha():
                            key = key.upper()
                        elif key == '=':
                            key = '+'
                        elif key == '.':
                            key = '>'
            except Exception:
                pass

        # Cherche le raccourci dans le dictionnaire (exact d'abord, puis minuscule)
        if key in self.raccourcis_autorises:
            logger.debug(f"Raccourci clavier '{original_key}' → '{key}' trouvé")
            self.raccourcis_autorises[key](event)
        elif key.lower() in self.raccourcis_autorises:
            # Fallback: si pas trouvé exactement, cherche la minuscule
            logger.debug(f"Raccourci clavier '{original_key}' → '{key.lower()}' (fallback)")
            self.raccourcis_autorises[key.lower()](event)
        else:
            logger.debug(f"Raccourci clavier '{original_key}' non reconnu")

    def on_span_select(self, vmin, vmax):
        """
        Callback du ``SpanSelector`` : zoom horizontal sur l'axe X.

        Parameters
        ----------
        vmin : float
            Borne inférieure de la sélection en coordonnées de données.
        vmax : float
            Borne supérieure de la sélection en coordonnées de données.
        """
        if self.mode == EditorMode.ZOOM_X:
            self.ax.set_xlim(vmin, vmax)
            if hasattr(self, 'ax_phase') and self.ax_phase:
                self.ax_phase.set_xlim(vmin, vmax)
            self.fig.canvas.draw_idle()

    # =========================================================
    # GESTION DES MODES
    # =========================================================

    def _set_mode(self, new_mode) -> None:
        """Définit le mode et gère l'activation des widgets Matplotlib."""
        self.mode = new_mode
        if new_mode is not None:
            self.inspect_active = False
        if hasattr(self, 'rs'):
            self.rs.set_active(False)
        if hasattr(self, 'rs_flag'):
            self.rs_flag.set_active(False)
        if hasattr(self, 'span_x'):
            self.span_x.set_active(False)

        if self.mode in EditorMode.ALL_RECT:
            self.rs.set_active(True)
        elif self.mode == EditorMode.INTERACTIVE_FLAG:
            self.rs_flag.set_active(True)
        elif self.mode == EditorMode.ZOOM_X:
            self.span_x.set_active(True)

        etat = self.mode if self.mode else "Inspection"
        logger.info("Mode : %s", etat)
        self.fig.canvas.draw_idle()
        if self.sync_callback:
            tool_state = self.mode if self.mode else ("INSPECT" if self.inspect_active else None)
            state = {'inspect_active': self.inspect_active}
            if tool_state is not None:
                state['active_tool'] = tool_state
            self.sync_callback(state)

    def action_toggle_zoom(self, _event=None):
        """Active le mode ZOOM (sélection rectangulaire pour zoomer). Touche ``Z``."""
        self._set_mode(EditorMode.ZOOM)

    def action_toggle_cut(self, _event=None):
        """Active le mode CUT (sélection rectangulaire pour flagguer). Touche ``C``."""
        self._set_mode(EditorMode.CUT)

    def action_toggle_interactive_flag(self, _event=None):
        """
        Bascule le mode flagging interactif à la souris. Touche ``F``.

        - Clic gauche : flagge les points dans la boîte.
        - Clic droit : dé-flagge les points dans la boîte.
        """
        if self.mode == EditorMode.INTERACTIVE_FLAG:
            self._set_mode(None)  # Désactiver
        else:
            self._set_mode(EditorMode.INTERACTIVE_FLAG)  # Activer

    def action_toggle_pan(self, _event=None):
        """Active le mode PAN (déplacement de la vue). Touche ``M``."""
        self._set_mode(EditorMode.PAN)

    def action_toggle_stats(self, _event=None):
        """Active le mode STATS scalaires (sélection rectangulaire). Touche ``S``."""
        self._set_mode(EditorMode.STATS)

    def action_toggle_zoom_x(self, _event=None):
        """Active le mode ZOOM_X (sélection horizontale de rayon UV). Touche ``U``."""
        self._set_mode(EditorMode.ZOOM_X)

    def action_toggle_stats_vec(self, _event=None):
        """Active le mode STATS vectorielles (Re/Im). Touche ``V``."""
        self._set_mode(EditorMode.STATS_V)

    def action_cancel_cut(self, _event=None):
        """Annule le mode de sélection actif et désactive tous les selectors. Touche ``D``."""
        if self.mode in EditorMode.ALL_RECT or self.mode == EditorMode.ZOOM or self.mode == EditorMode.INTERACTIVE_FLAG:
            self.mode = None
            if hasattr(self, 'rs'):
                self.rs.set_active(False)
            if hasattr(self, 'rs_flag'):
                self.rs_flag.set_active(False)
            if hasattr(self, 'span_x'):
                self.span_x.set_active(False)
            logger.info("Selection cancelled.")

    def action_home(self, event=None):
        """
        Réinitialise la vue aux limites d'origine et supprime le focus antenne. Touche ``R``.

        Émet ``reset_all`` via ``sync_callback`` pour réinitialiser tous les graphiques.

        Parameters
        ----------
        event : matplotlib.backend_bases.KeyEvent, optional
            Événement clavier (ignoré).
        """
        if self.original_limits:
            self.ax.set_xlim(self.original_limits[0])
            self.ax.set_ylim(self.original_limits[1])
            self.index_antenne_actuelle = -1
            self._nom_antenne_courante = ""
            self._update_colors()
            self.fig.canvas.draw_idle()
            logger.info("Vue réinitialisée.", extra={'difmap_level': 'success'})
        if self.sync_callback:
            self.sync_callback({'reset_all': True})

    def action_redisplay(self, event=None):
        """Force un rafraîchissement du canvas. Touche ``L``."""
        self.fig.canvas.draw_idle()

    def action_dezoom(self, event=None):
        """Dézoom de 50 % — élargit la vue courante. Touche ``O``."""
        xl, xr = self.ax.get_xlim()
        yl, yr = self.ax.get_ylim()
        cx, cy = (xl + xr) / 2, (yl + yr) / 2
        dx, dy = (xr - xl) * 0.75, (yr - yl) * 0.75
        self.ax.set_xlim(cx - dx, cx + dx)
        self.ax.set_ylim(cy - dy, cy + dy)
        self.fig.canvas.draw_idle()
        logger.info("Dézoom appliqué.")

    def action_toggle_zoom_y(self, _event=None):
        """Active le mode ZOOM_Y (sélection verticale sur axe Y). Surchargé par RadPlotEditor."""
        pass

    def action_toggle_inspect(self, event=None):
        """Bascule le mode Inspect (clic gauche affiche les infos de la visibilité). Touche ``s``."""
        self.inspect_active = not self.inspect_active
        self._set_mode(None)
        status = "ON" if self.inspect_active else "OFF"
        logger.info("Inspect mode : %s", status)

    def _on_figure_leave(self, event=None):
        """Cache les lignes du crosshair quand la souris quitte la figure."""
        if not self.cursor_active or self.cursor is None:
            return
        for line in getattr(self.cursor, 'vlines', []):
            line.set_visible(False)
        for line in getattr(self.cursor, 'hlines', []):
            line.set_visible(False)
        self.cursor.set_active(False)
        self.fig.canvas.draw()

    def _on_figure_enter(self, event=None):
        """Réaffiche les lignes du crosshair quand la souris entre dans la figure."""
        if not self.cursor_active or self.cursor is None:
            return
        for line in getattr(self.cursor, 'vlines', []):
            line.set_visible(True)
        for line in getattr(self.cursor, 'hlines', []):
            line.set_visible(True)
        self.cursor.set_active(True)

    def _disconnect_crosshair(self) -> None:
        """Déconnecte et masque entièrement le crosshair courant, s'il existe."""
        if not self.cursor:
            self.cursor_active = False
            return
        try:
            if hasattr(self.cursor, 'vlines'):
                for line in self.cursor.vlines:
                    line.set_visible(False)
                    try:
                        line.remove()
                    except Exception:
                        pass
            if hasattr(self.cursor, 'hlines'):
                for line in self.cursor.hlines:
                    line.set_visible(False)
                    try:
                        line.remove()
                    except Exception:
                        pass
            if hasattr(self.cursor, 'set_active'):
                self.cursor.set_active(False)
            if hasattr(self.cursor, 'disconnect_events'):
                self.cursor.disconnect_events()
            elif hasattr(self.cursor, 'disconnect'):
                self.cursor.disconnect()
        except Exception:
            pass
        self.cursor = None
        self.cursor_active = False

    def set_crosshair_visible(self, visible: bool):
        """
        Définit explicitement l'état du crosshair sans toggle aveugle.

        Cela évite les doublons de MultiCursor quand plusieurs contrôles UI
        essaient de synchroniser le même état.
        """
        visible = bool(visible)
        if visible == self.cursor_active and (visible or self.cursor is None):
            return

        _xlim = self.ax.get_xlim()
        _ylim = self.ax.get_ylim()

        self._disconnect_crosshair()
        if visible:
            self.cursor = MultiCursor(
                self.fig.canvas, self.axes_list,
                color=DesignSystem.PLOT_FOCUS, lw=0.8,
                horizOn=True, vertOn=True
            )
            self.cursor_active = True

        self.fig.canvas.draw_idle()
        self.ax.set_xlim(_xlim)
        self.ax.set_ylim(_ylim)
        if self.sync_callback:
            self.sync_callback({'crosshair': self.cursor_active})

    def action_toggle_crosshair(self, event=None):
        """
        Active ou désactive le crosshair plein écran (``MultiCursor``). Touche ``+``.

        Crée un :class:`MultiCursor` sur tous les axes si activation,
        le déconnecte proprement si désactivation. Notifie l'UI via ``sync_callback``.

        Parameters
        ----------
        event : matplotlib.backend_bases.KeyEvent, optional
            Événement clavier (ignoré).
        """
        self.set_crosshair_visible(not self.cursor_active)
        status = "Activé" if self.cursor_active else "Désactivé"
        logger.info("Cross-hair : %s", status)

    def action_toggle_channels(self, event=None):
        """
        Bascule entre le flagging d'un seul canal et de tous les canaux IF. Touche ``W``.

        Parameters
        ----------
        event : matplotlib.backend_bases.KeyEvent, optional
            Événement clavier (ignoré).
        """
        self.flag_all_channels = not self.flag_all_channels
        etat = "TOUS LES CANAUX" if self.flag_all_channels else "CANAUX SÉLECTIONNÉS"
        logger.warning("Portée du flagging : %s", etat)
        if self.sync_callback:
            self.sync_callback({'flag_all_channels': self.flag_all_channels})

    def action_toggle_marker_size(self, event=None):
        """
        Augmente la taille de marqueur de 10 % (boucle 100 % → 10 %). Touche ``.``.

        Parameters
        ----------
        event : matplotlib.backend_bases.KeyEvent, optional
            Événement clavier (ignoré).
        """
        next_pct = (self.marker_size_pct % 100) + 10
        self.update_marker_size(next_pct)
        if self.sync_callback:
            self.sync_callback({'marker_size': next_pct})

    def set_conjugate_visible(self, visible: bool):
        """
        Affiche ou masque les points conjugués (no-op dans la classe de base).

        Surchargé par :class:`UVPlotEditor`.

        Parameters
        ----------
        visible : bool
            ``True`` pour afficher les points conjugués.
        """
        logger.info(f"Conjugate toggle: {visible} (no-op for this plot)")

    def set_flag_all_channels(self, flag: bool):
        """
        Définit la portée du flagging (un canal ou tous les canaux IF).

        Parameters
        ----------
        flag : bool
            ``True`` pour flagguer tous les canaux, ``False`` pour le canal sélectionné.
        """
        self.flag_all_channels = flag
        etat = "TOUS LES CANAUX" if flag else "CANAUX SÉLECTIONNÉS"
        logger.warning("Portée du flagging : %s", etat)

    def set_model_visible(self, visible: bool):
        """
        Active ou masque le modèle mathématique (no-op dans la classe de base).

        Surchargé par :class:`RadPlotEditor`.

        Parameters
        ----------
        visible : bool
            ``True`` pour afficher la superposition du modèle.
        """
        logger.info(f"Model visibility: {visible} (no-op for this plot)")

    def set_residuals_visible(self, visible: bool):
        """
        Active ou masque l'affichage des résidus (no-op dans la classe de base).

        Surchargé par :class:`RadPlotEditor`.

        Parameters
        ----------
        visible : bool
            ``True`` pour afficher les résidus (Data − Model).
        """
        logger.info(f"Residuals visibility: {visible} (no-op for this plot)")

    def set_show_errors(self, visible: bool):
        """
        Active ou masque le sous-graphique d'erreurs 1/√w (no-op dans la classe de base).

        Surchargé par :class:`RadPlotEditor`.

        Parameters
        ----------
        visible : bool
            ``True`` pour afficher le panneau d'erreurs théoriques.
        """
        logger.info(f"Errors visibility: {visible} (no-op for this plot)")

    def action_undo(self, event=None):
        """
        Annule la dernière opération de flagging. Touche ``U`` ou ``Ctrl+Z``.

        Dépile le dernier tableau d'indices depuis ``historique_coupes``,
        appelle ``obs.unflag_data()`` et met à jour les couleurs.

        Parameters
        ----------
        event : matplotlib.backend_bases.KeyEvent, optional
            Événement clavier (ignoré).
        """
        if not self.obs.historique_coupes:
            logger.warning("Aucune opération à annuler.")
            return
        derniers_morts = self.obs.historique_coupes.pop()
        self.obs.unflag_data(derniers_morts)
        self.obs.masque_flagges[derniers_morts] = False
        self._update_colors()
        logger.info("Restauration de %d visibilités.", len(derniers_morts),
                    extra={'difmap_level': 'success'})
        if self.sync_callback:
            self.sync_callback()

    def action_save(self, event=None):
        """
        Ouvre le dialogue de sauvegarde (save / wobs). ``Ctrl+S``.

        Si ``full_save_callback`` est défini il est appelé directement (délègue au
        dialogue de la MainWindow). Sinon, repli sur l'ancien comportement wobs.
        """
        if callable(getattr(self, 'full_save_callback', None)):
            self.full_save_callback()
            return
        path_origine = getattr(self.obs, 'filepath', "data.fits")
        if self.save_callback:
            nom_final = self.save_callback(path_origine)
            if not nom_final:
                return
        else:
            logger.error("Sauvegarde annulée : Dialog non connecté.")
            return
        try:
            self.obs.save_wobs(nom_final)
            logger.info("Fichier enregistré : %s", nom_final,
                        extra={'difmap_level': 'success'})
        except Exception as e:
            logger.error("Échec sauvegarde : %s", e)

    def action_quit(self, event=None):
        """
        Ferme la figure Matplotlib. Touches ``X``, ``Q``.

        Parameters
        ----------
        event : matplotlib.backend_bases.KeyEvent, optional
            Événement clavier (ignoré).
        """
        import matplotlib.pyplot as plt
        plt.close(self.fig)

    # =========================================================
    # NAVIGATION TÉLESCOPES
    # =========================================================

    def action_next_telescope(self, event=None):
        """
        Passe à l'antenne suivante dans la liste globale triée alphabétiquement. Touche ``n``.

        Boucle sur TOUTES les antennes connues (pas seulement celles avec des visibilités
        dans le subarray courant). Affiche "[pas de visibilités]" si l'antenne est absente
        du subarray. Sur le premier appui après reset, démarre sur la première antenne.

        Parameters
        ----------
        event : optional
            Ignoré.
        """
        n = len(self.toutes_antennes_sorted)
        if n == 0:
            logger.info("Aucune antenne disponible.")
            return
        if self.index_antenne_actuelle < 0 or not self._nom_antenne_courante:
            self.index_antenne_actuelle = 0
        else:
            self.index_antenne_actuelle = (self.index_antenne_actuelle + 1) % n
        self._nom_antenne_courante = self.toutes_antennes_sorted[self.index_antenne_actuelle]
        self._update_colors()

    def action_prev_telescope(self, event=None):
        """
        Revient à l'antenne précédente dans la liste globale triée alphabétiquement. Touche ``p``.

        Boucle sur TOUTES les antennes connues (pas seulement celles avec des visibilités
        dans le subarray courant). Affiche "[pas de visibilités]" si l'antenne est absente
        du subarray. Sur le premier appui après reset, démarre sur la première antenne.

        Parameters
        ----------
        event : optional
            Ignoré.
        """
        n = len(self.toutes_antennes_sorted)
        if n == 0:
            logger.info("Aucune antenne disponible.")
            return
        if self.index_antenne_actuelle < 0 or not self._nom_antenne_courante:
            self.index_antenne_actuelle = 0
        else:
            self.index_antenne_actuelle = (self.index_antenne_actuelle - 1) % n
        self._nom_antenne_courante = self.toutes_antennes_sorted[self.index_antenne_actuelle]
        self._update_colors()

    def action_next_subarray(self, event=None):
        """
        Passe au sous-réseau suivant en gardant le même NOM d'antenne. Touche ``N``.

        Règle : on incrémente le numéro de sous-réseau sur TOUS les sous-réseaux
        (y compris ceux sans visibilités).  Le nom de l'antenne est conservé et
        recherché dans le nouveau sous-réseau ; un log indique si le sous-réseau
        est vide ou si l'antenne est absente.
        Si on est déjà au dernier subarray, on boucle sur le subarray 1 et on
        passe à l'antenne suivante dans le subarray 1.

        Parameters
        ----------
        event : optional
            Ignoré.
        """
        if not self._nom_antenne_courante:
            self.index_subarray_actuel = 0
            self._sync_antenna_after_subarray_change()
        elif self.index_subarray_actuel < len(self.liste_subarrays) - 1:
            self.index_subarray_actuel += 1
            self._sync_antenna_after_subarray_change()
        else:
            # Dernier subarray atteint : revenir au subarray 1 et avancer l'antenne globalement.
            n = len(self.toutes_antennes_sorted)
            if n > 0:
                if self.index_antenne_actuelle < 0:
                    self.index_antenne_actuelle = 0
                else:
                    self.index_antenne_actuelle = (self.index_antenne_actuelle + 1) % n
                self._nom_antenne_courante = self.toutes_antennes_sorted[self.index_antenne_actuelle]
            self.index_subarray_actuel = 0
            self._sync_antenna_after_subarray_change()
        self._update_colors()

    def action_prev_subarray(self, event=None):
        """
        Revient au sous-réseau précédent en gardant le même NOM d'antenne. Touche ``P``.

        Règle : on décrémente le numéro de sous-réseau sur TOUS les sous-réseaux
        (y compris ceux sans visibilités).  Le nom de l'antenne est conservé et
        recherché dans le nouveau sous-réseau ; un log indique si le sous-réseau
        est vide ou si l'antenne est absente.
        Si on est déjà au premier subarray, on boucle sur le dernier subarray et on
        recule l'antenne dans le subarray 1.

        Parameters
        ----------
        event : optional
            Ignoré.
        """
        if not self._nom_antenne_courante:
            self.index_subarray_actuel = 0
            self._sync_antenna_after_subarray_change()
        elif self.index_subarray_actuel > 0:
            self.index_subarray_actuel -= 1
            self._sync_antenna_after_subarray_change()
        else:
            # Premier subarray atteint : aller au dernier et reculer l'antenne globalement.
            n = len(self.toutes_antennes_sorted)
            if n > 0:
                if self.index_antenne_actuelle < 0:
                    self.index_antenne_actuelle = 0
                else:
                    self.index_antenne_actuelle = (self.index_antenne_actuelle - 1) % n
                self._nom_antenne_courante = self.toutes_antennes_sorted[self.index_antenne_actuelle]
            self.index_subarray_actuel = len(self.liste_subarrays) - 1
            self._sync_antenna_after_subarray_change()
        self._update_colors()

    def _sync_antenna_after_subarray_change(self) -> None:
        """
        Après un changement de sous-réseau, retrouve l'antenne courante par son NOM
        dans toutes_antennes_sorted. L'index reste valide même si l'antenne n'a pas de
        visibilités dans le nouveau sous-réseau (affichage "[pas de visibilités]").
        """
        new_sub = self.liste_subarrays[self.index_subarray_actuel]
        ants_in_sub = self.antennes_par_subarray.get(new_sub, [])

        if self._nom_antenne_courante:
            nom_up = self._nom_antenne_courante.upper()
            for a_idx, ant_name in enumerate(self.toutes_antennes_sorted):
                if ant_name.upper() == nom_up:
                    self.index_antenne_actuelle = a_idx
                    ant_id = self._find_local_antenna_id(new_sub, self._nom_antenne_courante)
                    if not ants_in_sub:
                        logger.info("Subarray %s : aucune visibilité.", new_sub)
                    elif ant_id is not None:
                        logger.info("Subarray %s : focus sur %s.", new_sub, self._nom_antenne_courante)
                    else:
                        logger.info(
                            "Subarray %s : antenne '%s' absente — pas de visibilités.",
                            new_sub, self._nom_antenne_courante,
                        )
                    return
            logger.warning("Antenne '%s' introuvable dans la liste globale.", self._nom_antenne_courante)
            return

        if not ants_in_sub:
            logger.info("Subarray %s : aucune visibilité.", new_sub)
            return

        if self.toutes_antennes_sorted:
            self.index_antenne_actuelle = 0
            self._nom_antenne_courante = self.toutes_antennes_sorted[0]
            logger.info("Subarray %s : focus automatique sur %s.", new_sub, self._nom_antenne_courante)

    def _find_antenna_index(self, sub_id, name_upper: str) -> int:
        """Retourne l'index dans toutes_antennes_sorted de l'antenne par nom dans sub_id, ou 0."""
        if name_upper:
            for idx, ant_name in enumerate(self.toutes_antennes_sorted):
                if ant_name.upper() == name_upper:
                    return idx
        return 0

    def _find_antenna_index_by_name(self, sub_id, nom: str) -> int:
        """Retourne l'index dans toutes_antennes_sorted de l'antenne par nom dans sub_id, ou -1."""
        nom_up = nom.upper()
        for idx, ant_name in enumerate(self.toutes_antennes_sorted):
            if ant_name.upper() == nom_up:
                return idx
        return -1

    def action_specific_telescope(self, event=None, target_name=None):
        """
        Focalise le graphique sur un télescope identifié par son nom ou son ID. Touche ``T``.

        Accepte les formats ``"BR"``, ``"1:BR"``, ``"1BR"``.
        Si appelé sans ``target_name``, déclenche l'ouverture du champ de recherche via
        ``sync_callback``.

        Parameters
        ----------
        event : optional
            Événement clavier (peut être ``None``).
        target_name : str, optional
            Nom ou identifiant du télescope cible (ex. ``"BR"``, ``"1:BR"``).
        """
        if event is not None and target_name is None:
            if self.sync_callback:
                self.sync_callback({'focus_search': True})
            return

        recherche = str(target_name).strip().upper() if target_name else ""
        if not recherche:
            return

        if recherche in {"ALL", "NONE", "RESET", "RESET VIEW", "CLEAR", "NO HIGHLIGHT"}:
            self.index_antenne_actuelle = -1
            self._nom_antenne_courante = ""
            if self.sync_callback:
                self.sync_callback({'inspect_active': self.inspect_active})
            self._update_colors()
            logger.info("Telescope focus cleared.")
            return

        sub_target = None
        if ":" in recherche:
            parts = recherche.split(":")
            sub_target, recherche = parts[0], parts[1]
        elif len(recherche) > 1 and recherche[0].isdigit() and recherche[1].isalpha():
            m = re.match(r"^(\d+)([A-Z0-9]+)$", recherche)
            if m:
                sub_target, recherche = m.group(1), m.group(2)

        found = False
        for s_idx, sub_id in enumerate(self.liste_subarrays):
            if sub_target and str(sub_id) != sub_target:
                continue
            for ant_id in self.antennes_par_subarray.get(sub_id, []):
                nom_ant = self.noms_antennes.get(ant_id, "").upper()
                if recherche == nom_ant or recherche == str(ant_id) or recherche in nom_ant:
                    self.index_subarray_actuel = s_idx
                    self.index_antenne_actuelle = self._find_antenna_index(sub_id, nom_ant)
                    self._nom_antenne_courante = self.noms_antennes.get(ant_id, "")
                    found = True
                    break
            if found:
                break

        if not found:
            idx = self._find_antenna_index_by_name(self.liste_subarrays[0], recherche)
            if idx >= 0:
                self.index_antenne_actuelle = idx
                self._nom_antenne_courante = self.toutes_antennes_sorted[idx]
                found = True

        if found:
            sub_id = self.liste_subarrays[self.index_subarray_actuel]
            logger.info("Focus sur %s:%s.", sub_id, self._nom_antenne_courante)
            self._update_colors()
        else:
            logger.warning("Télescope '%s' introuvable.", target_name)

    def action_clear_focus(self, event=None):
        """
        Clear the telescope focus / highlight and return to the default view.

        Remet le subarray et l'antenne à leur état initial (aucun focus).
        Le prochain appui sur n/p repartira depuis la première antenne.

        Parameters
        ----------
        event : optional
            Ignored.
        """
        self.index_antenne_actuelle = -1
        self._nom_antenne_courante = ""
        self.index_subarray_actuel = 0
        self._update_colors()
        if self.sync_callback:
            self.sync_callback({'inspect_active': self.inspect_active})
        logger.info("Telescope focus cleared.")

    def action_help(self, event=None):
        """
        Demande l'affichage de la boîte d'aide via ``sync_callback``. Touche ``H``.

        Parameters
        ----------
        event : optional
            Ignoré.
        """
        if self.sync_callback:
            self.sync_callback({'show_help': True})

    # =========================================================
    # MÉTHODES VIRTUELLES (surchargées dans les sous-classes)
    # =========================================================

    def action_show_info_nearest(self, event=None):
        """Affiche les infos du point le plus proche du centre de la vue. Surchargée par les sous-classes."""
        pass

    def apply_cut(self, x1, y1, x2, y2):
        """Flagge les visibilités dans le rectangle (x1,y1)→(x2,y2). Surchargée par les sous-classes."""
        pass

    def _apply_interactive_flag(self, x1, y1, x2, y2, is_flag: bool):
        """
        Applique le flagging interactif sur une sélection rectangulaire.
        
        Surchargée par UVPlotEditor et RadPlotEditor pour adapter à leur système de coordonnées.
        
        Parameters
        ----------
        x1, y1, x2, y2 : float
            Coordonnées du rectangle dessiné
        is_flag : bool
            True = flaguer (bouton gauche), False = dé-flaguer (bouton droit)
        """
        pass

    def _update_colors(self):
        """Met à jour les couleurs des scatter plots selon le focus antenne. Surchargée par les sous-classes."""
        pass

    def action_show_info(self, event):
        """Affiche les informations de la visibilité la plus proche du clic. Surchargée par les sous-classes."""
        pass

    def apply_stats(self, x1, y1, x2, y2):
        """Calcule les statistiques scalaires dans le rectangle sélectionné. Surchargée par les sous-classes."""
        pass

    def apply_stats_vec(self, x1, y1, x2, y2):
        """Calcule les statistiques vectorielles (Re/Im) dans le rectangle. Surchargée par les sous-classes."""
        pass

    def action_flag_nearest(self, event=None):
        """Flagge la visibilité la plus proche du curseur. Surchargée par les sous-classes."""
        logger.info("Flag nearest not yet specified for this plot.")

    def update_data_alpha(self, alpha: float):
        """Met à jour la transparence des points de données (0.0–1.0). Surchargée par les sous-classes."""
        pass

    def update_data_color(self, color: str):
        """Met à jour la couleur des points de données. Surchargée par les sous-classes."""
        pass

    # =========================================================
    # UTILITAIRE INTERNE
    # =========================================================

    def _flag_indices(self, indices) -> None:
        """
        Flagge les indices dans le moteur C, le masque numpy et l'historique.

        Parameters
        ----------
        indices : array-like of int
            Indices des visibilités à flagguer. Si vide, la méthode est no-op.
        """
        if len(indices) == 0:
            return
        indices_np = np.array(indices, dtype=np.int32)
        self.obs.flag_data(indices_np)
        self.obs.masque_flagges[indices_np] = True
        self.obs.historique_coupes.append(indices_np)
        self._update_colors()
        if self.sync_callback:
            self.sync_callback()
