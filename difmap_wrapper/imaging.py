import numpy as np
import difmap_native
import matplotlib.pyplot as plt
from .exceptions import DifmapError , DifmapStateError

class DifmapImager:
    """
    Moteur de rendu mathématique pour la génération d'images astrophysiques.

    Gère la grille de calcul, la pondération, l'inversion de Fourier (Dirty Map) 
    et l'affichage des images. Accessible via l'attribut `imager` d'une session.

    Examples
    --------
    >>> with DifmapSession() as session:
    >>>     session.observe("data/0003-066.fits")
    >>>     session.imager.mapsize(512, 1.0)
    """

    def __init__(self):
        self._native = difmap_native
        self._last_cellsize = None  
        self._current_uvtaper = None
        self._current_uvweight = None
        
    def get_map(self) -> np.ndarray:
        """
        Récupère l'image brute (matrice 2D) depuis la RAM en Zéro-Copie.

        Returns
        -------
        numpy.ndarray
            La matrice 2D représentant l'image calculée (Dirty ou Clean map).

        Examples
        --------
        >>> img_data = session.imager.get_map()
        """
        return self._native.get_map()

    def get_cropped_map(self, target_shape: tuple) -> np.ndarray:
        """
        Récupère l'image en RAM et la recadre dynamiquement autour de son centre.

        Utile pour comparer les données avec un FITS de référence plus petit.

        Parameters
        ----------
        target_shape : tuple of int
            Les dimensions cibles (hauteur, largeur) en pixels.

        Returns
        -------
        numpy.ndarray
            L'image recadrée aux dimensions demandées.

        Raises
        ------
        ValueError
            Si la taille cible demandée est supérieure à la taille de l'image en RAM.

        Examples
        --------
        >>> cropped_data = session.imager.get_cropped_map((256, 256))
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
        Définit la pondération des visibilités pour l'imagerie.

        Si appelée sans arguments, la fonction affiche l'état actuel de la 
        pondération en mémoire (comportement d'interrogation de Difmap).

        Parameters
        ----------
        bin_size : float, optional
            Taille de la cellule de la grille UV. Par défaut 2.0.
        err_power : float, optional
            Puissance d'erreur pour la pondération uniforme/naturelle. Par défaut 0.0.
        radial : bool, optional
            Applique une pondération radiale si True. Par défaut False.

        Raises
        ------
        DifmapError
            Si le moteur C échoue à appliquer les poids.

        Examples
        --------
        >>> session.imager.uvweight() # Mode Interrogation
        >>> session.imager.uvweight(bin_size=2.0, err_power=-1.0) # Pondération Uniforme
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
        Applique un flou gaussien (Taper) aux visibilités dans le plan UV.

        A pour effet de baisser la résolution spatiale de l'image finale. 
        Si appelée sans arguments, elle affiche l'état actuel. Si on lui 
        passe (0, 0), elle désactive le taper.

        Parameters
        ----------
        gaussian_value : float, optional
            La valeur d'atténuation gaussienne à appliquer au rayon spécifié.
        gaussian_radius_wav : float, optional
            Le rayon dans le plan UV (en longueurs d'onde) où l'atténuation s'applique.

        Raises
        ------
        DifmapError
            Si l'application du taper échoue.

        Examples
        --------
        >>> session.imager.uvtaper() # Mode Interrogation
        >>> session.imager.uvtaper(0.5, 100000.0) # Applique un taper
        >>> session.imager.uvtaper(0, 0) # Nettoie le taper
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
        """
        Définit la taille de la grille et la taille du pixel pour l'image.

        Cette fonction détermine l'astrométrie et le champ de vue de la carte 
        qui sera générée par l'inversion de Fourier.

        Parameters
        ----------
        size : int
            Le nombre de pixels sur chaque axe (ex: 512, 1024).
        cellsize : float
            La taille angulaire d'un pixel en milli-arcsecondes (mas).

        Raises
        ------
        DifmapError
            En cas d'erreur d'allocation mémoire dans le moteur C.

        Examples
        --------
        >>> session.imager.mapsize(512, 1.0) # 512x512 px avec des pixels de 1 mas
        """
        if self._native.mapsize(size, cellsize) != 0:
            raise DifmapError("Erreur lors de l'allocation de la grille (mapsize).")
        self._last_cellsize = cellsize

    def invert(self) -> None:
        """
        Exécute la Transformée de Fourier inverse (FFT) pour créer l'image.

        Génère simultanément la Dirty Map et le Faisceau Synthétique (Beam) 
        à partir des visibilités pondérées et calibrées en mémoire.

        Raises
        ------
        DifmapError
            En cas d'échec de la FFT.

        Examples
        --------
        >>> session.imager.invert()
        """
        if self._native.invert() != 0:
            raise DifmapError("Échec de la transformée de Fourier (invert).")
        
    def get_map_package(self, cellsize: float) -> dict:
        """
        Extrait l'image, le beam et l'astrométrie pour créer un package de données complet.

        Parameters
        ----------
        cellsize : float
            La taille angulaire d'un pixel en milli-arcsecondes (mas) pour 
            calculer l'étendue physique de l'image (extent).

        Returns
        -------
        dict
            Dictionnaire contenant 'data', 'beam_data', 'info' et 'extent'.

        Examples
        --------
        >>> pkg = session.imager.get_map_package(cellsize=1.0)
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
        Méthode de haut niveau qui orchestre la création d'une Dirty Map de A à Z.

        Sélectionne la polarisation, définit la grille, inverse les données 
        et retourne le package complet prêt à être affiché ou sauvegardé.

        Parameters
        ----------
        size : int
            La taille de l'image en pixels (carrée).
        cellsize : float
            La taille d'un pixel en milli-arcsecondes (mas).
        pol : str, optional
            La polarisation à imager ("I", "RR", "LL", etc.). Par défaut "I".

        Returns
        -------
        dict
            Dictionnaire contenant les données de l'image et l'astrométrie.

        Examples
        --------
        >>> img_dict = session.imager.make_dirty_map(512, 1.0, pol="I")
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
        Affiche la carte actuellement chargée en mémoire.

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
        >>> session.imager.mapplot() # S'affiche automatiquement !
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

