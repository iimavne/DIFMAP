# difmap_wrapper/editors/uv_editor.py
import logging
import numpy as np
import matplotlib.pyplot as plt

from PyQt6.QtCore import QTimer
from .base import BasePlotEditor
from difmap_wrapper.enums import EditorMode
from difmap_wrapper.gui.styles.design_system import DesignSystem

logger = logging.getLogger("difmap.uv_editor")


class UVPlotEditor(BasePlotEditor):
    """
    Éditeur interactif pour les visibilités dans le plan U/V.
    """

    def __init__(self, observation, fig, ax, data, base_color,
                 save_callback=None, sync_callback=None):
        """
        Parameters
        ----------
        observation : Observation
            Objet portant le masque de flagging.
        fig : matplotlib.figure.Figure
            Figure Matplotlib partagée avec le widget.
        ax : matplotlib.axes.Axes
            Axe UV principal.
        data : dict
            Données UV brutes.
        base_color : str
            Couleur des points non-flaggués (ex. :attr:`DesignSystem.PLOT_DATA`).
        save_callback : callable, optional
            Fonction retournant le chemin de sauvegarde.
        sync_callback : callable, optional
            Fonction de synchronisation état → MainWindow.
        """
        self.base_color  = base_color
        self.data_alpha  = 0.5
        u = data['u'] / 1e6
        v = data['v'] / 1e6
        self.scat_main = ax.scatter(u,  v,  s=1, color=base_color, alpha=self.data_alpha, edgecolors='none')
        self.scat_conj = ax.scatter(-u, -v, s=1, color=base_color, alpha=self.data_alpha, edgecolors='none')
        self.scat_conj.set_visible(True)  # conjugué affiché par défaut

        # Limites symétriques identiques sur X et Y pour un affichage carré.
        # Doit être positionné avant super().__init__() pour que original_limits
        # (utilisé pour le reset de vue) capture ces limites symétriques.
        max_range = float(max(np.abs(u).max(), np.abs(v).max())) * 1.1
        ax.set_xlim(max_range, -max_range)  # axe RA conventionnellement inversé
        ax.set_ylim(-max_range, max_range)

        super().__init__(observation, fig, ax, data, save_callback, sync_callback)

        self.raccourcis_autorises["%"] = self.action_toggle_conjugate

    # =========================================================
    # ZOOM SYMÉTRIQUE
    # =========================================================

    def on_select(self, eclick, erelease):
        """Override : zoom rectangulaire forcé carré (symétrie U/V préservée)."""
        if self.mode not in EditorMode.ALL_RECT:
            return
        if abs(erelease.x - eclick.x) < 10 and abs(erelease.y - eclick.y) < 10:
            return

        if self.mode == EditorMode.ZOOM:
            u1, v1 = eclick.xdata, eclick.ydata
            u2, v2 = erelease.xdata, erelease.ydata
            cx = (u1 + u2) / 2
            cy = (v1 + v2) / 2
            half = max(abs(u2 - u1), abs(v2 - v1)) / 2
            if half == 0:
                return
            self.ax.set_xlim(cx + half, cx - half)  # axe RA inversé
            self.ax.set_ylim(cy - half, cy + half)
            self.fig.canvas.draw_idle()
        else:
            super().on_select(eclick, erelease)

    def action_dezoom(self, event=None):
        """Override : dézoom 50 % en conservant la symétrie U/V."""
        xl, xr = self.ax.get_xlim()
        yl, yr = self.ax.get_ylim()
        cx = (xl + xr) / 2
        cy = (yl + yr) / 2
        half = max(abs(xr - xl), abs(yr - yl)) / 2 * 1.5
        self.ax.set_xlim(cx + half, cx - half)  # axe RA inversé
        self.ax.set_ylim(cy - half, cy + half)
        self.fig.canvas.draw_idle()

    # =========================================================
    # FLAGGING
    # =========================================================

    def apply_cut(self, x1, y1, x2, y2):
        """
        Flagge les visibilités dans la boîte (u1,v1)→(u2,v2), conjugués inclus.

        Parameters
        ----------
        x1, y1 : float
            Coin supérieur gauche de la boîte en Mλ.
        x2, y2 : float
            Coin inférieur droit de la boîte en Mλ.
        """
        u_min, u_max = min(x1, x2), max(x1, x2)
        v_min, v_max = min(y1, y2), max(y1, y2)

        u_data = self.data["u"] / 1e6
        v_data = self.data["v"] / 1e6

        mask_main = (u_data >= u_min) & (u_data <= u_max) & (v_data >= v_min) & (v_data <= v_max)
        mask_conj = (-u_data >= u_min) & (-u_data <= u_max) & (-v_data >= v_min) & (-v_data <= v_max)
        masque_final = (mask_main | mask_conj) & (~self.obs.masque_flagges)
        indices = np.where(masque_final)[0]

        if len(indices) > 0:
            logger.info(
                f"✂ {len(indices)} visibilités flaggées (UV plot).",
                extra={'difmap_level': 'success'}
            )
            self._flag_indices(indices)

    def _apply_interactive_flag(self, x1, y1, x2, y2, is_flag: bool):
        """
        Flagging interactif sur le plan UV avec détection du bouton de souris.
        
        Gauche (is_flag=True) : FLAG
        Droit (is_flag=False) : UNFLAG
        
        Gère les conjugués correctement : un point et son symétrique (-u, -v) 
        correspondent au même indice de visibilité.
        """
        u_min, u_max = min(x1, x2), max(x1, x2)
        v_min, v_max = min(y1, y2), max(y1, y2)

        u_data = self.data["u"] / 1e6
        v_data = self.data["v"] / 1e6

        # Points dans la boîte (y compris conjugués)
        mask_main = (u_data >= u_min) & (u_data <= u_max) & (v_data >= v_min) & (v_data <= v_max)
        mask_conj = (-u_data >= u_min) & (-u_data <= u_max) & (-v_data >= v_min) & (-v_data <= v_max)
        masque_intersection = mask_main | mask_conj

        if is_flag:
            # FLAGUER : sélectionner les points non-flaguées
            masque_final = masque_intersection & (~self.obs.masque_flagges)
            indices = np.where(masque_final)[0]
            if len(indices) > 0:
                self._flag_indices(indices)
                logger.info(f"🚩 {len(indices)} points FLAG (souris gauche)", 
                           extra={'difmap_level': 'success'})
        else:
            # DÉ-FLAGUER : sélectionner les points flaguées
            masque_final = masque_intersection & self.obs.masque_flagges
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

    def apply_external_cut(self, indices):
        """
        Reçoit une demande de flagging depuis un autre widget (ex. Radplot).

        Filtre les indices déjà flaggués avant d'appeler ``_flag_indices()``.

        Parameters
        ----------
        indices : array-like of int
            Indices de visibilités à flagguer.
        """
        if len(indices) == 0:
            return
        indices_valides = [i for i in indices if not self.obs.masque_flagges[i]]
        if not indices_valides:
            return
        indices_np = np.array(indices_valides, dtype=np.int32)
        self.obs.flag_data(indices_np)
        self.obs.masque_flagges[indices_np] = True
        self.obs.historique_coupes.append(indices_np)
        self._update_colors()
        logger.info(
            f"✂ {len(indices_np)} visibilités flaggées depuis le Radplot.",
            extra={'difmap_level': 'success'}
        )
        if self.sync_callback:
            self.sync_callback()

    # =========================================================
    # AFFICHAGE
    # =========================================================

    def update_marker_size(self, pct: float):
        """
        Met à jour la taille des marqueurs sur les deux scatters.

        Parameters
        ----------
        pct : float
            Pourcentage (1–100). Converti en pts² via la plage ``_SIZE_MIN``–``_SIZE_MAX``.
        """
        self.marker_size_pct = int(pct)
        size = self._SIZE_MIN + (pct / 100.0) * (self._SIZE_MAX - self._SIZE_MIN)
        self.scat_main.set_sizes([size])
        self.scat_conj.set_sizes([size])
        self.fig.canvas.draw_idle()

    def update_data_alpha(self, alpha: float):
        """Met à jour la transparence des points (0.0–1.0)."""
        self.data_alpha = alpha
        self.scat_main.set_alpha(alpha)
        self.scat_conj.set_alpha(alpha)
        self.fig.canvas.draw_idle()

    def update_data_color(self, color: str):
        """Met à jour la couleur de base des points de données."""
        self.base_color = color
        self._update_colors()

    def set_conjugate_visible(self, visible: bool):
        """
        Affiche ou masque les points conjugués (−u, −v). Appelé par la checkbox.

        Parameters
        ----------
        visible : bool
            ``True`` pour afficher ``scat_conj``.
        """
        self.scat_conj.set_visible(visible)
        etat = "affichés" if visible else "masqués"
        logger.info("Points conjugués %s.", etat)
        self.fig.canvas.draw_idle()

    def action_toggle_conjugate(self, _event=None):
        """
        Bascule la visibilité des points conjugués et notifie l'UI. Touche ``%``.

        Parameters
        ----------
        _event : optional
            Ignoré.
        """
        is_visible = self.scat_conj.get_visible()
        self.scat_conj.set_visible(not is_visible)
        etat = "affichés" if not is_visible else "masqués"
        logger.info(f"Points conjugués {etat}.")
        if self.sync_callback:
            self.sync_callback({'show_conjugate': not is_visible})
        self.fig.canvas.draw_idle()

    def action_redisplay(self, _event=None):
        """
        Clignotement visuel pour confirmer le rafraîchissement. Touche ``L``.

        Masque temporairement les scatter plots (50 ms) via ``QTimer``
        pour éviter le blocage de l'interface avec ``plt.pause()``.

        Parameters
        ----------
        _event : optional
            Ignoré.
        """
        vis_m, vis_c = self.scat_main.get_visible(), self.scat_conj.get_visible()
        self.scat_main.set_visible(False)
        self.scat_conj.set_visible(False)
        self.fig.canvas.draw_idle()        

        
        # Remplacement de plt.pause() par une fonction asynchrone PyQt
        def restore_visibility():
            if not self.scat_main or not self.scat_conj: return
            self.scat_main.set_visible(vis_m)
            self.scat_conj.set_visible(vis_c)
            self._update_colors()
            
        QTimer.singleShot(50, restore_visibility)

    def _update_colors(self):
        """
        Met à jour les couleurs, tailles et positions des scatter plots UV.

        Applique le focus antenne (rouge sur les baselines de l'antenne cible),
        masque les points flaggués via NaN et met à jour le titre de l'axe.
        Utilise :meth:`BasePlotEditor._build_focus_colors` (M1).
        """
        couleurs, sub_actif = self._build_focus_colors()

        if self.index_antenne_actuelle < 0:
            self.ax.set_title(
                "All baselines",
                color=DesignSystem.PLOT_TITLE_INACTIVE, fontsize=10
            )
        elif sub_actif not in self.antennes_par_subarray:
            label = self._nom_antenne_courante or "—"
            self.ax.set_title(
                f"FOCUS : {sub_actif}:{label}  [vide]",
                color=DesignSystem.PLOT_FOCUS, fontsize=10
            )
            logger.info("Subarray %s : aucune visibilité.", sub_actif)
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

        u = self.data["u"] / 1e6
        v = self.data["v"] / 1e6
        off_m = np.column_stack((u,  v))
        off_c = np.column_stack((-u, -v))
        off_m[self.obs.masque_flagges] = [np.nan, np.nan]
        off_c[self.obs.masque_flagges] = [np.nan, np.nan]

        self.scat_main.set_offsets(off_m)
        self.scat_conj.set_offsets(off_c)
        self.scat_main.set_facecolors(couleurs)
        self.scat_main.set_edgecolors('none')
        self.scat_main.set_alpha(self.data_alpha)
        self.scat_conj.set_facecolors(couleurs)
        self.scat_conj.set_edgecolors('none')
        self.scat_conj.set_alpha(self.data_alpha)
        self.fig.canvas.draw_idle()

    # =========================================================
    #  Observer — rafraîchissement complet à la demande
    # =========================================================

    def refresh_data(self) -> None:
        """
        Surchargé pour mettre à jour les offsets des scatters après
        un notify_data_changed() (calibration, gain apply, etc.).
        """
        self.data = self.obs.get_data()
        self._refresh_telescope_names()
        # Mise à jour des scatters en place (pas de recréation)
        u = self.data['u'] / 1e6
        v = self.data['v'] / 1e6
        self.scat_main.set_offsets(np.column_stack([u, v]))
        self.scat_conj.set_offsets(np.column_stack([-u, -v]))
        self._update_colors()

    # =========================================================
    # INSPECTION
    # =========================================================

    def action_show_info(self, event, strict=True):
        """
        Affiche les informations de la visibilité la plus proche du clic.

        Parameters
        ----------
        event : matplotlib.backend_bases.MouseEvent
            Événement portant ``xdata`` et ``ydata`` en Mλ.
        strict : bool, optional
            Si ``True``, ignore les clics à plus de 1,5 % de la largeur de la vue.
        """
        if getattr(event, 'xdata', None) is None or getattr(event, 'ydata', None) is None:
            return
        u_s, v_s = event.xdata, event.ydata
        u_d, v_d = self.data["u"] / 1e6, self.data["v"] / 1e6

        dist_main = (u_d - u_s) ** 2 + (v_d - v_s) ** 2
        dist_conj = (-u_d - u_s) ** 2 + (-v_d - v_s) ** 2
        min_m, min_c = np.min(dist_main), np.min(dist_conj)
        
        if strict:
            tolerance_sq = ((self.ax.get_xlim()[1] - self.ax.get_xlim()[0]) * 0.015) ** 2
            if min(min_m, min_c) > tolerance_sq:
                return

        idx = np.argmin(dist_main) if min_m < min_c else np.argmin(dist_conj)
        if self.obs.masque_flagges[idx]:
            return

        sub   = self.data.get("subarray", [0] * len(u_d))[idx]
        t_a   = self.data.get("tel_a",    [0] * len(u_d))[idx]
        t_b   = self.data.get("tel_b",    [0] * len(u_d))[idx]
        nom_a = self.noms_antennes.get(t_a, f"An{t_a}")
        nom_b = self.noms_antennes.get(t_b, f"An{t_b}")
        if_no = self.data.get("if_no", [1] * len(u_d))[idx]
        ut_raw = self.data.get("time", np.zeros(len(u_d)))[idx]
        flux   = self.data.get("amp",  np.zeros(len(u_d)))[idx]
        phs    = self.data.get("phase", np.zeros(len(u_d)))[idx]
        radius = np.sqrt(u_d[idx]**2 + v_d[idx]**2)

        doy = int(ut_raw // 86400)
        hh  = int((ut_raw % 86400) // 3600)
        mm  = int((ut_raw % 3600)  // 60)
        ss  = int(ut_raw % 60)

        info_text = (
            f"--- Quick Inspect (s) ---\n"
            f"Antennas : {sub}:{nom_a}-{nom_b} (IF {if_no})\n"
            f"Time UT  : {doy:03d}-{hh:02d}:{mm:02d}:{ss:02d}\n"
            f"Amplitude: {flux:.4f} Jy\n"
            f"Phase    : {phs:.1f}°\n"
            f"UV Radius: {radius:.2f} Mλ\n"
            f"-------------------------"
        )
        logger.info(info_text, extra={'difmap_level': 'inspect'})

    def action_show_info_nearest(self, event=None):
        """
        Affiche les infos du point le plus proche du centre de la vue. Touche ``s``.

        Si ``event`` ne porte pas de coordonnées, fabrique un événement synthétique
        pointant vers le centre des limites actuelles de l'axe.

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
                    xdata = (xl + xr) / 2
                    ydata = (yl + yr) / 2
                    inaxes = self.ax
                event = _Ev()
            else:
                return
        self.action_show_info(event, strict=False)

    # =========================================================
    # NO-OPS pour compatibilité avec le routing global
    # =========================================================

    def set_model_visible(self, _visible: bool):
        """No-op : le modèle n'est pas disponible sur le plan UV."""
        logger.info("[INFO] Model display not available for UV plot.")

    def set_residuals_visible(self, _visible: bool):
        """No-op : les résidus ne sont pas disponibles sur le plan UV."""
        logger.info("[INFO] Residuals not available for UV plot.")

    def set_show_errors(self, _visible: bool):
        """No-op : le graphique d'erreurs n'est pas disponible sur le plan UV."""
        logger.info("[INFO] Error plot not available for UV plot.")
