import numpy as np
from matplotlib.patches import Ellipse, Rectangle
from matplotlib.colors import Normalize, LogNorm, PowerNorm
from matplotlib.offsetbox import AnchoredOffsetbox, AuxTransformBox
from matplotlib.widgets import RectangleSelector
from matplotlib.backend_bases import cursors
from PyQt6.QtWidgets import QLabel, QPushButton, QComboBox, QHBoxLayout, QWidget
from PyQt6.QtCore import Qt
from .base_plot_widget import BasePlotWidget
from difmap_wrapper.gui.utils import MatplotlibStyler
from difmap_wrapper.gui.styles import DesignSystem
from difmap_wrapper.utils.map_geometry import DifmapMapGeometry
from difmap_wrapper.core.visualizer import Visualizer
from difmap_wrapper.utils.map_annotations import create_pgplot_style_annotations, DifmapMapAnnotations

D = DesignSystem

_TOOLBAR_QSS = f"""
QWidget#MapToolbar {{
    background-color: {D.SURFACE_ALT};
    border-bottom: 1px solid {D.BORDER};
    padding: 4px 0;
    height: 32px;
}}
QPushButton {{
    background-color: {D.SURFACE};
    color: {D.TEXT};
    border: 1px solid {D.BORDER};
    border-radius: 5px;
    padding: 4px 10px;
    font-size: 10px;
    min-height: 26px;
    min-width: 70px;
}}
QPushButton:hover {{
    background-color: {D.SURFACE_ALT};
    border-color: {D.PRIMARY};
    color: {D.TEXT};
}}
QPushButton:pressed {{
    background-color: {D.BORDER_LIGHT};
    border-color: {D.PRIMARY_ACTIVE};
    color: {D.TEXT};
}}
QLabel {{
    color: {D.TEXT_MUTED};
    font-size: 10px;
    font-weight: bold;
    background: transparent;
    padding-left: 4px;
}}
QComboBox {{
    background-color: {D.SURFACE};
    color: {D.TEXT};
    border: 1px solid {D.BORDER};
    border-radius: 5px;
    padding: 3px 8px;
    font-size: 10px;
    min-width: 160px;
    min-height: 26px;
}}
QComboBox:hover {{ border-color: {D.PRIMARY}; }}
QComboBox::drop-down {{ border: none; width: 18px; }}
QComboBox::down-arrow {{ width: 10px; height: 10px; }}
"""


def _central_peak(data: np.ndarray) -> float:
    """Pic signé sur la région d'affichage complète.

    Difmap garde le signe de l'extrême dominant dans maplot.c:setcont().
    """
    dmin = float(np.nanmin(data))
    dmax = float(np.nanmax(data))
    return dmax if abs(dmax) > abs(dmin) else dmin


def _imageable_zone_peak(full_data: np.ndarray) -> float:
    """Pic signé sur la zone imageable (centre 1/4 à 3/4 de la carte).
    
    Difmap calcule les niveaux de contours sur la zone imageable complète,
    pas sur la zone zoomée. La zone imageable est typiquement le centre
    de la carte (nx/4..3nx/4, ny/4..3ny/4).
    """
    ny, nx = full_data.shape
    # Zone imageable: centre 1/4 à 3/4 de la carte
    y_start, y_end = ny // 4, 3 * ny // 4
    x_start, x_end = nx // 4, 3 * nx // 4
    
    # S'assurer que les indices sont valides
    y_start = max(0, y_start)
    y_end = min(ny, y_end)
    x_start = max(0, x_start)
    x_end = min(nx, x_end)
    
    imageable_data = full_data[y_start:y_end, x_start:x_end]
    return _central_peak(imageable_data)


def _make_norm(scale: str, vmin, vmax, data: np.ndarray):
    """Normalisation matplotlib équivalente à mapfunc de difmap (linear/log/sqrt)."""
    dmin = float(np.nanmin(data))
    dmax = float(np.nanmax(data))
    v_lo = vmin if vmin is not None else dmin
    v_hi = vmax if vmax is not None else dmax
    if scale == 'log':
        safe_lo = max(v_lo, v_hi * 1e-4, 1e-12) if v_hi > 0 else 1e-6
        return LogNorm(vmin=safe_lo, vmax=v_hi)
    if scale == 'sqrt':
        return PowerNorm(gamma=0.5, vmin=max(v_lo, 0.0), vmax=v_hi)
    return Normalize(vmin=v_lo, vmax=v_hi)


def _compute_contour_levels(peak, mode='pct', absmin=1.0, absmax=100.0,
                             factor=2.0, custom=None):
    return Visualizer._compute_contour_levels(peak, mode, absmin, absmax, factor, custom)


def _draw_contours(ax, map_data, x_coords, y_coords, peak, lw=0.6,
                   mode='pct', absmin=1.0, absmax=100.0, factor=2.0, custom=None):
    """
    Trace les contours isophotes en suivant la convention PGPLOT de DIFMAP :
    - négatifs : rouge (color index 2), traits pleins
    - positifs : blanc (color index 1), traits pleins
    - Utilise les niveaux exacts de DIFMAP
    - Coordonnées précises des pixels pour correspondre à PGPLOT
    Retourne la liste des niveaux tracés (Jy/beam, pour annotation).
    """
    levels = _compute_contour_levels(peak, mode, absmin, absmax, factor, custom)
    if not levels:
        return []
    
    cmin = float(np.nanmin(map_data))
    cmax = float(np.nanmax(map_data))
    visible = [l for l in levels if cmin < l < cmax]
    drawn = []
    
    # Tracer tous les contours d'un coup pour optimisation
    if visible:
        # Séparer niveaux positifs et négatifs pour couleurs différentes
        pos_levels = [l for l in visible if l >= 0]
        neg_levels = [l for l in visible if l < 0]
        
        # Contours positifs en blanc - approche haute résolution
        if pos_levels:
            cs_pos = ax.contour(
                x_coords, y_coords, map_data, levels=pos_levels,
                colors='white', linewidths=lw*0.5, linestyles='solid',
                alpha=1.0
            )
            drawn.extend(pos_levels)
        
        # Contours négatifs en rouge - approche haute résolution
        if neg_levels:
            cs_neg = ax.contour(
                x_coords, y_coords, map_data, levels=neg_levels,
                colors='red', linewidths=lw*0.5, linestyles='solid',
                alpha=1.0
            )
            drawn.extend(neg_levels)
    
    return drawn


def _add_map_annotations(ax, fig, map_data, map_type, beam_info=None,
                          contour_levels=None, contour_mode='pct',
                          observation_data=None, map_info=None):
    """
    Ajoute les annotations texte style PGPLOT propre et moderne.
    """
    # Préparer les informations pour map_annotations.py
    if map_info is None:
        map_info = {}
    
    # Ajouter les informations de beam si disponibles
    if beam_info:
        map_info.update(beam_info)
    
    # Créer les annotations style PGPLOT
    annotations_dict = create_pgplot_style_annotations(
        map_data, map_info, observation_data, contour_levels
    )
    
    main_text = annotations_dict['main_text']
    
    if main_text:
        # Solution minimaliste : annotation petite et discrète
        # Réduire le texte pour ne pas cacher l'image
        lines = main_text.split('\n')
        essential_lines = []
        
        for line in lines:
            line = line.strip()
            # Garder seulement les infos critiques
            if any(keyword in line for keyword in ['Peak:', 'Beam:', 'Map:']):
                essential_lines.append(line)
        
        if essential_lines:
            compact_text = '\n'.join(essential_lines[:3])  # Max 3 lignes
            ax.text(0.02, 0.98, compact_text, transform=ax.transAxes,
                    fontsize=6, color=DesignSystem.ASTRAL_ACCENT, va='top', ha='left',
                    bbox=dict(boxstyle='round,pad=0.2', facecolor=DesignSystem.SURFACE_ALT, 
                              edgecolor=DesignSystem.ASTRAL_ACCENT, alpha=0.8, linewidth=1))


class MapPlotWidget(BasePlotWidget):
    """
    Widget de base pour l'affichage d'une carte d'intensité avec colorbar.

    Ne pas instancier directement — utiliser :class:`DirtyMapPlotWidget`,
    :class:`CleanMapPlotWidget` ou :class:`ResidualMapPlotWidget`.
    """

    _map_title: str = "Map"
    _cmap: str = "inferno"
    _map_type: str = "dirty"  # "dirty" | "clean" | "residual"

    _MAP_TOOLS = [
        ("Navigate  [R]",      "NAVIGATE"),
        ("Zoom Box  [Z]",      "ZOOM"),
        ("Add Window  [W]",    "ADD_WINDOW"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent=parent, figsize=(6, 6), include_toolbar=True, layout_type='constrained')
        # Hide matplotlib NavigationToolbar — we use our own combo-based toolbar
        self.toolbar.setVisible(False)

        self.image = None
        self.cbar = None

        # CLEAN window selection
        self.window_selector = None
        self.window_selection_mode = False
        self.selected_window = None

        self.canvas.mpl_connect('button_press_event', self._on_mouse_press)
        self.canvas.mpl_connect('key_press_event', self._on_key_press)

        self._build_map_toolbar()

    def _build_map_toolbar(self) -> None:
        """Toolbar — même pattern que UV/Radplot : combo d'outils + boutons d'action."""
        row = self.plot_toolbar_row
        row.setObjectName("MapToolbar")
        row.setStyleSheet(_TOOLBAR_QSS)
        row.setFixedHeight(32)
        row.setVisible(True)
        lay = self.plot_toolbar_layout

        lay.addWidget(QLabel("  Tools:"))

        self._tool_combo = QComboBox()
        self._tool_combo.setToolTip("Active tool (keyboard shortcut)")
        for label, data in self._MAP_TOOLS:
            self._tool_combo.addItem(label, data)
        lay.addWidget(self._tool_combo)

        lay.addSpacing(10)

        self._btn_peak_window   = QPushButton("Peak Win  [P]")
        self._btn_delete_windows = QPushButton("Del All  [D]")
        self._btn_reset          = QPushButton("Reset  [Home]")
        self._btn_dezoom         = QPushButton("Dezoom  [O]")

        self._btn_peak_window.setToolTip("Ajouter une fenêtre autour du pic de flux")
        self._btn_delete_windows.setToolTip("Supprimer toutes les fenêtres CLEAN")
        self._btn_reset.setToolTip("Revenir à la vue complète")
        self._btn_dezoom.setToolTip("Dézoomer (vue précédente)")

        for btn in (self._btn_peak_window, self._btn_delete_windows,
                    self._btn_reset, self._btn_dezoom):
            lay.addWidget(btn)

        lay.addStretch()

        self._tool_combo.currentIndexChanged.connect(self._on_tool_changed)
        self._btn_peak_window.clicked.connect(self._add_peak_window)
        self._btn_delete_windows.clicked.connect(self._delete_all_windows)
        self._btn_reset.clicked.connect(self._reset_view)
        self._btn_dezoom.clicked.connect(self._dezoom)

    def _on_tool_changed(self, index: int) -> None:
        if index < 0:
            return
        mode = self._tool_combo.itemData(index)
        if mode == "NAVIGATE":
            self._exit_window_selection_mode()
            self._deactivate_mpl_tools()
        elif mode == "ZOOM":
            self._exit_window_selection_mode()
            self._activate_mpl_zoom()
        elif mode == "ADD_WINDOW":
            self._deactivate_mpl_tools()
            self._activate_window_selection_mode()
        self.canvas.setFocus()

    def _deactivate_mpl_tools(self) -> None:
        if self.toolbar is None:
            return
        mode_str = str(getattr(self.toolbar, 'mode', '')).lower()
        if 'zoom' in mode_str:
            self.toolbar.zoom()
        elif 'pan' in mode_str:
            self.toolbar.pan()

    def _activate_mpl_zoom(self) -> None:
        if self.toolbar is None:
            return
        mode_str = str(getattr(self.toolbar, 'mode', '')).lower()
        if 'pan' in mode_str:
            self.toolbar.pan()
        if 'zoom' not in mode_str:
            self.toolbar.zoom()

    def _reset_view(self) -> None:
        if self.toolbar:
            self.toolbar.home()
        self.canvas.setFocus()

    def _dezoom(self) -> None:
        if self.toolbar:
            self.toolbar.back()
        self.canvas.setFocus()

    def _sync_combo_to(self, tool_data: str) -> None:
        """Sync the combo to the given tool data value without triggering signals."""
        idx = next((i for i in range(self._tool_combo.count())
                    if self._tool_combo.itemData(i) == tool_data), 0)
        self._tool_combo.blockSignals(True)
        self._tool_combo.setCurrentIndex(idx)
        self._tool_combo.blockSignals(False)

    def _add_peak_window(self):
        """Ajoute une fenêtre autour du pic depuis la toolbar."""
        try:
            # Trouver le parent MainWindow
            parent = self.parent()
            while parent and hasattr(parent, 'parent'):
                if hasattr(parent, '_add_peak_window'):
                    parent._add_peak_window()
                    break
                parent = parent.parent()
        except Exception as e:
            print(f"Error adding peak window: {e}")

    def _delete_all_windows(self):
        """Supprime toutes les fenêtres depuis la toolbar."""
        try:
            # Trouver le parent MainWindow
            parent = self.parent()
            while parent and hasattr(parent, 'parent'):
                if hasattr(parent, '_delete_clean_windows'):
                    parent._delete_clean_windows()
                    break
                parent = parent.parent()
        except Exception as e:
            print(f"Error deleting windows: {e}")

    def _setup_axes(self):
        MatplotlibStyler.setup_axes(
            self.ax,
            title_text=self._map_title,
            xlabel="Décalage RA (mas)",
            ylabel="Décalage Dec (mas)"
        )
        # Note: L'inversion de l'axe RA est gérée automatiquement par imshow via l'extent

    def plot_map(self, map_data, cellsize, cellsize_y=None,
                scale='linear', vmin=None, vmax=None, extent=None,
                contour_mode='pct', contour_absmin=1.0, contour_absmax=100.0,
                contour_factor=2.0, contour_custom=None, windows=None):
        """
        Affiche la carte (Dirty ou Residual) avec orientation radio-astronomique
        en utilisant la géométrie exacte de DIFMAP.

        Parameters
        ----------
        map_data : numpy.ndarray or None
            Tableau 2D de flux en Jy/beam (shape: ny × nx).
        cellsize : float
            Taille d'une cellule en mas sur l'axe X.
        cellsize_y : float, optional
            Taille d'une cellule en mas sur l'axe Y.
        scale : str, optional
            Échelle de couleur : ``'linear'``, ``'log'`` ou ``'sqrt'`` (mapfunc).
        vmin, vmax : float, optional
            Bornes de la colormap (``None`` = automatique).
        extent : list of float, optional
            Limites astrométriques ``[xmax, xmin, ymin, ymax]`` déjà calculées
            selon la géométrie Difmap.
        contour_mode : str, optional
            Mode des contours : ``'pct'``, ``'log'`` ou ``'custom'``.
        contour_absmin, contour_absmax : float, optional
            Limites absolues pour le mode ``'log'``.
        contour_factor : float, optional
            Facteur multiplicatif pour le mode ``'log'``.
        contour_custom : list, optional
            Niveaux de contours personnalisés pour le mode ``'custom'``.
        """
        if self.cbar is not None:
            self.cbar.remove()
            self.cbar = None
        self.ax.cla()
        self._setup_axes()

        if map_data is None or len(map_data) == 0:
            self.ax.text(0.5, 0.5, "No Map Data", ha='center', va='center',
                         transform=self.ax.transAxes)
            self.draw()
            return

        # Récupérer les limites personnalisées depuis le ControlPanel si disponibles
        xmin = xmax = ymin = ymax = None
        try:
            parent = self.parent()
            while parent and hasattr(parent, 'parent'):
                if hasattr(parent, 'control_panel'):
                    xmin, xmax, ymin, ymax = parent.control_panel.get_display_area_params()
                    break
                parent = parent.parent()
        except:
            pass  # Ignorer les erreurs, utiliser les valeurs par défaut
        
        # Si des limites personnalisées sont définies, on doit recadrer même si extent est fourni
        custom_limits = any(v is not None for v in (xmin, xmax, ymin, ymax))
        
        # Utiliser la géométrie DIFMAP exacte
        if extent is not None and not custom_limits:
            # Utiliser l'extent fourni (déjà calculé) sans recadrage
            cropped_data = map_data
            astrometric_extent = extent
            nx_crop, ny_crop = cropped_data.shape[1], cropped_data.shape[0]
        else:
            # Appliquer le crop DIFMAP avec limites personnalisées ou par défaut
            cropped_data, astrometric_extent, nx_crop, ny_crop = DifmapMapGeometry.crop_map_data(
                map_data, cellsize, cellsize_y,
                xmin=xmin, xmax=xmax, ymin=ymin, ymax=ymax
            )

        norm = _make_norm(scale, vmin, vmax, cropped_data)
        self.image = self.ax.imshow(
            cropped_data, cmap=self._cmap, origin='lower', extent=astrometric_extent, norm=norm
        )
        self.ax.set_aspect('equal', adjustable='box')

        self.cbar = self.fig.colorbar(
            self.image, ax=self.ax,
            label="Flux (Jy/beam)",
            fraction=0.046, pad=0.04
        )

        # Ajouter les contours si demandé
        if contour_mode != 'none':
            peak = _imageable_zone_peak(map_data)
            contour_levels = _compute_contour_levels(
                peak, mode=contour_mode, absmin=contour_absmin, 
                absmax=contour_absmax, factor=contour_factor, custom=contour_custom
            )
            x_coords = np.linspace(astrometric_extent[0], astrometric_extent[1], cropped_data.shape[1] + 1)[:-1]
            y_coords = np.linspace(astrometric_extent[2], astrometric_extent[3], cropped_data.shape[0] + 1)[:-1]
            _draw_contours(self.ax, cropped_data, x_coords, y_coords, peak, mode=contour_mode,
                          absmin=contour_absmin, absmax=contour_absmax, factor=contour_factor, custom=contour_custom)
        else:
            contour_levels = []

        if windows:
            for (xa, xb, ya, yb) in windows:
                x0, y0 = min(xa, xb), min(ya, yb)
                w, h   = abs(xb - xa), abs(yb - ya)
                self.ax.add_patch(Rectangle(
                    (x0, y0), w, h,
                    linewidth=1.3, edgecolor='cyan', facecolor='none',
                    linestyle='--', alpha=0.85, zorder=4
                ))

        _add_map_annotations(self.ax, self.fig, cropped_data, self._map_type, contour_levels=contour_levels)
        self.draw()

    def _on_mouse_press(self, event):
        """Gère les clics de souris pour la sélection de fenêtres."""
        if event.inaxes != self.ax:
            return
            
        if event.button == 1 and self.window_selection_mode:  # Clic gauche en mode sélection
            self._start_window_selection()
        elif event.button == 3:  # Clic droit pour basculer le mode sélection
            self._toggle_window_selection_mode()

    def _on_key_press(self, event):
        if event.key == 'r':
            self._sync_combo_to("NAVIGATE")
            self._exit_window_selection_mode()
            self._deactivate_mpl_tools()
        elif event.key == 'z':
            self._sync_combo_to("ZOOM")
            self._exit_window_selection_mode()
            self._activate_mpl_zoom()
        elif event.key == 'w':
            self._toggle_window_selection_mode()
        elif event.key == 'p':
            self._add_peak_window()
        elif event.key == 'd':
            self._delete_all_windows()
        elif event.key == 'm':
            self._toggle_show_model()
        elif event.key == 'escape':
            self._sync_combo_to("NAVIGATE")
            self._exit_window_selection_mode()
            self._deactivate_mpl_tools()

    def _toggle_show_model(self):
        """Toggle l'affichage des composantes du modèle (comme PGPLOT 'M')."""
        parent = self.parent()
        while parent and hasattr(parent, 'parent'):
            if hasattr(parent, 'control_panel'):
                chk = parent.control_panel.chk_show_model_map
                chk.setChecked(not chk.isChecked())
                break
            parent = parent.parent()

    def _activate_window_selection_mode(self):
        self.window_selection_mode = True
        if self.window_selector is None:
            self.window_selector = RectangleSelector(
                self.ax,
                self._on_rectangle_select,
                useblit=True,
                button=[1],
                minspanx=0.01,
                minspany=0.01,
                spancoords='data',
                interactive=False,
                props=dict(facecolor='yellow', alpha=0.3, edgecolor='red', linewidth=2)
            )
        else:
            self.window_selector.set_active(True)
        self.canvas.set_cursor(cursors.SELECT_REGION)
        self._sync_combo_to("ADD_WINDOW")

    def _toggle_window_selection_mode(self):
        if self.window_selection_mode:
            self._exit_window_selection_mode()
        else:
            self._activate_window_selection_mode()

    def _exit_window_selection_mode(self):
        self.window_selection_mode = False
        if self.window_selector:
            self.window_selector.set_active(False)
            self.window_selector = None
        self.canvas.set_cursor(cursors.POINTER)
        self._sync_combo_to("NAVIGATE")
        self.draw()

    def _start_window_selection(self):
        """Démarre une sélection de fenêtre (déjà géré par RectangleSelector)."""
        pass  # RectangleSelector gère la sélection automatiquement

    def _on_rectangle_select(self, eclick, erelease):
        """Callback quand un rectangle est sélectionné."""
        if not self.window_selection_mode:
            return

        x1, y1 = eclick.xdata, eclick.ydata
        x2, y2 = erelease.xdata, erelease.ydata

        if None in (x1, y1, x2, y2):
            return

        xa, xb = sorted([x1, x2])
        ya, yb = sorted([y1, y2])

        if abs(xb - xa) < 0.01 or abs(yb - ya) < 0.01:
            return

        self.selected_window = (xa, xb, ya, yb)

        # Notifier le parent (MainWindow) — le redraw cyan gérera l'affichage
        parent = self.parent()
        while parent is not None:
            if hasattr(parent, '_add_clean_window_from_coords'):
                parent._add_clean_window_from_coords(xa, xb, ya, yb)
                break
            parent = parent.parent()

        self._exit_window_selection_mode()

    def enable_window_selection(self):
        self._activate_window_selection_mode()

class DirtyMapPlotWidget(MapPlotWidget):
    """Widget d'affichage de la Dirty Map (résidu après inversion FFT, avant CLEAN)."""

    _map_title = "Dirty Map"
    _cmap = "inferno"
    _map_type = "dirty"

    def plot_map(self, map_data, cellsize, cellsize_y=None,
                scale='linear', vmin=None, vmax=None, extent=None,
                contour_mode='pct', contour_absmin=1.0, contour_absmax=100.0,
                contour_factor=2.0, contour_custom=None, windows=None):
        """Override to force contour_mode='none' for dirty maps."""
        return super().plot_map(
            map_data=map_data, cellsize=cellsize, cellsize_y=cellsize_y,
            scale=scale, vmin=vmin, vmax=vmax, extent=extent,
            contour_mode='none',  # Force no contours for dirty maps
            contour_absmin=contour_absmin, contour_absmax=contour_absmax,
            contour_factor=contour_factor, contour_custom=contour_custom,
            windows=windows,
        )


class ResidualMapPlotWidget(MapPlotWidget):
    """
    Widget d'affichage de la Residual Map.

    La Residual Map est le buffer **après** ``clean()`` et **avant** ``restore()`` :
    elle représente le résidu que l'algorithme CLEAN n'a pas réussi à déconvoluer.
    Contrairement à la Dirty Map, les lobes de synthèse des sources ont été soustraits.
    Comme pour la Dirty Map, l'ellipse du faisceau n'est pas affichée (ncmp == 0).
    """

    _map_title = "Residual Map"
    _cmap = "inferno"
    _map_type = "residual"

    def plot_map(self, map_data, cellsize, cellsize_y=None,
                scale='linear', vmin=None, vmax=None, extent=None,
                contour_mode='pct', contour_absmin=1.0, contour_absmax=100.0,
                contour_factor=2.0, contour_custom=None, windows=None):
        """Override to force contour_mode='none' for residual maps."""
        return super().plot_map(
            map_data=map_data, cellsize=cellsize, cellsize_y=cellsize_y,
            scale=scale, vmin=vmin, vmax=vmax, extent=extent,
            contour_mode='none',  # Force no contours for residual maps
            contour_absmin=contour_absmin, contour_absmax=contour_absmax,
            contour_factor=contour_factor, contour_custom=contour_custom,
            windows=windows,
        )


class CleanMapPlotWidget(MapPlotWidget):
    """
    Widget d'affichage de la Clean Map restaurée.

    Affichage scientifique complet :
    - Contours isophotes (rouge pour négatifs, blanc pour positifs)
    - Ellipse du faisceau propre dans le coin inférieur gauche
    - Rectangles des fenêtres CLEAN actives
    - Annotations texte (pic, niveaux de contours, paramètres beam)
    """

    _map_title = "Clean Map"
    _cmap = "inferno"
    _map_type = "clean"

    def plot_map(self, map_data, cellsize, cellsize_y=None,
                 beam_info=None, windows=None,
                 scale='linear', vmin=None, vmax=None,
                 contour_mode='pct', contour_absmin=1.0, contour_absmax=100.0,
                 contour_factor=2.0, contour_custom=None, extent=None,
                 show_model=False, model_components=None):
        """
        Affiche la Clean Map avec contours, ellipse de faisceau et fenêtres CLEAN.

        Parameters
        ----------
        map_data : numpy.ndarray or None
            Tableau 2D de flux en Jy/beam.
        cellsize : float
            Taille du pixel en mas sur l'axe X.
        cellsize_y : float, optional
            Taille du pixel en mas sur l'axe Y.
        beam_info : dict, optional
            Paramètres du faisceau propre : ``'bmaj'``, ``'bmin'``, ``'bpa'``.
        windows : list of tuple, optional
            Fenêtres CLEAN actives ``[(xa, xb, ya, yb), ...]`` en mas.
        scale : str, optional
            Échelle de couleur : ``'linear'``, ``'log'`` ou ``'sqrt'`` (mapfunc).
        vmin, vmax : float, optional
            Bornes de la colormap (``None`` = automatique).
        contour_mode : str, optional
            Mode de calcul des contours : ``'pct'`` (levs Difmap), ``'log'``
            (loglevs) ou ``'custom'``.
        contour_absmin : float
            Pour ``mode='log'`` : niveau minimal en % du pic (défaut 1 %).
        contour_absmax : float
            Pour ``mode='log'`` : niveau maximal en % du pic (défaut 100 %).
        contour_factor : float
            Pour ``mode='log'`` : facteur multiplicatif (défaut 2.0).
        contour_custom : list of float, optional
            Pour ``mode='custom'`` : niveaux absolus en Jy/beam.
        extent : list of float, optional
            Limites astrométriques ``[xmax, xmin, ymin, ymax]`` déjà calculées
            selon la géométrie Difmap.
        """
        if self.cbar is not None:
            self.cbar.remove()
            self.cbar = None
        self.ax.cla()
        self._setup_axes()

        if map_data is None or len(map_data) == 0:
            self.ax.text(0.5, 0.5, "No Map Data", ha='center', va='center',
                         transform=self.ax.transAxes)
            self.draw()
            return

        # Récupérer les limites personnalisées depuis le ControlPanel si disponibles
        xmin = xmax = ymin = ymax = None
        try:
            parent = self.parent()
            while parent and hasattr(parent, 'parent'):
                if hasattr(parent, 'control_panel'):
                    xmin, xmax, ymin, ymax = parent.control_panel.get_display_area_params()
                    break
                parent = parent.parent()
        except:
            pass  # Ignorer les erreurs, utiliser les valeurs par défaut
        
        # Si des limites personnalisées sont définies, on doit recadrer même si extent est fourni
        custom_limits = any(v is not None for v in (xmin, xmax, ymin, ymax))
        
        # Utiliser la géométrie DIFMAP exacte
        if extent is not None and not custom_limits:
            # Utiliser l'extent fourni (déjà calculé) sans recadrage
            cropped_data = map_data
            astrometric_extent = extent
            nx_crop, ny_crop = cropped_data.shape[1], cropped_data.shape[0]
        else:
            # Appliquer le crop DIFMAP avec limites personnalisées ou par défaut
            cropped_data, astrometric_extent, nx_crop, ny_crop = DifmapMapGeometry.crop_map_data(
                map_data, cellsize, cellsize_y,
                xmin=xmin, xmax=xmax, ymin=ymin, ymax=ymax
            )

        # 1. Image de fond
        norm = _make_norm(scale, vmin, vmax, cropped_data)
        self.image = self.ax.imshow(
            cropped_data, cmap=self._cmap, origin='lower', extent=astrometric_extent, norm=norm
        )
        self.ax.set_aspect('equal', adjustable='box')

        self.cbar = self.fig.colorbar(
            self.image, ax=self.ax,
            label="Flux (Jy/beam)",
            fraction=0.046, pad=0.04
        )

        # 2. Contours isophotes - SEULEMENT sur la clean map (comme difmap.c:3855)
        # Les contours ne sont tracés que sur les cartes restaurées (clean map)
        # selon difmap.c:3855: docont = mappar.docont && ((vlbmap->ncmp && domap) || ...)
        drawn = []
        # Vérifier si c'est une clean map via map_type ou ncmp dans beam_info
        map_type = beam_info.get('map_type', 'dirty') if beam_info else 'dirty'
        ncmp = beam_info.get('ncmp', 0) if beam_info else 0
        is_clean_map = (map_type == 'clean') or (ncmp > 0)
        
        if is_clean_map:
            peak = _imageable_zone_peak(map_data)
            # Coordonnées des CENTRES des pixels (comme PGPLOT tr[] matrix)
            # extent = [xmax, xmin, ymin, ymax] selon convention Difmap
            # Les centres des pixels sont au milieu de chaque cellule
            x_pixel_size = (astrometric_extent[1] - astrometric_extent[0]) / nx_crop
            y_pixel_size = (astrometric_extent[3] - astrometric_extent[2]) / ny_crop
            
            # Centres des pixels X dans le même sens que l'image affichée par imshow().
            # Avec extent=[xmax,xmin,...], la colonne 0 est à x=xmax (bord gauche).
            x_coords = np.linspace(astrometric_extent[0], astrometric_extent[1], nx_crop, endpoint=False) + x_pixel_size / 2
            y_coords = np.linspace(astrometric_extent[2], astrometric_extent[3], ny_crop, endpoint=False) + y_pixel_size / 2
            
            # Créer la grille 2D pour les contours
            x_grid, y_grid = np.meshgrid(x_coords, y_coords)
            drawn = _draw_contours(self.ax, cropped_data, x_grid, y_grid, peak, lw=0.7,
                                   mode=contour_mode, absmin=contour_absmin,
                                   absmax=contour_absmax, factor=contour_factor,
                                   custom=contour_custom)

        # 3. Fenêtres CLEAN (rectangles cyan pointillés)
        if windows:
            for (xa, xb, ya, yb) in windows:
                x0, y0 = min(xa, xb), min(ya, yb)
                w, h   = abs(xb - xa), abs(yb - ya)
                self.ax.add_patch(Rectangle(
                    (x0, y0), w, h,
                    linewidth=1.3, edgecolor='cyan', facecolor='none',
                    linestyle='--', alpha=0.85, zorder=4
                ))

        # 4. Ellipse du faisceau avec ajustement automatique de position (comme plbeam.c)
        if beam_info:
            bmaj = beam_info.get('bmaj', 0.0)
            bmin = beam_info.get('bmin', 0.0)
            bpa  = beam_info.get('bpa',  0.0)
            beam_map_type = beam_info.get('map_type', 'dirty')
            
            # N'afficher le beam que si c'est une clean map (comme difmap.c:1688)
            if bmaj > 0 and bmin > 0 and beam_map_type == 'clean':
                # Calculer la taille relative du beam par rapport à la carte
                xwid = abs(astrometric_extent[0] - astrometric_extent[1])
                ywid = abs(astrometric_extent[3] - astrometric_extent[2])
                
                # Vérification de taille (comme plbeam.c:73-75)
                beam_rel_size = max(bmaj / xwid, bmin / ywid)
                min_rel_size = 0.02  # Au moins 2% de la carte
                max_rel_size = 0.5   # Pas plus de 50% de la carte
                
                if min_rel_size <= beam_rel_size <= max_rel_size:
                    # Position initiale: coin inférieur gauche (normalisée 0-1)
                    margin = 0.05  # Marge de 5% comme plbeam.c:50
                    
                    # Ajustement automatique pour éviter les bords (plbeam.c:80-83)
                    # Calculer la demi-largeur du beam en coordonnées normalisées
                    x_half_width = (bmaj / 2) / xwid if bmaj >= bmin else (bmin / 2) / xwid
                    y_half_width = (bmin / 2) / ywid if bmaj >= bmin else (bmaj / 2) / ywid
                    
                    # Position normalisée ajustée pour éviter les bords
                    # Positionner à 15% depuis le bord gauche, ajusté si nécessaire
                    xpos_norm = max(x_half_width + margin, min(0.15, 1.0 - x_half_width - margin))
                    ypos_norm = max(y_half_width + margin, min(0.15, 1.0 - y_half_width - margin))
                    
                    beam_box = AuxTransformBox(self.ax.transData)
                    beam_box.add_artist(Ellipse(
                        (0.0, 0.0), width=bmaj, height=bmin, angle=90 - bpa,
                        facecolor='gold', edgecolor='white', linewidth=1,
                        alpha=0.85, zorder=5
                    ))
                    self.ax.add_artist(AnchoredOffsetbox(
                        loc='lower left', child=beam_box,
                        pad=0.0, borderpad=1.5, frameon=False
                    ))

        # 5. Annotations texte style difmap complètes
        map_info = {
            'nx': nx_crop,
            'ny': ny_crop,
            'cellsize': cellsize,
            'cellsize_y': cellsize_y,
            'map_type': 'clean'
        }
        if beam_info:
            map_info.update(beam_info)
            
        # 6. Composantes du modèle CLEAN (si show_model=True)
        # Logique exacte de DIFMAP modplot.c:cmpplot():
        # - type == delta → affiche '+' (symbole 2 PGPLOT)
        # - type != delta → affiche ellipse (major, ratio, phi)
        # Couleurs selon DIFMAP modplot.c:31-70:
        # - freepar=0 (fixed) + flux>0 → color 10 (lime/green)
        # - freepar=0 (fixed) + flux<0 → color 2 (red)
        # Les composantes CLEAN sont toujours freepar=0 (fixed)
        # Vérification des limites comme DIFMAP modplot.c:74
        if show_model and model_components:
            import math
            # Récupérer les limites d'affichage (xa < xb, ya < yb)
            xa, xb = astrometric_extent[0], astrometric_extent[1]
            ya, yb = astrometric_extent[2], astrometric_extent[3]
            if xa > xb:
                xa, xb = xb, xa
            if ya > yb:
                ya, yb = yb, ya
            
            nhidden = 0  # Compteur de composantes hors limites
            for cmp in model_components:
                cx, cy = cmp['x'], cmp['y']
                cmp_type = cmp.get('type', 'delta')
                major = cmp.get('major', 0.0)
                flux = cmp.get('flux', 0.0)
                
                # Vérifier si le centre est visible (comme DIFMAP cmpplot:74)
                visible = (cx >= xa and cx <= xb and cy >= ya and cy <= yb)
                if not visible:
                    nhidden += 1
                    continue  # Ne pas afficher les composantes hors limites
                
                # Couleur selon le signe du flux (comme DIFMAP)
                # Les composantes CLEAN sont fixed (freepar=0)
                if flux >= 0:
                    color = 'lime'      # PGPLOT color 10 (green/yellow)
                else:
                    color = 'red'        # PGPLOT color 2 (red)
                
                # Delta components: afficher '+'
                if cmp_type == 'delta' or major <= 0:
                    self.ax.plot(cx, cy, '+', color=color, markersize=6,
                                markeredgewidth=1.0, alpha=0.9, zorder=6)
                else:
                    # Composantes étendues (gaussian, disk, ellipsoid, ring, etc.)
                    # DIFMAP: phi = angle du grand axe depuis Nord vers Est (radians)
                    # Matplotlib: angle antihoraire depuis l'axe X (Est)
                    # Conversion: angle_mpl = 90° - phi_deg
                    phi_rad = cmp.get('phi', 0.0)
                    ratio = cmp.get('ratio', 1.0)
                    angle_deg = 90.0 - math.degrees(phi_rad)
                    
                    # el_define() en DIFMAP: minor = major * ratio
                    # Matplotlib: width = minor, height = major
                    minor = major * ratio
                    self.ax.add_patch(Ellipse(
                        (cx, cy),
                        width=minor,
                        height=major,
                        angle=angle_deg,
                        facecolor='none', edgecolor=color,
                        linewidth=0.8, alpha=0.9, zorder=6
                    ))
            
            # Signaler les composantes hors limites (comme DIFMAP maplot.c:2215-2218)
            if nhidden > 0:
                import logging
                logging.info(f"[MODEL] {nhidden} composante(s) hors de la zone d'affichage")

        _add_map_annotations(self.ax, self.fig, cropped_data, "clean",
                              beam_info=beam_info, contour_levels=drawn,
                              contour_mode=contour_mode, map_info=map_info)

        self.draw()
