# difmap_wrapper/gui/main_window.py
from PyQt6.QtWidgets import QMainWindow, QTabWidget, QFileDialog, QWidget, QMessageBox
from PyQt6.QtCore import Qt
from difmap_wrapper import DifmapSession
import difmap_native

from difmap_wrapper.gui.styles.design_system import DesignSystem

from .plot_widget import UVPlotWidget
from .components.improved_log_console import ImprovedLogConsole
from .components.control_panel import ControlPanel
from .components.main_toolbar import MainToolbar
from .map_widget import MapPlotWidget
from .radplot_widget import RadPlotWidget
from .routing.signal_router import SignalRouter 

class MainWindow(QMainWindow):
    def __init__(self, fichier_initial=None):
        super().__init__()
        self.setWindowTitle("DIFMAP Modern")
        self.resize(1400, 850)
        
        # Style global de la fenêtre
        self.setStyleSheet(DesignSystem.get_full_app_style())
        
        # 1. INITIALISATION DU MOTEUR C
        self.session = DifmapSession()
        
        # 2. INSTANCIATION DES COMPOSANTS UI
        self.log_console = ImprovedLogConsole(parent=self)
        self.control_panel = ControlPanel(parent=self)
        self.toolbar = MainToolbar(parent=self)
        self.toolbar.add_standard_actions(self)
        self.addToolBar(self.toolbar)

        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.control_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.log_console)

        self._create_menu_bar()

        # 3. ZONE CENTRALE (Onglets)
        # CRÉATION de l'objet d'abord
        self.tabs = QTabWidget()
        
        self.setCentralWidget(self.tabs)

        # On prépare les conteneurs du plot
        self.plot_widget = None
        self.map_widget = MapPlotWidget(self)
        
        # On passe sync_callback et info_callback normalement
        self.radplot_widget = RadPlotWidget(
            parent=self,
            info_callback=self._log_event,  
            sync_callback=self._sync_all_plots
        )
        
        # On initialise les 3 onglets dans le bon ordre (0, 1, 2)
        self.tabs.addTab(QWidget(), "UV Coverage")               # Index 0
        self.tabs.addTab(self.radplot_widget, "Radplot")         # Index 1
        self.tabs.addTab(self.map_widget, "Dirty Map")           # Index 2
        
        # 4. CÂBLAGE DES SIGNAUX
        self._connect_signals()

        # 5. CHARGEMENT INITIAL
        if fichier_initial:
            self._load_file_logic(fichier_initial)
        
        # 6. GESTIONNAIRE D'ÉTAT (L'appel manuel doit être ici, à la toute fin !)
        self._on_tab_changed(0)
        
        self.log_console.log("DIFMAP Modern initialized. Ready to observe.")

    # ==========================================
    # LOGIQUE DE CHARGEMENT
    # ==========================================
    def _load_file_logic(self, filepath):
        """Logique technique pour charger un fichier dans le moteur et l'UI."""
        try:
            self.log_console.log(f"Loading: {filepath}...")
            
            # Charger dans le moteur C
            self.session.observe(filepath)
            self.session.obs.select(pol="RR")
            
            # Récupérer les nouvelles données
            self.data = difmap_native.get_uv_data()
            
            # Rafraîchir tous les plots
            self._reload_all_plots()
            
            self.log_console.log(f"Successfully loaded {len(self.data['u'])} visibilities.")
            self.setWindowTitle(f"DIFMAP Modern - {filepath.split('/')[-1]}")
            
        except Exception as e:
            self.log_console.log(f"Error loading file: {e}")
            QMessageBox.critical(self, "Load Error", f"Could not load FITS file:\n{e}")
    
    def _reload_all_plots(self):
        """Reconstruit intégralement les graphiques pour éviter les conflits d'événements souris."""
        # 1. On mémorise l'onglet en cours pour ne pas perturber l'astronome
        current_idx = self.tabs.currentIndex()
        if current_idx not in [0, 1]: 
            current_idx = 0
            
        # 2. On supprime les DEUX anciens onglets (Radplot en premier, puis UV)
        self.tabs.removeTab(1)
        self.tabs.removeTab(0)
        
        # 3. Création du NOUVEAU widget UV (Totalement vierge)
        self.plot_widget = UVPlotWidget(
            observation=self.session.obs, 
            data=self.data,
            info_callback=self._log_event,
            save_callback=self._handle_save_dialog,
            sync_callback=self._sync_all_plots
        )
        
        # 4. Création du NOUVEAU widget Radplot (Totalement vierge)
        self.radplot_widget = RadPlotWidget(
            parent=self,
            info_callback=self._log_event,
            sync_callback=self._sync_all_plots
        )
        
        # 5. On les réinsère dans la fenêtre
        self.tabs.insertTab(0, self.plot_widget, "UV Coverage")
        self.tabs.insertTab(1, self.radplot_widget, "Radplot")
        
        # 6. On injecte les données et les masques dans le Radplot
        self.radplot_widget.plot_data(
            data=self.data, 
            shared_mask=self.plot_widget.editor.masque_flagges, 
            shared_history=self.plot_widget.editor.historique_coupes,
            observation=self.session.obs
        )
        
        # 7. On restaure l'affichage et les outils (Pan, Zoom, etc.)
        self.tabs.setCurrentIndex(current_idx)
        self._on_tab_changed(current_idx)



    # ==========================================
    # CÂBLAGE (ROUTING)
    # ==========================================
    def _get_active_editor(self):
        """Retourne l'éditeur de l'onglet actuellement visible."""
        if self.tabs.currentIndex() == 0 and self.plot_widget:
            return getattr(self.plot_widget, 'editor', None)
        elif self.tabs.currentIndex() == 1 and self.radplot_widget:
            return getattr(self.radplot_widget, 'editor', None)
        return None

    def _connect_signals(self):
        """Connecte tous les signaux avec un câblage direct pour la barre d'outils."""
        router = SignalRouter(self)
        
        # 1. ACTIONS INSTANTANÉES DE LA TOOLBAR (Câblage direct et robuste)
        self.toolbar.action_home.triggered.connect(
            lambda: self._get_active_editor().action_home() if self._get_active_editor() else None
        )
        self.toolbar.action_undo.triggered.connect(
            lambda: self._get_active_editor().action_undo() if self._get_active_editor() else None
        )
        
        def handle_save():
            editor = self._get_active_editor()
            if editor:
                # On force l'injection du dialogue PyQt dans l'éditeur actif
                editor.save_callback = self._handle_save_dialog
                editor.action_save()
                
        self.toolbar.action_save.triggered.connect(handle_save)

        self.toolbar.action_refresh.triggered.connect(self._sync_all_plots)
        self.toolbar.action_load.triggered.connect(self._on_load_triggered)
        # 2. MENU DÉROULANT DES OUTILS INTELLIGENT
        def tool_changed(text):
            editor = self._get_active_editor()
            if not editor: return
            
            if "Pan" in text: editor._set_mode("PAN")
            elif "Zoom X" in text: editor._set_mode("ZOOM_X")
            elif "Zoom" in text: editor._set_mode("ZOOM")
            elif "Cut" in text: editor._set_mode("CUT")
            elif "Stats (Scalar)" in text: editor._set_mode("STATS")
            elif "Stats (Vector)" in text: editor._set_mode("STATS_V")
            else: editor._set_mode(None)

        self.toolbar.combo_tools.currentTextChanged.connect(tool_changed)
        
        # 3. PANNEAU DE CONTRÔLE (Télescopes)
        router.route_button_both('btn_next_sub', 'action_next_subarray', [None])
        router.route_button_both('btn_prev_sub', 'action_prev_subarray', [None])
        router.route_button_both('btn_next_ant', 'action_next_telescope', [None])
        router.route_button_both('btn_prev_ant', 'action_prev_telescope', [None])
  
        # 4. RECHERCHE DE TÉLESCOPE
        def search_callback():
            target = self.control_panel.input_search_tel.text()
            if target:
                for widget in [self.plot_widget, self.radplot_widget]:
                    if widget and hasattr(widget, 'editor') and widget.editor:
                        editor = widget.editor
                        if hasattr(editor, 'action_specific_telescope'):
                            editor.action_specific_telescope(None, target)
        
        self.control_panel.btn_search_tel.clicked.connect(search_callback)
        
        # 5. CASES À COCHER & SLIDERS
        router.route_checkbox_both('chk_all_channels', 'set_flag_all_channels')
        router.route_checkbox_both('chk_conjugate', 'set_conjugate_visible')
        router.route_checkbox_both('chk_crosshair', 'set_crosshair_visible')
        router.route_slider_both('slider_size', 'update_marker_size')
        router.route_checkbox_both('chk_model', 'set_model_visible') 
        router.route_checkbox_both('chk_residuals', 'set_residuals_visible')
        router.route_checkbox_both('chk_errors', 'set_show_errors')
        
        # 6. IMAGERIE & ONGLETS
        self.control_panel.btn_compute.clicked.connect(self._compute_dirty_map)
        self.control_panel.combo_pol.currentTextChanged.connect(self._change_polarization)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.control_panel.combo_rad_mode.currentIndexChanged.connect(
            lambda idx: self.radplot_widget.set_display_mode(idx) if self.radplot_widget else None
        )
    # ==========================================
    # MENU ET DIALOGUES
    # ==========================================
    def _on_tab_changed(self, index):
        """
        Gestionnaire d'état unique : active/désactive l'UI selon l'onglet.
        Index 0: UV, Index 1: Radplot, Index 2: Dirty Map
        """
        ctrl, tb = self.control_panel, self.toolbar
        is_map = (index == 2)
        is_radplot = (index == 1)
        
        # 1. GESTION DES GROUPES (Panneau de gauche)
        ctrl.group_telescope.setEnabled(not is_map)
        ctrl.group_flagging.setEnabled(not is_map)
        ctrl.group_display.setEnabled(not is_map)
        
        ctrl.combo_rad_mode.setEnabled(is_radplot)
        
        ctrl.chk_conjugate.setEnabled(not is_map and not is_radplot)
        if is_radplot:
            ctrl.chk_conjugate.setChecked(False)
            
        ctrl.chk_model.setEnabled(is_radplot)
        ctrl.chk_residuals.setEnabled(is_radplot)
        ctrl.chk_errors.setEnabled(is_radplot)
        
        if not is_radplot:
            ctrl.chk_model.setChecked(False)
            ctrl.chk_residuals.setChecked(False)

        # 2. GESTION DE LA TOOLBAR INTELLIGENTE
        tb.action_home.setEnabled(not is_map)
        tb.action_undo.setEnabled(not is_map)
        tb.action_refresh.setEnabled(not is_map)
        
        combo = tb.combo_tools
        combo.setEnabled(not is_map)

        if not is_map:
            # On mémorise l'outil en cours pour ne pas perturber l'utilisateur
            current_tool = combo.currentText()

            # On reconstruit le menu déroulant selon l'onglet
            combo.blockSignals(True)
            combo.clear()
            items = ["None (Inspect)", "Pan (Move)", "Zoom Box", "Cut Box"]

            if is_radplot:
                # On ajoute les outils exclusifs au Radplot !
                items.insert(3, "Zoom X (UV Band)")
                items.extend(["Stats (Scalar)", "Stats (Vector)"])

            combo.addItems(items)

            # On restaure l'outil (s'il existe dans la nouvelle liste)
            if current_tool in items:
                combo.setCurrentText(current_tool)
            else:
                combo.setCurrentIndex(0) # Retour sur "Inspect" par défaut

            combo.blockSignals(False)

            # On force l'éditeur à prendre l'outil sélectionné
            self.toolbar.combo_tools.currentTextChanged.emit(combo.currentText())
            
    def _create_menu_bar(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")
        
        action_load = file_menu.addAction("Load FITS...")
        action_load.triggered.connect(self._on_load_triggered)
        
        action_save = file_menu.addAction("Save as wobs...")
        action_save.triggered.connect(lambda: self.plot_widget.editor.action_save(None) if self.plot_widget else None)
        
        file_menu.addSeparator()
        action_exit = file_menu.addAction("Exit (X)")
        action_exit.triggered.connect(self.close)

        help_menu = menubar.addMenu("Help")
        help_menu.addAction("Keyboard Shortcuts (H)").triggered.connect(self._show_help_dialog)

    def _on_load_triggered(self):
        """Slot appelé quand on clique sur Load FITS."""
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Open FITS Observation", "", "FITS files (*.fits *.1 *.SPLIT);;All files (*)"
        )
        if filepath:
            self._load_file_logic(filepath)

    def _handle_save_dialog(self, initial_path):
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save visibilities", initial_path, "FITS (*.fits)"
        )
        return filename

    def _show_help_dialog(self):
        help_text = """
        <h3>DIFMAP SmartEdit - Shortcuts</h3>
        <table border="0" cellpadding="4" cellspacing="0">
            <tr><td width="50"><b>S</b></td><td>Inspect Visibilities (Hover mouse)</td></tr>
            <tr><td><b>Z</b></td><td>Toggle Zoom mode (Left click/Drag to select)</td></tr>
            <tr><td><b>C</b></td><td>Toggle Cut/Flag mode (Left click to select area)</td></tr>
            <tr><td><b>U</b></td><td>Undo last flagging operation</td></tr>
            <tr><td><b>L</b></td><td>Refresh / Redraw plot</td></tr>
            <tr><td><b>N / P</b></td><td>Next / Previous Subarray</td></tr>
            <tr><td><b>n / p</b></td><td>Next / Previous Antenna in current Subarray</td></tr>
            <tr><td><b>W</b></td><td>Toggle Channel Flagging scope</td></tr>
            <tr><td><b>+</b></td><td>Toggle Crosshair cursor</td></tr>
            <tr><td><b>.</b></td><td>Toggle Marker size</td></tr>
            <tr><td><b>%</b></td><td>Toggle Conjugate points (-U, -V)</td></tr>
        </table>
        <br><hr>
        <i>Note: Most of these actions are also accessible via the UI panels.</i>
        """
        QMessageBox.about(self, "Help", help_text)

    # ==========================================
    # MÉTHODES MÉTIER (À CONNECTER PLUS TARD)
    # ==========================================
    def _compute_dirty_map(self):
        try:
            # 1. Récupération des paramètres de l'UI
            mapsize = int(self.control_panel.input_mapsize.text())
            cellsize = float(self.control_panel.input_cellsize.text())
            weight = self.control_panel.combo_weight.currentText().lower()
            
            # Récupération sécurisée du Taper
            taper_str = self.control_panel.input_taper.text().strip()
            taper_val = float(taper_str) if taper_str else 0.0

            self.log_console.log(f"Computing Dirty Map (Size: {mapsize}, Cell: {cellsize}, Weight: {weight}, Taper: {taper_val})...")
            
            # 2. Configuration du moteur d'imagerie
            self.session.imager.mapsize(mapsize, cellsize)
            
            # --- LE TRADUCTEUR DE POIDS (Weighting) ---
            if weight == "natural":
                self.session.imager.uvweight(bin_size=0.0, err_power=-1.0)
            elif weight == "uniform":
                self.session.imager.uvweight(bin_size=2.0, err_power=0.0)
            elif weight == "briggs":
                # Combinaison classique pour un compromis Résolution/Bruit
                self.session.imager.uvweight(bin_size=2.0, err_power=-1.0) 
            
            # --- L'APPLICATION DU TAPER ---
            if taper_val > 0.0:
                # Applique un taper symétrique (X et Y identiques)
                self.session.imager.uvtaper(taper_val, taper_val)
            else:
                self.session.imager.uvtaper(0.0, 0.0)
            
            # 3. Calcul de l'inversion de Fourier
            self.session.imager.invert()
            
            # 4. Récupération des données 2D
            map_data = difmap_native.get_map() 
            
            # 5. Affichage graphique
            self.map_widget.plot_map(map_data, cellsize)
            
            # Bascule automatiquement sur le 3ème onglet
            self.tabs.setCurrentIndex(2)
            self.log_console.log("Dirty Map computed successfully.")
            
        except Exception as e:
            err_msg = f"Failed to compute map: {e}"
            self.log_console.log(err_msg)
            QMessageBox.critical(self, "Imaging Error", err_msg)
            
    def _change_polarization(self, pol_text):
        try:
            # 1. Moteur C : On change la pol et on récupère la RAM
            pol = "I" if "Stokes I" in pol_text else pol_text.split(" ")[0]
            self.session.obs.select(pol=pol)
            self.data = difmap_native.get_uv_data()
            
            if not self.data or len(self.data.get('u', [])) == 0:
                self._log_event(f"No data for {pol}", level='warning')
                return

            # 2. On met à jour le titre de la fenêtre avec la nouvelle polarisation
            base_title = self.windowTitle().split(" [")[0]
            self.setWindowTitle(f"{base_title} [{pol}]")
            
            # 3. On recrée tous les graphiques de zéro
            if self.plot_widget:
                self._reload_all_plots()
            
            self._log_event(f"Switched to {pol}", level='success')
        except Exception as e:
            self._log_event(f"Fail: {e}", level='error')

    def closeEvent(self, event):
        self.log_console.log("Shutting down C-Engine...")
        self.session.cleanup()
        event.accept()


    def _sync_all_plots(self, state_dict=None):
        """
        Synchronise tous les plots et optionnellement met à jour l'UI.
        
        Parameters
        ----------
        state_dict : dict, optional
            Si fourni, contient l'état de l'éditeur depuis un raccourci clavier.
            Ex: {'show_errors': True, 'show_model': False, 'display_mode': 3}
        """
        # 1. Si on reçoit un état depuis un raccourci clavier, mettre à jour l'UI
        if state_dict:
            ctrl = self.control_panel
            # Block signals to prevent triggering callbacks while updating
            was_blocked_errors = ctrl.chk_errors.blockSignals(True)
            was_blocked_model = ctrl.chk_model.blockSignals(True)
            was_blocked_residuals = ctrl.chk_residuals.blockSignals(True)
            was_blocked_combo = ctrl.combo_rad_mode.blockSignals(True)
            
            try:
                # Update checkboxes based on editor state
                if 'show_errors' in state_dict:
                    ctrl.chk_errors.setChecked(state_dict['show_errors'])
                if 'show_model' in state_dict:
                    ctrl.chk_model.setChecked(state_dict['show_model'])
                if 'show_residuals' in state_dict:
                    ctrl.chk_residuals.setChecked(state_dict['show_residuals'])
                if 'display_mode' in state_dict:
                    # display_mode: 1->index 0, 2->index 1, 3->index 2
                    mode_idx = max(0, min(2, state_dict['display_mode'] - 1))
                    ctrl.combo_rad_mode.setCurrentIndex(mode_idx)
            finally:
                # Restore signal blocking state
                ctrl.chk_errors.blockSignals(was_blocked_errors)
                ctrl.chk_model.blockSignals(was_blocked_model)
                ctrl.chk_residuals.blockSignals(was_blocked_residuals)
                ctrl.combo_rad_mode.blockSignals(was_blocked_combo)
        
        # 2. Rafraîchissement visuel normal
        if self.plot_widget and self.plot_widget.editor:
            self.plot_widget.editor._update_colors()
        if self.radplot_widget and self.radplot_widget.editor:
            self.radplot_widget.editor._update_colors()
            
    def _log_event(self, msg, level='info'):
        """Routeur intelligent : dirige le message vers le bon niveau de la console."""
        log_method = getattr(self.log_console, f"log_{level}", self.log_console.log_info)
        log_method(msg)