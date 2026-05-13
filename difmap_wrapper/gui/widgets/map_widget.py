import numpy as np
import matplotlib as mpl
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
import difmap_native
import re

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


def _add_map_annotations(ax, fig, map_data, map_type, beam_info=None,
                          contour_levels=None, contour_mode='pct',
                          observation_data=None, map_info=None):
    """
    Ajoute les annotations texte en bas de l'axe (en dehors de la grille).
    """
    # Préparer les informations pour map_annotations.py
    if map_info is None:
        map_info = {}
    
    # Ajouter les informations de beam si disponibles
    if beam_info:
        map_info.update(beam_info)
    
    # Calculer les stats locales
    dmin = float(np.nanmin(map_data))
    dmax = float(np.nanmax(map_data))
    peak_signed = float(Visualizer._vis_central_peak(map_data))
    peak_abs = abs(peak_signed)

    # RMS sur toute la zone imageable (map_data est déjà croppée).
    # On privilégie map_info['rms'] si fourni par l'imager, sinon fallback calculé.
    if isinstance(map_info, dict) and map_info.get('rms', None) is not None:
        rms = float(map_info.get('rms') or 0.0)
    else:
        rms = float(np.sqrt(np.nanmean(map_data ** 2))) if map_data.size > 0 else 0.0
    
    formatted_lines: list[str] = []

    header_text = ""
    try:
        header_text = difmap_native.get_header_text() or ""
    except Exception:
        header_text = ""

    freq_ghz = 0.0
    if header_text:
        freqs = []
        for m in re.finditer(r"^\s*\d+\s+\d+\s+([0-9.]+e[+-]\d+)", header_text, flags=re.MULTILINE):
            try:
                freqs.append(float(m.group(1)))
            except Exception:
                continue
        if freqs:
            freq_ghz = float(np.mean(freqs)) / 1e9

    date_str = ""
    if header_text:
        m = re.search(r"\b(19|20)\d{2}\s+[A-Za-z]{3}\s+\d{1,2}\b", header_text)
        if m:
            date_str = m.group(0)

    stations_str = ""
    try:
        uv = difmap_native.get_uv_data() or {}
        tel_a = uv.get('tel_a')
        tel_b = uv.get('tel_b')
        sub = uv.get('subarray')
        if tel_a is not None and tel_b is not None and len(tel_a) and len(tel_b):
            n_tel = int(max(int(np.max(tel_a)), int(np.max(tel_b)))) + 1
            isub = int(sub[0]) if sub is not None and len(sub) else 0
            codes = []
            for itel in range(n_tel):
                name = difmap_native.get_telescope_name(isub, itel)
                if not name:
                    continue
                code = name.strip().upper()[:2]
                codes.append(code)
            if codes:
                stations_str = "".join(sorted(set(codes)))
    except Exception:
        stations_str = ""

    # Source/Pol (fallback robust)
    try:
        source = difmap_native.get_source()
    except Exception:
        source = "UNKNOWN"
    try:
        pol = difmap_native.get_polarization()
    except Exception:
        pol = "XX"

    ra = "00 00 00.000"
    dec = "+00 00 00.000"
    if header_text:
        m = re.search(
            r"^\s*OBSRA\s*=\s*\"?([^\"\n]+)\"?\s*$", header_text,
            flags=re.IGNORECASE | re.MULTILINE,
        )
        n = re.search(
            r"^\s*OBSDEC\s*=\s*\"?([^\"\n]+)\"?\s*$", header_text,
            flags=re.IGNORECASE | re.MULTILINE,
        )
        if m and n:
            ra = " ".join(m.group(1).strip().replace(':', ' ').split())
            dec = " ".join(n.group(1).strip().replace(':', ' ').split())
        else:
            m = re.search(
                r"RA\s*[=:]\s*([0-9hms:.\s]+)\s*[,;]?\s*Dec\s*[=:]\s*([+\-0-9dms:.\s]+)",
                header_text,
                flags=re.IGNORECASE,
            )
            if m:
                ra = " ".join(m.group(1).strip().replace(':', ' ').split())
                dec = " ".join(m.group(2).strip().replace(':', ' ').split())

    map_label = (map_type or 'dirty').capitalize()
    if stations_str:
        formatted_lines.append(f"{map_label} {pol} map.  Array: {stations_str}")
    else:
        formatted_lines.append(f"{map_label} {pol} map.")

    if freq_ghz > 0 and date_str:
        formatted_lines.append(f"{source}  at {freq_ghz:.3f} GHz  {date_str}")
    elif freq_ghz > 0:
        formatted_lines.append(f"{source}  at {freq_ghz:.3f} GHz")
    elif date_str:
        formatted_lines.append(f"{source}  {date_str}")
    else:
        formatted_lines.append(f"{source}")

    formatted_lines.append(f"Map center:  RA: {ra},  Dec: {dec} (2000.0)")
    formatted_lines.append(f"Displayed range: {dmin:.4g} to {dmax:.4g} Jy/beam")

    if map_type == "clean":
        formatted_lines.append(f"Map peak: {dmax:.4g} Jy/beam")
        if contour_levels:
            cpeak = Visualizer._vis_central_peak(map_data)
            if cpeak != 0:
                pct_levels = [float(lvl) / cpeak * 100.0 for lvl in contour_levels if np.isfinite(lvl)]
                show = pct_levels[:8]
                suffix = " ..." if len(pct_levels) > 8 else ""
                formatted_lines.append(
                    "Contours %: " + " ".join(f"{p:.0g}" for p in show) + suffix
                )

        bmaj = float(map_info.get('bmaj', 0.0) or 0.0)
        bmin = float(map_info.get('bmin', 0.0) or 0.0)
        bpa = float(map_info.get('bpa', 0.0) or 0.0)
        if bmaj > 0 and bmin > 0:
            formatted_lines.append(f"Beam FWHM: {bmaj:.3g} × {bmin:.3g} (mas) at {bpa:.2f}°")

    if map_type in {"residual", "clean"} and rms > 0:
        formatted_lines.append(f"RMS: {rms:.4g} Jy/beam")
        formatted_lines.append(f"{peak_abs / rms:.1f}σ")

    if formatted_lines:
        text_content = "\n".join(formatted_lines)
        ax.text(
            0.5, -0.12, text_content,
            transform=ax.transAxes,
            ha='center', va='top',
            fontsize=7.5,
            fontfamily='monospace',
            color=DesignSystem.TEXT,
            clip_on=False,
            zorder=10,
        )

    # Les labels scientifiques restent des labels d'axes
    ax.set_xlabel("Décalage RA (mas)", fontsize=9)
    ax.set_ylabel("Décalage Dec (mas)", fontsize=9)


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
        self._instance_cmap = self.__class__._cmap

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
        self._btn_reset          = QPushButton("Reset  [R]")
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
                contour_factor=2.0, contour_custom=None, windows=None,
                show_model=False, model_components=None):
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

        # Utiliser la géométrie DIFMAP exacte
        if extent is not None:
            # Utiliser l'extent fourni (déjà calculé) sans recadrage
            cropped_data = map_data
            astrometric_extent = extent
            nx_crop, ny_crop = cropped_data.shape[1], cropped_data.shape[0]
        else:
            # Appliquer le crop DIFMAP par défaut
            cropped_data, astrometric_extent, nx_crop, ny_crop = DifmapMapGeometry.crop_map_data(
                map_data, cellsize, cellsize_y,
                xmin=None, xmax=None, ymin=None, ymax=None
            )

        scale_l = (scale or 'linear').lower()
        data_show = np.ma.masked_less_equal(cropped_data, 0.0) if scale_l == 'log' else cropped_data
        norm = Visualizer._make_norm(scale, vmin, vmax, cropped_data)
        self.image = self.ax.imshow(
            data_show, cmap=self._instance_cmap, origin='lower', extent=astrometric_extent, norm=norm
        )
        self.ax.set_aspect('equal', adjustable='box')

        self.cbar = self.fig.colorbar(
            self.image, ax=self.ax,
            label="Flux (Jy/beam)",
            fraction=0.046, pad=0.04
        )

        # DIFMAP: pas de contours sur Dirty/Residual maps.
        # Les contours sont uniquement tracés sur la Clean Map restaurée.
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

        if show_model and model_components:
            import math
            xa, xb = astrometric_extent[0], astrometric_extent[1]
            ya, yb = astrometric_extent[2], astrometric_extent[3]
            if xa > xb:
                xa, xb = xb, xa
            if ya > yb:
                ya, yb = yb, ya
            for cmp in model_components:
                cx, cy = cmp['x'], cmp['y']
                if not (xa <= cx <= xb and ya <= cy <= yb):
                    continue
                flux = cmp.get('flux', 0.0)
                major = cmp.get('major', 0.0)
                color = 'lime' if flux >= 0 else 'red'
                if cmp.get('type', 'delta') == 'delta' or major <= 0:
                    self.ax.plot(cx, cy, '+', color=color, markersize=6,
                                 markeredgewidth=1.0, alpha=0.9, zorder=6)
                else:
                    phi_deg = 90.0 - math.degrees(cmp.get('phi', 0.0))
                    ratio = max(cmp.get('ratio', 1.0), 1e-6)
                    minor = major * ratio
                    ell = Ellipse(
                        (cx, cy), width=minor, height=major,
                        angle=phi_deg, linewidth=1.0,
                        edgecolor=color, facecolor='none', alpha=0.85, zorder=6
                    )
                    self.ax.add_patch(ell)

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
        if event.key in ('r', 'home'):
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

    def update_colormap(self, cmap_name: str) -> None:
        self._instance_cmap = cmap_name
        if self.image is not None:
            self.image.set_cmap(cmap_name)
            self.draw()

class DirtyMapPlotWidget(MapPlotWidget):
    """Widget d'affichage de la Dirty Map (résidu après inversion FFT, avant CLEAN)."""

    _map_title = "Dirty Map"
    _cmap = "inferno"
    _map_type = "dirty"

    def plot_map(self, map_data, cellsize, cellsize_y=None,
                scale='linear', vmin=None, vmax=None, extent=None,
                contour_mode='pct', contour_absmin=1.0, contour_absmax=100.0,
                contour_factor=2.0, contour_custom=None, windows=None,
                show_model=False, model_components=None):
        """Override to force contour_mode='none' for dirty maps."""
        return super().plot_map(
            map_data=map_data, cellsize=cellsize, cellsize_y=cellsize_y,
            scale=scale, vmin=vmin, vmax=vmax, extent=extent,
            contour_mode='none',
            contour_absmin=contour_absmin, contour_absmax=contour_absmax,
            contour_factor=contour_factor, contour_custom=contour_custom,
            windows=windows,
            show_model=show_model, model_components=model_components,
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
                contour_factor=2.0, contour_custom=None, windows=None,
                show_model=False, model_components=None):
        """Override to force contour_mode='none' for residual maps."""
        return super().plot_map(
            map_data=map_data, cellsize=cellsize, cellsize_y=cellsize_y,
            scale=scale, vmin=vmin, vmax=vmax, extent=extent,
            contour_mode='none',
            contour_absmin=contour_absmin, contour_absmax=contour_absmax,
            contour_factor=contour_factor, contour_custom=contour_custom,
            windows=windows,
            show_model=show_model, model_components=model_components,
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

        # Utiliser la géométrie DIFMAP exacte
        if extent is not None:
            # Utiliser l'extent fourni (déjà calculé) sans recadrage
            cropped_data = map_data
            astrometric_extent = extent
            nx_crop, ny_crop = cropped_data.shape[1], cropped_data.shape[0]
        else:
            # Appliquer le crop DIFMAP par défaut
            cropped_data, astrometric_extent, nx_crop, ny_crop = DifmapMapGeometry.crop_map_data(
                map_data, cellsize, cellsize_y,
                xmin=None, xmax=None, ymin=None, ymax=None
            )

        # 1. Image de fond
        scale_l = (scale or 'linear').lower()
        data_show = np.ma.masked_less_equal(cropped_data, 0.0) if scale_l == 'log' else cropped_data
        norm = Visualizer._make_norm(scale, vmin, vmax, cropped_data)
        self.image = self.ax.imshow(
            data_show, cmap=self._instance_cmap, origin='lower', extent=astrometric_extent, norm=norm
        )
        self.ax.set_aspect('equal', adjustable='box')

        self.cbar = self.fig.colorbar(
            self.image, ax=self.ax,
            label="Flux (Jy/beam)",
            fraction=0.046, pad=0.04
        )

        # 2. Contours isophotes - SEULEMENT sur la clean map (comme difmap.c:3855)
        # Ici on est dans le widget CleanMap, donc on trace les contours si demandés.
        drawn = []
        if contour_mode != 'none':
            # Peak sur la totalité de cropped_data (= zone imageable, déjà croppée).
            # Correspond au comportement de maplot.c:setcont() sur la zone imageable.
            peak = Visualizer._vis_central_peak(cropped_data)
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
            drawn = Visualizer._vis_draw_contours(
                self.ax, cropped_data, x_grid, y_grid, peak, lw=0.3,
                mode=contour_mode, absmin=contour_absmin,
                absmax=contour_absmax, factor=contour_factor,
                custom=contour_custom
            )

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
                        width=major,
                        height=minor,
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
