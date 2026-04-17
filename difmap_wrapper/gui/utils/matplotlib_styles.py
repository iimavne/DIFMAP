# difmap_wrapper/gui/utils/matplotlib_styles.py

class MatplotlibStyler:

    COLORS = {
        'title':      '#2C3E50',
        'axis_label': '#5A7080',
        'tick':       '#5A7080',
        'grid':       '#E8EDF2',
        'spine':      '#C8D4E0',
        'background': 'white',
    }

    SIZES = {
        'title':            10,
        'label':            9,
        'tick':             8,
        'grid_width':       0.5,
        'line_width_spine': 0.8,
    }

    @staticmethod
    def setup_axes(ax, title_text="", xlabel="", ylabel=""):
        ax.clear()
        ax.set_facecolor(MatplotlibStyler.COLORS['background'])
        ax.get_figure().set_facecolor(MatplotlibStyler.COLORS['background'])

        ax.set_title(title_text,
                     fontsize=MatplotlibStyler.SIZES['title'],
                     color=MatplotlibStyler.COLORS['title'], pad=6)
        ax.set_xlabel(xlabel, fontsize=MatplotlibStyler.SIZES['label'],
                      color=MatplotlibStyler.COLORS['axis_label'])
        ax.set_ylabel(ylabel, fontsize=MatplotlibStyler.SIZES['label'],
                      color=MatplotlibStyler.COLORS['axis_label'])

        ax.grid(color=MatplotlibStyler.COLORS['grid'],
                linestyle='-', linewidth=MatplotlibStyler.SIZES['grid_width'], alpha=0.8)

        ax.tick_params(axis='both', which='major',
                       labelsize=MatplotlibStyler.SIZES['tick'],
                       colors=MatplotlibStyler.COLORS['tick'])

        for spine in ax.spines.values():
            spine.set_color(MatplotlibStyler.COLORS['spine'])
            spine.set_linewidth(MatplotlibStyler.SIZES['line_width_spine'])

    @staticmethod
    def customize_colors(d): MatplotlibStyler.COLORS.update(d)

    @staticmethod
    def customize_sizes(d): MatplotlibStyler.SIZES.update(d)
