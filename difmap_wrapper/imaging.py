# difmap_wrapper/imaging.py
import difmap_native
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
            La polarisation à imager ("I", "Q", "U", "V"). 
            Par défaut défini sur "I" (intensité totale).

        Returns
        -------
        dict
            Le "Package Complet" de l'image contenant :
            - **data** (*numpy.ndarray*): La matrice 2D des flux (Jy/beam).
            - **header** (*dict*): Les métadonnées du header FITS (NX, NY, etc.).
            - **beam** (*dict*): Les paramètres de la PSF (bmaj, bmin, bpa).
            - **extent** (*list*): Coordonnées absolues `[x_min, x_max, y_min, y_max]` corrigées.

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