import numpy as np
import difmap_native
import matplotlib.pyplot as plt
from .exceptions import DifmapError, DifmapStateError

class DifmapImager:
    """
    Moteur de rendu mathématique pour la génération d'images astrophysiques.

    Gère la grille de calcul, la pondération, l'inversion de Fourier (Dirty Map) 
    et l'affichage des images. Accessible via l'attribut `imager` d'une session.
    """

    def __init__(self, session):
        self._session = session
        self._native = difmap_native
        self._last_cellsize = None  
        self._last_mapsize = None    # <-- AJOUT : Mémorisation de la taille
        self._current_uvtaper = None
        self._current_uvweight = None

    def _reissue_mapsize_if_needed(self):
        """
        Restaure silencieusement la grille C si elle a été effacée par une autre commande.
        Difmap a tendance à annuler la demande de carte quand on change les poids.
        """
        if self._last_mapsize is not None and self._last_cellsize is not None:
            self._native.mapsize(self._last_mapsize, self._last_cellsize)
            
    def get_map(self) -> np.ndarray:
        """Récupère l'image brute (matrice 2D) depuis la RAM en Zéro-Copie."""
        return self._native.get_map()

    def get_cropped_map(self, target_shape: tuple) -> np.ndarray:
        """Récupère l'image en RAM et la recadre dynamiquement autour de son centre."""
        img_ram = self.get_map()
        h_target, w_target = target_shape
        h_ram, w_ram = img_ram.shape

        y_start = (h_ram - h_target) // 2
        x_start = (w_ram - w_target) // 2

        if y_start < 0 or x_start < 0:
            raise ValueError(f"La taille cible {target_shape} est plus grande que l'image en RAM {img_ram.shape}.")

        return img_ram[y_start : y_start + h_target, x_start : x_start + w_target]

    def uvweight(self, bin_size: float = None, err_power: float = None, radial: bool = None) -> None:
        """Définit la pondération des visibilités pour l'imagerie."""
        # 1. Mode "Interrogation"
        if bin_size is None and err_power is None and radial is None:
            if self._current_uvweight is None:
                print("Pondération actuelle : Valeurs par défaut de Difmap (bin_size=2.0, err_power=0.0, radial=False)")
            else:
                b, e, r = self._current_uvweight
                rad_str = "Oui" if r else "Non"
                print(f"Pondération actuelle : bin_size={b}, err_power={e}, radial={rad_str}")
            return

        # 2. Mode "Application"
        b = 2.0 if bin_size is None else float(bin_size)
        e = 0.0 if err_power is None else float(err_power)
        r = False if radial is None else bool(radial)
        
        dorad = 1 if r else 0
        if self._native.uvweight(b, e, dorad) != 0:
            raise DifmapError("Erreur lors de l'application de uvweight.")
            
        # 3. Mise à jour de la mémoire et restauration de la grille C
        self._current_uvweight = (b, e, r)
        self._reissue_mapsize_if_needed()
        
        rad_str = "Oui" if r else "Non"
        print(f"Nouvelle pondération appliquée : bin_size={b}, err_power={e}, radial={rad_str}")
        
    def uvtaper(self, gaussian_value: float = None, gaussian_radius_wav: float = None) -> None:
        """Applique un flou gaussien (Taper) aux visibilités dans le plan UV."""
        # 1. Mode "Interrogation / Désactivation"
        if gaussian_value is None and gaussian_radius_wav is None:
            if self._current_uvtaper in [None, (0.0, 0.0)]:
                print("Taper actuel : Aucun (Désactivé)")
                self._native.uvtaper(0.0, 0.0) 
                self._current_uvtaper = (0.0, 0.0)
                self._reissue_mapsize_if_needed()
            else:
                val, rad = self._current_uvtaper
                print(f"Taper actuel : Valeur = {val}, Rayon = {rad} longueurs d'onde")
            return

        # 2. Mode "Application"
        val = float(gaussian_value) if gaussian_value is not None else 0.0
        rad = float(gaussian_radius_wav) if gaussian_radius_wav is not None else 0.0

        if self._native.uvtaper(val, rad) != 0:
            raise DifmapError("Erreur lors de l'application de uvtaper.")
        
        # 3. Mise à jour de la mémoire et restauration de la grille C
        self._current_uvtaper = (val, rad)
        self._reissue_mapsize_if_needed()
        
        if val == 0.0 and rad == 0.0:
            print("Taper désactivé avec succès.")
        else:
            print(f"Taper appliqué : Valeur = {val}, Rayon = {rad} longueurs d'onde")
        
    def mapsize(self, size: int, cellsize: float) -> None:
        """Définit la taille de la grille et la taille du pixel pour l'image."""
        if self._native.mapsize(size, cellsize) != 0:
            raise DifmapError("Erreur lors de l'allocation de la grille (mapsize).")
        self._last_cellsize = cellsize
        self._last_mapsize = size

    def invert(self) -> None:
        """Exécute la Transformée de Fourier inverse (FFT) pour créer l'image."""
        if self._native.invert() != 0:
            raise DifmapError("Échec de la transformée de Fourier (invert).")
        
    def get_map_package(self, cellsize: float) -> dict:
        """Extrait l'image, le beam et l'astrométrie pour créer un package de données."""
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
        """Méthode de haut niveau qui orchestre la création d'une Dirty Map de A à Z."""
        self._session.obs.select(pol=pol)
        self.mapsize(size, cellsize)
        self.invert()
        return self.get_map_package(cellsize)