# difmap_wrapper/gui/widgets/base_plot_widget.py
"""
Classe de base pour tous les widgets Matplotlib.

Évite la duplication de code entre UVPlotWidget, MapPlotWidget, RadPlotWidget.
"""

import os

from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QSizePolicy
from PyQt6.QtCore import Qt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

from difmap_wrapper.gui.utils import MatplotlibStyler


class BasePlotWidget(QWidget):
    """
    Widget parent pour tous les graphiques Matplotlib.
    
    Encapsule:
    - Creation de la Figure
    - Création du Canvas
    - Setup des axes
    - Optionnellement la toolbar
    
    Avantages:
    - Pas de duplication
    - Facile à étendre
    - Cohérent dans toute l'app
    
    Example
    -------
    >>> class MyPlotWidget(BasePlotWidget):
    >>>     def __init__(self, parent=None):
    >>>         super().__init__(parent=parent, figsize=(8, 6))
    >>>         # Code spécifique
    """
    
    def __init__(self, parent=None, figsize=(8, 8), include_toolbar=False,
                 facecolor='#141414', layout_type='constrained'):
        """
        Parameters
        ----------
        parent : QWidget, optional
        figsize : tuple
            Dimensions de la figure (width, height) en inches
        include_toolbar : bool
            Ajouter la barre d'outils Matplotlib standard
        facecolor : str
            Couleur du fond
        layout_type : str
            Type de layout Matplotlib ('constrained' ou None)
        """
        # Assurer qu'une QApplication existe avant de créer un QWidget.
        # Sans QApplication, Qt peut abort (Fatal Python error: Aborted).
        if QApplication.instance() is None:
            if not os.environ.get("DISPLAY"):
                os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
            self._qt_app = QApplication([])
        super().__init__(parent)

        # Layout principal
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # ── Toolbar locale (peuplée par les sous-classes) ────────
        self.plot_toolbar_row = QWidget()
        self.plot_toolbar_row.setVisible(False)
        self.plot_toolbar_row.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.plot_toolbar_layout = QHBoxLayout(self.plot_toolbar_row)
        self.plot_toolbar_layout.setContentsMargins(6, 2, 6, 2)
        self.plot_toolbar_layout.setSpacing(4)
        self.layout.addWidget(self.plot_toolbar_row)

        # Figure Matplotlib
        self.fig = Figure(
            figsize=figsize,
            facecolor=facecolor,
            layout=layout_type
        )
        self.ax = self.fig.add_subplot(111)

        # Canvas PyQt
        self.canvas = FigureCanvas(self.fig)

        # Toolbar optionnelle
        self.toolbar = None
        if include_toolbar:
            self.toolbar = NavigationToolbar(self.canvas, self)
            self.layout.addWidget(self.toolbar)

        # Ajout du canvas
        self.layout.addWidget(self.canvas)

        # Setup initial des axes
        self._setup_axes()

        # Focus policy pour les shortcuts
        self.canvas.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    
    def _setup_axes(self):
        """À surcharger dans les classes filles pour custom."""
        MatplotlibStyler.setup_axes(self.ax)
    
    def refresh(self):
        """Rafraîchit l'affichage du canvas."""
        self.canvas.draw_idle()
    
    def draw(self):
        """Planifie un redraw via l'event loop (draw_idle évite de saturer Wayland)."""
        self.canvas.draw_idle()
    
    def get_figure(self):
        """Retourne la Figure Matplotlib."""
        return self.fig
    
    def get_axes(self):
        """Retourne l'axe principal."""
        return self.ax
    
    def get_canvas(self):
        """Retourne le Canvas PyQt."""
        return self.canvas

    def _export_png(self, default_filename: str = "figure.png") -> None:
        """Ouvre une boîte de dialogue et exporte la figure courante en PNG."""
        from PyQt6.QtWidgets import QFileDialog
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Export PNG",
            default_filename,
            "PNG Images (*.png);;All Files (*)",
        )
        if not filepath:
            return
        if not filepath.lower().endswith(".png"):
            filepath += ".png"
        self.fig.savefig(
            filepath,
            dpi=150,
            bbox_inches="tight",
            facecolor=self.fig.get_facecolor(),
        )


