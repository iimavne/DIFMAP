# difmap_wrapper/gui/main_window.py
from PyQt6.QtWidgets import QMainWindow, QTabWidget, QFileDialog, QWidget, QMessageBox
from PyQt6.QtCore import Qt, QTimer
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
            # ✅ Charger Stokes I par défaut (comme en difmap classique)
            self.session.obs.select(pol="I")
            
            # Récupérer les nouvelles données
            self.data = difmap_native.get_uv_data()
            
            # ✅ Mettre à jour le combo de polarisation
            self.control_panel.combo_pol.blockSignals(True)
            self.control_panel.combo_pol.setCurrentIndex(0)  # Stokes I est la première option
            self.control_panel.combo_pol.blockSignals(False)
            
            # Rafraîchir tous les plots
            self._reload_all_plots()
            
            self.log_console.log(f"Successfully loaded {len(self.data['u'])} visibilities (Stokes I).")
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
        router = SignalRouter(self)
        tb = self.toolbar

        # ── 1. TOOLBAR — actions de fichier ──────────────────────
        tb.action_load.triggered.connect(self._on_load_triggered)

        def handle_save():
            editor = self._get_active_editor()
            if editor:
                editor.save_callback = self._handle_save_dialog
                editor.action_save()
        tb.action_save.triggered.connect(handle_save)

        # ── 2. TOOLBAR — actions de vue ──────────────────────────
        tb.action_home.triggered.connect(
            lambda: self._get_active_editor().action_home()
            if self._get_active_editor() else None
        )
        tb.action_undo.triggered.connect(
            lambda: self._get_active_editor().action_undo()
            if self._get_active_editor() else None
        )
        tb.action_refresh.triggered.connect(self._sync_all_plots)

        # ── 3. TOOLBAR — menu déroulant d'outils ────────────
        def _on_tool_changed(index):
            if index < 0: return
            mode = tb.combo_tools.itemData(index)
            editor = self._get_active_editor()
            if editor:
                editor._set_mode(mode)
            # Redonner le focus au graphique pour que les raccourcis clavier continuent de fonctionner
            if self._get_active_editor() and hasattr(self._get_active_editor(), 'fig'):
                self._get_active_editor().fig.canvas.setFocus()

        tb.combo_tools.currentIndexChanged.connect(_on_tool_changed)

        # ── 4. TOOLBAR — quick inspect (S) ───────────────────────
        def _quick_inspect():
            editor = self._get_active_editor()
            if editor and hasattr(editor, 'action_show_info_nearest'):
                editor.action_show_info_nearest(None)
        tb.action_inspect.triggered.connect(_quick_inspect)

        # ── 5. TOOLBAR — toggle terminal ─────────────────────────
        tb.action_terminal.triggered.connect(self._toggle_terminal)

        # ── 6. PANNEAU — navigation télescopes ───────────────────
        router.route_button_both('btn_next_sub', 'action_next_subarray', [None])
        router.route_button_both('btn_prev_sub', 'action_prev_subarray', [None])
        router.route_button_both('btn_next_ant', 'action_next_telescope', [None])
        router.route_button_both('btn_prev_ant', 'action_prev_telescope', [None])

        def search_callback():
            target = self.control_panel.input_search_tel.text()
            if target:
                premier_log_fait = False
                for widget in [self.plot_widget, self.radplot_widget]:
                    if widget and hasattr(widget, 'editor') and widget.editor:
                        editor = widget.editor
                        if hasattr(editor, 'action_specific_telescope'):
                            # Astuce : on "mute" les logs du 2ème éditeur pour éviter les doublons
                            callback_sauvegarde = editor.info_callback
                            if premier_log_fait:
                                editor.info_callback = None
                                
                            editor.action_specific_telescope(None, target)
                            
                            # On restaure le micro
                            editor.info_callback = callback_sauvegarde
                            premier_log_fait = True

        self.control_panel.btn_search_tel.clicked.connect(search_callback)
        self.control_panel.input_search_tel.returnPressed.connect(search_callback)
        # ── 7. PANNEAU — cases à cocher & sliders ────────────────
        router.route_checkbox_both('chk_all_channels', 'set_flag_all_channels')
        router.route_checkbox_both('chk_conjugate', 'set_conjugate_visible')
        router.route_checkbox_both('chk_crosshair', 'set_crosshair_visible')
        router.route_slider_both('slider_size', 'update_marker_size')
        router.route_checkbox_both('chk_model', 'set_model_visible')
        router.route_checkbox_both('chk_residuals', 'set_residuals_visible')
        router.route_checkbox_both('chk_errors', 'set_show_errors')

        # ── 8. IMAGERIE & ONGLETS ─────────────────────────────────
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
        Gestionnaire d'état unique adaptatif.
        Cache les menus ou options qui ne servent à rien sur l'onglet actif.
        """
        if index == 0 and self.plot_widget and hasattr(self.plot_widget, 'fig'):
            self.plot_widget.fig.canvas.setFocus()
        elif index == 1 and self.radplot_widget and hasattr(self.radplot_widget, 'fig'):
            self.radplot_widget.fig.canvas.setFocus()

        ctrl, tb = self.control_panel, self.toolbar
        has_data   = self.plot_widget is not None
        is_map     = (index == 2)
        is_radplot = (index == 1)
        is_uv      = (index == 0)

        # ── 1. PANNEAU GAUCHE (Visibilité Contextuelle) ──────────────────────
        ctrl.group_data_selection.setEnabled(has_data)
        
        # On cache entièrement les groupes si ce n'est pas le bon contexte ou si 0 données
        ctrl.group_telescope.setVisible(has_data and not is_map)
        ctrl.group_flagging.setVisible(has_data and not is_map)
        ctrl.group_display.setVisible(has_data and not is_map)
        ctrl.group_imaging.setVisible(has_data)

        # On cache finement les options DANS le menu "DISPLAY OPTIONS"
        if hasattr(ctrl, 'lbl_rad_mode'):
            # Options exclusives au Radplot
            ctrl.lbl_rad_mode.setVisible(has_data and is_radplot)
            ctrl.combo_rad_mode.setVisible(has_data and is_radplot)
            ctrl.sep_display.setVisible(has_data and is_radplot)
            ctrl.chk_model.setVisible(has_data and is_radplot)
            ctrl.chk_residuals.setVisible(has_data and is_radplot)
            ctrl.chk_errors.setVisible(has_data and is_radplot)
            
            # Option exclusive à la Couverture UV
            ctrl.chk_conjugate.setVisible(has_data and is_uv)

        # Synchronisation logique des checks si on change d'onglet
        if is_radplot:
            ctrl.chk_conjugate.setChecked(False)
        if not is_radplot:
            ctrl.chk_model.setChecked(False)
            ctrl.chk_residuals.setChecked(False)
            ctrl.chk_errors.setChecked(False)

        # ── 2. TOOLBAR ─────────────────────────────────────────────
        # ── 2. TOOLBAR (Visibilité Contextuelle) ───────────────────
        tb.action_save.setVisible(has_data)
        tb.action_home.setVisible(has_data and not is_map)
        tb.action_undo.setVisible(has_data and not is_map)
        tb.action_refresh.setVisible(has_data and not is_map)
        tb.action_inspect.setVisible(has_data and not is_map)
        
        # On affiche le menu déroulant uniquement s'il y a des données et qu'on n'est pas sur la Map
        tb.lbl_tools.setVisible(has_data and not is_map)
        tb.combo_tools.setVisible(has_data and not is_map)

        # Peupler dynamiquement le menu déroulant des outils selon l'onglet
        if has_data and not is_map:
            current_mode = tb.combo_tools.currentData()
            
            tb.combo_tools.blockSignals(True)
            tb.combo_tools.clear()
            tb.combo_tools.addItem("None (Inspect)", None)
            tb.combo_tools.addItem("Pan (Move)", "PAN")
            tb.combo_tools.addItem("Zoom Box", "ZOOM")
            tb.combo_tools.addItem("Cut Box", "CUT")
            
            # Outils spécifiques uniquement pour le Radplot !
            if is_radplot:
                tb.combo_tools.addItem("Zoom X (UV Band)", "ZOOM_X")
                tb.combo_tools.addItem("Stats (Scalar)", "STATS")
                tb.combo_tools.addItem("Stats (Vector)", "STATS_V")

            # Restaurer l'outil précédent s'il existe toujours, sinon Select (0)
            idx = tb.combo_tools.findData(current_mode)
            tb.combo_tools.setCurrentIndex(idx if idx >= 0 else 0)
            tb.combo_tools.blockSignals(False)

            editor = self._get_active_editor()
            if editor:
                editor._set_mode(tb.combo_tools.currentData())
            
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
        TBG = "#2a2a2a"
        help_text = f"""
        <style>
          body  {{ background:#1e1e1e; color:#d0d0d0; font-family:sans-serif; }}
          h3    {{ color:#d4a835; }}
          h4    {{ color:#d4a835; margin-top:12px; margin-bottom:4px; }}
          b     {{ color:#e8e8e8; }}
          table {{ background:{TBG}; border-radius:4px; width:100%; }}
          td    {{ padding:3px 6px; color:#c0c0c0; }}
          hr    {{ border-color:#3c3c3c; }}
          i     {{ color:#606060; }}
        </style>
        <h3>DIFMAP Modern — Keyboard Shortcuts</h3>
        <p>Press <b>H</b> at any time in a plot to open this dialog.</p>

        <h4>Navigation & Display</h4>
        <table><tr><td width="90"><b>X / Q</b></td><td>Close plot</td></tr>
        <tr><td><b>R / L</b></td><td>Reset / Refresh view</td></tr>
        <tr><td><b>H</b></td><td>This help dialog</td></tr></table>

        <h4>Telescope Focus</h4>
        <table><tr><td width="90"><b>n / p</b></td><td>Next / Prev antenna</td></tr>
        <tr><td><b>N / P</b></td><td>Next / Prev subarray</td></tr>
        <tr><td><b>T</b></td><td>Search telescope by name/ID</td></tr></table>

        <h4>Editing & Flagging</h4>
        <table><tr><td width="90"><b>A</b></td><td>Flag nearest point</td></tr>
        <tr><td><b>C</b></td><td>Flag rectangular area</td></tr>
        <tr><td><b>Z</b></td><td>Zoom to area</td></tr>
        <tr><td><b>W</b></td><td>Toggle flag-all-channels</td></tr>
        <tr><td><b>U</b></td><td>Undo last flag</td></tr>
        <tr><td><b>Ctrl+S</b></td><td>Save as FITS</td></tr></table>

        <h4>Radplot View</h4>
        <table><tr><td width="90"><b>1 / 2 / 3</b></td><td>Amplitude / Phase / Both</td></tr>
        <tr><td><b>M</b></td><td>Model overlay</td></tr>
        <tr><td><b>-</b></td><td>Residuals (Data − Model)</td></tr>
        <tr><td><b>E</b></td><td>Error plot (1/√w)</td></tr>
        <tr><td><b>U</b></td><td>Zoom UV-radius range</td></tr>
        <tr><td><b>S / V</b></td><td>Scalar / Vector statistics</td></tr></table>

        <h4>UV-plane View</h4>
        <table><tr><td width="90"><b>%</b></td><td>Toggle conjugate points</td></tr>
        <tr><td><b>Z</b></td><td>Zoom to area</td></tr>
        <tr><td><b>S</b></td><td>Show nearest point info</td></tr></table>

        <h4>Style</h4>
        <table><tr><td width="90"><b>+</b></td><td>Toggle crosshair</td></tr>
        <tr><td><b>.</b></td><td>Cycle marker size</td></tr>
        <tr><td><b>M (Pan)</b></td><td>Pan mode</td></tr></table>

        <br><hr>
        <i>Most actions are also accessible via the toolbar and left panel.</i>
        """
        from PyQt6.QtWidgets import QTextBrowser, QDialog, QVBoxLayout

        dialog = QDialog(self)
        dialog.setWindowTitle("Keyboard Shortcuts")
        dialog.resize(520, 620)

        text_browser = QTextBrowser()
        text_browser.setStyleSheet(f"""
            QTextBrowser {{
                background-color: #1e1e1e;
                color: #d0d0d0;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                font-size: 12px;
            }}
        """)
        text_browser.setHtml(help_text)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(text_browser)
        dialog.exec()

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

    def _toggle_terminal(self):
        """Affiche/cache le dock terminal."""
        self.log_console.setVisible(not self.log_console.isVisible())

    def _has_unsaved_changes(self):
        """Vérifie si des flags non sauvegardés existent."""
        if self.plot_widget and self.plot_widget.editor:
            return bool(self.plot_widget.editor.masque_flagges.any())
        return False

    def closeEvent(self, event):
        if self._has_unsaved_changes():
            reply = QMessageBox.question(
                self, "Quitter DIFMAP Modern",
                "Des modifications de flagging n'ont pas été sauvegardées.\n"
                "Êtes-vous sûr de vouloir quitter ?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return
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
            Ex: {'show_errors': True, 'show_model': False, 'display_mode': 3, 'crosshair': True, 'show_conjugate': False}
        """
        # 1. Si on reçoit un état depuis un raccourci clavier, mettre à jour l'UI
        if state_dict:
            ctrl = self.control_panel
            # Block signals to prevent triggering callbacks while updating
            was_blocked_errors = ctrl.chk_errors.blockSignals(True)
            was_blocked_model = ctrl.chk_model.blockSignals(True)
            was_blocked_residuals = ctrl.chk_residuals.blockSignals(True)
            was_blocked_combo = ctrl.combo_rad_mode.blockSignals(True)
            was_blocked_crosshair = ctrl.chk_crosshair.blockSignals(True)
            was_blocked_conjugate = ctrl.chk_conjugate.blockSignals(True)
            
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
                if 'crosshair' in state_dict:
                    ctrl.chk_crosshair.setChecked(state_dict['crosshair'])
                if 'show_conjugate' in state_dict:
                    ctrl.chk_conjugate.setChecked(state_dict['show_conjugate'])
                if 'show_conjugate' in state_dict:
                    ctrl.chk_conjugate.setChecked(state_dict['show_conjugate'])
                if 'marker_size' in state_dict:
                    was_blocked_size = ctrl.slider_size.blockSignals(True)
                    ctrl.slider_size.setValue(state_dict['marker_size'])
                    ctrl.slider_size.blockSignals(was_blocked_size)
                if 'focus_search' in state_dict:
                    ctrl.input_search_tel.setFocus()
                if 'show_help' in state_dict:
                    # QTimer évite un conflit d'événements en ouvrant la fenêtre juste APRES la touche
                    QTimer.singleShot(0, self._show_help_dialog)
            finally:
                # Restore signal blocking state
                ctrl.chk_errors.blockSignals(was_blocked_errors)
                ctrl.chk_model.blockSignals(was_blocked_model)
                ctrl.chk_residuals.blockSignals(was_blocked_residuals)
                ctrl.combo_rad_mode.blockSignals(was_blocked_combo)
                ctrl.chk_crosshair.blockSignals(was_blocked_crosshair)
                ctrl.chk_conjugate.blockSignals(was_blocked_conjugate)
        
        # 2. Sync bouton outil toolbar ← raccourci clavier
        # 2. Sync bouton outil toolbar ← raccourci clavier
        if state_dict and 'tool_mode' in state_dict:
            mode = state_dict['tool_mode']
            tb = self.toolbar
            tb.action_select.setChecked(mode is None)
            tb.action_cut.setChecked(mode == "CUT")
            tb.action_zoom.setChecked(mode == "ZOOM")
            tb.action_pan.setChecked(mode == "PAN")
            if hasattr(tb, 'action_zoom_x'): tb.action_zoom_x.setChecked(mode == "ZOOM_X")
            if hasattr(tb, 'action_stats'): tb.action_stats.setChecked(mode == "STATS")
            if hasattr(tb, 'action_stats_vec'): tb.action_stats_vec.setChecked(mode == "STATS_V")

        # 3. Rafraîchissement visuel normal
        if self.plot_widget and self.plot_widget.editor:
            self.plot_widget.editor._update_colors()
        if self.radplot_widget and self.radplot_widget.editor:
            self.radplot_widget.editor._update_colors()
            
    def _log_event(self, msg, level='info'):
        """Routeur intelligent : dirige le message vers le bon niveau de la console."""
        log_method = getattr(self.log_console, f"log_{level}", self.log_console.log_info)
        log_method(msg)