# difmap_wrapper/gui/utils/matplotlib_styles.py

class MatplotlibStyler:
    """
    Applique un style cohérent à tous les axes Matplotlib de l'application.

    Centralise les couleurs (``COLORS``) et les tailles (``SIZES``) pour
    garantir une apparence uniforme sur l'ensemble des graphiques.
    """

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
        """
        Applique le style standard DIFMAP à un axe Matplotlib.

        Efface l'axe, définit les couleurs, la grille, les polices de taille
        et les bordures (spines) selon la palette de l'application.

        Parameters
        ----------
        ax : matplotlib.axes.Axes
            Axe à styliser.
        title_text : str, optional
            Titre de l'axe.
        xlabel : str, optional
            Étiquette de l'axe X.
        ylabel : str, optional
            Étiquette de l'axe Y.
        """
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
    def customize_colors(d):
        """
        Met à jour partiellement la palette de couleurs.

        Parameters
        ----------
        d : dict
            Paires clé/valeur à fusionner dans ``COLORS``
            (ex. ``{'background': '#111111'}``).
        """
        MatplotlibStyler.COLORS.update(d)

    @staticmethod
    def customize_sizes(d):
        """
        Met à jour partiellement les tailles de police et de tracé.

        Parameters
        ----------
        d : dict
            Paires clé/valeur à fusionner dans ``SIZES``
            (ex. ``{'title': 12, 'label': 10}``).
        """
        MatplotlibStyler.SIZES.update(d)
