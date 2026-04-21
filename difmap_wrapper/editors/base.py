# difmap_wrapper/editors/base.py
import re
import logging
import numpy as np
from matplotlib.widgets import Cursor, MultiCursor, RectangleSelector, SpanSelector

from difmap_wrapper.enums import EditorMode
from difmap_wrapper.gui.styles.design_system import DesignSystem

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
        from difmap_wrapper.observation import Observation
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

        # Navigation antennes / sous-réseaux
        self.antennes_par_subarray: dict = {}
        for sub in np.unique(data["subarray"]):
            masque = data["subarray"] == sub
            self.antennes_par_subarray[sub] = list(
                np.unique(np.concatenate([data["tel_a"][masque], data["tel_b"][masque]]))
            )
        self.liste_subarrays = list(self.antennes_par_subarray.keys())
        self.index_subarray_actuel = 0
        self.index_antenne_actuelle = -1

        self._refresh_telescope_names()

        # État souris / vue
        self.mode = None
        self.press_info = None
        self.pan_start = None
        self.original_limits = (self.ax.get_xlim(), self.ax.get_ylim())
        self.current_size_idx = 0
        self.marker_sizes = [2.5, 6.0, 15.0]

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
        self.cursor_widget = Cursor(self.ax, useblit=True, color='gray', linewidth=0.8)
        self.cursor_widget.active = False

        self.raccourcis_autorises = {
            "r": self.action_home, "R": self.action_home,
            "x": self.action_quit, "X": self.action_quit,
            "q": self.action_quit, "Q": self.action_quit,
            "h": self.action_help, "H": self.action_help,
            "l": self.action_redisplay, "L": self.action_redisplay,
            "z": self.action_toggle_zoom, "Z": self.action_toggle_zoom,
            "m": self.action_toggle_pan, "M": self.action_toggle_pan,
            "c": self.action_toggle_cut, "C": self.action_toggle_cut,
            "d": self.action_cancel_cut, "D": self.action_cancel_cut,
            "f": self.action_toggle_interactive_flag, "F": self.action_toggle_interactive_flag,
            "a": self.action_flag_nearest, "A": self.action_flag_nearest,
            ".": self.action_toggle_marker_size,
            "+": self.action_toggle_crosshair,
            "w": self.action_toggle_channels, "W": self.action_toggle_channels,
            "u": self.action_undo, "ctrl+z": self.action_undo,
            "s": self.action_show_info_nearest,
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

        Construit ``self.noms_antennes`` (dict ``id → nom``).
        Appelé à l'initialisation et après tout changement de donnée
        """
        all_ids = np.unique(np.concatenate([self.data["tel_a"], self.data["tel_b"]]))
        self.noms_antennes = {
            num: self.obs._native.get_telescope_name(0, num)
            for num in all_ids
        }

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

        if self.index_antenne_actuelle >= 0:
            ant_cible = self.antennes_par_subarray[sub_actif][self.index_antenne_actuelle]
            m = (
                (self.data["subarray"] == sub_actif)
                & ((self.data["tel_a"] == ant_cible) | (self.data["tel_b"] == ant_cible))
            )
            couleurs[m] = DesignSystem.PLOT_FOCUS

        return couleurs, sub_actif

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
        if dist < 5.0 and event.xdata is not None:
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
            self.ax.set_xlim(min(u1, u2), max(u1, u2))
            self.ax.set_ylim(min(v1, v2), max(v1, v2))
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
        
        # Normalise les raccourcis Shift: 'shift+m' -> 'M', 'shift+=' -> '+'
        if key.startswith('shift+'):
            base_key = key[6:]  # Enlève 'shift+'
            if base_key == '=':  # Particularité : Shift+= = +
                key = '+'
            elif len(base_key) == 1:  # Caractère simple comme 'a'
                key = base_key.upper()  # 'a' -> 'A'
        
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

        Parameters
        ----------
        event : matplotlib.backend_bases.KeyEvent, optional
            Événement clavier (ignoré).
        """
        if self.original_limits:
            self.ax.set_xlim(self.original_limits[0])
            self.ax.set_ylim(self.original_limits[1])
            self.index_antenne_actuelle = -1
            self._update_colors()
            self.fig.canvas.draw_idle()
            logger.info("Vue réinitialisée. Focus antenne reset.",
                        extra={'difmap_level': 'success'})

    def action_redisplay(self, event=None):
        """Force un rafraîchissement du canvas. Touche ``L``."""
        self.fig.canvas.draw_idle()

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
        self.cursor_active = not self.cursor_active
        if self.cursor_active:
            self.cursor = MultiCursor(
                self.fig.canvas, self.axes_list,
                color=DesignSystem.PLOT_FOCUS, lw=0.8,
                horizOn=True, vertOn=True
            )
        else:
            if self.cursor:
                # 1. Rendre les lignes physiques invisibles
                if hasattr(self.cursor, 'vlines'):
                    for line in self.cursor.vlines:
                        line.set_visible(False)
                if hasattr(self.cursor, 'hlines'):
                    for line in self.cursor.hlines:
                        line.set_visible(False)
                
                # 2. Désactiver l'état actif du widget
                if hasattr(self.cursor, 'set_active'):
                    self.cursor.set_active(False)
                
                # 3. Déconnecter les signaux de la souris
                if hasattr(self.cursor, 'disconnect_events'):
                    self.cursor.disconnect_events()
                elif hasattr(self.cursor, 'disconnect'):
                    self.cursor.disconnect()
                    
                self.cursor = None
                
        self.fig.canvas.draw()
        status = "Activé" if self.cursor_active else "Désactivé"
        logger.info("Cross-hair : %s", status)
        if self.sync_callback:
            self.sync_callback({'crosshair': self.cursor_active})

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
        Cycle sur les trois tailles de marqueur disponibles (fin → moyen → gros). Touche ``.``.

        Parameters
        ----------
        event : matplotlib.backend_bases.KeyEvent, optional
            Événement clavier (ignoré).
        """
        self.current_size_idx = (self.current_size_idx + 1) % len(self.marker_sizes)
        self.update_marker_size(self.marker_sizes[self.current_size_idx])
        if self.sync_callback:
            self.sync_callback({'marker_size': self.current_size_idx + 1})

    def set_crosshair_visible(self, visible: bool):
        """
        ✅ CORRECTION: Synchronise crosshair via checkbox.
        
        Appelé depuis MainWindow checkboxe (et routing).
        Utile pour basculer le crosshair sans action clavier.
        """
        if visible and not self.cursor_active:
            # Activer : même logique que action_toggle_crosshair(True)
            self.action_toggle_crosshair(None)
        elif not visible and self.cursor_active:
            # Désactiver : même logique que action_toggle_crosshair(True) qui toggle
            self.action_toggle_crosshair(None)

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
        Sauvegarde les visibilités dans un fichier FITS via ``save_callback``. ``Ctrl+S``.

        Appelle ``save_callback`` pour obtenir le chemin de destination,
        puis ``obs.save_wobs()`` pour écrire le fichier.

        Parameters
        ----------
        event : matplotlib.backend_bases.KeyEvent, optional
            Événement clavier (ignoré).
        """
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
        Passe au télescope suivant dans le sous-réseau actif. Touche ``n``.

        Parameters
        ----------
        event : optional
            Ignoré.
        """
        sub_id = self.liste_subarrays[self.index_subarray_actuel]
        nb = len(self.antennes_par_subarray[sub_id])
        self.index_antenne_actuelle += 1
        if self.index_antenne_actuelle >= nb:
            self.index_subarray_actuel = (self.index_subarray_actuel + 1) % len(self.liste_subarrays)
            self.index_antenne_actuelle = 0
        self._update_colors()

    def action_prev_telescope(self, event=None):
        """
        Revient au télescope précédent dans le sous-réseau actif. Touche ``p``.

        Parameters
        ----------
        event : optional
            Ignoré.
        """
        self.index_antenne_actuelle -= 1
        if self.index_antenne_actuelle < 0:
            self.index_subarray_actuel = (self.index_subarray_actuel - 1) % len(self.liste_subarrays)
            sub_id = self.liste_subarrays[self.index_subarray_actuel]
            self.index_antenne_actuelle = len(self.antennes_par_subarray[sub_id]) - 1
        self._update_colors()

    def action_next_subarray(self, event=None):
        """
        Passe au sous-réseau suivant. Touche ``N``.

        Parameters
        ----------
        event : optional
            Ignoré.
        """
        self.index_subarray_actuel = (self.index_subarray_actuel + 1) % len(self.liste_subarrays)
        self.index_antenne_actuelle = 0
        self._update_colors()

    def action_prev_subarray(self, event=None):
        """
        Revient au sous-réseau précédent. Touche ``P``.

        Parameters
        ----------
        event : optional
            Ignoré.
        """
        self.index_subarray_actuel = (self.index_subarray_actuel - 1) % len(self.liste_subarrays)
        self.index_antenne_actuelle = 0
        self._update_colors()

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
            for a_idx, ant_id in enumerate(self.antennes_par_subarray[sub_id]):
                nom_ant = self.noms_antennes.get(ant_id, "").upper()
                if recherche == nom_ant or recherche == str(ant_id) or recherche in nom_ant:
                    self.index_subarray_actuel, self.index_antenne_actuelle = s_idx, a_idx
                    found = True
                    break
            if found:
                break

        if found:
            sub_id = self.liste_subarrays[self.index_subarray_actuel]
            nom = self.noms_antennes.get(
                self.antennes_par_subarray[sub_id][self.index_antenne_actuelle], "?"
            )
            logger.info("Focus sur %s:%s.", sub_id, nom)
            self._update_colors()
        else:
            logger.warning("Télescope '%s' introuvable.", target_name)

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
