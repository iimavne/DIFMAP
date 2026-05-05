import numpy as np
from matplotlib.patches import Ellipse, Rectangle
from matplotlib.colors import Normalize, LogNorm, PowerNorm
from matplotlib.offsetbox import AnchoredOffsetbox, AuxTransformBox
from difmap_wrapper.gui.widgets.base_plot_widget import BasePlotWidget
from difmap_wrapper.gui.utils import MatplotlibStyler
from difmap_wrapper.gui.styles.design_system import DesignSystem
from difmap_wrapper.map_geometry import DifmapMapGeometry, get_difmap_contour_levels
from difmap_wrapper.map_annotations import create_pgplot_style_annotations, DifmapMapAnnotations


def _central_peak(data: np.ndarray) -> float:
    """Pic signé sur la région d'affichage complète.

    Difmap garde le signe de l'extrême dominant dans maplot.c:setcont().
    """
    dmin = float(np.nanmin(data))
    dmax = float(np.nanmax(data))
    return dmax if abs(dmax) > abs(dmin) else dmin


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
    """
    Calcule les niveaux de contours selon Difmap en utilisant map_geometry.py.
    """
    return get_difmap_contour_levels(peak, mode, absmin, absmax, factor, custom)


def _draw_contours(ax, map_data, x_lin, y_lin, peak, lw=0.6,
                   mode='pct', absmin=1.0, absmax=100.0, factor=2.0, custom=None):
    """
    Trace les contours isophotes en suivant la convention PGPLOT de DIFMAP :
    - négatifs : rouge (color index 2), traits pleins
    - positifs : blanc (color index 1), traits pleins
    - Utilise les niveaux exacts de DIFMAP
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
        
        # Contours positifs en blanc
        if pos_levels:
            cs_pos = ax.contour(
                x_lin, y_lin, map_data, levels=pos_levels,
                colors='white', linewidths=lw, linestyles='solid',
                alpha=0.95
            )
            drawn.extend(pos_levels)
        
        # Contours négatifs en rouge
        if neg_levels:
            cs_neg = ax.contour(
                x_lin, y_lin, map_data, levels=neg_levels,
                colors='red', linewidths=lw, linestyles='solid',
                alpha=0.9
            )
            drawn.extend(neg_levels)
    
    return drawn


def _add_map_annotations(ax, map_data, map_type, beam_info=None,
                          contour_levels=None, contour_mode='pct',
                          observation_data=None, map_info=None):
    """
    Ajoute les annotations texte complètes style PGPLOT en utilisant map_annotations.py.
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
    
    # Afficher le texte principal en bas à gauche
    main_text = annotations_dict['main_text']
    if main_text:
        ax.text(0.02, 0.02, main_text, transform=ax.transAxes,
                fontsize=7, color='white', va='bottom', ha='left',
                bbox=dict(boxstyle='round,pad=0.2', facecolor='black', alpha=0.4, linewidth=0))


class MapPlotWidget(BasePlotWidget):
    """
    Widget de base pour l'affichage d'une carte d'intensité avec colorbar.

    Ne pas instancier directement — utiliser :class:`DirtyMapPlotWidget`,
    :class:`CleanMapPlotWidget` ou :class:`ResidualMapPlotWidget`.
    """

    _map_title: str = "Map"
    _cmap: str = "inferno"
    _map_type: str = "dirty"  # "dirty" | "clean" | "residual"

    def __init__(self, parent=None):
        super().__init__(parent=parent, figsize=(6, 6), include_toolbar=True, layout_type='constrained')
        self.toolbar.setMinimumHeight(32)
        self.toolbar.setMaximumHeight(32)
        self.toolbar.setStyleSheet(
            f"background-color: {DesignSystem.SURFACE_ALT}; "
            f"border-bottom: 1px solid {DesignSystem.BORDER};"
        )
        self.image = None
        self.cbar = None

    def _setup_axes(self):
        MatplotlibStyler.setup_axes(
            self.ax,
            title_text=self._map_title,
            xlabel="Décalage RA (mas)",
            ylabel="Décalage Dec (mas)"
        )
        # Forcer l'inversion de l'axe RA comme dans DIFMAP (RA croît de droite à gauche)
        self.ax.invert_xaxis()

    def plot_map(self, map_data, cellsize, cellsize_y=None,
                scale='linear', vmin=None, vmax=None, extent=None):
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
            # Utiliser l'extent fourni (déjà calculé)
            cropped_data = map_data
            astrometric_extent = extent
            nx_crop, ny_crop = cropped_data.shape[1], cropped_data.shape[0]
        else:
            # Appliquer le crop DIFMAP par défaut
            cropped_data, astrometric_extent, nx_crop, ny_crop = DifmapMapGeometry.crop_map_data(
                map_data, cellsize, cellsize_y
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

        _add_map_annotations(self.ax, cropped_data, self._map_type, contour_levels=[])
        self.draw()


class DirtyMapPlotWidget(MapPlotWidget):
    """Widget d'affichage de la Dirty Map (résidu après inversion FFT, avant CLEAN)."""

    _map_title = "Dirty Map"
    _cmap = "inferno"
    _map_type = "dirty"


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
                 contour_factor=2.0, contour_custom=None, extent=None):
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
            # Utiliser l'extent fourni (déjà calculé)
            cropped_data = map_data
            astrometric_extent = extent
            nx_crop, ny_crop = cropped_data.shape[1], cropped_data.shape[0]
        else:
            # Appliquer le crop DIFMAP par défaut
            cropped_data, astrometric_extent, nx_crop, ny_crop = DifmapMapGeometry.crop_map_data(
                map_data, cellsize, cellsize_y
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

        # 2. Contours isophotes
        peak = _central_peak(cropped_data)
        x_lin = np.linspace(astrometric_extent[0], astrometric_extent[1], nx_crop)
        y_lin = np.linspace(astrometric_extent[2], astrometric_extent[3], ny_crop)
        drawn = _draw_contours(self.ax, cropped_data, x_lin, y_lin, peak, lw=0.7,
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

        # 4. Ellipse du faisceau propre dans le coin inférieur gauche
        if beam_info:
            bmaj = beam_info.get('bmaj', 0.0)
            bmin = beam_info.get('bmin', 0.0)
            bpa  = beam_info.get('bpa',  0.0)
            if bmaj > 0 and bmin > 0:
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
            
        _add_map_annotations(self.ax, cropped_data, "clean",
                              beam_info=beam_info, contour_levels=drawn,
                              contour_mode=contour_mode, map_info=map_info)

        self.draw()
