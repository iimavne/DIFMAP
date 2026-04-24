import numpy as np
from difmap_wrapper.gui.widgets.base_plot_widget import BasePlotWidget
from difmap_wrapper.gui.utils import MatplotlibStyler
from difmap_wrapper.gui.styles.design_system import DesignSystem

class MapPlotWidget(BasePlotWidget):
    """
    Widget d'affichage de la Dirty Map avec colorbar.

    Hérite de :class:`BasePlotWidget` et inclut la toolbar Matplotlib standard
    pour zoomer/naviguer dans la carte d'intensité.
    """

    def __init__(self, parent=None):
        """
        Parameters
        ----------
        parent : QWidget, optional
            Widget parent Qt.
        """
        # La classe parente crée le layout, l'axe ET la toolbar (grâce au True) !
        super().__init__(parent=parent, figsize=(6, 6), include_toolbar=True, layout_type='constrained')
        self.toolbar.setMinimumHeight(32)
        self.toolbar.setMaximumHeight(32)
        self.toolbar.setStyleSheet(f"background-color: {DesignSystem.SURFACE_ALT}; border-bottom: 1px solid {DesignSystem.BORDER};")
        self.image = None
        self.cbar = None

    def _setup_axes(self):
        """Configure les axes avec les étiquettes RA/Dec pour la carte dirty."""
        MatplotlibStyler.setup_axes(
            self.ax,
            title_text="Dirty Map",
            xlabel="Décalage RA (mas)",
            ylabel="Décalage Dec (mas)"
        )

    def plot_map(self, map_data, cellsize):
        """
        Affiche la Dirty Map avec une colorbar flux en Jy/beam.

        Parameters
        ----------
        map_data : numpy.ndarray or None
            Tableau 2D de flux en Jy/beam. Si ``None`` ou vide, affiche un message.
        cellsize : float
            Taille d'une cellule en millisecondes d'arc (mas), utilisée pour
            calculer l'étendue spatiale de l'image.
        """
        # 1. On supprime proprement la colorbar précédente
        if self.cbar is not None:
            self.cbar.remove()
            self.cbar = None
            
        self._setup_axes()
        
        if map_data is None or len(map_data) == 0:
            self.ax.text(0.5, 0.5, "No Map Data", ha='center', va='center')
            self.draw()
            return

        size = map_data.shape[0]
        extent_val = (size * cellsize) / 2.0
        extent = [extent_val, -extent_val, -extent_val, extent_val]

        self.image = self.ax.imshow(
            map_data, 
            cmap='inferno',
            origin='lower',
            extent=extent
        )
        
        self.cbar = self.fig.colorbar(self.image, ax=self.ax, label="Flux (Jy/beam)", fraction=0.046, pad=0.04)
        self.draw()