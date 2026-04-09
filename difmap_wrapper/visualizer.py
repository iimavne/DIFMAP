import difmap_native
from matplotlib import pyplot as plt
import numpy as np

from difmap_wrapper.uv_editor import UVPlotEditor


class Visualizer():
    """
    Classe Visualizer pour l'affichage et l'extraction d'informations sur les 
    données d'observation chargées dans une session Difmap.

    Parameters
    ----------
    session : DifmapSession
        La session Difmap à laquelle ce visualiseur est associé.
        
    """
    
    def __init__(self, session):
        self._session = session
        self._native = difmap_native
    
    def uvplot(self, ax=None, figsize=(8, 8), color='blue', s=1, alpha=0.5, title=None, edgecolors='none', interactive=False, **kwargs):
            """
            Affiche un graphique de la couverture du plan UV (U vs V).

            Les coordonnées sont automatiquement converties en Méga-longueurs 
            d'onde (Mλ). 

            Parameters
            ----------
            ax : matplotlib.axes.Axes, optional
                Un axe Matplotlib existant sur lequel dessiner.
            figsize : tuple, optional
                Taille de la figure créée si ax est None. Par défaut (8, 8).
            color : str, optional
                Couleur des points de la couverture UV. Par défaut 'blue'.
            s : float, optional
                Taille des points (scatter size). Par défaut 1.
            alpha : float, optional
                Transparence des points (0 = invisible, 1 = opaque). Par défaut 0.5.
            title : str, optional
                Titre personnalisé du graphique. Si None, génère un titre par défaut 
                incluant le nom de la source.
            **kwargs : dict
                Arguments supplémentaires passés directement à matplotlib.axes.Axes.scatter

            Returns
            -------
            ax : matplotlib.axes.Axes
            """
            # 1. On récupère les données AVEC les métadonnées du C
            data = self._native.get_uv_data()
            if not data or len(data.get('u', [])) == 0:
                print("Aucune donnée UV. Appelez select() avant uvplot().")
                return None

            u = data['u'] / 1e6
            v = data['v'] / 1e6
            
            if ax is None:
                fig, ax = plt.subplots(figsize=figsize)
                cree_nouvelle_figure = True
            else:
                cree_nouvelle_figure = False
            
            # 2. CRUCIAL : On stocke les objets "scatter" dans des variables
            # On stocke aussi la couleur par défaut pour que l'éditeur s'en souvienne
            scat_main = ax.scatter(u, v, s=s, color=color, alpha=alpha, **kwargs)
            scat_conj = ax.scatter(-u, -v, s=s, color=color, alpha=alpha,**kwargs)
            
            ax.set_xlabel(r"U ($M\lambda$)")
            ax.set_ylabel(r"V ($M\lambda$)")
            
            if title is not None:
                ax.set_title(title)
            else:
                source_name = self._session.obs.source
                ax.set_title(f"Couverture UV : {source_name}")
            
            ax.invert_xaxis()
            ax.set_aspect('equal')
            ax.grid(True, linestyle=':', alpha=0.6)
            
            # 3. On passe TOUTES ces infos à l'Éditeur
            if interactive:
                # /!\ CRUCIAL : On passe self._session.obs (et non self)
                ax._editor = UVPlotEditor(self._session.obs, ax.figure, ax, data, scat_main, scat_conj, color)
                print("Mode UVPlot interactif activé ! ")                
            
            if cree_nouvelle_figure:
                plt.show()
                
            return ax

    def radplot(self, ax=None, figsize=(10, 6), color='black', alpha=0.5, s=1, title=None, **kwargs):
            """
            Affiche l'amplitude des visibilités en fonction du rayon UV.

            Le rayon UV représente la distance de la ligne de base au centre du plan, 
            exprimée en Méga-longueurs d'onde (Mλ).

            Parameters
            ----------
            ax : matplotlib.axes.Axes, optional
                Un axe matplotlib existant sur lequel dessiner. Si None, crée une nouvelle figure.
            figsize : tuple, optional
                Taille de la figure créée si ax est None. Par défaut (10, 6).
            color : str, optional
                Couleur des points du graphique Matplotlib. Par défaut 'black'.
            alpha : float, optional
                Transparence des points (0.0 à 1.0). Par défaut 0.5.
            s : int or float, optional
                Taille des points (scatter size). Par défaut 1.
            title : str, optional
                Titre personnalisé du graphique. Si None, génère un titre par défaut 
                incluant le nom de la source.
            **kwargs : dict
                Arguments supplémentaires passés à matplotlib.pyplot.scatter.

            Returns
            -------
            matplotlib.axes.Axes
                L'axe contenant le graphique.
            """       
            data = self._native.get_uv_data()
            if not data or len(data.get('u', [])) == 0:
                print("Aucune donnée UV. Appelez select() avant radplot().")
                return None

            # Récupération des données brutes
            u = data['u']
            v = data['v']
            amp = data['amp']
            
            # Calcul du rayon UV (distance au centre) converti en Méga-lambda
            uv_radius = np.sqrt(u**2 + v**2) / 1e6
            
            # Gestion  de l'axe
            if ax is None:
                fig, ax = plt.subplots(figsize=figsize)
                show = True
            else:
                show = False
                
            # Création du graphique sur l'axe spécifié
            ax.scatter(uv_radius, amp, s=s, color=color, alpha=alpha, **kwargs)
            
            # Formatage scientifique
            ax.set_xlabel(r"Rayon UV ($M\lambda$)")
            ax.set_ylabel("Amplitude (Jy)")
            
            # -Gestion  du Titre ---
            if title is not None:
                ax.set_title(title) # Titre forcé par l'utilisateur
            else:
                source_name = self._session.obs.source
                ax.set_title(f"Radplot (Amplitude vs Rayon) : {source_name}") # Titre automatique
            
            ax.set_ylim(bottom=0)
            ax.grid(True, linestyle=':', alpha=0.6)
            
            if show:
                plt.show()
                
            return ax
    @staticmethod
    def plot_image(img_dict: dict, cmap: str = 'magma', figsize: tuple = (8, 6), title: str = "Dirty Map", **kwargs) -> None:
        """
        Affiche graphiquement l'image scientifique avec Matplotlib.

        Parameters
        ----------
        img_dict : dict
            Le dictionnaire contenant l'image ('data') et l'astrométrie ('extent').
        cmap : str, optional
            Nom de la colormap Matplotlib. Par défaut 'magma'.
        figsize : tuple of int, optional
            Dimensions de la figure. Par défaut (8, 6).
        title : str, optional
            Titre de la figure. Par défaut "Dirty Map".
        **kwargs
            Arguments additionnels passés à `plt.imshow`.

        Raises
        ------
        KeyError
            Si le dictionnaire ne contient pas les bonnes clés.

        Examples
        --------
        >>> DifmapImager.plot_image(pkg, cmap='inferno')
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
        Affiche la carte actuellement chargée en mémoire via l'imager.

        Imite le comportement de l'ancien Difmap. Si aucun dictionnaire n'est fourni, 
        il récupère dynamiquement la dernière carte générée en mémoire et l'affiche.

        Parameters
        ----------
        img_dict : dict, optional
            Un package d'image généré manuellement. Si None, récupère la RAM.
        **kwargs
            Arguments additionnels de style passés à `plot_image`.

        Raises
        ------
        DifmapStateError
            Si l'astrométrie (mapsize) ou l'inversion (invert) n'ont pas encore été effectuées.

        Examples
        --------
        >>> session.imager.mapsize(512, 1.0)
        >>> session.imager.invert()
        >>> session.vis.mapplot() # S'affiche automatiquement !
        """
        if img_dict is None:
            # Déléguer à l'imager qui gère l'astrométrie
            from .exceptions import DifmapStateError
            
            if self._session.imager._last_cellsize is None:
                raise DifmapStateError(
                    "Astrométrie inconnue. Veuillez exécuter mapsize() avant mapplot()."
                )
            
            img_dict = self._session.imager.get_map_package(
                cellsize=self._session.imager._last_cellsize
            )
        
        # On envoie le dictionnaire au moteur de dessin
        return self.plot_image(img_dict, **kwargs)