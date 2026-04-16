import numpy as np
from .base import BasePlotEditor
from difmap_wrapper.gui.styles.design_system import DesignSystem

class RadPlotEditor(BasePlotEditor):
    def __init__(self, observation, fig, ax, ax_phase, ax_err, data, scats, base_color, info_callback=None, save_callback=None, sync_callback=None, shared_mask=None, shared_history=None):
        
        super().__init__(observation, fig, ax, data, info_callback, save_callback, sync_callback, shared_mask, shared_history)
        self.ax_phase = ax_phase
        self.ax_err = ax_err
        
        # Récupération propre depuis le dictionnaire scats
        self.scat_amp = scats.get("amp")
        self.scat_phase = scats.get("phs")
        self.scat_modamp = scats.get("m_amp")
        self.scat_modphs = scats.get("m_phs")
        self.scat_err = scats.get("err")
        
        self.base_color = base_color
        
        # Mappage des axes pour déterminer rapidement le type de clic
        self.axis_type = {}  # {ax_object: "amp" | "phase" | "error"}
        if self.ax: self.axis_type[self.ax] = "amp" if self.scat_amp else ("phase" if self.scat_phase else None)
        if self.ax_phase: self.axis_type[self.ax_phase] = "phase"
        if self.ax_err: self.axis_type[self.ax_err] = "error"
        
        # Liste unique des axes actifs pour le curseur MultiCursor (+)
        self.axes_list = list(dict.fromkeys([a for a in [self.ax, self.ax_phase, self.ax_err] if a is not None]))
        
        # Initialiser la mémoire du dernier axe cliqué (par défaut l'axe principal)
        self._last_pressed_axis = self.ax
            
        self.uv_radius = np.sqrt(self.data["u"]**2 + self.data["v"]**2) / 1e6
        self.amp = self.data.get("amp", np.zeros_like(self.uv_radius))
        self.phase = self.data.get("phase", np.zeros_like(self.uv_radius))
        self.modamp = self.data.get("modamp", np.zeros_like(self.uv_radius))
        self.modphs = self.data.get("modphs", np.zeros_like(self.uv_radius))

        # États des fonctionnalités avancées
        self.show_model = False
        self.show_residuals = False
        self.show_errors = False
        self.display_mode = 1  # 1: Amp, 2: Phase, 3: Both

        # Ajout des raccourcis
        self.raccourcis_autorises.update({
            "+": self.action_toggle_crosshair,
            "U": lambda e: self._set_mode("ZOOM_X"),
            "m": self.action_toggle_model, "M": self.action_toggle_model,
            "-": self.action_toggle_residuals,
            "e": self.action_toggle_errors, "E": self.action_toggle_errors,
            "v": self.action_toggle_stats_vec, "V": self.action_toggle_stats_vec,
            "1": self.action_set_amp_only,
            "2": self.action_set_phase_only,
            "3": self.action_set_both_plots
        })

    def _sync_ui_state(self):
        """Sync editor state back to UI checkboxes. Called after keyboard shortcuts."""
        if not self.sync_callback: return
        state = {
            'show_errors': self.show_errors,
            'show_model': self.show_model,
            'show_residuals': self.show_residuals,
            'display_mode': self.display_mode,
        }
        self.sync_callback(state)

    def action_toggle_errors(self, event=None):
        self.show_errors = not self.show_errors
        if self.info_callback:
            etat = "AFFICHE" if self.show_errors else "MASQUE"
            self.info_callback(f"[VIEW] Error subplot {etat}.", level='info')
        self._sync_ui_state()  # ✨ Sync checkbox state back to UI
        # Informe le widget parent pour qu'il redécoupe l'écran si nécessaire
        # Cherche le widget RadPlotWidget en remontant la hiérarchie
        try:
            parent = self.fig.canvas.parent()
            # Remonter jusqu'à trouver set_show_errors
            max_levels = 5  # Éviter boucle infinie
            while parent and max_levels > 0:
                if hasattr(parent, 'set_show_errors'):
                    parent.set_show_errors(self.show_errors)
                    return
                parent = parent.parent() if hasattr(parent, 'parent') else None
                max_levels -= 1
            
            # Si pas trouvé, log erreur
            if self.info_callback:
                self.info_callback(f"[ERROR] Cannot reach RadPlotWidget parent", level='error')
        except Exception as e:
            if self.info_callback:
                self.info_callback(f"[ERROR] {e}", level='error')
    
    def set_show_errors(self, visible: bool):
        """Appelé par le routing checkbox ou le keyboard shortcut + callback route_checkbox_both."""
        self.show_errors = visible
        if self.info_callback:
            etat = "AFFICHE" if self.show_errors else "MASQUE"
            self.info_callback(f"[VIEW] Error subplot {etat}.", level='info')
        
        # ✨ CRITICAL: Trigger plot refresh (same as action_toggle_errors does)
        self._sync_ui_state()  # Update checkbox state if needed
        
        # Informe le widget parent pour qu'il redécoupe l'écran si nécessaire
        try:
            parent = self.fig.canvas.parent()
            max_levels = 5  # Éviter boucle infinie
            while parent and max_levels > 0:
                if hasattr(parent, 'set_show_errors'):
                    parent.set_show_errors(self.show_errors)
                    return
                parent = parent.parent() if hasattr(parent, 'parent') else None
                max_levels -= 1
        except Exception as e:
            if self.info_callback:
                self.info_callback(f"[ERROR] set_show_errors parent traversal: {e}", level='error')

    def action_set_amp_only(self, event=None):
        """Touche 1 : afficher amplitude uniquement"""
        self.display_mode = 1
        parent = self.fig.canvas.parent()
        if parent and hasattr(parent, 'set_display_mode'):
            parent.set_display_mode(0)  # 0 = mode index, will be display_mode=1
            if self.info_callback: self.info_callback("[MODE] 1 - Amplitude only", level='info')
        else:
            if self.info_callback: self.info_callback("[ERROR] Cannot change display mode", level='error')
        self._sync_ui_state()  # ✨ Sync combo_rad_mode back to UI

    def action_set_phase_only(self, event=None):
        """Touche 2 : afficher phase uniquement"""
        self.display_mode = 2
        parent = self.fig.canvas.parent()
        if parent and hasattr(parent, 'set_display_mode'):
            parent.set_display_mode(1)  # 1 = mode index, will be display_mode=2
            if self.info_callback: self.info_callback("[MODE] 2 - Phase only", level='info')
        else:
            if self.info_callback: self.info_callback("[ERROR] Cannot change display mode", level='error')
        self._sync_ui_state()  # ✨ Sync combo_rad_mode back to UI

    def action_set_both_plots(self, event=None):
        """Touche 3 : afficher amp et phase"""
        self.display_mode = 3
        parent = self.fig.canvas.parent()
        if parent and hasattr(parent, 'set_display_mode'):
            parent.set_display_mode(2)  # 2 = mode index, will be display_mode=3
            if self.info_callback: self.info_callback("[MODE] 3 - Amplitude & Phase", level='info')
        else:
            if self.info_callback: self.info_callback("[ERROR] Cannot change display mode", level='error')
        self._sync_ui_state()  # ✨ Sync combo_rad_mode back to UI

    def action_toggle_model(self, event=None):
        self.show_model = not self.show_model
        etat = "AFFICHE" if self.show_model else "MASQUE"
        if self.info_callback: self.info_callback(f"[VIEW] Modele mathematique {etat}.", level='info')
        self._sync_ui_state()  # ✨ Sync checkbox state back to UI
        self._update_colors()

    def action_toggle_residuals(self, event=None):
        self.show_residuals = not self.show_residuals
        etat = "RESIDUS (Data - Model)" if self.show_residuals else "DONNEES BRUTES"
        if self.info_callback: self.info_callback(f"[VIEW] {etat}.", level='warning')
        self._sync_ui_state()  # ✨ Sync checkbox state back to UI
        self._update_colors()
    
    def set_residuals_visible_internal(self, visible: bool):
        """Appelé par le routing checkbox - évite duplication avec set_residuals_visible."""
        self.set_residuals_visible(visible)

    def set_model_visible(self, visible: bool):
        self.show_model = visible
        self._update_colors()
        self._sync_ui_state()  # Sync checkbox after programmatic change

    def set_residuals_visible(self, visible: bool):
        self.show_residuals = visible
        self._update_colors()
        self._sync_ui_state()  # Sync checkbox after programmatic change

    def _get_current_y_data(self):
        """Soustraction vectorielle blindée avec gestion de l'amplitude nulle - match C source."""
        if self.show_residuals:
            p_rad, mp_rad = np.radians(self.phase), np.radians(self.modphs)
            re = self.amp * np.cos(p_rad) - self.modamp * np.cos(mp_rad)
            im = self.amp * np.sin(p_rad) - self.modamp * np.sin(mp_rad)
            d_amp = np.sqrt(re**2 + im**2)
            
            # Phase calculation - match C source (uvradplt.c r_vis_phs)
            d_phs_rad = np.where(d_amp < 1e-10, 0.0, np.arctan2(im, re))
            
            # Phase wrapping to [-π, π] range (match C: phs -= twopi * floor(phs/twopi+0.5))
            twopi = 2.0 * np.pi
            d_phs_rad = d_phs_rad - twopi * np.floor(d_phs_rad / twopi + 0.5)
            
            # Phase conjugation for negative U (match C: if(u < 0.0f) phs = -phs)
            u_data = self.data["u"] / 1e6  # Convert from wavelengths to Mλ for comparison
            d_phs_rad = np.where(u_data < 0, -d_phs_rad, d_phs_rad)
            
            # Convert to degrees for display
            d_phs = np.degrees(d_phs_rad)
            
            return d_amp, d_phs
        return self.amp, self.phase

    def _update_colors(self):
        couleurs = np.full(len(self.data["u"]), self.base_color, dtype=object)
        base_size = self.marker_sizes[self.current_size_idx]
        tailles = np.full(len(self.data["u"]), base_size, dtype=float)
        
        # Gestion du focus antenne
        sub_actif = self.liste_subarrays[self.index_subarray_actuel]
        if self.index_antenne_actuelle >= 0:
            ant_cible = self.antennes_par_subarray[sub_actif][self.index_antenne_actuelle]
            m = (self.data["subarray"] == sub_actif) & ((self.data["tel_a"] == ant_cible) | (self.data["tel_b"] == ant_cible))
            couleurs[m], tailles[m] = DesignSystem.PLOT_FOCUS, base_size
        
        d_amp, d_phs = self._get_current_y_data()

        # Update Amplitude
        if self.scat_amp and self.scat_amp.axes: # Sécurité ajoutée
            off = np.column_stack((self.uv_radius, d_amp))
            off[self.masque_flagges] = [np.nan, np.nan]
            self.scat_amp.set_offsets(off)
            self.scat_amp.set_facecolors(couleurs)
            self.scat_amp.set_sizes(tailles)
            self.scat_amp.axes.set_ylabel("Res Amp (Jy)" if self.show_residuals else "Amp (Jy)")

        # Update Phase
        if self.scat_phase:
            off = np.column_stack((self.uv_radius, d_phs))
            off[self.masque_flagges] = [np.nan, np.nan]
            self.scat_phase.set_offsets(off)
            self.scat_phase.set_facecolors(couleurs)
            self.scat_phase.set_sizes(tailles)
            self.scat_phase.axes.set_ylabel("Res Phase (°)" if self.show_residuals else "Phase (°)")

        # Update Modèle Amp
        if self.scat_modamp:
            off_m = np.column_stack((self.uv_radius, self.modamp))
            off_m[self.masque_flagges] = [np.nan, np.nan]
            self.scat_modamp.set_offsets(off_m)
            self.scat_modamp.set_sizes(tailles * 0.8)
            self.scat_modamp.set_visible(self.show_model and not self.show_residuals)

        # Update Modèle Phase
        if self.scat_modphs:
            off_m = np.column_stack((self.uv_radius, self.modphs))
            off_m[self.masque_flagges] = [np.nan, np.nan]
            self.scat_modphs.set_offsets(off_m)
            self.scat_modphs.set_sizes(tailles * 0.8)
            self.scat_modphs.set_visible(self.show_model and not self.show_residuals)

        # Update Erreurs (1/√|w|) - Difmap formula: 1.0/sqrt(fabs(wt))
        if self.scat_err:
            weight = self.data.get('weight', np.ones_like(self.uv_radius))
            # Match C code: check weight != 0 and use fabs() for absolute value
            err_vals = np.where(weight != 0, 1.0 / np.sqrt(np.fabs(weight)), 0.0)
            off_e = np.column_stack((self.uv_radius, err_vals))
            off_e[self.masque_flagges] = [np.nan, np.nan]
            self.scat_err.set_offsets(off_e)
            self.scat_err.set_facecolors(couleurs)
            self.scat_err.set_sizes(tailles)
            
            # Auto-scale error axis limits: errmin=0, errmax=1/sqrt(|wtmin|)
            if self.ax_err and len(weight[weight != 0]) > 0:
                wtmin = np.min(np.fabs(weight[weight != 0]))
                err_max = 1.0 / np.sqrt(wtmin) if wtmin > 0 else 0.0
                self.ax_err.set_ylim([0.0, err_max * 1.1])  # Add 10% margin

        self.fig.canvas.draw_idle()

    def update_marker_size(self, size):
        if size in self.marker_sizes:
            self.current_size_idx = self.marker_sizes.index(size)
        self._update_colors()

    def apply_cut(self, x1, y1, x2, y2):
        xmin, xmax = min(x1, x2), max(x1, x2)
        ymin, ymax = min(y1, y2), max(y1, y2)
        
        d_amp, d_phs = self._get_current_y_data()
        
        # Détecte robustement le type d'axe depuis l'objet event
        y_data = d_phs if hasattr(self, '_last_pressed_axis') and self.axis_type.get(self._last_pressed_axis) == "phase" else d_amp
        
        mask_box = (self.uv_radius >= xmin) & (self.uv_radius <= xmax) & (y_data >= ymin) & (y_data <= ymax)
        masque_final = mask_box & (~self.masque_flagges)
        indices_a_supprimer = np.where(masque_final)[0]
        
        if len(indices_a_supprimer) > 0:
            if self.info_callback: self.info_callback(f"✂ {len(indices_a_supprimer)} points supprimés.", level='success')
            self._flag_indices(indices_a_supprimer)

    def action_show_info(self, event):
        if event.xdata is None or event.ydata is None or event.inaxes is None: return
        x_s, y_s = event.xdata, event.ydata
        
        d_amp, d_phs = self._get_current_y_data()
        # Détecte directement à partir de l'axe reçu
        is_phase_click = event.inaxes == self.ax_phase
        y_data = d_phs if is_phase_click else d_amp
        
        x_span = event.inaxes.get_xlim()[1] - event.inaxes.get_xlim()[0]
        y_span = event.inaxes.get_ylim()[1] - event.inaxes.get_ylim()[0]
        
        norm_dx = (self.uv_radius - x_s) / x_span
        norm_dy = (y_data - y_s) / y_span
        dist_sq = norm_dx**2 + norm_dy**2
        
        idx = np.argmin(dist_sq)
        if dist_sq[idx] > (0.015**2) or self.masque_flagges[idx]: return
            
        sub = self.data.get("subarray", [0]*len(self.uv_radius))[idx]
        nom_a = self.noms_antennes.get(self.data.get("tel_a", [0]*len(self.uv_radius))[idx], "?")
        nom_b = self.noms_antennes.get(self.data.get("tel_b", [0]*len(self.uv_radius))[idx], "?")
        
        lbl_a = "Res Amp" if self.show_residuals else "Amp"
        lbl_p = "Res Phs" if self.show_residuals else "Phase"

        msg = (
            f"--- Quick Inspect (S) ---\n"
            f"Antennas : {sub}:{nom_a}-{nom_b}\n"
            f"Radius   : {self.uv_radius[idx]:.2f} Mλ\n"
            f"{lbl_a:<8} : {d_amp[idx]:.4f} Jy\n"
            f"{lbl_p:<8} : {d_phs[idx]:.1f}°\n"
            f"-------------------------"
        )
        if self.info_callback: self.info_callback(msg, level='inspect')
    
    def apply_stats(self, x1, y1, x2, y2):
        xmin, xmax = min(x1, x2), max(x1, x2)
        ymin, ymax = min(y1, y2), max(y1, y2)
        
        d_amp, d_phs = self._get_current_y_data()
        # Détecte robustement le type d'axe
        is_phase_axis = hasattr(self, '_last_pressed_axis') and self.axis_type.get(self._last_pressed_axis) == "phase"
        y_ref = d_phs if is_phase_axis else d_amp
        
        # ✅ CORRECTION: Vérifier weight > 0 ET que weight existe
        weight = self.data.get('weight', np.ones(len(self.uv_radius)))
        mask = (self.uv_radius >= xmin) & (self.uv_radius <= xmax) & \
               (y_ref >= ymin) & (y_ref <= ymax) & \
               (~self.masque_flagges) & (weight > 0)
        indices = np.where(mask)[0]
        n = len(indices)
        
        if n == 0:
            if self.info_callback: self.info_callback("No visibilities within the selection box.", level='warning')
            return
            
        a_sub = d_amp[indices]
        p_sub = d_phs[indices]
        
        a_mean = np.mean(a_sub)
        a_std = np.std(a_sub, ddof=1) if n > 1 else 0.0
        a_err = a_std / np.sqrt(n) if n > 1 else 0.0
        
        p_mean = np.mean(p_sub)
        p_std = np.std(p_sub, ddof=1) if n > 1 else 0.0
        p_err = p_std / np.sqrt(n) if n > 1 else 0.0
        
        lbl_a = "Res Amp" if self.show_residuals else "Amp"
        lbl_p = "Res Phs" if self.show_residuals else "Phs"

        msg = (
            f"The statistics of the {n} visibilities within the box are:\n"
            f"  {lbl_a} mean = {a_mean:.6f} +/- {a_err:.6f}   RMS scatter = {a_std:.6f}\n"
            f"  {lbl_p} mean = {p_mean:.6f} +/- {p_err:.6f}   RMS scatter = {p_std:.6f}  (degrees)"
        )
        if self.info_callback: self.info_callback(msg, level='stats')

    def apply_stats_vec(self, x1, y1, x2, y2):
        xmin, xmax = min(x1, x2), max(x1, x2)
        ymin, ymax = min(y1, y2), max(y1, y2)

        d_amp, d_phs = self._get_current_y_data()
        # Détecte robustement le type d'axe
        is_phase_axis = hasattr(self, '_last_pressed_axis') and self.axis_type.get(self._last_pressed_axis) == "phase"
        y_ref = d_phs if is_phase_axis else d_amp

        # ✅ CORRECTION: Vérifier weight > 0 ET que weight existe
        weight = self.data.get('weight', np.ones(len(self.uv_radius)))
        mask = (self.uv_radius >= xmin) & (self.uv_radius <= xmax) & \
               (y_ref >= ymin) & (y_ref <= ymax) & \
               (~self.masque_flagges) & (weight > 0)
        indices = np.where(mask)[0]
        n = len(indices)

        if n == 0:
            if self.info_callback: self.info_callback("No visibilities within the selection box.", level='warning')
            return

        a_sub = d_amp[indices]
        p_sub_rad = np.radians(d_phs[indices])

        real_part = a_sub * np.cos(p_sub_rad)
        imag_part = a_sub * np.sin(p_sub_rad)

        r_mean = np.mean(real_part)
        r_std = np.std(real_part, ddof=1) if n > 1 else 0.0
        r_err = r_std / np.sqrt(n) if n > 1 else 0.0

        i_mean = np.mean(imag_part)
        i_std = np.std(imag_part, ddof=1) if n > 1 else 0.0
        i_err = i_std / np.sqrt(n) if n > 1 else 0.0

        msg = (
            f"The VECTOR statistics of the {n} visibilities within the box are:\n"
            f"  Real mean = {r_mean:.6f} +/- {r_err:.6f}   RMS scatter = {r_std:.6f}\n"
            f"  Imag mean = {i_mean:.6f} +/- {i_err:.6f}   RMS scatter = {i_std:.6f}"
        )
        if self.info_callback: self.info_callback(msg, level='stats')
    
    def action_flag_nearest(self, event=None):
        """Touche A : Flag le point le plus proche du curseur"""
        if event is None or event.xdata is None or event.ydata is None:
            if self.info_callback: self.info_callback("Position curseur invalide pour Action A.", level='warning')
            return
        
        x_s, y_s = event.xdata, event.ydata
        d_amp, d_phs = self._get_current_y_data()
        
        # Détecte le type d'axe cliqué
        is_phase_click = event.inaxes == self.ax_phase
        y_data = d_phs if is_phase_click else d_amp
        
        # Calcul normalisé de la distance
        x_span = event.inaxes.get_xlim()[1] - event.inaxes.get_xlim()[0]
        y_span = event.inaxes.get_ylim()[1] - event.inaxes.get_ylim()[0]
        
        norm_dx = (self.uv_radius - x_s) / x_span
        norm_dy = (y_data - y_s) / y_span
        dist_sq = norm_dx**2 + norm_dy**2
        
        idx = np.argmin(dist_sq)
        
        # Vérification: point assez proche (pas au-delà de 1.5% de la plage)
        if dist_sq[idx] > (0.015**2):
            if self.info_callback: self.info_callback("No point close enough to cursor.", level='warning')
            return
        
        # Vérification: point pas déjà flaggé
        if self.masque_flagges[idx]:
            if self.info_callback: self.info_callback("Point already flagged.", level='info')
            return
        
        # Flaguer le point
        self._flag_indices([idx])
        
        # Affiche l'info du point qui a été flaggé
        sub = self.data.get("subarray", [0]*len(self.uv_radius))[idx]
        nom_a = self.noms_antennes.get(self.data.get("tel_a", [0]*len(self.uv_radius))[idx], "?")
        nom_b = self.noms_antennes.get(self.data.get("tel_b", [0]*len(self.uv_radius))[idx], "?")
        
        msg = f"--- Flagged (A) ---\nAntennas: {sub}:{nom_a}-{nom_b}\nRadius: {self.uv_radius[idx]:.2f} Mλ"
        if self.info_callback: self.info_callback(msg, level='success')