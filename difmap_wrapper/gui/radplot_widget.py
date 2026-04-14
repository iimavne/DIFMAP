import numpy as np
from difmap_wrapper.gui.widgets.base_plot_widget import BasePlotWidget
from difmap_wrapper.editors.rad_editor import RadPlotEditor
from difmap_wrapper.gui.utils import MatplotlibStyler
from difmap_wrapper.gui.styles.design_system import DesignSystem

class RadPlotWidget(BasePlotWidget):
    def __init__(self, parent=None, info_callback=None, sync_callback=None):
        super().__init__(parent=parent, figsize=(8, 5), layout_type='constrained')
        self.info_callback = info_callback
        self.sync_callback = sync_callback
        self.data = None
        self.editor = None

    def _setup_axes(self):
        MatplotlibStyler.setup_axes(
            self.ax,
            title_text="Visibility Amplitude vs UV-Radius",
            xlabel="UV Distance (Mega-wavelengths, Mλ)",
            ylabel="Amplitude (Janskys, Jy)"
        )

    def plot_data(self, data, shared_mask=None, shared_history=None, observation=None):
        self.data = data
        self._setup_axes()
        
        if data is None or len(data.get('u', [])) == 0:
            self.draw() # Hérité de BasePlotWidget
            return

        u, v, amp = data['u'], data['v'], data['amp']
        uv_radius = np.sqrt(u**2 + v**2) / 1e6

        scat_main = self.ax.scatter(
            uv_radius, amp, 
            s=1, color=DesignSystem.PLOT_DATA, alpha=0.5, edgecolors='none'
        )
        self.ax.set_xlim(left=0)
        self.ax.set_ylim(bottom=0)
        
        if observation:
            self.editor = RadPlotEditor(
                observation=observation, fig=self.fig, ax=self.ax, data=self.data,
                scat_main=scat_main, base_color=DesignSystem.PLOT_DATA,
                info_callback=self.info_callback, sync_callback=self.sync_callback,
                shared_mask=shared_mask, shared_history=shared_history
            )
            self.editor._update_colors()
        self.refresh() # Hérité de BasePlotWidget