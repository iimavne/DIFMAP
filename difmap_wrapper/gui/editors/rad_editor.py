# difmap_wrapper/editors/rad_editor.py
import logging
import numpy as np
from matplotlib.widgets import RectangleSelector, SpanSelector

from .base import BasePlotEditor
from difmap_wrapper.types import EditorMode, DisplayMode
from difmap_wrapper.gui.styles import DesignSystem

logger = logging.getLogger("difmap.rad_editor")


class RadPlotEditor(BasePlotEditor):
    """
    Éditeur interactif pour le Radplot (Amplitude/Phase vs rayon UV).
    """

    def __init__(self, observation, fig, ax, ax_phase, ax_err,
                 data, scats, base_color,
                 save_callback=None, sync_callback=None):
        """
        Parameters
        ----------
        observation : Observation
            Objet portant le masque de flagging.
        fig : matplotlib.figure.Figure
            Figure Matplotlib partagée avec le widget.
        ax : matplotlib.axes.Axes
            Axe principal (amplitude ou phase selon le mode).
        ax_phase : matplotlib.axes.Axes or None
            Axe de phase (``None`` si mode amplitude seule).
        ax_err : matplotlib.axes.Axes or None
            Axe d'erreurs théoriques 1/√w (``None`` si ``show_errors=False``).
        data : dict
            Données UV brutes avec clés ``'u'``, ``'v'``, ``'amp'``, ``'phase'``,
            ``'weight'``, ``'modamp'``, ``'modphs'``.
        scats : RadScatters
            Dataclass portant les ``PathCollection`` déjà tracés sur les axes.
        base_color : str
            Couleur des points non-flaggués.
        save_callback : callable, optional
            Fonction retournant le chemin de sauvegarde.
        sync_callback : callable, optional
            Fonction de synchronisation état → MainWindow.
        """
        super().__init__(observation, fig, ax, data,
                         save_callback, sync_callback)

        self.ax_phase   = ax_phase
        self.ax_err     = ax_err
        self.base_color = base_color
        self.data_alpha = 0.6

        self.scat_amp    = scats.amp
        self.scat_phase  = scats.phase
        self.scat_modamp = scats.model_amp
        self.scat_modphs = scats.model_phs
        self.scat_err    = scats.err

        # Mappage axe → type (pour détecter le type de clic)
        self.axis_type: dict = {}
        if self.ax:
            self.axis_type[self.ax] = "amp" if self.scat_amp else ("phase" if self.scat_phase else None)
        if self.ax_phase:
            self.axis_type[self.ax_phase] = "phase"
        if self.ax_err:
            self.axis_type[self.ax_err] = "error"

        self.axes_list = list(dict.fromkeys(
            a for a in [self.ax, self.ax_phase, self.ax_err] if a is not None
        ))
        self._last_pressed_axis = self.ax

        # RectangleSelectors pour le flagging interactif et les stats sur chaque axe
        self.rs_flag_phase  = None
        self.rs_flag_err    = None
        self.rs_stats_phase = None
        self.rs_stats_err   = None
        if self.ax_phase:
            def on_select_phase_flag(eclick, erelease, ax=self.ax_phase):
                self._last_pressed_axis = ax
                self._on_interactive_select(eclick, erelease)

            def on_select_phase_stats(eclick, erelease, ax=self.ax_phase):
                self._last_pressed_axis = ax
                self.on_select(eclick, erelease)

            self.rs_flag_phase = RectangleSelector(
                self.ax_phase, on_select_phase_flag, useblit=True, button=[1, 3],
                minspanx=5, minspany=5, spancoords="pixels", interactive=False,
            )
            self.rs_flag_phase.set_active(False)

            self.rs_stats_phase = RectangleSelector(
                self.ax_phase, on_select_phase_stats, useblit=True, button=[1],
                minspanx=5, minspany=5, spancoords="pixels", interactive=False,
            )
            self.rs_stats_phase.set_active(False)

        if self.ax_err:
            def on_select_err_flag(eclick, erelease, ax=self.ax_err):
                self._last_pressed_axis = ax
                self._on_interactive_select(eclick, erelease)

            def on_select_err_stats(eclick, erelease, ax=self.ax_err):
                self._last_pressed_axis = ax
                self.on_select(eclick, erelease)

            self.rs_flag_err = RectangleSelector(
                self.ax_err, on_select_err_flag, useblit=True, button=[1, 3],
                minspanx=5, minspany=5, spancoords="pixels", interactive=False,
            )
            self.rs_flag_err.set_active(False)

            self.rs_stats_err = RectangleSelector(
                self.ax_err, on_select_err_stats, useblit=True, button=[1],
                minspanx=5, minspany=5, spancoords="pixels", interactive=False,
            )
            self.rs_stats_err.set_active(False)

        self.uv_radius = np.sqrt(self.data["u"]**2 + self.data["v"]**2) / 1e6
        self.amp    = self.data.get("amp",    np.zeros_like(self.uv_radius))
        self.phase  = self.data.get("phase",  np.zeros_like(self.uv_radius))
        self.modamp = self.data.get("modamp", np.zeros_like(self.uv_radius))
        self.modphs = self.data.get("modphs", np.zeros_like(self.uv_radius))

        self.show_model     = False
        self.show_residuals = False
        self.show_errors    = False
        self.display_mode   = DisplayMode.AMP_ONLY

        # Limites originales des axes supplémentaires (pour action_home)
        self._orig_ylim_phase = self.ax_phase.get_ylim() if self.ax_phase else None
        self._orig_ylim_err   = self.ax_err.get_ylim()   if self.ax_err   else None

        # SpanSelectors pour zoom vertical (Y) sur chaque axe
        _span_kw = dict(useblit=True, props=dict(alpha=0.2, facecolor=DesignSystem.PLOT_FOCUS))
        self.span_y_amp = SpanSelector(
            self.ax,
            lambda vmin, vmax: self._on_zoom_y(self.ax, vmin, vmax),
            'vertical', **_span_kw
        )
        self.span_y_amp.set_active(False)

        self.span_y_phase = None
        if self.ax_phase:
            self.span_y_phase = SpanSelector(
                self.ax_phase,
                lambda vmin, vmax: self._on_zoom_y(self.ax_phase, vmin, vmax),
                'vertical', **_span_kw
            )
            self.span_y_phase.set_active(False)

        self.raccourcis_autorises.update({
            "+": self.action_toggle_crosshair,
            "U": lambda _e: self._set_mode(EditorMode.ZOOM_X),
            "y": self.action_toggle_zoom_y, "Y": self.action_toggle_zoom_y,
            "m": self.action_toggle_model,    "M": self.action_toggle_model,
            "-": self.action_toggle_residuals,
            "e": self.action_toggle_errors,   "E": self.action_toggle_errors,
            "v": self.action_toggle_stats_vec, "V": self.action_toggle_stats_vec,
            "1": self.action_set_amp_only,
            "2": self.action_set_phase_only,
            "3": self.action_set_both_plots,
        })

    def _set_mode(self, new_mode) -> None:
        """
        Surcharge de BasePlotEditor._set_mode pour gérer tous les Selectors multiples.
        """
        super()._set_mode(new_mode)

        # RectangleSelectors interactifs de flagging (ax_phase, ax_err)
        flag_active = (self.mode == EditorMode.INTERACTIVE_FLAG)
        if self.rs_flag_phase:
            self.rs_flag_phase.set_active(flag_active)
        if self.rs_flag_err:
            self.rs_flag_err.set_active(flag_active)

        # RectangleSelectors statistiques (ax_phase, ax_err) — STATS et STATS_V
        stats_active = self.mode in (EditorMode.STATS, EditorMode.STATS_V)
        if self.rs_stats_phase:
            self.rs_stats_phase.set_active(stats_active)
        if self.rs_stats_err:
            self.rs_stats_err.set_active(stats_active)

        # SpanSelectors zoom Y
        zoom_y_active = (self.mode == EditorMode.ZOOM_Y)
        self.span_y_amp.set_active(zoom_y_active)
        if self.span_y_phase:
            self.span_y_phase.set_active(zoom_y_active)

    def cleanup(self) -> None:
        """Surcharge pour nettoyer tous les Selectors supplémentaires."""
        for sel in (self.rs_flag_phase, self.rs_flag_err,
                    self.rs_stats_phase, self.rs_stats_err,
                    self.span_y_amp, self.span_y_phase):
            if sel is None:
                continue
            try:
                sel.set_active(False)
                if hasattr(sel, 'disconnect_events'):
                    sel.disconnect_events()
            except Exception:
                pass
        super().cleanup()

    # =========================================================
    # ZOOM Y
    # =========================================================

    def _on_zoom_y(self, ax, vmin, vmax) -> None:
        """Callback SpanSelector vertical : zoom l'axe Y de ``ax``."""
        if self.mode == EditorMode.ZOOM_Y and abs(vmax - vmin) > 1e-10:
            ax.set_ylim(vmin, vmax)
            self.fig.canvas.draw_idle()
            logger.info("Zoom Y appliqué.")

    def action_toggle_zoom_y(self, _event=None):
        """Active le mode ZOOM_Y (sélection verticale). Touche ``Y`` (Shift+Y)."""
        self._set_mode(EditorMode.ZOOM_Y)

    def action_dezoom(self, event=None):
        """Dézoom 50 % sur tous les axes (X partagé + Y indépendants). Touche ``O``."""
        # X est partagé : on agit sur l'axe principal
        xl, xr = self.ax.get_xlim()
        cx = (xl + xr) / 2
        dx = (xr - xl) * 0.75
        self.ax.set_xlim(cx - dx, cx + dx)
        # Y : chaque axe indépendamment
        for ax in self.axes_list:
            yl, yr = ax.get_ylim()
            cy = (yl + yr) / 2
            dy = (yr - yl) * 0.75
            ax.set_ylim(cy - dy, cy + dy)
        self.fig.canvas.draw_idle()
        logger.info("Dézoom appliqué.")

    def action_home(self, event=None):
        """
        Réinitialise la vue de tous les axes et supprime le focus antenne. Touche ``R``.
        Émet ``reset_all`` pour synchroniser le graphique UV.
        """
        if self.original_limits:
            self.ax.set_xlim(self.original_limits[0])
            self.ax.set_ylim(self.original_limits[1])
        if self.ax_phase and self._orig_ylim_phase:
            self.ax_phase.set_ylim(self._orig_ylim_phase)
        if self.ax_err and self._orig_ylim_err:
            self.ax_err.set_ylim(self._orig_ylim_err)
        self.index_antenne_actuelle = -1
        self._nom_antenne_courante = ""
        self.index_subarray_actuel = 0
        self._update_colors()
        self.fig.canvas.draw_idle()
        logger.info("Vue réinitialisée.", extra={'difmap_level': 'success'})
        if self.sync_callback:
            self.sync_callback({'reset_all': True})

    # =========================================================
    # SYNC UI
    # =========================================================

    def _sync_ui_state(self, refresh_layout: bool = False) -> None:
        """
        Émet l'état de l'éditeur vers MainWindow via sync_callback.

        refresh_layout=True demande à MainWindow de redécouper les axes
        (changement du nombre d'axes actifs).
        """
        if not self.sync_callback:
            return
        state = {
            'show_errors':    self.show_errors,
            'show_model':     self.show_model,
            'show_residuals': self.show_residuals,
            'display_mode':   self.display_mode,
        }
        if refresh_layout:
            state['_refresh_layout'] = True
        self.sync_callback(state)

    # =========================================================
    # ACTIONS CLAVIER
    # =========================================================

    def action_toggle_errors(self, event=None):
        """
        Bascule l'affichage du sous-graphique d'erreurs théoriques. Touche ``E``.

        Notifie ``MainWindow`` avec ``_refresh_layout=True`` pour recréer les axes.

        Parameters
        ----------
        event : optional
            Ignoré.
        """
        self.show_errors = not self.show_errors
        etat = "AFFICHÉ" if self.show_errors else "MASQUÉ"
        logger.info(f"[VIEW] Error subplot {etat}.")
        self._sync_ui_state(refresh_layout=True)

    def set_show_errors(self, visible: bool) -> None:
        """
        Définit la visibilité du panneau d'erreurs. Appelé par le routing checkbox.

        Parameters
        ----------
        visible : bool
            ``True`` pour afficher le sous-graphique 1/√w.
        """
        self.show_errors = visible
        etat = "AFFICHÉ" if self.show_errors else "MASQUÉ"
        logger.info(f"[VIEW] Error subplot {etat}.")
        self._sync_ui_state(refresh_layout=True)

    def action_set_amp_only(self, event=None):
        """
        Passe en mode amplitude uniquement. Touche ``1``.

        Parameters
        ----------
        event : optional
            Ignoré.
        """
        self.display_mode = DisplayMode.AMP_ONLY
        logger.info("[MODE] 1 - Amplitude only")
        self._sync_ui_state(refresh_layout=True)

    def action_set_phase_only(self, event=None):
        """
        Passe en mode phase uniquement. Touche ``2``.

        Parameters
        ----------
        event : optional
            Ignoré.
        """
        self.display_mode = DisplayMode.PHASE_ONLY
        logger.info("[MODE] 2 - Phase only")
        self._sync_ui_state(refresh_layout=True)

    def action_set_both_plots(self, event=None):
        """
        Passe en mode amplitude et phase. Touche ``3``.

        Parameters
        ----------
        event : optional
            Ignoré.
        """
        self.display_mode = DisplayMode.BOTH
        logger.info("[MODE] 3 - Amplitude & Phase")
        self._sync_ui_state(refresh_layout=True)

    def action_toggle_model(self, event=None):
        """
        Bascule la superposition du modèle mathématique. Touche ``M``.

        Parameters
        ----------
        event : optional
            Ignoré.
        """
        self.show_model = not self.show_model
        etat = "AFFICHÉ" if self.show_model else "MASQUÉ"
        logger.info(f"[VIEW] Modèle mathématique {etat}.")
        self._sync_ui_state()
        self._update_colors()

    def action_toggle_residuals(self, event=None):
        """
        Bascule entre données brutes et résidus (Data − Model). Touche ``-``.

        Parameters
        ----------
        event : optional
            Ignoré.
        """
        self.show_residuals = not self.show_residuals
        etat = "RÉSIDUS (Data - Model)" if self.show_residuals else "DONNÉES BRUTES"
        logger.warning(f"[VIEW] {etat}.")
        self._sync_ui_state()
        self._update_colors()

    def set_model_visible(self, visible: bool) -> None:
        """
        Définit la visibilité de la superposition du modèle. Appelé par la checkbox.

        Parameters
        ----------
        visible : bool
            ``True`` pour afficher ``scat_modamp`` / ``scat_modphs``.
        """
        if visible and not np.any(self.modamp != 0):
            logger.warning("Model is empty — no model data to display.")
            return
        self.show_model = visible
        self._update_colors()
        self._sync_ui_state()

    def set_residuals_visible(self, visible: bool) -> None:
        """
        Définit l'affichage des résidus. Appelé par la checkbox.

        Parameters
        ----------
        visible : bool
            ``True`` pour afficher Data − Model, ``False`` pour les données brutes.
        """
        self.show_residuals = visible
        self._update_colors()
        self._sync_ui_state()

    # =========================================================
    # CALCUL DES DONNÉES Y (résidus ou brutes)
    # =========================================================

    def _get_current_y_data(self) -> tuple[np.ndarray, np.ndarray]:
        """
        Retourne les données Y selon le mode résidus ou brut.

        En mode résidus, calcule amplitude et phase à partir de la différence
        vectorielle (Data − Model) en Re/Im. Applique la convention de signe
        de phase ``r_vis_phs()`` de ``uvradplt.c`` (conjugué pour u < 0).

        Returns
        -------
        d_amp : numpy.ndarray
            Amplitudes en Jy (brutes ou résiduelles).
        d_phs : numpy.ndarray
            Phases en degrés dans [−180, 180] (brutes ou résiduelles).
        """
        u_data = self.data["u"] / 1e6

        if self.show_residuals:
            p_rad,  mp_rad = np.radians(self.phase), np.radians(self.modphs)
            re = self.amp * np.cos(p_rad) - self.modamp * np.cos(mp_rad)
            im = self.amp * np.sin(p_rad) - self.modamp * np.sin(mp_rad)
            d_amp = np.sqrt(re**2 + im**2)

            d_phs_rad = np.where(d_amp < 1e-10, 0.0, np.arctan2(im, re))
            twopi = 2.0 * np.pi
            d_phs_rad = d_phs_rad - twopi * np.floor(d_phs_rad / twopi + 0.5)
            d_phs_rad = np.where(u_data < 0, -d_phs_rad, d_phs_rad)
            return d_amp, np.degrees(d_phs_rad)

        # Wrap phases into [-180, 180] and conjugate for u < 0, matching r_vis_phs() in uvradplt.c
        d_phs = self.phase - 360.0 * np.floor(self.phase / 360.0 + 0.5)
        d_phs = np.where(u_data < 0, -d_phs, d_phs)
        return self.amp, d_phs

    def _update_colors(self):
        """
        Met à jour tous les scatter plots selon l'état courant de l'éditeur.

        - Applique le focus antenne (couleurs via :meth:`_build_focus_colors`).
        - Masque les points flaggués via NaN.
        - Gère la visibilité du modèle, des résidus et des erreurs.
        - Ajuste l'échelle verticale de ``ax_err`` (M1).
        """
        couleurs, sub_actif = self._build_focus_colors()
        base_size = self._SIZE_MIN + (self.marker_size_pct / 100.0) * (self._SIZE_MAX - self._SIZE_MIN)
        tailles   = np.full(len(self.data["u"]), base_size, dtype=float)

        # Label focus sur l'axe principal (comme UVPlotEditor)
        if self.ax:
            if self.index_antenne_actuelle < 0:
                ax_title = "Phase" if self.display_mode == DisplayMode.PHASE_ONLY else "Amplitude"
                self.ax.set_title(ax_title, color=DesignSystem.PLOT_TITLE_INACTIVE, fontsize=10)
            elif sub_actif not in self.antennes_par_subarray:
                label = self._nom_antenne_courante or "—"
                self.ax.set_title(
                    f"FOCUS : {sub_actif}:{label}  [vide]",
                    color=DesignSystem.PLOT_FOCUS, fontsize=10
                )
            elif self.index_antenne_actuelle < len(self.toutes_antennes_sorted):
                vrai_nom = self.toutes_antennes_sorted[self.index_antenne_actuelle]
                ant_cible = self._find_local_antenna_id(sub_actif, vrai_nom)
                if ant_cible is not None:
                    self.ax.set_title(
                        f"FOCUS : {sub_actif}:{vrai_nom}",
                        color=DesignSystem.PLOT_FOCUS, fontsize=10
                    )
                    m_focus = (
                        (self.data["subarray"] == sub_actif)
                        & ((self.data["tel_a"] == ant_cible) | (self.data["tel_b"] == ant_cible))
                    )
                    if not np.any(m_focus & ~self.obs.masque_flagges):
                        logger.warning("No data for %s:%s", sub_actif, vrai_nom)
                else:
                    self.ax.set_title(
                        f"FOCUS : {sub_actif}:{vrai_nom}  [pas de visibilités]",
                        color=DesignSystem.PLOT_FOCUS, fontsize=10
                    )
                    logger.info("Pas de visibilités pour %s dans le subarray %s.", vrai_nom, sub_actif)

        d_amp, d_phs = self._get_current_y_data()
        mask = self.obs.masque_flagges

        def _apply(scat, x, y, label=None):
            if scat and scat.axes:
                off = np.column_stack((x, y))
                off[mask] = [np.nan, np.nan]
                scat.set_offsets(off)
                scat.set_facecolors(couleurs)
                scat.set_sizes(tailles)
                scat.set_alpha(self.data_alpha)
                if label and hasattr(scat.axes, 'set_ylabel'):
                    scat.axes.set_ylabel(label)

        _apply(self.scat_amp,  self.uv_radius, d_amp,
               "Res Amp (Jy)" if self.show_residuals else "Amp (Jy)")
        _apply(self.scat_phase, self.uv_radius, d_phs,
               "Res Phase (°)" if self.show_residuals else "Phase (°)")

        has_model_data = np.any(self.modamp != 0)

        if self.scat_modamp:
            off_m = np.column_stack((self.uv_radius, self.modamp))
            off_m[mask] = [np.nan, np.nan]
            self.scat_modamp.set_offsets(off_m)
            self.scat_modamp.set_sizes(tailles)
            self.scat_modamp.set_visible(self.show_model and not self.show_residuals and has_model_data)

        if self.scat_modphs:
            u_data = self.data["u"] / 1e6
            mod_phs = self.modphs - 360.0 * np.floor(self.modphs / 360.0 + 0.5)
            mod_phs = np.where(u_data < 0, -mod_phs, mod_phs)
            off_m = np.column_stack((self.uv_radius, mod_phs))
            off_m[mask] = [np.nan, np.nan]
            self.scat_modphs.set_offsets(off_m)
            self.scat_modphs.set_sizes(tailles)
            self.scat_modphs.set_visible(self.show_model and not self.show_residuals and has_model_data)

        if self.scat_err:
            weight   = self.data.get('weight', np.ones_like(self.uv_radius))
            err_vals = np.where(weight != 0, 1.0 / np.sqrt(np.fabs(weight)), 0.0)
            off_e    = np.column_stack((self.uv_radius, err_vals))
            off_e[mask] = [np.nan, np.nan]
            self.scat_err.set_offsets(off_e)
            self.scat_err.set_facecolors(couleurs)
            self.scat_err.set_sizes(tailles)
            if self.ax_err:
                valid = weight[weight != 0]
                if len(valid) > 0:
                    wtmin   = np.min(np.fabs(valid))
                    err_max = 1.0 / np.sqrt(wtmin) if wtmin > 0 else 0.0
                    self.ax_err.set_ylim([0.0, err_max * 1.1])

        self.fig.canvas.draw_idle()

    def update_marker_size(self, pct: float):
        """
        Met à jour la taille des marqueurs et rafraîchit les couleurs.

        Parameters
        ----------
        pct : float
            Pourcentage (1–100). Converti en pts² via ``_SIZE_MIN``–``_SIZE_MAX``.
        """
        self.marker_size_pct = int(pct)
        self._update_colors()

    def update_data_alpha(self, alpha: float):
        """Met à jour la transparence des points de données (0.0–1.0)."""
        self.data_alpha = alpha
        for scat in (self.scat_amp, self.scat_phase, self.scat_err):
            if scat is not None:
                scat.set_alpha(alpha)
        self.fig.canvas.draw_idle()

    def update_data_color(self, color: str):
        """Met à jour la couleur de base des points de données."""
        self.base_color = color
        self._update_colors()

    # =========================================================
    # FLAGGING ET STATISTIQUES
    # =========================================================

    def apply_cut(self, x1, y1, x2, y2):
        """
        Flagge les visibilités dans la boîte de sélection (opération « cut »).

        Correspondance ``difmap_src`` (``radplot.c``) : flagge tous les points
        contenus dans une boîte dessinée à la souris.

        Détecte automatiquement l'axe cliqué (amplitude ou phase) et récupère
        les données Y courantes (brutes ou résiduelles).

        Parameters
        ----------
        x1, y1 : float
            Premier coin de la boîte en coordonnées de données (rayon UV, Y).
        x2, y2 : float
            Coin opposé de la boîte.
        """
        xmin, xmax = min(x1, x2), max(x1, x2)
        ymin, ymax = min(y1, y2), max(y1, y2)
        
        d_amp, d_phs = self._get_current_y_data()
        is_phase = (hasattr(self, '_last_pressed_axis')
                    and self.axis_type.get(self._last_pressed_axis) == "phase")
        y_data = d_phs if is_phase else d_amp
        
        mask_box = ((self.uv_radius >= xmin) & (self.uv_radius <= xmax)
                    & (y_data >= ymin) & (y_data <= ymax))
        masque_final = mask_box & (~self.obs.masque_flagges)
        indices = np.where(masque_final)[0]
        
        if len(indices) > 0:
            logger.info(f"✂ {len(indices)} points supprimés.", extra={'difmap_level': 'success'})
            self._flag_indices(indices)

    def _apply_interactive_flag(self, x1, y1, x2, y2, is_flag: bool):
        """
        Flagging interactif sur le Radplot avec détection bouton de souris.
        
        Gauche (is_flag=True) : FLAG
        Droit (is_flag=False) : UNFLAG
        
        Détecte automatiquement quel axe a été cliqué (amplitude, phase, ou erreur)
        et applique la sélection rectangulaire sur les données correspondantes.
        
        Parameters
        ----------
        x1, y1, x2, y2 : float
            Coordonnées du rectangle en espace de données
        is_flag : bool
            True = bouton gauche (FLAG), False = bouton droit (UNFLAG)
        """
        xmin, xmax = min(x1, x2), max(x1, x2)
        ymin, ymax = min(y1, y2), max(y1, y2)
        
        # Détecte quel axe a été cliqué
        is_phase = (hasattr(self, '_last_pressed_axis')
                    and self.axis_type.get(self._last_pressed_axis) == "phase")
        
        # Récupère les données Y courantes (brutes ou résiduelles)
        d_amp, d_phs = self._get_current_y_data()
        y_data = d_phs if is_phase else d_amp
        
        # Masque des points dans la boîte de sélection
        mask_box = ((self.uv_radius >= xmin) & (self.uv_radius <= xmax)
                    & (y_data >= ymin) & (y_data <= ymax))
        
        if is_flag:
            # FLAGUER : sélectionner les points non-flaguées
            masque_final = mask_box & (~self.obs.masque_flagges)
            indices = np.where(masque_final)[0]
            if len(indices) > 0:
                self._flag_indices(indices)
                logger.info(f"🚩 {len(indices)} points FLAG (souris gauche)", 
                           extra={'difmap_level': 'success'})
        else:
            # DÉ-FLAGUER : sélectionner les points flaguées
            masque_final = mask_box & self.obs.masque_flagges
            indices = np.where(masque_final)[0]
            if len(indices) > 0:
                self.obs.unflag_data(indices)
                self.obs.masque_flagges[indices] = False
                self.obs.historique_coupes.append(indices)
                self._update_colors()
                logger.info(f"🔓 {len(indices)} points UNFLAG (souris droit)", 
                           extra={'difmap_level': 'success'})
                if self.sync_callback:
                    self.sync_callback()

    def apply_stats(self, x1, y1, x2, y2):
        """
        Calcule et affiche les statistiques scalaires (amplitude, phase) dans la boîte.

        Correspondance ``difmap_src`` (``radplot.c``) : fonction ``radstat()`` en mode scalaire.

        Parameters
        ----------
        x1, y1 : float
            Premier coin de la boîte (rayon UV en Mλ, valeur Y).
        x2, y2 : float
            Coin opposé de la boîte.

        Returns
        -------
        dict or None
            Dictionnaire avec ``n``, ``amp_mean``, ``amp_err``, ``amp_rms``,
            ``phs_mean``, ``phs_err``, ``phs_rms``. ``None`` si aucune visibilité sélectionnée.
        """
        xmin, xmax = min(x1, x2), max(x1, x2)
        ymin, ymax = min(y1, y2), max(y1, y2)
        
        d_amp, d_phs = self._get_current_y_data()
        is_phase = (hasattr(self, '_last_pressed_axis')
                    and self.axis_type.get(self._last_pressed_axis) == "phase")
        y_ref = d_phs if is_phase else d_amp
        weight = self.data.get('weight', np.ones(len(self.uv_radius)))
        
        mask = ((self.uv_radius >= xmin) & (self.uv_radius <= xmax)
                & (y_ref >= ymin) & (y_ref <= ymax)
                & (~self.obs.masque_flagges) & (weight > 0))
        indices = np.where(mask)[0]
        n = len(indices)
        
        if n == 0:
            logger.warning("No visibilities within the selection box.")
            return
        
        a_sub, p_sub = d_amp[indices], d_phs[indices]
        a_mean = np.mean(a_sub)
        a_std = np.std(a_sub, ddof=0) if n > 1 else 0.0
        a_err = a_std / np.sqrt(n) if n > 1 else 0.0

        p_mean = np.mean(p_sub)
        p_std = np.std(p_sub, ddof=0) if n > 1 else 0.0
        p_err = p_std / np.sqrt(n) if n > 1 else 0.0
        
        lbl_a = "Res Amp" if self.show_residuals else "Amp"
        lbl_p = "Res Phs" if self.show_residuals else "Phs"
        
        msg = (
            f"The statistics of the {n} visibilities within the box are:\n"
            f"  {lbl_a} mean = {a_mean:.6f} +/- {a_err:.6f}   RMS scatter = {a_std:.6f}\n"
            f"  {lbl_p} mean = {p_mean:.6f} +/- {p_err:.6f}   RMS scatter = {p_std:.6f}  (degrees)"
        )
        logger.info(msg, extra={'difmap_level': 'stats'})
        return {
            "n": n,
            "amp_mean": a_mean, "amp_err": a_err, "amp_rms": a_std,
            "phs_mean": p_mean, "phs_err": p_err, "phs_rms": p_std,
        }

    def apply_stats_vec(self, x1, y1, x2, y2):
        """
        Calcule et affiche les statistiques vectorielles (Re/Im) dans la boîte.

        Correspondance ``difmap_src`` (``radplot.c``) : fonction ``radstat()`` en mode vectoriel.
        Convertit amplitude + phase → Re/Im via :
        ``Real = Amp × cos(Phase_rad)`` et ``Imag = Amp × sin(Phase_rad)``.

        Parameters
        ----------
        x1, y1 : float
            Premier coin de la boîte (rayon UV en Mλ, valeur Y).
        x2, y2 : float
            Coin opposé de la boîte.

        Returns
        -------
        dict or None
            Dictionnaire avec ``n``, ``re_mean``, ``re_err``, ``re_rms``,
            ``im_mean``, ``im_err``, ``im_rms``. ``None`` si aucune visibilité sélectionnée.
        """
        xmin, xmax = min(x1, x2), max(x1, x2)
        ymin, ymax = min(y1, y2), max(y1, y2)
        
        d_amp, d_phs = self._get_current_y_data()
        is_phase = (hasattr(self, '_last_pressed_axis')
                    and self.axis_type.get(self._last_pressed_axis) == "phase")
        y_ref = d_phs if is_phase else d_amp
        weight = self.data.get('weight', np.ones(len(self.uv_radius)))
        
        mask = ((self.uv_radius >= xmin) & (self.uv_radius <= xmax)
                & (y_ref >= ymin) & (y_ref <= ymax)
                & (~self.obs.masque_flagges) & (weight > 0))
        indices = np.where(mask)[0]
        n = len(indices)
        
        if n == 0:
            logger.warning("No visibilities within the selection box.")
            return
        
        a_sub = d_amp[indices]
        p_sub_rad = np.radians(d_phs[indices])
        real_part = a_sub * np.cos(p_sub_rad)
        imag_part = a_sub * np.sin(p_sub_rad)
        
        r_mean = np.mean(real_part)
        r_std = np.std(real_part, ddof=0) if n > 1 else 0.0
        r_err = r_std / np.sqrt(n) if n > 1 else 0.0

        i_mean = np.mean(imag_part)
        i_std = np.std(imag_part, ddof=0) if n > 1 else 0.0
        i_err = i_std / np.sqrt(n) if n > 1 else 0.0
        
        msg = (
            f"The VECTOR statistics of the {n} visibilities within the box are:\n"
            f"  Real mean = {r_mean:.6f} +/- {r_err:.6f}   RMS scatter = {r_std:.6f}\n"
            f"  Imag mean = {i_mean:.6f} +/- {i_err:.6f}   RMS scatter = {i_std:.6f}"
        )
        logger.info(msg, extra={'difmap_level': 'stats'})
        return {
            "n": n,
            "re_mean": r_mean, "re_err": r_err, "re_rms": r_std,
            "im_mean": i_mean, "im_err": i_err, "im_rms": i_std,
        }

    # =========================================================
    # INSPECTION
    # =========================================================

    def action_show_info(self, event, strict=True):
        """
        Affiche les informations de la visibilité la plus proche du clic.

        Utilise une distance normalisée (Δx/plage_x)² + (Δy/plage_y)² pour
        trouver le point le plus proche indépendamment des unités des axes.

        Parameters
        ----------
        event : matplotlib.backend_bases.MouseEvent
            Événement portant ``xdata``, ``ydata`` et ``inaxes``.
        strict : bool, optional
            Si ``True``, ignore les clics à plus de 1,5 % de la plage de vue.
        """
        if getattr(event, 'xdata', None) is None or getattr(event, 'ydata', None) is None or getattr(event, 'inaxes', None) is None:
            return
        x_s, y_s = event.xdata, event.ydata
        d_amp, d_phs = self._get_current_y_data()
        is_phase_click = (event.inaxes == self.ax_phase)
        y_data = d_phs if is_phase_click else d_amp
        x_span = event.inaxes.get_xlim()[1] - event.inaxes.get_xlim()[0]
        y_span = event.inaxes.get_ylim()[1] - event.inaxes.get_ylim()[0]
        norm_dx = (self.uv_radius - x_s) / x_span
        norm_dy = (y_data - y_s) / y_span
        dist_sq = norm_dx**2 + norm_dy**2
        idx = np.argmin(dist_sq)
        
        if strict and dist_sq[idx] > (0.015**2):
            return
            
        if self.obs.masque_flagges[idx]:
            return
            
        sub    = self.data.get("subarray", [0] * len(self.uv_radius))[idx]
        nom_a  = self.noms_antennes.get(self.data.get("tel_a", [0] * len(self.uv_radius))[idx], "?")
        nom_b  = self.noms_antennes.get(self.data.get("tel_b", [0] * len(self.uv_radius))[idx], "?")
        if_no  = self.data.get("if_no", [1] * len(self.uv_radius))[idx]
        ut_raw = self.data.get("time", np.zeros(len(self.uv_radius)))[idx]
        doy = int(ut_raw // 86400)
        hh  = int((ut_raw % 86400) // 3600)
        mm  = int((ut_raw % 3600)  // 60)
        ss  = int(ut_raw % 60)
        lbl_a = "Res Amp" if self.show_residuals else "Amp"
        lbl_p = "Res Phs" if self.show_residuals else "Phase"
        msg = (
            f"--- Quick Inspect (s) ---\n"
            f"Antennas : {sub}:{nom_a}-{nom_b} (IF {if_no})\n"
            f"Time UT  : {doy:03d}-{hh:02d}:{mm:02d}:{ss:02d}\n"
            f"{lbl_a:<8} : {d_amp[idx]:.4f} Jy\n"
            f"{lbl_p:<8} : {d_phs[idx]:.1f}°\n"
            f"UV Radius: {self.uv_radius[idx]:.2f} Mλ\n"
            f"-------------------------"
        )
        logger.info(msg, extra={'difmap_level': 'inspect'})

    def action_show_info_nearest(self, event=None):
        """
        Affiche les infos du point le plus proche du centre de la vue. Touche ``s``.

        Si ``event`` ne porte pas de coordonnées, fabrique un événement synthétique
        pointant vers le centre de l'axe principal.

        Parameters
        ----------
        event : optional
            Événement clavier ou ``None``.
        """
        if getattr(event, 'xdata', None) is None:
            if self.ax:
                xl, xr = self.ax.get_xlim()
                yl, yr = self.ax.get_ylim()
                class _Ev:
                    xdata   = (xl + xr) / 2
                    ydata   = (yl + yr) / 2
                    inaxes  = self.ax
                event = _Ev()
            else:
                return
        self.action_show_info(event, strict=False)

    def action_flag_nearest(self, event=None):
        """
        Flagge la visibilité la plus proche du curseur. Touche ``A``.

        Utilise la même distance normalisée que :meth:`action_show_info`.
        Ignore les points déjà flaggués ou trop éloignés (> 1,5 % de la plage).

        Parameters
        ----------
        event : matplotlib.backend_bases.MouseEvent
            Événement portant ``xdata``, ``ydata`` et ``inaxes``.
        """
        if event is None or event.xdata is None or event.ydata is None:
            logger.warning("Position curseur invalide pour Action A.")
            return
        x_s, y_s = event.xdata, event.ydata
        d_amp, d_phs = self._get_current_y_data()
        is_phase_click = (event.inaxes == self.ax_phase)
        y_data = d_phs if is_phase_click else d_amp
        x_span = event.inaxes.get_xlim()[1] - event.inaxes.get_xlim()[0]
        y_span = event.inaxes.get_ylim()[1] - event.inaxes.get_ylim()[0]
        norm_dx = (self.uv_radius - x_s) / x_span
        norm_dy = (y_data - y_s) / y_span
        dist_sq = norm_dx**2 + norm_dy**2
        idx = np.argmin(dist_sq)
        if dist_sq[idx] > (0.015**2):
            logger.warning("No point close enough to cursor.")
            return
        if self.obs.masque_flagges[idx]:
            logger.info("Point already flagged.")
            return
        self._flag_indices([idx])
        sub   = self.data.get("subarray", [0] * len(self.uv_radius))[idx]
        nom_a = self.noms_antennes.get(self.data.get("tel_a", [0] * len(self.uv_radius))[idx], "?")
        nom_b = self.noms_antennes.get(self.data.get("tel_b", [0] * len(self.uv_radius))[idx], "?")
        msg = f"--- Flagged (A) ---\nAntennas: {sub}:{nom_a}-{nom_b}\nRadius: {self.uv_radius[idx]:.2f} Mλ"
        logger.info(msg, extra={'difmap_level': 'success'})

    # =========================================================
    #  Observer — rafraîchissement complet à la demande
    # =========================================================

    def refresh_data(self) -> None:
        """
        Surchargé pour mettre à jour les tableaux intermédiaires (uv_radius, amp, phase…)
        après un notify_data_changed() (calibration, gain apply, etc.).
        """
        # Mettre à jour self.data d'abord, puis recalculer les tableaux
        # intermédiaires AVANT d'appeler _update_colors() via super().
        # Sans ça, _update_colors() utilise self.amp/phase de l'ancienne taille
        # pendant que self.data["u"] a déjà la nouvelle taille → ValueError.
        self.data = self.obs.get_data()
        self.uv_radius = np.sqrt(self.data["u"]**2 + self.data["v"]**2) / 1e6
        self.amp    = self.data.get("amp",    np.zeros_like(self.uv_radius))
        self.phase  = self.data.get("phase",  np.zeros_like(self.uv_radius))
        self.modamp = self.data.get("modamp", np.zeros_like(self.uv_radius))
        self.modphs = self.data.get("modphs", np.zeros_like(self.uv_radius))
        self._refresh_telescope_names()
        self._update_colors()
