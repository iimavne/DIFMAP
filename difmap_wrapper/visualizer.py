# difmap_wrapper/visualizer.py
import difmap_native
import numpy as np
from matplotlib import pyplot as plt

# C2 : UVPlotEditor N'EST PLUS importé ici.
# La couche Core (visualizer) ne doit pas connaître la couche Editors (Matplotlib).
# L'éditeur interactif est créé exclusivement dans gui/plot_widget.py (Couche GUI).


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
               title=None, edgecolors='none', **kwargs):
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

        if ax is None:
            fig, ax = plt.subplots(figsize=figsize)
            show = True
        else:
            show = False

        ax.scatter(u,  v,  s=s, color=color, alpha=alpha, edgecolors=edgecolors, **kwargs)
        ax.scatter(-u, -v, s=s, color=color, alpha=alpha, edgecolors=edgecolors, **kwargs)

        ax.set_xlabel(r"U ($M\lambda$)")
        ax.set_ylabel(r"V ($M\lambda$)")
        source_name = self._session.obs.source
        ax.set_title(title or f"Couverture UV : {source_name}")
        ax.invert_xaxis()
        ax.set_aspect('equal')
        ax.grid(True, linestyle=':', alpha=0.6)

        if show:
            plt.show()

        return ax

    def radplot(self, ax=None, figsize=(10, 6), color='black', alpha=0.5, s=1,
                title=None, **kwargs):
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

        if ax is None:
            fig, ax = plt.subplots(figsize=figsize)
            show = True
        else:
            show = False

        ax.scatter(uv_radius, amp, s=s, color=color, alpha=alpha, **kwargs)
        ax.set_xlabel(r"Rayon UV ($M\lambda$)")
        ax.set_ylabel("Amplitude (Jy)")
        source_name = self._session.obs.source
        ax.set_title(title or f"Radplot (Amplitude vs Rayon) : {source_name}")
        ax.set_ylim(bottom=0)
        ax.grid(True, linestyle=':', alpha=0.6)

        if show:
            plt.show()

        return ax

    @staticmethod
    def plot_image(img_dict: dict, cmap: str = 'magma', figsize: tuple = (8, 6),
                   title: str = "Dirty Map", **kwargs) -> None:
        """
        Affiche une image astrophysique avec sa barre de couleur et ses axes astrométriques.

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
        **kwargs
            Paramètres supplémentaires transmis à ``matplotlib.pyplot.imshow``.

        Raises
        ------
        KeyError
            Si les clés ``'data'`` ou ``'extent'`` sont absentes du dictionnaire.

        Examples
        --------
        >>> img = session.imager.make_dirty_map(512, 0.1)
        >>> session.vis.plot_image(img, cmap='viridis', title="Source J0003")
        """
        if "data" not in img_dict or "extent" not in img_dict:
            raise KeyError("Le dictionnaire d'image doit contenir les clés 'data' et 'extent'.")
        plt.figure(figsize=figsize)
        plt.imshow(img_dict['data'], extent=img_dict['extent'], origin='lower', cmap=cmap, **kwargs)
        plt.colorbar(label='Densité de flux (Jy/beam)')
        plt.title(title)
        plt.xlabel("Décalage RA (mas)")
        plt.ylabel("Décalage Dec (mas)")
        plt.show()

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
