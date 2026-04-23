# difmap_wrapper/gui/main_window.py
from PyQt6.QtWidgets import QMainWindow, QTabWidget, QFileDialog, QWidget, QMessageBox
from PyQt6.QtCore import Qt, QTimer

from difmap_wrapper import DifmapSession
from difmap_wrapper.enums import TabIndex  
from difmap_wrapper.gui.styles.design_system import DesignSystem
import logging
from difmap_wrapper.gui.log_handler import DifmapLogHandler
from .plot_widget import UVPlotWidget
from .components.improved_log_console import ImprovedLogConsole
from .components.control_panel import ControlPanel
from .components.main_toolbar import MainToolbar
from .map_widget import MapPlotWidget
from .radplot_widget import RadPlotWidget
from .routing.signal_router import SignalRouter



class MainWindow(QMainWindow):
    """
    Fenêtre principale de DIFMAP Modern.

    Orchestre tous les composants de l'interface : onglets de visualisation
    (UV, Radplot, Dirty Map), panneau de contrôle, console de logs et toolbar.
    """

    def __init__(self, fichier_initial=None):
        """
        Parameters
        ----------
        fichier_initial : str, optional
            Chemin vers un fichier FITS à charger automatiquement au démarrage.
        """
        super().__init__()
        self.setWindowTitle("DIFMAP Interface")
        self.resize(1400, 850)
        self.setStyleSheet(DesignSystem.get_full_app_style())

        # 1. Moteur C
        self.session = DifmapSession()
        self.data    = None

        # 2. Composants UI
        self.log_console  = ImprovedLogConsole(parent=self)
        self.difmap_log_handler = DifmapLogHandler()
        logging.getLogger("difmap").setLevel(logging.INFO)
        logging.getLogger("difmap").addHandler(self.difmap_log_handler)
        self.log_console.connect_handler(self.difmap_log_handler)
        self.control_panel = ControlPanel(self.session, parent=self)
        self.toolbar       = MainToolbar(parent=self)
        self.toolbar.add_standard_actions(self)
        self.addToolBar(self.toolbar)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea,  self.control_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.log_console)
        self._create_menu_bar()

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.plot_widget    = None
        self.map_widget     = MapPlotWidget(self)
        self.radplot_widget = RadPlotWidget(
            parent=self,
            sync_callback=self._sync_all_plots,
        )

        self.tabs.addTab(QWidget(),               "UVplot")  # TabIndex.UV
        self.tabs.addTab(self.radplot_widget,      "Radplot")      # TabIndex.RADPLOT
        self.tabs.addTab(self.map_widget,          "Dirty Map")    # TabIndex.MAP

        # 4. Signaux
        self._connect_signals()

        # 5. Chargement initial
        if fichier_initial:
            self._load_file_logic(fichier_initial)

        self._on_tab_changed(TabIndex.UV)
        self.log_console.log("DIFMAP Modern initialized. Ready to observe.")

    # =========================================================
    # CHARGEMENT 
    # =========================================================

    def _load_file_logic(self, filepath: str) -> None:
        """Charge un fichier FITS dans le moteur et rafraîchit l'UI."""
        try:
            self.log_console.log(f"Loading: {filepath}...")
            self.session.observe(filepath)
            self.session.obs.select(pol="I")

            self.data = self.session.obs.get_data()

            self.control_panel.combo_pol.blockSignals(True)
            self.control_panel.combo_pol.setCurrentIndex(0)
            self.control_panel.combo_pol.blockSignals(False)

            self._reload_all_plots()

            n = len(self.data['u'])
            n_sub = len(set(self.data.get('subarray', [])))
            n_ant = len(set(list(self.data.get('tel_a', [])) + list(self.data.get('tel_b', []))))
            self.log_console.log(
                f"Loaded {n:,} visibilities — {n_ant} antennas, {n_sub} subarray(s) — Stokes I."
            )
            self.setWindowTitle(f"DIFMAP Modern - {filepath.split('/')[-1]}")

        except Exception as e:
            self.log_console.log(f"Error loading file: {e}")
            QMessageBox.critical(self, "Load Error", f"Could not load FITS file:\n{e}")

    def _reload_all_plots(self) -> None:
        """
        Premier chargement : crée UVPlotWidget et l'insère dans le bon onglet.
        Rechargements suivants : appelle reload_data() sur le widget existant.
        """
        current_idx = self.tabs.currentIndex()
        if current_idx not in (TabIndex.UV, TabIndex.RADPLOT):
            current_idx = TabIndex.UV

        if self.plot_widget is None:
            # Premier chargement : créer le widget UV et remplacer le placeholder
            self.plot_widget = UVPlotWidget(
                observation=self.session.obs,
                data=self.data,
                save_callback=self._handle_save_dialog,
                sync_callback=self._sync_all_plots,
            )
            self.tabs.removeTab(TabIndex.UV)
            self.tabs.insertTab(TabIndex.UV, self.plot_widget, "UV Coverage")
        else:
            self.plot_widget.reload_data(self.data, self.session.obs)

        # Radplot : plot_data() gère le cas d'un rechargement correctement
        self.radplot_widget.plot_data(
            data=self.data,
            observation=self.session.obs,
        )

        self.tabs.setCurrentIndex(current_idx)
        self._on_tab_changed(current_idx)

    # =========================================================
    # CÂBLAGE SIGNAUX
    # =========================================================

    def _get_active_editor(self):
        """
        Retourne l'éditeur actif sur l'onglet courant.

        Returns
        -------
        UVPlotEditor or RadPlotEditor or None
            L'éditeur de l'onglet sélectionné, ou ``None`` si aucun n'est disponible.
        """
        idx = self.tabs.currentIndex()
        if idx == TabIndex.UV and self.plot_widget:
            return getattr(self.plot_widget, 'editor', None)
        if idx == TabIndex.RADPLOT and self.radplot_widget:
            return getattr(self.radplot_widget, 'editor', None)
        return None

    def _connect_signals(self):
        """
        Câble tous les signaux PyQt6 aux slots correspondants.

        Connecte les actions toolbar, les boutons et checkboxes du panneau
        de contrôle, et les sliders via le :class:`SignalRouter`.
        """
        router = SignalRouter(self)
        tb = self.toolbar

        tb.action_load.triggered.connect(self._on_load_triggered)

        def handle_save():
            editor = self._get_active_editor()
            if editor:
                editor.save_callback = self._handle_save_dialog
                editor.action_save()
        tb.action_save.triggered.connect(handle_save)

        # ✅ CORRECTION 2: Utiliser SafeEditor pour les toolbar actions
        def safe_editor_action(method_name, *args):
            """Pattern SafeEditor: vérifie l'existence avant d'appeler"""
            def _action():
                editor = self._get_active_editor()
                if editor and hasattr(editor, method_name):
                    method = getattr(editor, method_name)
                    if args:
                        method(*args)
                    else:
                        method(None)
            return _action

        tb.action_home.triggered.connect(safe_editor_action('action_home'))
        tb.action_undo.triggered.connect(safe_editor_action('action_undo'))
        tb.action_refresh.triggered.connect(self._sync_all_plots)

        def _on_tool_changed(index):
            if index < 0:
                return
            mode   = tb.combo_tools.itemData(index)
            editor = self._get_active_editor()
            if editor:
                editor._set_mode(mode)
            if editor and hasattr(editor, 'fig'):
                editor.fig.canvas.setFocus()

        tb.combo_tools.currentIndexChanged.connect(_on_tool_changed)

        def _toggle_inspect(checked):
            editor = self._get_active_editor()
            if editor and hasattr(editor, 'action_toggle_inspect'):
                # Synchroniser l'état editor avec l'état du bouton
                if editor.inspect_active != checked:
                    editor.action_toggle_inspect(None)
        tb.action_inspect.toggled.connect(_toggle_inspect)

        tb.action_terminal.triggered.connect(self._toggle_terminal)

        router.route_button_both('btn_next_sub',  'action_next_subarray',  [None])
        router.route_button_both('btn_prev_sub',  'action_prev_subarray',  [None])
        router.route_button_both('btn_next_ant',  'action_next_telescope', [None])
        router.route_button_both('btn_prev_ant',  'action_prev_telescope', [None])

        def search_callback():
            target = self.control_panel.input_search_tel.text()
            if not target:
                return
            for widget in [self.plot_widget, self.radplot_widget]:
                if widget and getattr(widget, 'editor', None):
                    widget.editor.action_specific_telescope(None, target)
                    break  # Chercher dans le première widget actif seulement

        self.control_panel.btn_search_tel.clicked.connect(search_callback)
        self.control_panel.input_search_tel.returnPressed.connect(search_callback)

        # ✅ CORRECTION 3: SYNC CROSSHAIR SUR CHANGEMENT D'ONGLET + CHECKBOX
        # Le crosshair doit être APPLIQUÉ au nouvel onglet quand on change de tab
        def _handle_crosshair_changed(checked):
            """Applique le crosshair à TOUS les éditeurs actifs"""
            for widget in [self.plot_widget, self.radplot_widget]:
                if not widget or not hasattr(widget, 'editor'):
                    continue
                editor = widget.editor
                if not editor or not hasattr(editor, 'cursor_active'):
                    continue  # ✅ Skip si cursor_active n'existe pas
                
                try:
                    if not checked and getattr(editor, 'cursor_active', False):
                        editor.action_toggle_crosshair(None)
                    elif checked and not getattr(editor, 'cursor_active', False):
                        editor.action_toggle_crosshair(None)
                except Exception:
                    pass  # ✅ Silencieusement ignorer les erreurs crosshair
        
        # Maintenant brancher le routeur CUSTOM crosshair (pas le generic route_checkbox_both)
        self.control_panel.chk_crosshair.toggled.connect(_handle_crosshair_changed)

        # Les autres checkboxes peuvent utiliser le routeur générique
        router.route_checkbox_both('chk_all_channels', 'set_flag_all_channels')
        router.route_checkbox_both('chk_conjugate',    'set_conjugate_visible')
        # crosshair est géré au-dessus (custom handler)
        router.route_slider_both  ('slider_size',      'update_marker_size')
        router.route_checkbox_both('chk_model',        'set_model_visible')
        router.route_checkbox_both('chk_residuals',    'set_residuals_visible')
        router.route_checkbox_both('chk_errors',       'set_show_errors')

        # Transparence des points — appliquée à tous les éditeurs actifs
        def _on_alpha_changed(val):
            alpha = val / 100.0
            for editor in (
                self.plot_widget.editor if self.plot_widget else None,
                self.radplot_widget.editor if self.radplot_widget else None,
            ):
                if editor and hasattr(editor, 'update_data_alpha'):
                    editor.update_data_alpha(alpha)
        self.control_panel.slider_alpha.valueChanged.connect(_on_alpha_changed)

        # Couleur des points — appliquée à tous les éditeurs actifs dès la sélection
        def _on_color_selected(color: str):
            for editor in (
                self.plot_widget.editor if self.plot_widget else None,
                self.radplot_widget.editor if self.radplot_widget else None,
            ):
                if editor and hasattr(editor, 'update_data_color'):
                    editor.update_data_color(color)
        self.control_panel.data_color_changed.connect(_on_color_selected)

        self.control_panel.btn_compute.clicked.connect(self._compute_dirty_map)
        self.control_panel.combo_pol.currentTextChanged.connect(self._change_polarization)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.control_panel.combo_rad_mode.currentIndexChanged.connect(
            lambda idx: self.radplot_widget.set_display_mode(idx)
            if self.radplot_widget else None
        )
        
        def _sync_ui_on_tab_change(index):
            """Synchronise les checkboxes et boutons toolbar avec l'état du nouvel onglet actif."""
            try:
                editor = self._get_active_editor()
                if not editor:
                    return
                ctrl = self.control_panel
                ctrl.chk_crosshair.blockSignals(True)
                ctrl.chk_crosshair.setChecked(getattr(editor, 'cursor_active', False))
                ctrl.chk_crosshair.blockSignals(False)
                self.toolbar.action_inspect.blockSignals(True)
                self.toolbar.action_inspect.setChecked(getattr(editor, 'inspect_active', False))
                self.toolbar.action_inspect.blockSignals(False)
            except Exception:
                pass
        
        self.tabs.currentChanged.connect(_sync_ui_on_tab_change)

    # =========================================================
    # MENU ET DIALOGUES
    # =========================================================

    def _on_tab_changed(self, index: int) -> None:
        """
        Met à jour la visibilité des contrôles selon l'onglet actif.

        Adapte dynamiquement la toolbar, le panneau de contrôle et le menu
        déroulant des outils en fonction du contexte (UV, Radplot, Dirty Map).

        Parameters
        ----------
        index : int
            Index du nouvel onglet sélectionné (voir :class:`TabIndex`).
        """
        # M7 : TabIndex remplace les magic ints
        # ✅ CORRECTION 1: Force le focus ET utilise QTimer pour assurer la propagation
        def set_focus_delayed():
            try:
                if index == TabIndex.UV and self.plot_widget and hasattr(self.plot_widget, 'fig'):
                    canvas = self.plot_widget.fig.canvas
                    canvas.setFocus()
                    canvas.raise_()
                elif index == TabIndex.RADPLOT and self.radplot_widget and hasattr(self.radplot_widget, 'fig'):
                    canvas = self.radplot_widget.fig.canvas
                    canvas.setFocus()
                    canvas.raise_()
            except Exception:
                pass  # ✅ Ignorer les erreurs de focus
        
        # ✅ Force le focus après 50ms pour permettre au Qt de finir le changement d'onglet
        QTimer.singleShot(50, set_focus_delayed)

        ctrl = self.control_panel
        tb   = self.toolbar
        has_data   = self.plot_widget is not None
        is_map     = (index == TabIndex.MAP)
        is_radplot = (index == TabIndex.RADPLOT)
        is_uv      = (index == TabIndex.UV)

        ctrl.group_data_selection.setEnabled(has_data)
        ctrl.group_telescope.setVisible(has_data and not is_map)
        ctrl.group_flagging.setVisible(has_data and not is_map)
        ctrl.group_display.setVisible(has_data and not is_map)
        ctrl.group_imaging.setVisible(has_data and is_map)

        if hasattr(ctrl, 'lbl_rad_mode'):
            ctrl.lbl_rad_mode.setVisible(has_data and is_radplot)
            ctrl.combo_rad_mode.setVisible(has_data and is_radplot)
            ctrl.sep_display.setVisible(has_data and is_radplot)
            _mod = self.data.get('modamp') if (has_data and self.data) else None
            has_model = _mod is not None and any(v != 0 for v in _mod)
            ctrl.chk_model.setVisible(has_data and is_radplot and has_model)
            ctrl.chk_residuals.setVisible(has_data and is_radplot and has_model)
            ctrl.chk_errors.setVisible(has_data and is_radplot)
            ctrl.chk_conjugate.setVisible(has_data and is_uv)

        if is_radplot:
            ctrl.chk_conjugate.setChecked(False)
        elif is_uv and self.plot_widget and self.plot_widget.editor:
            # Synchroniser la checkbox avec l'état réel du scatter conjugué
            conj_visible = self.plot_widget.editor.scat_conj.get_visible()
            ctrl.chk_conjugate.blockSignals(True)
            ctrl.chk_conjugate.setChecked(conj_visible)
            ctrl.chk_conjugate.blockSignals(False)
        if not is_radplot:
            ctrl.chk_model.setChecked(False)
            ctrl.chk_residuals.setChecked(False)
            ctrl.chk_errors.setChecked(False)

        tb.action_save.setVisible(has_data)
        tb.action_home.setVisible(has_data and not is_map)
        tb.action_undo.setVisible(has_data and not is_map)
        tb.action_refresh.setVisible(has_data and not is_map)
        tb.action_inspect.setVisible(has_data and not is_map)
        tb.lbl_tools.setVisible(has_data and not is_map)
        tb.combo_tools.setVisible(has_data and not is_map)

        if has_data and not is_map:
            current_mode = tb.combo_tools.currentData()
            tb.combo_tools.blockSignals(True)
            tb.combo_tools.clear()
            tb.combo_tools.addItem("None (Inspect)", None)
            tb.combo_tools.addItem("Pan (Move)", "PAN")
            tb.combo_tools.addItem("Zoom Box",   "ZOOM")
            tb.combo_tools.addItem("Flag Box",   "CUT")
            if is_radplot:
                tb.combo_tools.addItem("Zoom UV range",    "ZOOM_X")
                tb.combo_tools.addItem("Stats (Amp/Phase)", "STATS")
                tb.combo_tools.addItem("Stats (Real/Imag)", "STATS_V")
            idx = tb.combo_tools.findData(current_mode)
            tb.combo_tools.setCurrentIndex(idx if idx >= 0 else 0)
            tb.combo_tools.blockSignals(False)
            editor = self._get_active_editor()
            if editor:
                editor._set_mode(tb.combo_tools.currentData())

    def _create_menu_bar(self):
        """
        Construit la barre de menus (File, Help).

        Entrées créées :

        - **File** : Load FITS, Save as wobs, Exit
        - **Help** : Keyboard Shortcuts
        """
        menubar  = self.menuBar()
        file_menu = menubar.addMenu("File")
        file_menu.addAction("Load FITS...").triggered.connect(self._on_load_triggered)
        file_menu.addAction("Save as wobs...").triggered.connect(
            lambda: self.plot_widget.editor.action_save(None) if self.plot_widget else None
        )
        file_menu.addSeparator()
        file_menu.addAction("Exit (X)").triggered.connect(self.close)
        menubar.addMenu("Help").addAction("Keyboard Shortcuts (H)").triggered.connect(
            self._show_help_dialog
        )

    def _on_load_triggered(self):
        """
        Ouvre un dialogue de sélection de fichier FITS et charge l'observation.

        Accepte les extensions ``.fits``, ``.1`` et ``.SPLIT``.
        Délègue le chargement effectif à :meth:`_load_file_logic`.
        """
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Open UV FITS Observation", "",
            "All files (*);;FITS files (*.fits *.1 *.SPLIT)"
        )
        if filepath:
            self._load_file_logic(filepath)

    def _handle_save_dialog(self, initial_path: str) -> str:
        """
        Ouvre un dialogue de sauvegarde FITS et retourne le chemin choisi.

        Parameters
        ----------
        initial_path : str
            Chemin suggéré comme point de départ dans le dialogue.

        Returns
        -------
        str
            Chemin complet du fichier de destination, ou chaîne vide si annulé.
        """
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save visibilities", initial_path, "FITS (*.fits)"
        )
        return filename

    def _show_help_dialog(self):
        """
        Affiche une boîte de dialogue récapitulant tous les raccourcis clavier.

        La fenêtre est stylisée avec le thème sombre de l'application et
        organisée par catégorie (Navigation, Telescope, Flagging, Radplot, UV, Style).
        """
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
        <h4>Navigation & Display</h4>
        <table>
          <tr><td width="90"><b>X / Q</b></td><td>Close plot</td></tr>
          <tr><td><b>R / L</b></td><td>Reset / Refresh view</td></tr>
          <tr><td><b>H</b></td><td>This help dialog</td></tr>
        </table>
        <h4>Telescope Focus</h4>
        <table>
          <tr><td width="90"><b>n / p</b></td><td>Next / Prev antenna</td></tr>
          <tr><td><b>N / P</b></td><td>Next / Prev subarray</td></tr>
          <tr><td><b>T</b></td><td>Search telescope by name/ID</td></tr>
        </table>
        <h4>Editing & Flagging</h4>
        <table>
          <tr><td width="90"><b>A</b></td><td>Flag nearest point</td></tr>
          <tr><td><b>C</b></td><td>Flag rectangular area</td></tr>
          <tr><td><b>Z</b></td><td>Zoom to area</td></tr>
          <tr><td><b>W</b></td><td>Toggle flag-all-channels</td></tr>
          <tr><td><b>u</b></td><td>Undo last flag</td></tr>
          <tr><td><b>Ctrl+S</b></td><td>Save as FITS</td></tr>
        </table>
        <h4>Radplot View</h4>
        <table>
          <tr><td width="90"><b>1 / 2 / 3</b></td><td>Amplitude / Phase / Both</td></tr>
          <tr><td><b>M</b></td><td>Model overlay</td></tr>
          <tr><td><b>-</b></td><td>Residuals (Data − Model)</td></tr>
          <tr><td><b>E</b></td><td>Error plot (1/√w)</td></tr>
          <tr><td><b>Shift+U</b></td><td>Zoom UV range</td></tr>
          <tr><td><b>S / V</b></td><td>Stats Amp/Phase / Real/Imag</td></tr>
        </table>
        <h4>UV-plane View</h4>
        <table>
          <tr><td width="90"><b>%</b></td><td>Toggle conjugate points</td></tr>
          <tr><td><b>Z</b></td><td>Zoom to area</td></tr>
          <tr><td><b>S</b></td><td>Show nearest point info</td></tr>
        </table>
        <h4>Style</h4>
        <table>
          <tr><td width="90"><b>+</b></td><td>Toggle crosshair</td></tr>
          <tr><td><b>.</b></td><td>Cycle marker size</td></tr>
          <tr><td><b>M (Pan)</b></td><td>Pan mode</td></tr>
        </table>
        <br><hr>
        <i>Most actions are also accessible via the toolbar and left panel.</i>
        """
        from PyQt6.QtWidgets import QTextBrowser, QDialog, QVBoxLayout
        dialog = QDialog(self)
        dialog.setWindowTitle("Keyboard Shortcuts")
        dialog.resize(520, 620)
        text_browser = QTextBrowser()
        text_browser.setStyleSheet("""
            QTextBrowser {
                background-color: #1e1e1e; color: #d0d0d0;
                border: 1px solid #3c3c3c; border-radius: 4px; font-size: 12px;
            }
        """)
        text_browser.setHtml(help_text)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(text_browser)
        dialog.exec()

    # =========================================================
    # MÉTHODES MÉTIER
    # =========================================================

    def _compute_dirty_map(self):
        """
        Calcule la Dirty Map à partir des paramètres saisis dans le panneau.

        Lit ``mapsize``, ``cellsize``, la pondération UV et le taper gaussien
        depuis le ``ControlPanel``, puis exécute le pipeline d'imagerie C :
        ``mapsize → uvweight → uvtaper → invert``.
        Affiche le résultat dans :class:`MapPlotWidget` et bascule sur l'onglet Map.

        Raises
        ------
        Exception
            Tout échec du moteur C déclenche un ``QMessageBox`` d'erreur critique.
        """
        try:
            mapsize  = int(self.control_panel.input_mapsize.text())
            cellsize = float(self.control_panel.input_cellsize.text())
            weight   = self.control_panel.combo_weight.currentText().lower()
            taper_str = self.control_panel.input_taper.text().strip()
            taper_val = float(taper_str) if taper_str else 0.0

            self.log_console.log(
                f"Computing Dirty Map (Size: {mapsize}, Cell: {cellsize}, "
                f"Weight: {weight}, Taper: {taper_val})..."
            )
            self.session.imager.mapsize(mapsize, cellsize)

            if weight == "natural":
                self.session.imager.uvweight(bin_size=0.0,  err_power=-1.0)
            elif weight == "uniform":
                self.session.imager.uvweight(bin_size=2.0,  err_power=0.0)
            elif weight == "briggs":
                self.session.imager.uvweight(bin_size=2.0,  err_power=-1.0)

            if taper_val > 0.0:
                self.session.imager.uvtaper(taper_val, taper_val)
            else:
                self.session.imager.uvtaper(0.0, 0.0)

            self.session.imager.invert()

            # M6 : session.imager.get_map() remplace difmap_native.get_map()
            map_data = self.session.imager.get_map()
            self.map_widget.plot_map(map_data, cellsize)
            self.tabs.setCurrentIndex(TabIndex.MAP)
            self.log_console.log("Dirty Map computed successfully.")

        except Exception as e:
            err_msg = f"Failed to compute map: {e}"
            self.log_console.log(err_msg)
            QMessageBox.critical(self, "Imaging Error", err_msg)

    def _change_polarization(self, pol_text: str) -> None:
        """
        Change la polarisation active et recharge toutes les visualisations.

        Parameters
        ----------
        pol_text : str
            Texte sélectionné dans ``combo_pol`` (ex. ``"Stokes I"``, ``"RR"``, ``"LL"``).
        """
        try:
            pol = "I" if "Stokes I" in pol_text else pol_text.split(" ")[0]
            self.session.obs.select(pol=pol)

            # M6 : get_data() remplace difmap_native.get_uv_data()
            self.data = self.session.obs.get_data()

            if not self.data or len(self.data.get('u', [])) == 0:
                self._log_event(f"No data for {pol}", level='warning')
                return

            base_title = self.windowTitle().split(" [")[0]
            self.setWindowTitle(f"{base_title} [{pol}]")

            if self.plot_widget:
                self._reload_all_plots()

            self._log_event(f"Switched to {pol}", level='success')
        except Exception as e:
            self._log_event(f"Fail: {e}", level='error')

    def _toggle_terminal(self):
        """Bascule la visibilité du panneau de logs (console terminale droite)."""
        self.log_console.setVisible(not self.log_console.isVisible())

    def _has_unsaved_changes(self) -> bool:
        """
        Indique si des opérations de flagging non sauvegardées sont présentes.

        Returns
        -------
        bool
            ``True`` si le masque de flagging contient des modifications non exportées.
        """
        if self.plot_widget and self.plot_widget.editor:
            return bool(self.session.obs.masque_flagges is not None
                        and self.session.obs.masque_flagges.any())
        return False

    def closeEvent(self, event):
        """
        Intercepte la fermeture de l'application.

        Demande confirmation si des modifications non sauvegardées existent,
        puis appelle ``session.cleanup()`` pour libérer les ressources du moteur C.

        Parameters
        ----------
        event : QCloseEvent
            Événement de fermeture Qt.
        """
        if self._has_unsaved_changes():
            reply = QMessageBox.question(
                self, "Quitter DIFMAP Modern",
                "Des modifications de flagging n'ont pas été sauvegardées.\n"
                "Êtes-vous sûr de vouloir quitter ?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return
        self.log_console.log("Shutting down C-Engine...")
        self.session.cleanup()
        event.accept()

    # =========================================================
    # C5 : _sync_all_plots — flux UNIDIRECTIONNEL éditeur → UI
    # =========================================================

    def _sync_all_plots(self, state_dict: dict = None) -> None:
        """
        Synchronise l'UI depuis l'état de l'éditeur.

        C5 — Le flux est strictement unidirectionnel : éditeur → MainWindow → UI.
        blockSignals() empêche que la mise à jour des checkboxes
        déclenche à nouveau les callbacks vers l'éditeur.

        C6 — La clé '_refresh_layout' déclenche le redécoupage des axes
        du Radplot (remplace la remontée d'arbre Qt dans rad_editor.py).
        """
        if state_dict:
            ctrl = self.control_panel

            # Blocage de tous les signaux avant mise à jour
            signals_to_block = [
                ctrl.chk_errors, ctrl.chk_model, ctrl.chk_residuals,
                ctrl.combo_rad_mode, ctrl.chk_crosshair, ctrl.chk_conjugate,
                ctrl.chk_all_channels,
            ]
            saved = {w: w.blockSignals(True) for w in signals_to_block}

            try:
                if 'show_errors' in state_dict:
                    ctrl.chk_errors.setChecked(state_dict['show_errors'])
                if 'show_model' in state_dict:
                    ctrl.chk_model.setChecked(state_dict['show_model'])
                if 'show_residuals' in state_dict:
                    ctrl.chk_residuals.setChecked(state_dict['show_residuals'])
                if 'display_mode' in state_dict:
                    mode_idx = max(0, min(2, state_dict['display_mode'] - 1))
                    ctrl.combo_rad_mode.setCurrentIndex(mode_idx)
                if 'crosshair' in state_dict:
                    ctrl.chk_crosshair.setChecked(state_dict['crosshair'])
                if 'show_conjugate' in state_dict:
                    ctrl.chk_conjugate.setChecked(state_dict['show_conjugate'])
                if 'flag_all_channels' in state_dict:
                    ctrl.chk_all_channels.setChecked(state_dict['flag_all_channels'])
                if 'marker_size' in state_dict:
                    ctrl.slider_size.blockSignals(True)
                    ctrl.slider_size.setValue(state_dict['marker_size'])
                    ctrl.slider_size.blockSignals(False)
                if 'focus_search' in state_dict:
                    ctrl.input_search_tel.setFocus()
                if 'show_help' in state_dict:
                    QTimer.singleShot(0, self._show_help_dialog)
                if 'inspect_active' in state_dict:
                    self.toolbar.action_inspect.blockSignals(True)
                    self.toolbar.action_inspect.setChecked(state_dict['inspect_active'])
                    self.toolbar.action_inspect.blockSignals(False)

                # C6 : _refresh_layout déclenche le redécoupage du Radplot
                # sans que l'éditeur ait besoin de connaître RadPlotWidget
                if state_dict.get('_refresh_layout'):
                    if 'show_errors' in state_dict:
                        self.radplot_widget.set_show_errors(state_dict['show_errors'])
                    if 'display_mode' in state_dict:
                        mode_idx = max(0, min(2, state_dict['display_mode'] - 1))
                        self.radplot_widget.set_display_mode(mode_idx)

            finally:
                for w, was in saved.items():
                    w.blockSignals(was)

        # Rafraîchissement visuel
        if self.plot_widget and self.plot_widget.editor:
            self.plot_widget.editor._update_colors()
        if self.radplot_widget and self.radplot_widget.editor:
            self.radplot_widget.editor._update_colors()

    def _log_event(self, msg: str, level: str = 'info') -> None:
        """Routeur : dirige le message vers le bon niveau de la console."""
        log_method = getattr(self.log_console, f"log_{level}", self.log_console.log_info)
        log_method(msg)
