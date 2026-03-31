# difmap_wrapper/imaging.py
import difmap_native
import matplotlib.pyplot as plt
from .exceptions import DifmapError 

class DifmapImager:
    """
    Moteur de rendu mathématique pour la génération d'images astrophysiques.

    Cette classe est 'stateless' (sans état interne). Elle rassemble des méthodes 
    statiques pour transformer les visibilités UV actuellement en RAM 
    vers des matrices de pixels.
    """

    @staticmethod
    def uvweight(bin_size: float = 2.0, err_power: float = 0.0, radial: bool = False) -> None:
        """
        Définit la pondération des visibilités avant la Transformée de Fourier.
        """
        dorad = 1 if radial else 0
        if difmap_native.uvweight(bin_size, err_power, dorad) != 0:
            raise DifmapError("Erreur lors de l'application de uvweight. (Aucune donnée chargée ?)")

    @staticmethod
    def uvtaper(gaussian_value: float, gaussian_radius_wav: float) -> None:
        """
        Applique un flou gaussien (Taper) dans le plan UV pour baisser la résolution.
        """
        if difmap_native.uvtaper(gaussian_value, gaussian_radius_wav) != 0:
            raise DifmapError("Erreur lors de l'application de uvtaper. (Aucune donnée chargée ?)")

    @staticmethod
    def make_dirty_map(size: int, cellsize: float, pol: str = "I") -> dict:
        """
        Calcule la Dirty Map (image brute) à partir des visibilités en RAM.
        """
        
        # 1. Sélection des données
        if difmap_native.select(pol.upper(), 1, 0, 1, 0) != 0:
             raise DifmapError(f"Erreur de sélection de la polarisation {pol}")
             
        # 2. Allocation de la grille mémoire
        if difmap_native.mapsize(size, cellsize) != 0:
            raise DifmapError("Erreur lors de l'allocation de la grille (mapsize).")
        
        # 3. Calcul de la FFT
        if difmap_native.invert() != 0:
            raise DifmapError("Échec de la transformée de Fourier (invert).")
            
        # 4. Récupération des dimensions depuis le C
        nx = difmap_native.get_native_map_nx()
        ny = difmap_native.get_native_map_ny()
        
        if nx <= 0 or ny <= 0:
             raise DifmapError("Erreur interne : Les dimensions de l'image sont invalides après invert().")

        # 5. Astrométrie : Calcul rigoureux de l'extent (avec le décalage de 0.5 pixel)
        # Difmap définit le pixel (0,0) au centre, mais Matplotlib affiche les limites des bords de pixels.
        demi_pixel = 0.5 * cellsize
        
        extent_corrige = [
             (nx / 2.0) * cellsize + demi_pixel,   # Bord gauche (RA +)
            -(nx / 2.0) * cellsize + demi_pixel,   # Bord droit (RA -)
            -(ny / 2.0) * cellsize - demi_pixel,   # Bord bas (Dec -)
             (ny / 2.0) * cellsize - demi_pixel    # Bord haut (Dec +)
        ]
            
        # 6. Assemblage du "Package Image" complet
        return {
            "data": difmap_native.get_native_map_data(),
            "beam_data": difmap_native.get_native_beam_data(),
            "info": {
                "nx": nx,
                "ny": ny,
                "cellsize": cellsize,
                "bmaj": difmap_native.get_native_bmaj(),
                "bmin": difmap_native.get_native_bmin(),
                "bpa": difmap_native.get_native_bpa()
            },
            "extent": extent_corrige
        }
        
    @staticmethod
    def plot_image(img_dict: dict, cmap: str = 'magma', figsize: tuple = (8, 6), title: str = "Dirty Map", **kwargs) -> None:
        """
        Affiche l'image scientifique avec Matplotlib.
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