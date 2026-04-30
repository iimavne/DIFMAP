# difmap_wrapper/visualizer.py
import difmap_native
import numpy as np
from matplotlib import pyplot as plt
from matplotlib.patches import Ellipse

class Visualizer:
    """
    Graphiques statiques pour explorer les données UV et les images.

    Accessible via ``session.vis``. Pour l'interactivité (flagging au clic,
    zoom, statistiques), utiliser l'interface graphique PyQt6.

    Examples
    --------
    >>> session.obs.select(pol="RR")
    >>> session.vis.uvplot()           # couverture UV
    >>> session.vis.radplot()          # amplitude vs rayon UV
    """

    def __init__(self, session):
        self._session = session
        self._native = difmap_native

    def uvplot(self, ax=None, figsize=(8, 8), color='blue', s=1, alpha=0.5,
               title=None, edgecolors='none', xlim=None, ylim=None,
               save_path: str = None, show: bool = True, **kwargs):
        """
        Affiche la couverture du plan UV (U en abscisse, V en ordonnée).

        Les coordonnées sont converties en Méga-longueurs d'onde (Mλ).
        Les points conjugués (−U, −V) sont ajoutés automatiquement.

        Parameters
        ----------
        ax : matplotlib.axes.Axes, optional
            Axe sur lequel dessiner. Si absent, une nouvelle figure est créée.
        figsize : tuple of float, optional
            Taille ``(largeur, hauteur)`` en pouces si une nouvelle figure est créée.
            Par défaut ``(8, 8)``.
        color : str, optional
            Couleur des points. Par défaut ``'blue'``.
        s : float, optional
            Taille des marqueurs en points². Par défaut ``1``.
        alpha : float, optional
            Transparence des points, entre 0 (invisible) et 1 (opaque).
            Par défaut ``0.5``.
        title : str, optional
            Titre du graphique. Si absent, un titre est généré automatiquement
            à partir du nom de la source.
        **kwargs
            Paramètres supplémentaires transmis à ``matplotlib.axes.Axes.scatter``.

        Returns
        -------
        matplotlib.axes.Axes
            L'axe sur lequel la figure a été tracée.

        Examples
        --------
        >>> session.vis.uvplot(color='steelblue', s=2)

        Sur un axe existant :

        >>> fig, ax = plt.subplots()
        >>> session.vis.uvplot(ax=ax, color='red')
        """
        data = self._native.get_uv_data()
        if not data or len(data.get('u', [])) == 0:
            print("Aucune donnée UV. Appelez select() avant uvplot().")
            return None

        u = data['u'] / 1e6
        v = data['v'] / 1e6

        # Suivi de la création de la figure
        created_fig = False
        if ax is None:
            fig, ax = plt.subplots(figsize=figsize)
            created_fig = True

        ax.scatter(u,  v,  s=s, color=color, alpha=alpha, edgecolors=edgecolors, **kwargs)
        ax.scatter(-u, -v, s=s, color=color, alpha=alpha, edgecolors=edgecolors, **kwargs)

        ax.set_xlabel(r"U ($M\lambda$)")
        ax.set_ylabel(r"V ($M\lambda$)")
        source_name = self._session.obs.source
        ax.set_title(title or f"Couverture UV : {source_name}")
        if xlim is not None:
            ax.set_xlim(xlim)
        if ylim is not None:
            ax.set_ylim(ylim)
        ax.invert_xaxis()
        ax.set_aspect('equal', adjustable='box')
        ax.grid(True, linestyle=':', alpha=0.6)

        # Sauvegarde de la figure si demandée (avant l'affichage potentiel)
        if save_path:
            ax.get_figure().savefig(save_path, bbox_inches='tight')

        # Gestion de l'affichage et de la mémoire
        if created_fig:
            if show:
                plt.show()
            else:
                plt.close(ax.get_figure())

        return ax

    def radplot(self, ax=None, figsize=(10, 6), color='black', alpha=0.5, s=1,
                title=None, save_path: str = None, show: bool = True, **kwargs):
        """
        Affiche l'amplitude des visibilités en fonction de leur rayon UV.

        Ce graphique (aussi appelé "amplitude vs uv-distance") donne une vue
        rapide de la structure de la source : une source ponctuelle donne une
        ligne horizontale, une source étendue montre une décroissance.

        Parameters
        ----------
        ax : matplotlib.axes.Axes, optional
            Axe sur lequel dessiner. Si absent, une nouvelle figure est créée.
        figsize : tuple of float, optional
            Taille ``(largeur, hauteur)`` en pouces. Par défaut ``(10, 6)``.
        color : str, optional
            Couleur des points. Par défaut ``'black'``.
        alpha : float, optional
            Transparence des points. Par défaut ``0.5``.
        s : float, optional
            Taille des marqueurs. Par défaut ``1``.
        title : str, optional
            Titre du graphique. Généré automatiquement si absent.
        **kwargs
            Paramètres supplémentaires transmis à ``matplotlib.axes.Axes.scatter``.

        Returns
        -------
        matplotlib.axes.Axes

        Examples
        --------
        >>> session.vis.radplot(color='navy', alpha=0.3, s=0.5)
        """
        data = self._native.get_uv_data()
        if not data or len(data.get('u', [])) == 0:
            print("Aucune donnée UV. Appelez select() avant radplot().")
            return None

        u = data['u']
        v = data['v']
        amp = data['amp']
        uv_radius = np.sqrt(u**2 + v**2) / 1e6

        # Suivi de la création de la figure
        created_fig = False
        if ax is None:
            fig, ax = plt.subplots(figsize=figsize)
            created_fig = True

        ax.scatter(uv_radius, amp, s=s, color=color, alpha=alpha, **kwargs)
        ax.set_xlabel(r"Rayon UV ($M\lambda$)")
        ax.set_ylabel("Amplitude (Jy)")
        source_name = self._session.obs.source
        ax.set_title(title or f"Radplot (Amplitude vs Rayon) : {source_name}")
        ax.set_ylim(bottom=0)
        ax.grid(True, linestyle=':', alpha=0.6)

        # Sauvegarde de la figure si demandée
        if save_path:
            ax.get_figure().savefig(save_path, bbox_inches='tight')

        # Gestion de l'affichage et de la mémoire
        if created_fig:
            if show:
                plt.show()
            else:
                plt.close(ax.get_figure())

        return ax


    @staticmethod
    def plot_image(img_dict: dict, cmap: str = 'magma', figsize: tuple = (8, 6),
                   title: str = "Dirty Map", xlim=None, ylim=None,
                   show_contours: bool = True, contour_levels=None,
                   contour_color: str = 'white',
                   show_beam: bool = True,
                   save_path: str = None, show: bool = True, **kwargs) -> None:
        """
        Affiche une image astrophysique à la manière de difmap :
        image colorée + contours blancs + ellipse de faisceau.

        Parameters
        ----------
        img_dict : dict
            Dictionnaire retourné par ``DifmapImager.get_map_package()``.
            Doit contenir les clés ``'data'`` (tableau 2D) et ``'extent'``
            (limites en mas pour les axes).
        cmap : str, optional
            Palette de couleurs Matplotlib. Par défaut ``'magma'``.
        figsize : tuple of float, optional
            Taille ``(largeur, hauteur)`` en pouces. Par défaut ``(8, 6)``.
        title : str, optional
            Titre affiché au-dessus de l'image. Par défaut ``"Dirty Map"``.
        show_contours : bool, optional
            Trace les contours de flux à la manière de difmap. Par défaut ``True``.
        contour_levels : list of float, optional
            Niveaux de contour absolus (Jy/beam). Si absent, utilise une séquence
            doublante de 1 % à 90 % du pic (style difmap).
        contour_color : str, optional
            Couleur des contours. Par défaut ``'white'``.
        show_beam : bool, optional
            Dessine l'ellipse du faisceau synthétique en bas à gauche. Par défaut ``True``.
        **kwargs
            Paramètres supplémentaires transmis à ``matplotlib.pyplot.imshow``.

        Raises
        ------
        KeyError
            Si les clés ``'data'`` ou ``'extent'`` sont absentes du dictionnaire.

        Examples
        --------
        >>> img = session.imager.make_clean_map(512, 0.1)
        >>> session.vis.plot_image(img, cmap='viridis', title="Clean Map J0003")
        """
        if "data" not in img_dict or "extent" not in img_dict:
            raise KeyError("Le dictionnaire d'image doit contenir les clés 'data' et 'extent'.")

        data   = img_dict['data']
        extent = img_dict['extent']   # [xmax, xmin, ymin, ymax] en mas
        info   = img_dict.get('info', {})

        fig, ax = plt.subplots(figsize=figsize)
        im = ax.imshow(data, extent=extent, origin='lower', cmap=cmap, **kwargs)
        plt.colorbar(im, ax=ax, label='Densité de flux (Jy/beam)')

        # --- Contours style difmap ---
        peak = float(data.max())
        if show_contours and peak > 0:
            ny, nx = data.shape
            # Coordonnées pixel → monde (extent = [left, right, bottom, top])
            xs = np.linspace(extent[0], extent[1], nx)
            ys = np.linspace(extent[2], extent[3], ny)

            if contour_levels is None:
                # Séquence doublante 1 % → 90 % du pic (style difmap)
                fracs = np.array([0.01, 0.02, 0.04, 0.08, 0.16, 0.32, 0.64, 0.90])
                pos_levels = peak * fracs
                neg_levels = [-peak * 0.01]
            else:
                pos_levels = [l for l in contour_levels if l > 0]
                neg_levels = [l for l in contour_levels if l < 0]

            ax.contour(xs, ys, data, levels=pos_levels,
                       colors=contour_color, linewidths=0.6, origin='lower')
            if neg_levels:
                ax.contour(xs, ys, data, levels=neg_levels,
                           colors=contour_color, linewidths=0.6,
                           linestyles='dashed', origin='lower')

        # --- Ellipse du faisceau synthétique ---
        bmaj = info.get('bmaj', 0.0)
        bmin = info.get('bmin', 0.0)
        bpa  = info.get('bpa',  0.0)   # degrés, Nord vers Est

        if show_beam and bmaj > 0:
            # Coin bas-gauche : 12 % des plages x/y depuis le bord
            x_range = abs(extent[0] - extent[1])
            y_range = abs(extent[3] - extent[2])
            beam_cx = min(extent[0], extent[1]) + 0.12 * x_range
            beam_cy = min(extent[2], extent[3]) + 0.12 * y_range

            # BPA (Nord→Est) → angle matplotlib (axe x inversé : Est à gauche)
            # Nord = +y = 90° CCW depuis +x ; Est = -x = 180° → angle = 90° + BPA
            ell = Ellipse(xy=(beam_cx, beam_cy),
                          width=bmin, height=bmaj,
                          angle=90.0 + bpa,
                          facecolor='white', edgecolor='black',
                          linewidth=0.8, zorder=5)
            ax.add_patch(ell)

        ax.set_title(title)
        ax.set_xlabel("Décalage RA (mas)")
        ax.set_ylabel("Décalage Dec (mas)")
        if xlim is not None:
            ax.set_xlim(xlim)
        if ylim is not None:
            ax.set_ylim(ylim)

        if save_path:
            fig.savefig(save_path, bbox_inches='tight')

        if show:
            plt.show()
        else:
            plt.close(fig)
    def mapplot(self, img_dict: dict = None, **kwargs):
        """
        Affiche l'image actuellement en mémoire.

        Si ``img_dict`` est absent, récupère automatiquement l'image depuis le
        moteur C avec les paramètres du dernier ``mapsize()``.

        Parameters
        ----------
        img_dict : dict, optional
            Package image (sortie de ``get_map_package()``). Si absent, l'image
            courante en mémoire C est utilisée.
        **kwargs
            Paramètres supplémentaires transmis à ``plot_image()``.

        Raises
        ------
        DifmapStateError
            Si ``mapsize()`` n'a pas encore été appelé.

        Examples
        --------
        >>> session.imager.mapsize(512, 0.1)
        >>> session.imager.invert()
        >>> session.vis.mapplot(title="Dirty Map après inversion")
        """
        if img_dict is None:
            from .exceptions import DifmapStateError
            if self._session.imager._last_cellsize is None:
                raise DifmapStateError(
                    "Astrométrie inconnue. Veuillez exécuter mapsize() avant mapplot()."
                )
            img_dict = self._session.imager.get_map_package(
                cellsize=self._session.imager._last_cellsize
            )
        return self.plot_image(img_dict, **kwargs)
