# difmap_wrapper/gui/main_window.py
import re
import numpy as np
import difmap_native

from PyQt6.QtWidgets import QMainWindow, QTabWidget, QFileDialog, QWidget, QMessageBox, QGridLayout
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal

from difmap_wrapper import DifmapSession
from difmap_wrapper.types import TabIndex  
from difmap_wrapper.gui.styles import DesignSystem
import logging
from difmap_wrapper.gui.utils import DifmapLogHandler
from .widgets.plot_widget import UVPlotWidget
from .widgets.log_console import ImprovedLogConsole
from .widgets.control_panel import ControlPanel
from .widgets.main_toolbar import MainToolbar
from .widgets.map_widget import DirtyMapPlotWidget, CleanMapPlotWidget, ResidualMapPlotWidget
from .widgets.radplot_widget import RadPlotWidget
from .utils import SignalRouter
from .widgets.header_widget import HeaderWidget



class CleanWorker(QThread):
    """Exécute le CLEAN difmap en arrière-plan, itération par chunk."""
    progress = pyqtSignal(int, int)   # (done, total)
    paused   = pyqtSignal(int, int)   # (done, total) when a conditional breakpoint is reached
    finished = pyqtSignal()
    error    = pyqtSignal(str)

    def __init__(self, imager, niter, gain, cutoff, chunk_size=50, pause_after=0):
        super().__init__()
        self._imager     = imager
        self._niter      = niter
        self._gain       = gain
        self._cutoff     = cutoff
        self._chunk_size = chunk_size
        self._pause_after = pause_after   # 0 = no conditional breakpoint
        self._done   = 0
        self._paused = False
        self._abort  = False
        self._cutoff_reached = False

    def request_pause(self):
        self._paused = True

    def request_resume(self):
        self._paused = False

    def abort(self):
        self._abort  = True
        self._paused = False

    def run(self):
        try:
            while self._done < self._niter and not self._abort:
                while self._paused and not self._abort:
                    self.msleep(50)
                if self._abort:
                    break
                chunk = min(self._chunk_size, self._niter - self._done)
                if self._pause_after > 0:
                    since_last = self._done % self._pause_after
                    to_bp = (self._pause_after - since_last) if since_last else self._pause_after
                    chunk = min(chunk, to_bp)
                self._imager.clean(chunk, self._gain, self._cutoff)
                self._done += chunk
                self.progress.emit(self._done, self._niter)

                if self._cutoff > 0:
                    try:
                        peak_info = self._imager.peak()
                        if peak_info and float(peak_info.get('flux', 0.0)) <= float(self._cutoff):
                            self._cutoff_reached = True
                            break
                    except Exception:
                        pass
                if self._pause_after > 0 and self._done % self._pause_after == 0 and self._done < self._niter:
                    self._paused = True
                    self.paused.emit(self._done, self._niter)
            if not self._abort:
                self.finished.emit()
        except Exception as exc:
            self.error.emit(str(exc))


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
        self.toolbar.setStyleSheet(DesignSystem.get_unified_toolbar_style())
        self.addToolBar(self.toolbar)
        self.menuBar().setVisible(False)  # remplacé par la toolbar unifiée
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea,  self.control_panel)
        self.control_panel.setMinimumWidth(330)
        self.control_panel.setMaximumWidth(520)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.log_console)

        # ── Widgets de contenu ────────────────────────────────────────
        self.plot_widget          = None
        self.map_widget           = DirtyMapPlotWidget(self, show_annotations=True)
        self.clean_map_widget     = CleanMapPlotWidget(self, show_annotations=True)
        self.residual_map_widget  = ResidualMapPlotWidget(self, show_annotations=True)

        self.all_maps_widget = QWidget(self)
        all_maps_layout = QGridLayout(self.all_maps_widget)
        all_maps_layout.setContentsMargins(10, 10, 10, 10)
        all_maps_layout.setHorizontalSpacing(10)
        all_maps_layout.setVerticalSpacing(10)
        self.all_maps_residual_widget = ResidualMapPlotWidget(
            self.all_maps_widget, show_annotations=True, show_tools=True
        )
        self.all_maps_dirty_widget = DirtyMapPlotWidget(
            self.all_maps_widget, show_annotations=False, show_tools=False
        )
        self.all_maps_clean_widget = CleanMapPlotWidget(
            self.all_maps_widget, show_annotations=False, show_tools=False
        )
        all_maps_layout.addWidget(self.all_maps_residual_widget, 0, 0, 2, 1)
        all_maps_layout.addWidget(self.all_maps_dirty_widget,    0, 1, 1, 1)
        all_maps_layout.addWidget(self.all_maps_clean_widget,    1, 1, 1, 1)
        all_maps_layout.setColumnStretch(0, 3)
        all_maps_layout.setColumnStretch(1, 2)
        all_maps_layout.setRowStretch(0, 1)
        all_maps_layout.setRowStretch(1, 1)
        self.radplot_widget    = RadPlotWidget(
            parent=self,
            sync_callback=self._sync_all_plots,
        )
        self.header_widget  = HeaderWidget(self.session, parent=self)

        # ── Sous-onglets "Graphiques" ──────────────────────────────
        self.inner_graphiques = QTabWidget()
        self.inner_graphiques.setStyleSheet(DesignSystem.get_inner_tab_style())
        self.inner_graphiques.addTab(QWidget(),             "UV Plan")      # inner 0 → UV=0
        self.inner_graphiques.addTab(self.radplot_widget,   "Radplot")      # inner 1 → RADPLOT=1

        # ── Sous-onglets "Imagerie" ────────────────────────────────
        self.inner_imagerie = QTabWidget()
        self.inner_imagerie.setStyleSheet(DesignSystem.get_inner_tab_style())
        self.inner_imagerie.addTab(self.map_widget,          "Dirty Map")     # inner 0
        self.inner_imagerie.addTab(self.residual_map_widget, "Residual Map")  # inner 1
        self.inner_imagerie.addTab(self.clean_map_widget,    "Clean Map")     # inner 2
        self.inner_imagerie.addTab(self.all_maps_widget,     "All Maps")      # inner 3

        # ── Super-onglets (outer) ──────────────────────────────────
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(DesignSystem.get_outer_tab_style())
        self.tabs.addTab(self.header_widget,    "Header")      # outer 0 = OUTER_HEADER
        self.tabs.addTab(self.inner_graphiques, "Graphiques")  # outer 1 = OUTER_GRAPHIQUES
        self.tabs.addTab(self.inner_imagerie,   "Imagerie")    # outer 2 = OUTER_IMAGERIE
        self.setCentralWidget(self.tabs)

        self._help_dialog_open = False   # garde anti-ouvertures multiples

        self._last_clean_package = None
        self._last_dirty_package = None
        self._last_added_window = None
        self._clean_worker = None
        self._last_mapsize_params = None   # (mapsize, cellsize) last sent to C
        self._last_uvtaper_params = None   # (taper_amp, taper_val) last sent to C

        # 4. Signaux
        self._connect_signals()

        # 5. Chargement initial
        if fichier_initial:
            self._load_file_logic(fichier_initial)

        self._on_tab_changed(TabIndex.UV)
        self.log_console.log("DIFMAP Modern initialized. Ready to observe.")

    # =========================================================
    # NAVIGATION ONGLETS (flat index ↔ outer+inner)
    # =========================================================

    def _get_logical_tab(self) -> int:
        """Retourne l'index logique (TabIndex.*) à partir de l'état outer+inner."""
        outer = self.tabs.currentIndex()
        if outer == TabIndex.OUTER_GRAPHIQUES:
            return self.inner_graphiques.currentIndex()  # UV=0, RADPLOT=1
        elif outer == TabIndex.OUTER_IMAGERIE:
            return (TabIndex.MAP, TabIndex.RESIDUAL, TabIndex.CLEAN, TabIndex.ALL_MAPS)[
                self.inner_imagerie.currentIndex()
            ]
        else:
            return TabIndex.HEADER

    def _set_logical_tab(self, idx: int) -> None:
        """Positionne outer+inner à partir d'un index logique (TabIndex.*)."""
        if idx in (TabIndex.UV, TabIndex.RADPLOT):
            self.tabs.setCurrentIndex(TabIndex.OUTER_GRAPHIQUES)
            self.inner_graphiques.setCurrentIndex(idx)
        elif idx == TabIndex.MAP:
            self.tabs.setCurrentIndex(TabIndex.OUTER_IMAGERIE)
            self.inner_imagerie.setCurrentIndex(0)
        elif idx == TabIndex.RESIDUAL:
            self.tabs.setCurrentIndex(TabIndex.OUTER_IMAGERIE)
            self.inner_imagerie.setCurrentIndex(1)
        elif idx == TabIndex.CLEAN:
            self.tabs.setCurrentIndex(TabIndex.OUTER_IMAGERIE)
            self.inner_imagerie.setCurrentIndex(2)
        elif idx == TabIndex.ALL_MAPS:
            self.tabs.setCurrentIndex(TabIndex.OUTER_IMAGERIE)
            self.inner_imagerie.setCurrentIndex(3)
        elif idx == TabIndex.HEADER:
            self.tabs.setCurrentIndex(TabIndex.OUTER_HEADER)

    # =========================================================
    # CHARGEMENT
    # =========================================================

    def _load_file_logic(self, filepath: str) -> None:
        """Charge un fichier FITS dans le moteur et rafraîchit l'UI."""
        try:
            self.log_console.log(f"Loading: {filepath}...")
            from PyQt6.QtWidgets import QApplication
            QApplication.processEvents()  # force immediate log display before C operation
            self.session.observe(filepath)
            # Remettre à zéro l'état UI qui appartient à la session précédente.
            # reset_state() synchronise les miroirs Python avec le C qui vient de
            # réinitialiser invpar=invdef, et efface les fenêtres CLEAN de la
            # session précédente (active_windows + vlbwins via delwin()).
            self.session.imager.reset_state()
            try:
                self.session.imager.delwin()
            except Exception:
                pass
            self._last_clean_package = None
            self._last_mapsize_params = None
            self._last_uvtaper_params = None
            self._set_selfcal_ready(False)
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

            # Caler les sliders UV sur la plage réelle des données (signée)
            try:
                import numpy as np
                u_ml = self.data['u'] / 1e6
                v_ml = self.data['v'] / 1e6
                margin = 0.05
                u_span = float(np.max(u_ml) - np.min(u_ml)) * margin
                v_span = float(np.max(v_ml) - np.min(v_ml)) * margin
                self.control_panel.set_uv_data_range(
                    float(np.min(u_ml)) - u_span, float(np.max(u_ml)) + u_span,
                    float(np.min(v_ml)) - v_span, float(np.max(v_ml)) + v_span,
                )
            except Exception:
                pass

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
            current_idx = self._get_logical_tab()
            if current_idx not in (TabIndex.UV, TabIndex.RADPLOT):
                current_idx = TabIndex.UV

            if self.plot_widget is None:
                self.plot_widget = UVPlotWidget(
                    observation=self.session.obs,
                    data=self.data,
                    save_callback=self._handle_save_dialog,
                    sync_callback=self._sync_all_plots,
                )
                self.inner_graphiques.removeTab(0)  # UV placeholder
                self.inner_graphiques.insertTab(0, self.plot_widget, "UV Plan")
            else:
                self.plot_widget.reload_data(self.data, self.session.obs)

            self.radplot_widget.plot_data(
                data=self.data,
                observation=self.session.obs,
            )

            for tw in (self.tabs, self.inner_graphiques, self.inner_imagerie):
                tw.blockSignals(True)
            self._set_logical_tab(current_idx)
            for tw in (self.tabs, self.inner_graphiques, self.inner_imagerie):
                tw.blockSignals(False)
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
        idx = self._get_logical_tab()
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

        tb.action_help.triggered.connect(self._show_help_dialog)
        tb.action_exit.triggered.connect(self.close)
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
                    if hasattr(editor, 'set_crosshair_visible'):
                        editor.set_crosshair_visible(checked)
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

        self.control_panel.uv_limits_changed.connect(self._on_uv_limits_changed)
        self.control_panel.rad_limits_changed.connect(self._on_rad_limits_changed)
        self.control_panel.btn_compute.clicked.connect(self._compute_dirty_map)
        try:
            if self.control_panel.btn_apply_imaging.isVisible():
                self.control_panel.btn_apply_imaging.clicked.connect(self._on_apply_imaging)
        except Exception:
            pass
        self.control_panel.btn_compute_clean.clicked.connect(self._start_clean)
        self.control_panel.btn_restore.clicked.connect(self._run_restore)
        self.control_panel.btn_run_selfcal.clicked.connect(self._run_selfcal)
        self._set_selfcal_ready(False)  # désactivé jusqu'au premier CLEAN
        self.control_panel.chk_show_model_map.toggled.connect(self._on_show_model_map_changed)
        self.control_panel.colormap_changed.connect(self._on_colormap_changed)
        self.control_panel.show_windows_changed.connect(self._on_show_windows_changed)
        self.control_panel.combo_pol.currentTextChanged.connect(self._change_polarization)
        self.control_panel.ifs_range_changed.connect(self._on_ifs_range_changed)

        # Auto-refresh des cartes quand les paramètres d'affichage changent.
        # Ne recalcul pas la carte (pas de CLEAN), seulement un re-render.
        try:
            self.control_panel.combo_scale.currentIndexChanged.connect(self._refresh_current_map_tab)
            self.control_panel.input_vmin.editingFinished.connect(self._refresh_current_map_tab)
            self.control_panel.input_vmax.editingFinished.connect(self._refresh_current_map_tab)

            self.control_panel.combo_contour_mode.currentIndexChanged.connect(self._refresh_current_map_tab)
            self.control_panel.input_absmin.editingFinished.connect(self._refresh_current_map_tab)
            self.control_panel.input_absmax.editingFinished.connect(self._refresh_current_map_tab)
            self.control_panel.input_factor.editingFinished.connect(self._refresh_current_map_tab)
            self.control_panel.input_custom_levels.editingFinished.connect(self._refresh_current_map_tab)
        except Exception:
            pass
        
        def _on_any_tab_changed(_):
            self._on_tab_changed(self._get_logical_tab())

        self.tabs.currentChanged.connect(_on_any_tab_changed)
        self.inner_graphiques.currentChanged.connect(_on_any_tab_changed)
        self.inner_imagerie.currentChanged.connect(_on_any_tab_changed)

        self.control_panel.combo_rad_mode.currentIndexChanged.connect(
            lambda idx: self.radplot_widget.set_display_mode(idx)
            if self.radplot_widget else None
        )

        def _sync_ui_on_tab_change(_):
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
        self.inner_graphiques.currentChanged.connect(_sync_ui_on_tab_change)
        self.inner_imagerie.currentChanged.connect(_sync_ui_on_tab_change)

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
        is_map     = index in (TabIndex.MAP, TabIndex.CLEAN, TabIndex.RESIDUAL, TabIndex.ALL_MAPS)
        is_radplot = (index == TabIndex.RADPLOT)
        is_uv      = (index == TabIndex.UV)
        is_header  = (index == TabIndex.HEADER)

        # Détection modèle via le compteur C (équivalent ob->hasmod de difmap_src).
        # Utilisé à la fois pour Radplot et pour les cartes (overlay composantes).
        has_model = False
        if has_data and hasattr(self, 'session') and self.session:
            try:
                has_model = len(self.session.imager.get_model_components()) > 0
            except Exception:
                has_model = False

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

            # Si on arrive sur le radplot avec un modèle dont modamp n'est pas encore
            # dans les données cachées, on rafraîchit self.data (déclenche moddif() côté C)
            # puis on recharge le widget — comportement identique à ob->hasmod=1 dans
            # uvradplt.c qui force le tracé du modèle à la prochaine commande radplot.
            if is_radplot and has_model and self.session and self.radplot_widget:
                _mod = self.data.get('modamp') if self.data else None
                _modamp_stale = (_mod is None or not np.any(np.asarray(_mod) != 0))
                if _modamp_stale:
                    try:
                        self.data = self.session.obs.get_data()
                        self.radplot_widget.plot_data(
                            data=self.data,
                            observation=self.session.obs,
                        )
                    except Exception:
                        pass

            ctrl.chk_model.setVisible(has_data and is_radplot and has_model)
            ctrl.chk_residuals.setVisible(has_data and is_radplot and has_model)
            ctrl.chk_errors.setVisible(has_data and is_radplot)
            ctrl.chk_conjugate.setVisible(has_data and is_uv)

        # Sections de limites contextuelles
        if hasattr(ctrl, '_uv_limits_section'):
            ctrl._uv_limits_section.setVisible(has_data and is_uv)
        if hasattr(ctrl, '_rad_limits_section'):
            ctrl._rad_limits_section.setVisible(has_data and is_radplot)

        # Sous-sections Imaging contextuelles (Dirty / Residual / Clean / All Maps)
        if is_map and has_data:
            is_dirty     = (index == TabIndex.MAP)
            is_residual  = (index == TabIndex.RESIDUAL)
            is_clean_map = (index == TabIndex.CLEAN)
            is_all_maps  = (index == TabIndex.ALL_MAPS)
            for attr, visible in [
                ('_imaging_params_section',  True),
                ('_dirty_btn_section',       is_dirty),
                ('_clean_controls_section',  is_residual or is_clean_map or is_all_maps),
                ('_selfcal_section',         is_residual or is_clean_map),
                ('_map_display_section',     True),
                ('_display_windows_section', is_residual or is_clean_map or is_all_maps),
                ('_display_clean_section',   is_clean_map or is_all_maps),
            ]:
                w = getattr(ctrl, attr, None)
                if w is not None:
                    w.setVisible(visible)

            # All Maps : on ne veut pas d'options Dirty (bouton invert + options spécifiques)
            if is_all_maps:
                try:
                    ctrl._dirty_btn_section.setVisible(False)
                except Exception:
                    pass

        # Show Model Components : visible sur toutes les cartes, grisée si pas de modèle
        ctrl.chk_show_model_map.setVisible(is_map)
        ctrl.chk_show_model_map.setEnabled(is_map and has_model)
        if is_map and not has_model:
            ctrl.chk_show_model_map.setToolTip("Aucun modèle — lancez CLEAN d'abord")
        else:
            ctrl.chk_show_model_map.setToolTip("Afficher les composantes CLEAN sur la carte")

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
            for chk in [ctrl.chk_model, ctrl.chk_residuals, ctrl.chk_errors]:
                chk.blockSignals(True)
                chk.setChecked(False)
                chk.blockSignals(False)

        tb.action_save.setVisible(has_data)

        if has_data and index == TabIndex.ALL_MAPS:
            try:
                self._refresh_all_maps()
            except Exception:
                pass

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
        text_browser.setStyleSheet(f"""
            QTextBrowser {
                background-color: {DesignSystem.TERMINAL_BG};
                color: {DesignSystem.TERMINAL_TEXT};
                border: 1px solid {DesignSystem.TERMINAL_BORDER};
                border-radius: {DesignSystem.RADIUS_MD};
                font-size: {DesignSystem.FONT_SIZE_BASE};
                padding: 10px;
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
        try:
            mapsize = int(self.control_panel.input_mapsize.text())
            if mapsize <= 0:
                raise ValueError(f"mapsize doit être > 0, obtenu: {mapsize}")
        except ValueError as exc:
            raise ValueError(f"Mapsize invalide: {exc}") from exc
        try:
            cellsize = float(self.control_panel.input_cellsize.text())
            if cellsize <= 0:
                raise ValueError(f"cellsize doit être > 0, obtenu: {cellsize}")
        except ValueError as exc:
            raise ValueError(f"Cellsize invalide: {exc}") from exc
        weight    = self.control_panel.combo_weight.currentText().lower()
        taper_str = self.control_panel.input_taper.text().strip()
        try:
            taper_val = float(taper_str) if taper_str else 0.0
            if taper_val < 0:
                raise ValueError(f"taper doit être ≥ 0, obtenu: {taper_val}")
        except ValueError as exc:
            raise ValueError(f"Taper invalide: {exc}") from exc
        taper_amp_str = self.control_panel.input_taper_amp.text().strip()
        try:
            taper_amp = float(taper_amp_str) if taper_amp_str else 0.0
            if taper_amp != 0.0 and not (0.0 < taper_amp < 0.99):
                raise ValueError(f"amplitude taper doit être dans ]0, 0.99[, obtenu: {taper_amp}")
        except ValueError as exc:
            raise ValueError(f"Amplitude taper invalide: {exc}") from exc

        if taper_val > 0.0 and taper_amp == 0.0:
            raise ValueError(
                "Taper: si Rayon (Mλ) > 0, alors Valeur doit être renseignée (]0, 1[)."
            )

        if self._last_mapsize_params != (mapsize, cellsize):
            self.session.imager.mapsize(mapsize, cellsize)
            self._last_mapsize_params = (mapsize, cellsize)

        if weight == "uniform":
            self.session.imager.uvweight(bin_size=2.0, err_power=0.0)
        elif weight == "natural":
            self.session.imager.uvweight(bin_size=0.0, err_power=-2.0)
        elif weight == "custom":
            try:
                custom_bin = float(self.control_panel.input_weight_bin.text() or "2.0")
                custom_err = float(self.control_panel.input_weight_err.text() or "0.0")
            except ValueError:
                raise ValueError("Poids Custom invalide — vérifiez Bin et ErrPow.")
            self.session.imager.uvweight(bin_size=custom_bin, err_power=custom_err)

        new_taper = (taper_amp, taper_val)
        if self._last_uvtaper_params != new_taper:
            if taper_val > 0.0:
                self.session.imager.uvtaper(gaussian_value=taper_amp, gaussian_radius_wav=taper_val)
            else:
                self.session.imager.uvtaper(gaussian_value=0.0, gaussian_radius_wav=0.0)
            self._last_uvtaper_params = new_taper

        uvmin_wav = 0.0
        uvmax_wav = 0.0
        try:
            if self.control_panel.chk_uv_filter.isChecked():
                t = self.control_panel.input_uvfilter_min.text().strip()
                uvmin_wav = float(t) * 1e6 if t else 0.0
                t = self.control_panel.input_uvfilter_max.text().strip()
                uvmax_wav = float(t) * 1e6 if t else 0.0
        except (ValueError, AttributeError):
            pass

        return mapsize, cellsize, taper_val, uvmin_wav, uvmax_wav

    def _compute_dirty_map(self):
        """
        Calcule la Dirty Map (inversion FFT uniquement) et l'affiche dans l'onglet
        dédié. Ne lance pas CLEAN ni restore().
        """
        try:
            mapsize, cellsize, taper_val, uvmin_wav, uvmax_wav = self._apply_imaging_params()
            weight = self.control_panel.combo_weight.currentText().lower()
            self.log_console.log(
                f"Computing Dirty Map — size: {mapsize}, cell: {cellsize} mas, "
                f"weight: {weight}, taper: {taper_val} Mλ ..."
            )
            self.session.imager.invert(uvmin_wav, uvmax_wav)

            # Rendre le résiduel disponible immédiatement (avant CLEAN) :
            # utile pour l'onglet Residual et pour certaines actions dépendantes du résiduel.
            try:
                self.session.imager.snapshot_residual_from_current_map()
            except Exception:
                pass

            img_dict = self.session.imager.get_map_package(cellsize)
            # Suivre la maquette: Dirty Map n'expose pas Scale/Min/Max/Contours.
            # On force donc un rendu auto (linear + vmin/vmax auto) et pas de contours.
            scale, vmin, vmax = 'linear', None, None
            contour_mode, contour_absmin, contour_absmax, contour_factor, contour_custom = 'none', 1.0, 100.0, 2.0, None
            self.map_widget.plot_map(
                img_dict['data'], cellsize,
                extent=img_dict.get('extent'),
                scale=scale, vmin=vmin, vmax=vmax,
                contour_mode=contour_mode, contour_absmin=contour_absmin,
                contour_absmax=contour_absmax, contour_factor=contour_factor,
                contour_custom=contour_custom
            )

            # Pré-rendre l'onglet Residual (identique à la dirty au départ) pour
            # éviter un onglet vide lors du premier switch.
            try:
                self._refresh_residual_map()
            except Exception:
                pass
            self._set_logical_tab(TabIndex.MAP)
            self.log_console.log("Dirty Map computed successfully.")

        except Exception as e:
            err_msg = f"Failed to compute Dirty Map: {e}"
            self.log_console.log(err_msg)
            QMessageBox.critical(self, "Imaging Error", err_msg)

    def _start_clean(self):
        """Lance ou reprend le CLEAN de façon asynchrone via CleanWorker (QThread)."""
        if (self._clean_worker is not None
                and self._clean_worker.isRunning()
                and getattr(self._clean_worker, '_paused', False)):
            self._clean_worker.request_resume()
            self.control_panel.btn_compute_clean.setText("⏳  Running...")
            self.control_panel.btn_compute_clean.setEnabled(False)
            self.log_console.log("CLEAN repris.")
            return
        try:
            try:
                niter = int(self.control_panel.input_niter.text())
                if niter <= 0:
                    raise ValueError(f"Niter doit être > 0, obtenu: {niter}")
            except ValueError:
                raise ValueError("Niter invalide — entrez un entier strictement positif.")
            try:
                gain = float(self.control_panel.input_gain.text())
                if not (0.0 < gain <= 1.0):
                    raise ValueError(f"Gain doit être dans ]0, 1], obtenu: {gain}")
            except ValueError as exc:
                raise ValueError(f"Gain invalide: {exc}") from exc
            try:
                cutoff = float(self.control_panel.input_cutoff.text())
                if cutoff < 0:
                    raise ValueError(f"Cutoff doit être ≥ 0, obtenu: {cutoff}")
            except ValueError as exc:
                raise ValueError(f"Cutoff invalide: {exc}") from exc

            mapsize, cellsize, taper_val, uvmin_wav, uvmax_wav = self._apply_imaging_params()

            pause_after = 0
            if self.control_panel.chk_conditional_bp.isChecked():
                try:
                    pause_after = int(self.control_panel.input_pause_after.text())
                except ValueError:
                    pause_after = 0

            self.session.imager.clrmod()

            self.session.imager.invert(uvmin_wav, uvmax_wav)

            self.control_panel.progress_bar.setValue(0)
            self.control_panel.lbl_progress.setText(f"0 / {niter}")

            cutoff_str = f", cutoff: {cutoff}" if cutoff > 0 else ""
            self.log_console.log(
                f"CLEAN started — niter: {niter}, gain: {gain}{cutoff_str}, taper: {taper_val} Mλ"
            )

            self._clean_worker = CleanWorker(
                imager=self.session.imager,
                niter=niter,
                gain=gain,
                cutoff=cutoff,
                chunk_size=50,
                pause_after=pause_after,
            )
            self._clean_worker.progress.connect(self._on_clean_progress)
            self._clean_worker.paused.connect(self._on_clean_paused)
            self._clean_worker.finished.connect(self._on_clean_finished)
            self._clean_worker.error.connect(self._on_clean_error)
            self._set_ui_for_clean(True)
            self._clean_worker.start()

        except Exception as e:
            err_msg = f"Failed to start CLEAN: {e}"
            self.log_console.log(err_msg)
            QMessageBox.critical(self, "Imaging Error", err_msg)

    def _on_clean_progress(self, done: int, total: int) -> None:
        pct = int(done / total * 100) if total > 0 else 0
        self.control_panel.progress_bar.setValue(pct)
        self.control_panel.lbl_progress.setText(f"{done} / {total}")

    def _on_clean_paused(self, done: int, total: int) -> None:
        """Called when conditional breakpoint triggers an auto-pause."""
        try:
            self._refresh_residual_map()
        except Exception:
            pass
        self.control_panel.btn_compute_clean.setText("▶  Reprendre")
        self.control_panel.btn_compute_clean.setEnabled(True)
        self.log_console.log(f"CLEAN en pause à {done} / {total} itérations.")

    def _on_clean_finished(self) -> None:
        cutoff_reached = bool(
            self._clean_worker is not None
            and getattr(self._clean_worker, '_cutoff_reached', False)
        )
        try:
            self._refresh_residual_map()
            self.control_panel.progress_bar.setValue(100)
            try:
                peak_info = self.session.imager.peak()
                self.log_console.log(
                    f"CLEAN terminé — Peak résiduel: {peak_info['flux']:.4f} Jy/beam"
                    " — Cliquez 'Restore' pour la carte finale, ou relancez selfcal."
                )
            except Exception:
                self.log_console.log("CLEAN terminé. Cliquez 'Restore' ou relancez selfcal.")
            if cutoff_reached:
                self.log_console.log(
                    f"Cutoff atteint — le CLEAN ne peut plus progresser."
                )
            # Activer Run Selfcal maintenant qu'un modèle existe
            self._set_selfcal_ready(True)
        except Exception as e:
            self.log_console.log(f"Post-CLEAN error: {e}")
        finally:
            self._set_ui_for_clean(False, cutoff_reached=cutoff_reached)
            self._clean_worker = None

    def _on_clean_error(self, msg: str) -> None:
        self.log_console.log(f"CLEAN error: {msg}")
        QMessageBox.critical(self, "CLEAN Error", msg)
        self._set_ui_for_clean(False)
        self._clean_worker = None

    def _set_ui_for_clean(self, running: bool, cutoff_reached: bool = False) -> None:
        ctrl = self.control_panel
        ctrl.btn_compute.setEnabled(not running)
        ctrl.btn_apply_imaging.setEnabled(not running)
        if running:
            ctrl.btn_compute_clean.setEnabled(False)
        elif cutoff_reached:
            ctrl.btn_compute_clean.setText("▶  Start")
            ctrl.btn_compute_clean.setEnabled(False)
            ctrl.btn_compute_clean.setToolTip(
                "Cutoff atteint — modifiez le Cutoff ou Niter pour relancer le CLEAN"
            )
            ctrl.input_cutoff.textChanged.connect(self._on_cutoff_edited_after_stop)
        else:
            ctrl.btn_compute_clean.setEnabled(True)
            ctrl.btn_compute_clean.setText("▶  Start")
            ctrl.btn_compute_clean.setToolTip("Lancer invert + CLEAN + restore")

    def _on_cutoff_edited_after_stop(self) -> None:
        """Réactive le bouton Start dès que l'utilisateur modifie le cutoff."""
        ctrl = self.control_panel
        ctrl.btn_compute_clean.setEnabled(True)
        ctrl.btn_compute_clean.setToolTip("Lancer invert + CLEAN + restore")
        try:
            ctrl.input_cutoff.textChanged.disconnect(self._on_cutoff_edited_after_stop)
        except Exception:
            pass

    def _on_apply_imaging(self) -> None:
        try:
            self._apply_imaging_params()
            self.log_console.log("Imaging parameters applied.")
        except Exception as e:
            self.log_console.log(f"Error applying imaging params: {e}")

    def _set_selfcal_ready(self, ready: bool) -> None:
        ctrl = self.control_panel
        if hasattr(ctrl, 'btn_run_selfcal'):
            ctrl.btn_run_selfcal.setEnabled(ready)
            ctrl.btn_run_selfcal.setToolTip(
                "Exécute selfflag + selflims + selftaper + selfcal → invert"
                if ready else
                "Lancez d'abord un CLEAN pour construire un modèle."
            )
        if hasattr(ctrl, 'lbl_selfcal_status'):
            ctrl.lbl_selfcal_status.setText(
                "Modèle CLEAN prêt" if ready else "Aucun modèle — lancez CLEAN d'abord"
            )

    def _run_restore(self) -> None:
        try:
            self.session.imager.restore()
            self._refresh_clean_map()
            self._refresh_residual_map()
            self._refresh_all_maps()
            self.log_console.log("Restore appliqué — carte finale disponible.")
        except Exception as e:
            err_msg = f"Restore error: {e}"
            self.log_console.log(err_msg)
            QMessageBox.critical(self, "Restore Error", err_msg)

    def _run_selfcal(self) -> None:
        """Lance l'auto-calibration avec les paramètres du panneau Selfcal."""
        ctrl = self.control_panel
        try:
            # Garde-fou : selfcal nécessite un modèle CLEAN
            try:
                has_model = len(self.session.imager.get_model_components()) > 0
            except Exception:
                has_model = False

            if hasattr(ctrl, 'lbl_selfcal_status'):
                ctrl.lbl_selfcal_status.setText(
                    "Model: OK" if has_model else "Model: none — do CLEAN first"
                )

            if not has_model:
                raise ValueError(
                    "Selfcal nécessite un modèle CLEAN. Lance d'abord 'Start CLEAN' (au moins quelques itérations)."
                )

            # Lecture des paramètres
            doamp = (ctrl.combo_sc_mode.currentText() == "Amp+Phase")
            dofloat = ctrl.chk_sc_float_amp.isChecked()
            doflag  = ctrl.chk_sc_doflag.isChecked()
            clip    = ctrl.chk_sc_clip.isChecked()

            try:
                solint = float(ctrl.input_sc_solint.text() or "0")
                if solint < 0:
                    raise ValueError(f"solint doit être ≥ 0, obtenu: {solint}")
            except ValueError as exc:
                raise ValueError(f"Solint invalide: {exc}") from exc

            try:
                maxphs = float(ctrl.input_sc_maxphs.text() or "0")
                if maxphs < 0:
                    raise ValueError(f"maxphs doit être ≥ 0, obtenu: {maxphs}")
            except ValueError as exc:
                raise ValueError(f"MaxPhs invalide: {exc}") from exc

            try:
                maxamp = float(ctrl.input_sc_maxamp.text() or "0")
                if maxamp != 0.0 and maxamp < 1.0:
                    raise ValueError(f"maxamp doit être 0 (illimité) ou ≥ 1, obtenu: {maxamp}")
            except ValueError as exc:
                raise ValueError(f"MaxAmp invalide: {exc}") from exc

            p_mintel = ctrl.spin_sc_p_mintel.value()
            a_mintel = ctrl.spin_sc_a_mintel.value()

            # Selfcal taper (optionnel)
            sc_tap_amp_str = ctrl.input_sc_taper_amp.text().strip()
            sc_tap_rad_str = ctrl.input_sc_taper_rad.text().strip()
            sc_tap_amp = float(sc_tap_amp_str) if sc_tap_amp_str else 0.0
            sc_tap_rad = float(sc_tap_rad_str) if sc_tap_rad_str else 0.0
            if sc_tap_amp != 0.0 and not (0.0 < sc_tap_amp < 0.99):
                raise ValueError(f"Amplitude taper selfcal doit être dans ]0, 0.99[, obtenu: {sc_tap_amp}")
            if sc_tap_rad > 0.0 and sc_tap_amp == 0.0:
                raise ValueError("Selfcal taper : si Rayon > 0 alors Valeur doit être renseignée.")

            mode_str = "Amp+Phase" if doamp else "Phase only"
            self.log_console.log(
                f"Selfcal — mode: {mode_str}, solint: {solint} min, "
                f"maxphs: {maxphs}°, maxamp: {maxamp}, "
                f"mintel φ/A: {p_mintel}/{a_mintel}"
            )

            # Appliquer le taper selfcal si renseigné
            if sc_tap_rad > 0.0:
                self.session.imager.selfcal_taper(sc_tap_amp, sc_tap_rad)
            else:
                self.session.imager.selfcal_taper(0.0, 0.0)

            # Lancer selfcal
            self.session.imager.selfcal(
                doamp=doamp, dofloat=dofloat, solint=solint,
                maxamp=maxamp, maxphs=maxphs,
                p_mintel=p_mintel, a_mintel=a_mintel,
                doflag=doflag, clip=clip,
            )
            self.log_console.log("Selfcal terminé.")

            # Re-invert automatique pour obtenir la carte résiduelle corrigée
            self.log_console.log("Re-invert post-selfcal…")
            mapsize, cellsize, taper_val, uvmin_wav, uvmax_wav = self._apply_imaging_params()
            self.session.imager.invert(uvmin_wav, uvmax_wav)
            self._last_uvtaper_params = None  # force re-apply taper au prochain CLEAN

            self._refresh_residual_map()
            self._refresh_dirty_map()
            self.log_console.log("Re-invert post-selfcal effectué — carte résiduelle mise à jour.")

        except Exception as e:
            err_msg = f"Selfcal error: {e}"
            self.log_console.log(err_msg)
            QMessageBox.critical(self, "Selfcal Error", err_msg)

    def _on_colormap_changed(self, cmap_name: str) -> None:
        for w in (self.map_widget, self.clean_map_widget, self.residual_map_widget):
            if hasattr(w, 'update_colormap'):
                w.update_colormap(cmap_name)

    def _on_show_windows_changed(self, _visible: bool) -> None:
        self._refresh_current_map_tab()

    def _add_clean_window_from_coords(self, xa, xb, ya, yb):
        """Ajoute une fenêtre CLEAN depuis les coordonnées de la souris."""
        try:
            self.session.imager.addwin(xa, xb, ya, yb)
            self._last_added_window = (min(xa, xb), max(xa, xb), min(ya, yb), max(ya, yb))
            self.log_console.log(f"Added CLEAN window from mouse: ({xa:.2f}, {xb:.2f}, {ya:.2f}, {yb:.2f}) mas")
            self._refresh_clean_windows_overlay()
            self._refresh_residual_map()
            self._refresh_dirty_map()
            
        except Exception as e:
            err_msg = f"Failed to add CLEAN window from mouse: {e}"
            self.log_console.log_error(err_msg)
            QMessageBox.critical(self, "Window Error", err_msg)

    def _delete_clean_windows(self):
        """Supprime toutes les fenêtres CLEAN."""
        try:
            self.session.imager.delwin()
            self.log_console.log("Deleted all CLEAN windows")
            self._refresh_clean_windows_overlay()
            self._refresh_residual_map()
            self._refresh_dirty_map()
            
        except Exception as e:
            err_msg = f"Failed to delete CLEAN windows: {e}"
            self.log_console.log_error(err_msg)
            QMessageBox.critical(self, "Window Error", err_msg)

    def _delete_last_clean_window(self):
        try:
            # Utiliser active_windows (coordonnées Python d'origine) et non
            # _get_clean_windows() (readback C) pour éviter la dérive float32
            # sur des re-addwin successifs.
            windows = list(self.session.imager.active_windows)
            if not windows:
                return
            windows = windows[:-1]
            self.session.imager.delwin()
            for xa, xb, ya, yb in windows:
                self.session.imager.addwin(xa, xb, ya, yb)
            self.log_console.log("Deleted last CLEAN window")
            self._refresh_clean_windows_overlay()
            self._refresh_residual_map()
            self._refresh_dirty_map()
        except Exception as e:
            err_msg = f"Failed to delete last CLEAN window: {e}"
            self.log_console.log_error(err_msg)
            QMessageBox.critical(self, "Window Error", err_msg)

    def _delete_this_clean_window(self):
        try:
            target = self._last_added_window
            windows = list(self.session.imager.active_windows)
            if not windows:
                return
            if target and target in windows:
                windows.remove(target)
            else:
                windows = windows[:-1]
            self.session.imager.delwin()
            for xa, xb, ya, yb in windows:
                self.session.imager.addwin(xa, xb, ya, yb)
            self.log_console.log("Deleted selected CLEAN window")
            self._refresh_clean_windows_overlay()
            self._refresh_residual_map()
            self._refresh_dirty_map()
        except Exception as e:
            err_msg = f"Failed to delete CLEAN window: {e}"
            self.log_console.log_error(err_msg)
            QMessageBox.critical(self, "Window Error", err_msg)

    def _add_peak_window(self):
        """Ajoute une fenêtre autour du pic de flux (taille par défaut DIFMAP = 1.0 FWHM)."""
        try:
            current_idx = self._get_logical_tab()
            # Garde-fou scientifique (soft): peakwin() doit se baser sur une dirty map
            # fraîche correspondant aux paramètres d'imagerie courants (mapsize/weight/taper).
            # On applique les paramètres et on force invert() avant peakwin().
            mapsize, cellsize, taper_val, uvmin_wav, uvmax_wav = self._apply_imaging_params()
            weight = self.control_panel.combo_weight.currentText().lower()
            self.log_console.log(
                f"PeakWin — refreshing dirty map first (size: {mapsize}, cell: {cellsize} mas, "
                f"weight: {weight}, taper: {taper_val} Mλ)"
            )
            self.session.imager.invert(uvmin_wav, uvmax_wav)
            self.session.imager.peakwin(size=1.0)
            self.log_console.log("Added peak window (1.0 FWHM)")
            windows = self.session.imager._get_clean_windows()
            if windows:
                self._last_added_window = windows[-1]
            self._refresh_clean_windows_overlay()
            self._refresh_residual_map()
            self._refresh_dirty_map()

            # Ne pas basculer d'onglet: le refresh du résiduel est un update secondaire.
            try:
                self._set_logical_tab(current_idx)
            except Exception:
                pass
            
        except Exception as e:
            # Gérer spécifiquement le cas où aucune carte n'est disponible
            if "aucune carte" in str(e).lower() or "no map" in str(e).lower():
                self.log_console.log("Peak window requires a map to be computed first. Please compute a Dirty Map or Clean Map first.")
                QMessageBox.information(self, "Peak Window", 
                    "A map must be computed before adding a peak window.\n\n"
                    "Please:\n"
                    "1. Compute a Dirty Map, or\n"
                    "2. Compute a Clean Map\n\n"
                    "Then try adding the peak window again.")
            else:
                err_msg = f"Failed to add peak window: {e}"
                self.log_console.log_error(err_msg)
                QMessageBox.critical(self, "Window Error", err_msg)

    def _on_show_model_map_changed(self, checked: bool) -> None:
        """Callback quand le checkbox Show Model pour Maps change."""
        current_tab = self._get_logical_tab()
        if current_tab == TabIndex.CLEAN:
            self._refresh_clean_map()
        elif current_tab == TabIndex.MAP:
            self._refresh_dirty_map()
        elif current_tab == TabIndex.RESIDUAL:
            self._refresh_residual_map()
        elif current_tab == TabIndex.ALL_MAPS:
            self._refresh_all_maps()

    def _refresh_current_map_tab(self):
        """Rafraîchit l'onglet de carte actif sans recalculer."""
        try:
            current_tab = self._get_logical_tab()
            if current_tab == TabIndex.MAP:
                self._refresh_dirty_map()
            elif current_tab == TabIndex.CLEAN:
                self._refresh_clean_map()
            elif current_tab == TabIndex.RESIDUAL:
                self._refresh_residual_map()
            elif current_tab == TabIndex.ALL_MAPS:
                self._refresh_all_maps()
        except Exception as e:
            self.log_console.log_error(f"Failed to refresh map: {e}")

    def _refresh_all_maps(self) -> None:
        """Rafraîchit l'onglet All Maps (Residual grand + Dirty/Clean à droite)."""
        try:
            self._refresh_residual_map(target_widget=self.all_maps_residual_widget)
        except Exception:
            pass
        try:
            self._refresh_dirty_map(target_widget=self.all_maps_dirty_widget)
        except Exception:
            pass
        try:
            self._refresh_clean_map(target_widget=self.all_maps_clean_widget)
        except Exception:
            pass

    def _get_valid_cellsize(self) -> float:
        """Récupère un cellsize valide depuis le panneau de contrôle."""
        try:
            if hasattr(self, 'control_panel') and self.control_panel:
                cellsize_text = self.control_panel.input_cellsize.text()
                if cellsize_text and cellsize_text.strip():
                    cellsize = float(cellsize_text)
                    if cellsize > 0:  # Validation que le cellsize est positif
                        return cellsize
        except (ValueError, AttributeError, TypeError):
            pass
        
        # Valeur par défaut robuste
        return 0.1

    def _refresh_dirty_map(self, target_widget=None):
        """Rafraîchit la Dirty Map sans recalculer."""
        try:
            if not (hasattr(self, 'session') and self.session and
                    hasattr(self.session, 'imager') and self.session.imager):
                return
            if not self.session.imager.has_map_data():
                return

            cellsize = self._get_valid_cellsize()
            map_package = self.session.imager.get_map_package(cellsize=cellsize)
            if not (map_package and map_package.get('data') is not None):
                return

            info = map_package.get('info', {})
            map_type = map_package.get('map_type') or info.get('map_type')
            if map_type != 'dirty':
                if self._last_dirty_package:
                    map_package = self._last_dirty_package
                else:
                    return

            # Suivre la maquette: Dirty Map n'expose pas Scale/Min/Max/Contours.
            # Forcer un rendu auto.
            scale, vmin, vmax = 'linear', None, None
            info = map_package.get('info', {})
            show_model = self.control_panel.chk_show_model_map.isChecked()
            model_components = []
            if show_model:
                try:
                    model_components = self.session.imager.get_model_components()
                except Exception:
                    pass
            widget = target_widget or self.map_widget
            widget.plot_map(
                map_data=map_package['data'],
                cellsize=info.get('cellsize', cellsize),
                cellsize_y=info.get('cellsize_y'),
                scale=scale,
                vmin=vmin, vmax=vmax,
                extent=map_package['extent'],
                windows=map_package.get('windows', []),
                show_model=show_model,
                model_components=model_components,
            )

            data = map_package.get('data')
            frozen = dict(map_package)
            if hasattr(data, 'copy'):
                frozen['data'] = data.copy()
            extent = map_package.get('extent')
            if isinstance(extent, list):
                frozen['extent'] = list(extent)
            info_frozen = map_package.get('info')
            if isinstance(info_frozen, dict):
                frozen['info'] = dict(info_frozen)
            self._last_dirty_package = frozen
        except Exception as e:
            self.log_console.log_error(f"Failed to refresh dirty map: {e}")

    def _refresh_clean_map(self, target_widget=None):
        """Rafraîchit la Clean Map sans recalculer."""
        try:
            if not (hasattr(self, 'session') and self.session and
                    hasattr(self.session, 'imager') and self.session.imager):
                return
            if not self.session.imager.has_map_data():
                return

            chk_win = getattr(self.control_panel, 'chk_show_windows', None)
            show_windows = (chk_win is None or chk_win.isChecked())

            cellsize = self._get_valid_cellsize()
            clean_package = self.session.imager.get_map_package(cellsize=cellsize)
            if not (clean_package and clean_package.get('data') is not None):
                return

            info = clean_package.get('info', {})
            map_type = clean_package.get('map_type') or info.get('map_type')
            if map_type != 'clean':
                # Si le buffer C n'est plus une carte clean (ex: peakwin() a forcé un invert()),
                # on ré-affiche la dernière clean map cachée pour éviter un onglet vide.
                if self._last_clean_package:
                    pkg = self._last_clean_package
                    info = pkg.get('info', {})
                    scale, vmin, vmax = self.control_panel.get_scale_params()
                    contour_mode, contour_absmin, contour_absmax, contour_factor, contour_custom = (
                        self.control_panel.get_contour_params()
                    )
                    show_model = self.control_panel.chk_show_model_map.isChecked()
                    model_components = pkg.get('model_components', [])
                    windows = self.session.imager._get_clean_windows() if show_windows else []
                    widget = target_widget or self.clean_map_widget
                    widget.plot_map(
                        map_data=pkg['data'],
                        cellsize=info.get('cellsize', cellsize),
                        cellsize_y=info.get('cellsize_y'),
                        scale=scale,
                        vmin=vmin, vmax=vmax,
                        extent=pkg['extent'],
                        beam_info=info,
                        windows=windows,
                        contour_mode=contour_mode,
                        contour_absmin=contour_absmin,
                        contour_absmax=contour_absmax,
                        contour_factor=contour_factor,
                        contour_custom=contour_custom,
                        show_model=show_model,
                        model_components=model_components,
                    )
                return
            scale, vmin, vmax = self.control_panel.get_scale_params()
            contour_mode, contour_absmin, contour_absmax, contour_factor, contour_custom = (
                self.control_panel.get_contour_params()
            )
            show_model = self.control_panel.chk_show_model_map.isChecked()
            model_components = clean_package.get('model_components', [])
            windows = clean_package.get('windows', []) if show_windows else []
            widget = target_widget or self.clean_map_widget
            widget.plot_map(
                map_data=clean_package['data'],
                cellsize=info.get('cellsize', cellsize),
                cellsize_y=info.get('cellsize_y'),
                scale=scale,
                vmin=vmin, vmax=vmax,
                extent=clean_package['extent'],
                beam_info=info,
                windows=windows,
                contour_mode=contour_mode,
                contour_absmin=contour_absmin,
                contour_absmax=contour_absmax,
                contour_factor=contour_factor,
                contour_custom=contour_custom,
                show_model=show_model,
                model_components=model_components,
            )
            data = clean_package.get('data')
            frozen = dict(clean_package)
            if hasattr(data, 'copy'):
                frozen['data'] = data.copy()
            extent = clean_package.get('extent')
            if isinstance(extent, list):
                frozen['extent'] = list(extent)
            info_frozen = clean_package.get('info')
            if isinstance(info_frozen, dict):
                frozen['info'] = dict(info_frozen)
            # Copie profonde des model_components pour éviter les références partagées
            model_comps = clean_package.get('model_components')
            if model_comps:
                frozen['model_components'] = [dict(cmp) for cmp in model_comps]
            self._last_clean_package = frozen
        except Exception as e:
            self.log_console.log_error(f"Failed to refresh clean map: {e}")

    def _refresh_clean_windows_overlay(self) -> None:
        try:
            if not (hasattr(self, 'session') and self.session and
                    hasattr(self.session, 'imager') and self.session.imager):
                return
            if not self._last_clean_package:
                return
            chk_win = getattr(self.control_panel, 'chk_show_windows', None)
            show_windows = (chk_win is None or chk_win.isChecked())
            cellsize = self._get_valid_cellsize()
            scale, vmin, vmax = self.control_panel.get_scale_params()
            contour_mode, contour_absmin, contour_absmax, contour_factor, contour_custom = (
                self.control_panel.get_contour_params()
            )
            windows = self.session.imager._get_clean_windows() if show_windows else []
            pkg = self._last_clean_package
            info = pkg.get('info', {})
            show_model = self.control_panel.chk_show_model_map.isChecked()
            model_components = pkg.get('model_components', [])
            self.clean_map_widget.plot_map(
                map_data=pkg['data'],
                cellsize=info.get('cellsize', cellsize),
                cellsize_y=info.get('cellsize_y'),
                scale=scale,
                vmin=vmin, vmax=vmax,
                extent=pkg['extent'],
                beam_info=info,
                windows=windows,
                contour_mode=contour_mode,
                contour_absmin=contour_absmin,
                contour_absmax=contour_absmax,
                contour_factor=contour_factor,
                contour_custom=contour_custom,
                show_model=show_model,
                model_components=model_components,
            )
        except Exception:
            return

    def _refresh_residual_map(self, target_widget=None):
        """Rafraîchit la Residual Map sans recalculer."""
        try:
            if not (hasattr(self, 'session') and self.session and
                    hasattr(self.session, 'imager') and self.session.imager):
                return
            if self.session.imager._last_residual_map is None:
                return

            cellsize = self._get_valid_cellsize()
            residual_package = self.session.imager.get_residual_package(cellsize=cellsize)
            if not (residual_package and residual_package.get('data') is not None):
                return

            info = residual_package.get('info', {})
            scale, vmin, vmax = self.control_panel.get_scale_params()
            show_model = self.control_panel.chk_show_model_map.isChecked()
            model_components = []
            if show_model:
                try:
                    model_components = self.session.imager.get_model_components()
                except Exception:
                    pass
            chk_win = getattr(self.control_panel, 'chk_show_windows', None)
            windows = residual_package.get('windows', []) if (chk_win is None or chk_win.isChecked()) else []
            widget = target_widget or self.residual_map_widget
            widget.plot_map(
                map_data=residual_package['data'],
                cellsize=info.get('cellsize', cellsize),
                cellsize_y=info.get('cellsize_y'),
                scale=scale,
                vmin=vmin, vmax=vmax,
                extent=residual_package['extent'],
                windows=windows,
                show_model=show_model,
                model_components=model_components,
            )
        except Exception as e:
            self.log_console.log_error(f"Failed to refresh residual map: {e}")

    def _on_uv_limits_changed(self, umin, umax, vmin, vmax) -> None:
        """Applique les limites d'axe UV (umax / vmax difmap) au plot UV."""
        if self.plot_widget and hasattr(self.plot_widget, 'set_uv_limits'):
            self.plot_widget.set_uv_limits(umin, umax, vmin, vmax)

    def _on_rad_limits_changed(self, uvmin, uvmax, ampmin, ampmax, phsmin, phsmax) -> None:
        """Applique les limites d'affichage Radplot (équivalent r_setrange difmap)."""
        if self.radplot_widget and hasattr(self.radplot_widget, 'set_rad_limits'):
            self.radplot_widget.set_rad_limits(uvmin, uvmax, ampmin, ampmax, phsmin, phsmax)

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
                    for w in (self.plot_widget, self.radplot_widget):
                        if w and hasattr(w, 'sync_crosshair_btn'):
                            w.sync_crosshair_btn(state_dict['crosshair'])
                if 'show_conjugate' in state_dict:
                    ctrl.chk_conjugate.setChecked(state_dict['show_conjugate'])
                if 'marker_size' in state_dict:
                    ctrl.slider_size.blockSignals(True)
                    ctrl.slider_size.setValue(state_dict['marker_size'])
                    ctrl.slider_size.blockSignals(False)
                    try:
                        ctrl.lbl_slider_size_val.setText(f"{state_dict['marker_size']} %")
                    except Exception:
                        pass
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
                    # Apply all layout-affecting state changes to the widget BEFORE
                    # triggering a single refresh — avoids double redraw and prevents
                    # display_mode=AMP_ONLY (new-editor default) from overwriting BOTH.
                    layout_changed = False
                    if 'display_mode' in state_dict:
                        new_dm = max(1, min(3, state_dict['display_mode']))
                        if self.radplot_widget.display_mode != new_dm:
                            self.radplot_widget.display_mode = new_dm
                            layout_changed = True
                    if 'show_errors' in state_dict:
                        new_err = bool(state_dict['show_errors'])
                        if self.radplot_widget.show_errors != new_err:
                            self.radplot_widget.show_errors = new_err
                            layout_changed = True
                    if layout_changed and self.radplot_widget.data is not None:
                        self.radplot_widget._refresh_layout()

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
