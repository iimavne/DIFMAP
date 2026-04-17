from PyQt6.QtCore import Qt
from difmap_wrapper.gui.widgets.base_plot_widget import BasePlotWidget
from difmap_wrapper.editors.uv_editor import UVPlotEditor
from difmap_wrapper.gui.utils import MatplotlibStyler
from difmap_wrapper.gui.styles.design_system import DesignSystem

class UVPlotWidget(BasePlotWidget):
    """Widget PyQt encapsulant un graphique Matplotlib interactif pour le plan UV."""

    def __init__(self, observation, data, parent=None, info_callback=None, save_callback=None, sync_callback=None):
        # On délègue la création du Layout, Figure, et Canvas à la classe parente
        super().__init__(parent=parent, figsize=(8, 8), layout_type='constrained')
        
        self.observation = observation
        self.data = data

        u = self.data['u'] / 1e6
        v = self.data['v'] / 1e6

        # self.ax est fourni gratuitement par BasePlotWidget !
        self.scat_main = self.ax.scatter(u, v, s=1, color=DesignSystem.PLOT_DATA, alpha=0.5, edgecolors='none')
        self.scat_conj = self.ax.scatter(-u, -v, s=1, color=DesignSystem.PLOT_DATA, alpha=0.5, edgecolors='none')
        self.scat_conj.set_visible(False)

        # Connexion au contrôleur interactif
        self.editor = UVPlotEditor(
            observation=self.observation,
            fig=self.fig,
            ax=self.ax,
            data=self.data,
            scat_main=self.scat_main,
            scat_conj=self.scat_conj,
            base_color=DesignSystem.PLOT_DATA,
            info_callback=info_callback,
            save_callback=save_callback,
            sync_callback=sync_callback
        )
        
        # ✅ CRUCIAL: Appliquer la taille initiale des points (comme dans RadPlotWidget)
        # La taille commence à 2.5 (fine), puis grossit avec le slider/touche . : 2.5 → 6 → 15
        self.editor.update_marker_size(self.editor.marker_sizes[self.editor.current_size_idx])
        
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