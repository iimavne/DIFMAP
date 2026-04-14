# difmap_wrapper/gui/utils/matplotlib_styles.py
"""
Centralization des styles Matplotlib - ÉVITE DUPLICATION
Utilisé par plot_widget.py, map_widget.py, radplot_widget.py
"""


class MatplotlibStyler:
    """
    Centralise tous les styles Matplotlib au même endroit.
    
    Avantages:
    - Single Responsibility Principle ✓
    - DRY - Don't Repeat Yourself ✓
    - Facile à modifier globalement ✓
    - Maintenable ✓
    """
    
    # Palette de couleurs
    COLORS = {
        'title': '#333333',
        'axis_label': '#666666',
        'grid': '#e0e0e0',
        'spine': '#cccccc',
        'background': 'white'
    }
    
    # Tailles de fonts
    SIZES = {
        'title': 10,
        'label': 9,
        'tick': 8,
        'grid_width': 0.5,
        'line_width_spine': 1.0
    }
    
    @staticmethod
    def setup_axes(ax, title_text="...", xlabel="...", ylabel="..."):
        """
        Configure l'apparence uniforme d'un axe Matplotlib.
        
        Parameters
        ----------
        ax : matplotlib.axes.Axes
            L'axe à styler
        title_text : str
            Texte du titre
        xlabel : str
            Texte de l'axe X
        ylabel : str
            Texte de l'axe Y
        
        Example
        -------
        >>> MatplotlibStyler.setup_axes(self.ax, title_text="My Plot")
        """
        # Nettoie l'axe
        ax.clear()
        
        # Titres et labels
        ax.set_title(
            title_text, 
            fontsize=MatplotlibStyler.SIZES['title'], 
            color=MatplotlibStyler.COLORS['title']
        )
        ax.set_xlabel(
            xlabel, 
            fontsize=MatplotlibStyler.SIZES['label'], 
            color=MatplotlibStyler.COLORS['axis_label']
        )
        ax.set_ylabel(
            ylabel, 
            fontsize=MatplotlibStyler.SIZES['label'], 
            color=MatplotlibStyler.COLORS['axis_label']
        )
        
        # Grille légère et discrète
        ax.grid(
            color=MatplotlibStyler.COLORS['grid'], 
            linestyle='-', 
            linewidth=MatplotlibStyler.SIZES['grid_width'],
            alpha=0.5
        )
        
        # Ticks
        ax.tick_params(
            axis='both', 
            which='major', 
            labelsize=MatplotlibStyler.SIZES['tick'], 
            colors=MatplotlibStyler.COLORS['axis_label']
        )
        
        # Bordures (spines)
        for spine in ax.spines.values():
            spine.set_color(MatplotlibStyler.COLORS['spine'])
            spine.set_linewidth(MatplotlibStyler.SIZES['line_width_spine'])
    
    @staticmethod
    def customize_colors(colors_dict):
        """Permet de personaliser les couleurs globalement."""
        MatplotlibStyler.COLORS.update(colors_dict)
    
    @staticmethod
    def customize_sizes(sizes_dict):
        """Permet de personaliser les tailles globalement."""
        MatplotlibStyler.SIZES.update(sizes_dict)
