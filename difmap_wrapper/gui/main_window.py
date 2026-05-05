# difmap_wrapper/gui/main_window.py
import re
import difmap_native

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
from .map_widget import DirtyMapPlotWidget, CleanMapPlotWidget, ResidualMapPlotWidget
from .radplot_widget import RadPlotWidget
from .routing.signal_router import SignalRouter
from .header_widget import HeaderWidget



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
        self._bulk_reloading = False  # bloque _sync_all_plots pendant les rechargements

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
        self.control_panel.setMinimumWidth(250)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.log_console)
        self._create_menu_bar()

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.plot_widget          = None
        self.map_widget           = DirtyMapPlotWidget(self)
        self.clean_map_widget     = CleanMapPlotWidget(self)
        self.residual_map_widget  = ResidualMapPlotWidget(self)
        self.radplot_widget    = RadPlotWidget(
            parent=self,
            sync_callback=self._sync_all_plots,
        )
        self.header_widget  = HeaderWidget(self.session, parent=self)

        self.tabs.addTab(QWidget(),                   "UVplot")       # TabIndex.UV       = 0
        self.tabs.addTab(self.radplot_widget,          "Radplot")      # TabIndex.RADPLOT  = 1
        self.tabs.addTab(self.map_widget,              "Dirty Map")    # TabIndex.MAP      = 2
        self.tabs.addTab(self.clean_map_widget,        "Clean Map")    # TabIndex.CLEAN    = 3
        self.tabs.addTab(self.residual_map_widget,     "Residual Map") # TabIndex.RESIDUAL = 4
        self.tabs.addTab(self.header_widget,           "Header")       # TabIndex.HEADER   = 5

        self._help_dialog_open = False   # garde anti-ouvertures multiples

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
            available_pols = self.session.obs.available_polarizations()
            preferred_pol = "I" if "I" in available_pols else (available_pols[0] if available_pols else "I")
            self.control_panel.set_available_polarizations(available_pols, current=preferred_pol)

            actual_pol = self.session.obs.select(pol=preferred_pol)

            self.data = self.session.obs.get_data()

            self.control_panel.set_available_polarizations(available_pols, current=actual_pol)

            # Configurer le sélecteur d'IFs (obs.nif évite de scanner data['if_no'])
            n_ifs = self.session.obs.nif
            if n_ifs:
                self.control_panel.set_if_range(n_ifs)

            self._reload_all_plots()
            self.header_widget.refresh()

            n = len(self.data['u'])
            subarrays = self.data.get('subarray', [])
            tel_a = self.data.get('tel_a', [])
            tel_b = self.data.get('tel_b', [])

            # Les IDs tel_a/tel_b sont locaux a chaque subarray.
            # Pour afficher un nombre coherent avec le tableau des stations
            # du header UVFITS, on compte d'abord les stations physiques
            # directement dans le texte du header.
            station_names = set()
            station_fallback = set()
            station_line = re.compile(
                r"^\s*\d+\s+([A-Za-z0-9_+\-]+)\s+[-+0-9.eE]+\s+[-+0-9.eE]+\s+[-+0-9.eE]+\s*$"
            )

            try:
                header_text = self.session.obs.header()
            except Exception:
                header_text = ""

            for line in header_text.splitlines():
                match = station_line.match(line)
                if match:
                    station_names.add(match.group(1))

            unique_subarrays = sorted({int(sub) for sub in subarrays})

            # Fallback si le header ne fournit pas le tableau complet.
            if not station_names:
                for sub in unique_subarrays:
                    mask = subarrays == sub
                    antennas = set(int(ta) for ta in tel_a[mask]) | set(int(tb) for tb in tel_b[mask])
                    for ant in antennas:
                        station_fallback.add((sub, ant))
                        try:
                            name = self.session.obs._native.get_telescope_name(sub - 1, ant).strip()
                        except Exception:
                            name = ""
                        if name and name != "INCONNU":
                            station_names.add(name)

            n_sub = len(unique_subarrays)
            n_ant = len(station_names) if station_names else len(station_fallback)
            self.log_console.log(
                f"Loaded {n:,} visibilities — {n_ant} antennas, {n_sub} subarray(s), "
                f"{n_ifs} IF(s) — {actual_pol}."
            )
            self.setWindowTitle(f"DIFMAP Modern - {filepath.split('/')[-1]}")

        except Exception as e:
            self.log_console.log(f"Error loading file: {e}")
            QMessageBox.critical(self, "Load Error", f"Could not load FITS file:\n{e}")

    def _reload_all_plots(self) -> None:
        """
        Premier chargement : crée UVPlotWidget et l'insère dans le bon onglet.
        Rechargements suivants : appelle reload_data() sur le widget existant.

        _bulk_reloading bloque _sync_all_plots pendant que les deux widgets
        sont mis à jour, évitant les IndexError de masque_flagges.
        """
        self._bulk_reloading = True
        try:
            current_idx = self.tabs.currentIndex()
            if current_idx not in (TabIndex.UV, TabIndex.RADPLOT):
                current_idx = TabIndex.UV

            if self.plot_widget is None:
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

            self.radplot_widget.plot_data(
                data=self.data,
                observation=self.session.obs,
            )

            self.tabs.setCurrentIndex(current_idx)
            self._on_tab_changed(current_idx)
        finally:
            self._bulk_reloading = False

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

        Les actions vue (Undo/Reset/Refresh/Tool) sont désormais dans la toolbar
        locale de chaque widget de plot. Ici on câble uniquement : Load/Save,
        Terminal, panneau de contrôle et signaux cross-plot.
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
                    break

        self.control_panel.btn_search_tel.clicked.connect(search_callback)
        self.control_panel.input_search_tel.returnPressed.connect(search_callback)

        def clear_telescope_focus():
            for widget in [self.plot_widget, self.radplot_widget]:
                if widget and getattr(widget, 'editor', None):
                    widget.editor.action_clear_focus()

        self.control_panel.btn_clear_focus.clicked.connect(clear_telescope_focus)

        def _handle_crosshair_changed(checked):
            for widget in [self.plot_widget, self.radplot_widget]:
                if not widget or not hasattr(widget, 'editor'):
                    continue
                editor = widget.editor
                if not editor or not hasattr(editor, 'cursor_active'):
                    continue
                try:
                    if not checked and getattr(editor, 'cursor_active', False):
                        editor.action_toggle_crosshair(None)
                    elif checked and not getattr(editor, 'cursor_active', False):
                        editor.action_toggle_crosshair(None)
                except Exception:
                    pass

        self.control_panel.chk_crosshair.toggled.connect(_handle_crosshair_changed)

        router.route_checkbox_both('chk_conjugate',  'set_conjugate_visible')
        router.route_slider_both  ('slider_size',    'update_marker_size')
        router.route_checkbox_both('chk_model',      'set_model_visible')
        router.route_checkbox_both('chk_residuals',  'set_residuals_visible')
        router.route_checkbox_both('chk_errors',     'set_show_errors')

        def _on_alpha_changed(val):
            alpha = val / 100.0
            for editor in (
                self.plot_widget.editor if self.plot_widget else None,
                self.radplot_widget.editor if self.radplot_widget else None,
            ):
                if editor and hasattr(editor, 'update_data_alpha'):
                    editor.update_data_alpha(alpha)
        self.control_panel.slider_alpha.valueChanged.connect(_on_alpha_changed)

        def _on_color_selected(color: str):
            for editor in (
                self.plot_widget.editor if self.plot_widget else None,
                self.radplot_widget.editor if self.radplot_widget else None,
            ):
                if editor and hasattr(editor, 'update_data_color'):
                    editor.update_data_color(color)
        self.control_panel.data_color_changed.connect(_on_color_selected)

        self.control_panel.btn_compute.clicked.connect(self._compute_dirty_map)
        self.control_panel.btn_compute_clean.clicked.connect(self._compute_clean_map)
        self.control_panel.combo_pol.currentTextChanged.connect(self._change_polarization)
        self.control_panel.ifs_range_changed.connect(self._on_ifs_range_changed)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.control_panel.combo_rad_mode.currentIndexChanged.connect(
            lambda idx: self.radplot_widget.set_display_mode(idx)
            if self.radplot_widget else None
        )

        def _sync_ui_on_tab_change(index):
            """Synchronise les checkboxes avec l'état du nouvel onglet actif."""
            try:
                editor = self._get_active_editor()
                if not editor:
                    return
                ctrl = self.control_panel
                ctrl.chk_crosshair.blockSignals(True)
                ctrl.chk_crosshair.setChecked(getattr(editor, 'cursor_active', False))
                ctrl.chk_crosshair.blockSignals(False)
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
                pass  
            
        QTimer.singleShot(50, set_focus_delayed)

        ctrl = self.control_panel
        tb   = self.toolbar
        has_data   = self.plot_widget is not None
        is_map     = index in (TabIndex.MAP, TabIndex.CLEAN, TabIndex.RESIDUAL)
        is_radplot = (index == TabIndex.RADPLOT)
        is_uv      = (index == TabIndex.UV)
        is_header  = (index == TabIndex.HEADER)

        # Rafraîchissement automatique quand on bascule sur l'onglet Header
        if is_header:
            self.header_widget.refresh()

        ctrl.group_data_selection.setEnabled(has_data and not is_header)
        ctrl.group_telescope.setVisible(has_data and not is_map and not is_header)
        ctrl.group_display.setVisible(has_data and not is_map and not is_header)
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
            ctrl.chk_conjugate.blockSignals(True)
            ctrl.chk_conjugate.setChecked(False)
            ctrl.chk_conjugate.blockSignals(False)
        elif is_uv and self.plot_widget and self.plot_widget.editor:
            conj_visible = self.plot_widget.editor.scat_conj.get_visible()
            ctrl.chk_conjugate.blockSignals(True)
            ctrl.chk_conjugate.setChecked(conj_visible)
            ctrl.chk_conjugate.blockSignals(False)
        if not is_radplot:
            ctrl.chk_model.setChecked(False)
            ctrl.chk_residuals.setChecked(False)
            ctrl.chk_errors.setChecked(False)

        tb.action_save.setVisible(has_data)

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

        Un garde empêche l'ouverture de plusieurs fenêtres simultanées.
        """
        if self._help_dialog_open:
            return
        self._help_dialog_open = True

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
          <tr><td width="90"><b>X / Q</b></td><td>Fermer le graphique</td></tr>
          <tr><td><b>R</b></td><td>Reset vue (tous les graphiques)</td></tr>
          <tr><td><b>L</b></td><td>Rafraîchir l'affichage</td></tr>
          <tr><td><b>O</b></td><td>Dézoomer de 50 %</td></tr>
          <tr><td><b>H</b></td><td>Cette fenêtre d'aide</td></tr>
        </table>
        <h4>Focus Télescope</h4>
        <table>
          <tr><td width="90"><b>n / p</b></td><td>Antenne suivante / précédente</td></tr>
          <tr><td><b>N / P</b></td><td>Sous-réseau suivant / précédent</td></tr>
          <tr><td><b>T</b></td><td>Rechercher télescope par nom/ID</td></tr>
        </table>
        <h4>Édition & Flagging</h4>
        <table>
          <tr><td width="90"><b>A</b></td><td>Flagguer le point le plus proche</td></tr>
          <tr><td><b>C</b></td><td>Flagguer zone rectangulaire</td></tr>
          <tr><td><b>F</b></td><td>Flagging interactif (gauche=flag, droit=unflag)</td></tr>
          <tr><td><b>Z</b></td><td>Zoom sur zone</td></tr>
          <tr><td><b>u / Ctrl+Z</b></td><td>Annuler le dernier flagging</td></tr>
          <tr><td><b>Ctrl+S</b></td><td>Sauvegarder en FITS</td></tr>
        </table>
        <h4>Radplot</h4>
        <table>
          <tr><td width="90"><b>1 / 2 / 3</b></td><td>Amplitude / Phase / Les deux</td></tr>
          <tr><td><b>M</b></td><td>Superposition du modèle</td></tr>
          <tr><td><b>-</b></td><td>Résidus (Data − Modèle)</td></tr>
          <tr><td><b>E</b></td><td>Graphe d'erreurs (1/√w)</td></tr>
          <tr><td><b>U (Shift+U)</b></td><td>Zoom X — plage UV (horizontal)</td></tr>
          <tr><td><b>Y (Shift+Y)</b></td><td>Zoom Y — axe vertical</td></tr>
          <tr><td><b>S / V</b></td><td>Stats Amp/Phase / Réel/Imag</td></tr>
        </table>
        <h4>Plan UV</h4>
        <table>
          <tr><td width="90"><b>%</b></td><td>Afficher/masquer conjugués</td></tr>
          <tr><td><b>s</b></td><td>Mode Inspect (clic = info point)</td></tr>
        </table>
        <h4>Style</h4>
        <table>
          <tr><td width="90"><b>+</b></td><td>Crosshair plein écran</td></tr>
          <tr><td><b>.</b></td><td>Taille des marqueurs</td></tr>
          <tr><td><b>M</b></td><td>Mode Pan (déplacement vue)</td></tr>
        </table>
        <br><hr>
        <i>La plupart des actions sont aussi accessibles via la toolbar locale au-dessus de chaque graphique.</i>
        """
        from PyQt6.QtWidgets import QTextBrowser, QDialog, QVBoxLayout
        dialog = QDialog(self)
        dialog.setWindowTitle("Keyboard Shortcuts")
        dialog.resize(520, 650)
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
        dialog.finished.connect(lambda _: setattr(self, '_help_dialog_open', False))
        dialog.exec()

    # =========================================================
    # MÉTHODES MÉTIER
    # =========================================================

    def _apply_imaging_params(self) -> tuple:
        """
        Lit les paramètres d'imagerie du panneau et les applique au moteur C.

        Returns
        -------
        tuple
            ``(mapsize, cellsize, taper_val)`` pour usage par les appelants.
        """
        mapsize   = int(self.control_panel.input_mapsize.text())
        cellsize  = float(self.control_panel.input_cellsize.text())
        weight    = self.control_panel.combo_weight.currentText().lower()
        taper_str = self.control_panel.input_taper.text().strip()
        taper_val = float(taper_str) if taper_str else 0.0

        self.session.imager.mapsize(mapsize, cellsize)

        if weight == "none":
            # Ne rien appliquer - utiliser les paramètres par défaut de Difmap
            pass
        elif weight == "natural":
            self.session.imager.uvweight(bin_size=0.0, err_power=-2.0)  # difmap: uvweight 0,-2
        elif weight == "uniform":
            self.session.imager.uvweight(bin_size=2.0, err_power=0.0)
        elif weight == "briggs":
            self.session.imager.uvweight(bin_size=2.0, err_power=-1.0)

        if taper_val > 0.0:
            self.session.imager.uvtaper(taper_val, taper_val)
        else:
            self.session.imager.uvtaper(0.0, 0.0)

        return mapsize, cellsize, taper_val

    def _compute_dirty_map(self):
        """
        Calcule la Dirty Map (inversion FFT uniquement) et l'affiche dans l'onglet
        dédié. Ne lance pas CLEAN ni restore().
        """
        try:
            mapsize, cellsize, taper_val = self._apply_imaging_params()
            weight = self.control_panel.combo_weight.currentText().lower()
            self.log_console.log(
                f"Computing Dirty Map — size: {mapsize}, cell: {cellsize} mas, "
                f"weight: {weight}, taper: {taper_val} Mλ ..."
            )
            self.session.imager.invert()

            img_dict = self.session.imager.get_map_package(cellsize)
            self.map_widget.plot_map(
                img_dict['data'], cellsize,
                extent=img_dict.get('extent'),
            )
            self.tabs.setCurrentIndex(TabIndex.MAP)
            self.log_console.log("Dirty Map computed successfully.")

        except Exception as e:
            err_msg = f"Failed to compute Dirty Map: {e}"
            self.log_console.log(err_msg)
            QMessageBox.critical(self, "Imaging Error", err_msg)

    def _compute_clean_map(self):
        """
        Calcule la Clean Map restaurée (invert → clean → restore) et l'affiche
        dans l'onglet Clean Map dédié. Distinct de la Dirty Map.
        """
        try:
            niter = int(self.control_panel.input_niter.text())
            gain  = float(self.control_panel.input_gain.text())
            mapsize, cellsize, taper_val = self._apply_imaging_params()
            contour_mode, contour_absmin, contour_absmax, contour_factor, contour_custom = (
                self.control_panel.get_contour_params()
            )
            weight = self.control_panel.combo_weight.currentText().lower()
            self.log_console.log(
                f"Computing Clean Map — size: {mapsize}, cell: {cellsize} mas, "
                f"weight: {weight}, taper: {taper_val} Mλ, "
                f"niter: {niter}, gain: {gain} ..."
            )
            self.session.imager.invert()
            self.session.imager.clean(niter, gain)
            # Le résiduel est capturé automatiquement dans restore()
            self.session.imager.restore()

            # --- Clean Map ---
            img_dict = self.session.imager.get_map_package(cellsize)
            self.clean_map_widget.plot_map(
                img_dict['data'], cellsize,
                beam_info=img_dict['info'],
                windows=img_dict.get('windows', []),
                extent=img_dict.get('extent'),
                contour_mode=contour_mode,
                contour_absmin=contour_absmin,
                contour_absmax=contour_absmax,
                contour_factor=contour_factor,
                contour_custom=contour_custom,
            )

            # --- Residual Map ---
            try:
                res_dict = self.session.imager.get_residual_package(cellsize)
                self.residual_map_widget.plot_map(
                    res_dict['data'], cellsize,
                    extent=res_dict.get('extent'),
                    contour_mode=contour_mode,
                    contour_absmin=contour_absmin,
                    contour_absmax=contour_absmax,
                    contour_factor=contour_factor,
                    contour_custom=contour_custom,
                )
            except Exception:
                pass  # Ne pas bloquer si le résiduel est indisponible

            self.tabs.setCurrentIndex(TabIndex.CLEAN)
            peak_flux = float(img_dict['data'].max())
            rms = img_dict['info'].get('rms', 0.0)
            self.log_console.log(
                f"Clean Map restored — peak: {peak_flux:.4f} Jy/beam, "
                f"rms: {rms:.4f} Jy/beam, "
                f"windows: {len(img_dict.get('windows', []))}."
            )

        except Exception as e:
            err_msg = f"Failed to compute Clean Map: {e}"
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
            actual_pol = self.session.obs.select(pol=pol)

            # Si fallback, resynchroniser le combo sans déclencher de signal
            if actual_pol != pol:
                self.control_panel.combo_pol.blockSignals(True)
                self.control_panel.combo_pol.setCurrentText(actual_pol)
                self.control_panel.combo_pol.blockSignals(False)

            self.data = self.session.obs.get_data()

            if not self.data or len(self.data.get('u', [])) == 0:
                self._log_event(f"No data for {actual_pol}", level='warning')
                return

            # ob_select remet g_if_beg=0/g_if_end=-1 → resync spinners
            self.control_panel.set_if_range(self.session.obs.nif)

            base_title = self.windowTitle().split(" [")[0]
            self.setWindowTitle(f"{base_title} [{actual_pol}]")

            if self.plot_widget:
                self._reload_all_plots()

            self._log_event(f"Switched to {actual_pol}", level='success')
        except Exception as e:
            self._log_event(f"Fail: {e}", level='error')

    def _on_ifs_range_changed(self, if_beg: int, if_end: int) -> None:
        """Applique la plage d'IFs via obs.set_if_range() (pas d'ob_select côté C)."""
        if self.data is None or not self.plot_widget:
            return
        try:
            # set_if_range : juste met à jour g_if_beg/g_if_end — zéro I/O disque
            self.session.obs.set_if_range(if_beg, if_end)
            self.data = self.session.obs.get_data()
            self._reload_all_plots()
            n = len(self.data.get('u', []))
            n_tot = self.control_panel._n_ifs_total
            end_str = str(if_end) if if_end != 0 else f"{n_tot} (all)"
            self.log_console.log(
                f"IF range: {if_beg} → {end_str} — {n:,} visibilities."
            )
        except Exception as e:
            self.log_console.log(f"IF selection error: {e}")

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

        Ignoré pendant _bulk_reloading (les deux widgets ne sont pas encore
        tous les deux à jour — évite les IndexError de masque_flagges).
        """
        if self._bulk_reloading:
            return
        if state_dict:
            ctrl = self.control_panel

            # ── Reset tous les graphiques ──────────────────────────
            if state_dict.get('reset_all'):
                for widget in [self.plot_widget, self.radplot_widget]:
                    editor = getattr(widget, 'editor', None) if widget else None
                    if not editor or not editor.original_limits:
                        continue
                    editor.ax.set_xlim(editor.original_limits[0])
                    editor.ax.set_ylim(editor.original_limits[1])
                    if hasattr(editor, '_orig_ylim_phase') and getattr(editor, 'ax_phase', None):
                        if editor._orig_ylim_phase:
                            editor.ax_phase.set_ylim(editor._orig_ylim_phase)
                    if hasattr(editor, '_orig_ylim_err') and getattr(editor, 'ax_err', None):
                        if editor._orig_ylim_err:
                            editor.ax_err.set_ylim(editor._orig_ylim_err)
                    editor.index_antenne_actuelle = -1
                    editor._nom_antenne_courante = ""
                    editor.index_subarray_actuel = 0
                    editor._update_colors()
                return  # le redraw est déjà fait dans _update_colors

            # Blocage de tous les signaux avant mise à jour
            signals_to_block = [
                ctrl.chk_errors, ctrl.chk_model, ctrl.chk_residuals,
                ctrl.combo_rad_mode, ctrl.chk_crosshair, ctrl.chk_conjugate,
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
                if 'marker_size' in state_dict:
                    ctrl.slider_size.blockSignals(True)
                    ctrl.slider_size.setValue(state_dict['marker_size'])
                    ctrl.slider_size.blockSignals(False)
                if 'focus_search' in state_dict:
                    ctrl.input_search_tel.setFocus()
                if 'show_help' in state_dict:
                    QTimer.singleShot(0, self._show_help_dialog)
                if 'inspect_active' in state_dict:
                    # Synchronise le combo de la toolbar locale
                    for widget in [self.plot_widget, self.radplot_widget]:
                        if widget and hasattr(widget, 'sync_inspect_state'):
                            widget.sync_inspect_state(state_dict['inspect_active'])

                if 'active_tool' in state_dict:
                    for widget in [self.plot_widget, self.radplot_widget]:
                        if widget and hasattr(widget, 'sync_tool_state'):
                            widget.sync_tool_state(state_dict['active_tool'])

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
