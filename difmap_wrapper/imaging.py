# difmap_wrapper/imaging.py
import difmap_native
import matplotlib.pyplot as plt
# Ajout de DifmapError dans l'import car tu l'utilises en bas !
from .exceptions import DifmapStateError, DifmapError 

class DifmapImager:
    """
    Moteur de rendu mathématique pour la génération d'images astrophysiques.

    Cette classe est dite 'stateless' (sans état). Elle est pilotée par la 
    session principale pour transformer les visibilités UV en cartes FITS 
    via des Transformées de Fourier rapides (FFT).
    """
    
    @staticmethod
    def make_dirty_map(size: int, cellsize: float, pol: str = "I") -> dict:
        """
        Calcule la Dirty Map (image brute) à partir des visibilités en RAM.

        Cette fonction orchestre la sélection de la polarisation, l'allocation 
        de la grille d'image, et la Transformée de Fourier inverse. 
        
        **L'astuce magique** : Elle calcule et applique automatiquement le 
        décalage astrométrique du demi-pixel. L'utilisateur n'a plus à se 
        soucier de l'alignement des axes, la clé `extent` est prête à l'emploi.

        Parameters
        ----------
        size : int
            Dimension de la grille (ex: 512 pour une image 512x512). 
            Privilégiez les puissances de 2 pour optimiser la FFT.
        cellsize : float
            Résolution spatiale d'un pixel en millisecondes d'arc (mas).
        pol : str, default="I"
            La polarisation à imager. Accepte les paramètres de Stokes ou les corrélations brutes : <br>
            - "I" : Intensité totale (luminosité globale, valeur par défaut). <br>
            - "Q", "U" : Polarisation linéaire (cartographie des champs magnétiques). <br>
            - "V" : Polarisation circulaire. <BR>
            - "RR", "LL" : Corrélations directes des antennes (circulaire droite/gauche). <br>
            - "RL", "LR" : Polarisations croisées. <br>

        Returns
        -------
        dict
            Le "Package Complet" de l'image contenant : <br>
            - **data** (*numpy.ndarray*): La matrice 2D des flux (Jy/beam). <br>
            - **header** (*dict*): Les métadonnées du header FITS (NX, NY, etc.). <br>
            - **beam** (*dict*): Les paramètres de la PSF (bmaj, bmin, bpa). <br>
            - **extent** (*list*): Coordonnées absolues `[x_min, x_max, y_min, y_max]` corrigées.<br>

        Raises
        ------
        DifmapError
            Si l'allocation de la grille échoue (mapsize) ou si la FFT plante.

        Examples
        --------
        Affichage direct d'une image avec Matplotlib grâce à l'extent corrigé :
        
        ```python
        # L'image a déjà été calculée et récupérée
        img = session.create_image(size=512, cellsize=0.1, pol="I")
        
        import matplotlib.pyplot as plt
        plt.imshow(img["data"], extent=img["extent"], cmap="magma")
        plt.colorbar(label="Jy/beam")
        plt.show()
        ```
        """
        difmap_native.select(pol)
        if difmap_native.mapsize(size, cellsize) != 0:
            raise DifmapError("Erreur lors de l'allocation de la grille (mapsize).")
        
        if difmap_native.invert() != 0:
            raise DifmapError("Échec de la transformée de Fourier (invert).")
            
        # 1. On récupère les infos de base
        nx = difmap_native.get_header()["NX"]
        ny = difmap_native.get_header()["NY"]
        
        # 2. LE CALCUL AUTOMATIQUE DU DÉCALAGE (décalage de 0.5)
        demi_pixel = 0.5 * cellsize
        
        extent_corrige = [
             (nx / 2.0) * cellsize + demi_pixel,   # Bord gauche (RA +)
            -(nx / 2.0) * cellsize + demi_pixel,   # Bord droit (RA -)
            -(ny / 2.0) * cellsize - demi_pixel,   # Bord bas (Dec -)
             (ny / 2.0) * cellsize - demi_pixel    # Bord haut (Dec +)
        ]
            
        # 3. On renvoie le "Package Complet" à l'utilisateur
        return {
            "data": difmap_native.get_map(),
            "header": difmap_native.get_header(),
            "beam": difmap_native.get_beam(),
            "extent": extent_corrige
        }
        
    @staticmethod
    def plot_image(img_dict: dict, cmap: str = 'magma', figsize: tuple = (8, 6), title: str = "Imagerie Difmap", **kwargs) -> None:
        """
        Génère et affiche une visualisation scientifique de l'image reconstruite.

        Cette méthode statique extrait les données matricielles et les limites 
        spatiales du dictionnaire généré par le moteur Difmap pour produire une 
        figure Matplotlib formatée pour la radioastronomie (axes en décalage 
        angulaire, échelle de flux).

        Parameters
        ----------
        img_dict : dict
            Le dictionnaire de l'image produit par l'API Difmap. Il doit 
            impérativement contenir les clés 'data' (la matrice bidimensionnelle 
            des flux) et 'extent' (les limites spatiales corrigées). <br>
        cmap : str, optional
            La palette de couleurs Matplotlib à utiliser pour le rendu. 
            Par défaut défini sur 'magma'. <br>
        figsize : tuple, optional
            Les dimensions de la figure générée (largeur, hauteur) en pouces. 
            Par défaut défini sur (8, 6). <br>
        title : str, optional
            Le titre principal affiché au-dessus de la figure. 
            Par défaut défini sur "Imagerie Difmap". <br>
        **kwargs : dict, optional
            Arguments supplémentaires transmis directement à la fonction 
            `matplotlib.pyplot.imshow` (par exemple `vmin`, `vmax`, `interpolation`).

        Returns
        -------
        None
            Cette fonction ne retourne aucune valeur. Elle déclenche l'affichage 
            interactif de la figure via `matplotlib.pyplot.show()`.

        Raises
        ------
        KeyError
            Si le dictionnaire fourni ne contient pas les clés requises 
            ('data' ou 'extent').

        Examples
        --------
        Génération et affichage rapide d'une image avec des paramètres personnalisés :

        >>> from difmap_wrapper import DifmapSession
        >>> from difmap_wrapper.imaging import DifmapImager
        >>> 
        >>> with DifmapSession() as session:
        ...     session.load_observation("data_uv.fits")
        ...     img_package = session.create_image(size=512, cellsize=0.1)
        ...     
        ...     # Affichage avec une palette différente et des limites de flux
        ...     DifmapImager.plot_image(
        ...         img_package, 
        ...         title="Observation Radio", 
        ...         cmap="viridis", 
        ...         vmin=-0.01, 
        ...         vmax=0.5
        ...     )
        """
        plt.figure(figsize=figsize)
        
        # Injection des données et des arguments flexibles (**kwargs)
        plt.imshow(img_dict['data'], extent=img_dict['extent'], origin='lower', cmap=cmap, **kwargs)
        
        # Configuration des éléments d'habillage scientifique
        plt.colorbar(label='Densité de flux (Jy/beam)')
        plt.title(title)
        plt.xlabel("Décalage RA (mas)")
        plt.ylabel("Décalage Dec (mas)")
        
        # Affichage de la fenêtre
        plt.show()