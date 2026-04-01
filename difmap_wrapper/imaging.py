import numpy as np
import difmap_native
import matplotlib.pyplot as plt
from .exceptions import DifmapError , DifmapStateError

class DifmapImager:
    """
    Moteur de rendu mathématique pour la génération d'images astrophysiques.
    """

    def __init__(self):
        self._native = difmap_native
        self._last_cellsize = None  
        self._current_uvtaper = None
        self._current_uvweight = None
        
    def get_map(self) -> np.ndarray:
        """Récupère l'image brute (la matrice 2D) depuis la RAM en Zéro-Copie."""
        return self._native.get_map()

    def get_cropped_map(self, target_shape: tuple) -> np.ndarray:
        """
        Récupère l'image en RAM et la recadre dynamiquement autour du centre
        pour correspondre aux dimensions cibles (ex: celles d'un FITS de référence).
        """
        img_ram = self.get_map()
        h_target, w_target = target_shape
        h_ram, w_ram = img_ram.shape

        y_start = (h_ram - h_target) // 2
        x_start = (w_ram - w_target) // 2

        if y_start < 0 or x_start < 0:
            raise ValueError(f"La taille cible {target_shape} est plus grande que l'image en RAM {img_ram.shape}.")

        return img_ram[y_start : y_start + h_target, x_start : x_start + w_target]

    def uvweight(self, bin_size: float = None, err_power: float = None, radial: bool = None) -> None:
        """
        Définit la pondération des visibilités.
        Sans arguments : Affiche l'état actuel de la pondération sans la modifier.
        """
        # 1. Mode "Interrogation" (Aucun argument)
        if bin_size is None and err_power is None and radial is None:
            if self._current_uvweight is None:
                print("Pondération actuelle : Valeurs par défaut de Difmap (bin_size=2.0, err_power=0.0, radial=False)")
            else:
                b, e, r = self._current_uvweight
                rad_str = "Oui" if r else "Non"
                print(f"Pondération actuelle : bin_size={b}, err_power={e}, radial={rad_str}")
            return

        # 2. Mode "Application"
        # On applique les valeurs de Difmap si l'utilisateur ne précise qu'un paramètre sur les trois
        b = 2.0 if bin_size is None else float(bin_size)
        e = 0.0 if err_power is None else float(err_power)
        r = False if radial is None else bool(radial)
        
        dorad = 1 if r else 0
        if self._native.uvweight(b, e, dorad) != 0:
            raise DifmapError("Erreur lors de l'application de uvweight.")
            
        # 3. Mise à jour de la mémoire et feedback utilisateur
        self._current_uvweight = (b, e, r)
        rad_str = "Oui" if r else "Non"
        print(f"Nouvelle pondération appliquée : bin_size={b}, err_power={e}, radial={rad_str}")
    def uvtaper(self, gaussian_value: float = None, gaussian_radius_wav: float = None) -> None:
        """
        Applique un flou gaussien (Taper) dans le plan UV.
        - Sans arguments : Affiche l'état actuel ou désactive le taper.
        - Avec arguments : Applique la pondération et mémorise l'état.
        - Pour désactiver explicitement : uvtaper(0, 0)
        """
        # 1. Mode "Interrogation / Désactivation" (Aucun argument)
        if gaussian_value is None and gaussian_radius_wav is None:
            if self._current_uvtaper in [None, (0.0, 0.0)]:
                print("Taper actuel : Aucun (Désactivé)")
                # Sécurité : on force la désactivation en C au cas où
                self._native.uvtaper(0.0, 0.0) 
                self._current_uvtaper = (0.0, 0.0)
            else:
                val, rad = self._current_uvtaper
                print(f"Taper actuel : Valeur = {val}, Rayon = {rad} longueurs d'onde")
            return

        # 2. Mode "Application"
        # Si un seul argument est fourni, le second devient 0.0 par défaut
        val = float(gaussian_value) if gaussian_value is not None else 0.0
        rad = float(gaussian_radius_wav) if gaussian_radius_wav is not None else 0.0

        if self._native.uvtaper(val, rad) != 0:
            raise DifmapError("Erreur lors de l'application de uvtaper.")
        
        # 3. Mise à jour de la mémoire et feedback utilisateur
        self._current_uvtaper = (val, rad)
        if val == 0.0 and rad == 0.0:
            print("Taper désactivé avec succès.")
        else:
            print(f"Taper appliqué : Valeur = {val}, Rayon = {rad} longueurs d'onde")
        
    def mapsize(self, size: int, cellsize: float) -> None:
            """Définit la taille de la grille et du pixel pour l'image."""
            if self._native.mapsize(size, cellsize) != 0:
                raise DifmapError("Erreur lors de l'allocation de la grille (mapsize).")
            self._last_cellsize = cellsize

    def invert(self) -> None:
        """Exécute la Transformée de Fourier inverse pour créer la Dirty Map et le Beam."""
        if self._native.invert() != 0:
            raise DifmapError("Échec de la transformée de Fourier (invert).")
        
    def get_map_package(self, cellsize: float) -> dict:
        """
        Récupère l'image brute en RAM et l'emballe dans un dictionnaire 
        contenant l'astrométrie (extent) nécessaire pour mapplot.
        """
        hdr = self._native.get_header()
        nx = hdr.get('NX', 512)
        ny = hdr.get('NY', 512)

        demi_pixel = 0.5 * cellsize
        extent_corrige = [
             (nx / 2.0) * cellsize + demi_pixel,
            -(nx / 2.0) * cellsize + demi_pixel,
            -(ny / 2.0) * cellsize - demi_pixel,
             (ny / 2.0) * cellsize - demi_pixel
        ]
            
        return {
            "data": self.get_map(),
            "beam_data": self._native.get_beam(),
            "info": {
                "nx": nx,
                "ny": ny,
                "cellsize": cellsize,
                "bmaj": hdr.get('BMAJ', 0.0),
                "bmin": hdr.get('BMIN', 0.0),
                "bpa": hdr.get('BPA', 0.0)
            },
            "extent": extent_corrige
        }

    def make_dirty_map(self, size: int, cellsize: float, pol: str = "I") -> dict:
        """
        Calcule la Dirty Map (image brute) à partir des visibilités en RAM.
        Version optimisée utilisant les briques internes de l'Imager.
        """
        # 1. Sélection (Appel direct au module C natif car select appartient logiquement à Observation)
        if difmap_native.select(pol.upper(), 1, 0, 1, 0) != 0:
             raise DifmapError(f"Erreur de sélection de la polarisation {pol}")
             
        # 2. On réutilise nos propres méthodes !
        self.mapsize(size, cellsize)
        self.invert()
            
        # 3. On réutilise le packageur !
        return self.get_map_package(cellsize)
        
    @staticmethod
    def plot_image(img_dict: dict, cmap: str = 'magma', figsize: tuple = (8, 6), title: str = "Dirty Map", **kwargs) -> None:
        """Affiche l'image scientifique avec Matplotlib."""
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
            Affiche la Dirty Map. 
            Si img_dict n'est pas fourni, récupère la carte active en RAM (Comportement Difmap).
            """
            if img_dict is None:
                # --- 1er Filet de sécurité : A-t-on défini l'astrométrie ? ---
                if self._last_cellsize is None:
                    raise DifmapStateError(
                        "Astrométrie inconnue. Veuillez exécuter mapsize() avant mapplot()."
                    )
                
                # --- 2ème Filet de sécurité : L'image a-t-elle été calculée ? ---
                data = self.get_map()
                if data is None or data.size == 0:
                    raise DifmapStateError(
                        "Aucune image trouvée en mémoire. Avez-vous oublié d'exécuter invert() ?"
                    )
                
                # --- Mode Pilote Automatique ---
                # On demande à get_map_package de fabriquer le dictionnaire tout seul
                img_dict = self.get_map_package(cellsize=self._last_cellsize)
                
            # On envoie le dictionnaire (automatique ou manuel) au moteur de dessin
            return self.plot_image(img_dict, **kwargs)