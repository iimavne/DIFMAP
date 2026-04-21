# difmap_wrapper/gui/plot_widget.py
import numpy as np
from PyQt6.QtCore import Qt

from difmap_wrapper.gui.widgets.base_plot_widget import BasePlotWidget
from difmap_wrapper.editors.uv_editor import UVPlotEditor
from difmap_wrapper.gui.utils import MatplotlibStyler
from difmap_wrapper.gui.styles.design_system import DesignSystem


class UVPlotWidget(BasePlotWidget):
    """
    Widget PyQt6 encapsulant un graphique Matplotlib interactif pour le plan UV.

    M3 — reload_data() permet de réutiliser le widget sans détruire l'onglet.
         Les callbacks sont stockés à l'init pour être réutilisés lors du reload.
    """

    def __init__(self, observation, data, parent=None,
                 save_callback=None, sync_callback=None):
        """
        Parameters
        ----------
        observation : Observation
            Objet contenant les métadonnées et le masque de flagging.
        data : dict
            Données UV brutes (clés ``'u'``, ``'v'``, ``'amp'``, ``'phase'``, ``'weight'``...).
        parent : QWidget, optional
            Widget parent Qt.
        save_callback : callable, optional
            Fonction appelée lors de la sauvegarde (ouvre un dialogue fichier).
        sync_callback : callable, optional
            Fonction appelée pour synchroniser l'état éditeur → MainWindow.
        """
        super().__init__(parent=parent, figsize=(8, 8), layout_type='constrained')

        # Stocker les callbacks pour les réutiliser dans reload_data()
        self._save_callback = save_callback
        self._sync_callback = sync_callback

        self.observation = observation
        self.data        = data

        self._draw_and_create_editor()

    def _draw_and_create_editor(self) -> None:
        """Trace les scatter plots et instancie l'éditeur."""
        self.ax.clear()
        self._setup_axes()
        
        u = self.data['u'] / 1e6
        v = self.data['v'] / 1e6

        self.editor = UVPlotEditor(
            observation=self.observation,
            fig=self.fig,
            ax=self.ax,
            data=self.data,
            base_color=DesignSystem.PLOT_DATA,
            save_callback=self._save_callback,
            sync_callback=self._sync_callback,
        )
        self.editor.update_marker_size(self.editor.marker_sizes[self.editor.current_size_idx])

    def reload_data(self, data, observation=None) -> None:
        """
        M3 — Met à jour les données sans détruire/recréer le widget ni l'onglet.

        Déconnecte les écouteurs de l'ancien éditeur (cleanup()), puis recrée
        l'éditeur proprement.
        
        ✅ CORRECTION: Restore l'état du crosshair du nouvel éditeur.

        Parameters
        ----------
        data : dict
            Nouvelles données UV depuis Observation.get_data().
        observation : Observation, optional
            Nouvelle observation (ex : après changement de polarisation).
        """
        if observation is not None:
            self.observation = observation
        self.data = data

        # ✅ CORRECTION 1: Sauvegarder l'état du crosshair AVANT cleanup
        crosshair_was_active = False
        if self.editor and hasattr(self.editor, 'cursor_active'):
            crosshair_was_active = self.editor.cursor_active

        # Déconnexion propre des anciens écouteurs Matplotlib
        if self.editor:
            self.editor.cleanup()

        # Recréation de l'éditeur (nouvelles connexions événements, nouveau masque)
        self._draw_and_create_editor()
        
        # ✅ CORRECTION 2: Restaurer l'état du crosshair sur le nouvel éditeur
        if crosshair_was_active and self.editor and hasattr(self.editor, 'cursor_active'):
            if not self.editor.cursor_active:
                # Force l'activation du crosshair sur le nouvel éditeur
                self.editor.action_toggle_crosshair(None)
        
        self.fig.canvas.draw_idle()

    def _setup_axes(self):
        """Configure les axes spécifiques au plan UV."""
        MatplotlibStyler.setup_axes(
            self.ax,
            title_text="UV Coverage",
            xlabel=r"U ($M\lambda$)",
            ylabel=r"V ($M\lambda$)"
        )
        self.ax.invert_xaxis()
        self.ax.set_aspect('equal')
