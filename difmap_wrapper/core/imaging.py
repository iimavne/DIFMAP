import numpy as np
from ctypes import Structure, c_char_p, c_int, c_float, c_double, POINTER, byref
from typing import Optional, Tuple, List, Dict, Any, Union
import difmap_native
from ..types import Polarization

from ..utils.map_geometry import DifmapMapGeometry
from ..utils.exceptions import DifmapError, DifmapStateError

class DifmapImager:
    """
    Outils pour créer une image à partir des visibilités chargées.

    Gère la grille de calcul (taille, pixel), la pondération des baselines,
    et la transformée de Fourier inverse (Dirty Map). Accessible via
    ``session.imager``.

    Examples
    --------
    Workflow complet pour créer une Dirty Map :

    >>> session.obs.select(pol="I")
    >>> session.imager.mapsize(512, 0.1)       # grille 512×512, pixel 0.1 mas
    >>> session.imager.invert()                # calcul de la Dirty Map
    >>> img = session.imager.get_map_package(cellsize=0.1)
    >>> session.vis.plot_image(img)
    """

    def __init__(self, session):
        self._session = session
        self._native = difmap_native
        self._last_cellsize = None
        self._last_mapsize = None
        self._last_ny = None
        self._last_cellsize_y = None
        self._current_uvtaper = None
        self._current_uvweight = None
        self._current_map_type = None  # "dirty" après invert(), "clean" après restore()
        self.active_windows = []     # registre Python des fenêtres CLEAN actives [(xa,xb,ya,yb) en mas]
        self._last_residual_map = None  # copie du buffer résiduel capturée entre clean() et restore()

    def _reissue_mapsize_if_needed(self):
        """Restaure la grille si elle a été annulée par un changement de pondération."""
        if self._last_mapsize is not None and self._last_cellsize is not None:
            self._native.mapsize(
                self._last_mapsize, self._last_cellsize,
                self._last_ny or 0, self._last_cellsize_y or 0.0
            )
            
    def get_map(self) -> np.ndarray:
        """
        Retourne l'image courante depuis la mémoire C (tableau 2D, float).

        Returns
        -------
        np.ndarray
            Matrice 2D de taille ``(ny, nx)`` en Jy/beam.
        """
        return self._native.get_map()

    def has_map_data(self) -> bool:
        """
        Vérifie si des données de carte sont disponibles en mémoire C.
        
        Returns
        -------
        bool
            True si une carte (dirty ou clean) est disponible, False sinon.
        """
        try:
            map_data = self._native.get_map()
            return map_data is not None and map_data.size > 0
        except:
            return False

    def get_cropped_map(self, target_shape: tuple) -> np.ndarray:
        """
        Retourne l'image recadrée autour de son centre.

        Utile pour réduire la taille de la figure affichée sans recalculer la FFT.

        Parameters
        ----------
        target_shape : tuple of int
            ``(hauteur, largeur)`` en pixels. Doit être inférieur à la taille
            de la grille définie par ``mapsize()``.

        Returns
        -------
        np.ndarray
            Sous-image centrée de taille ``target_shape``.

        Raises
        ------
        ValueError
            Si ``target_shape`` dépasse la taille de l'image en mémoire.
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
        Définit comment les visibilités sont pondérées avant l'imagerie.

        Appelé sans argument, affiche la pondération active. Les trois paramètres
        correspondent aux options classiques de Difmap.

        Parameters
        ----------
        bin_size : float, optional
            Taille des cases UV pour la pondération uniforme.
            ``2.0`` = pondération uniforme standard.
            Valeurs proches de 0 → plus naturelle (bruit plus faible, résolution réduite).
        err_power : float, optional
            Exposant appliqué à l'erreur pour le pondération robuste.
            ``0.0`` = uniforme, ``-2.0`` = naturelle (poids proportionnel à 1/σ²).
        radial : bool, optional
            Si ``True``, applique une pondération radiale (favorise les grandes baselines).

        Examples
        --------
        Pondération uniforme standard :

        >>> session.imager.uvweight(bin_size=2.0, err_power=0.0)

        Pondération naturelle (meilleure sensibilité) :

        >>> session.imager.uvweight(bin_size=0.0, err_power=-2.0)

        Afficher la pondération active :

        >>> session.imager.uvweight()
        Pondération actuelle : bin_size=2.0, err_power=0.0, radial=Non
        """
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
        """
        Applique un filtre gaussien (taper) pour réduire la résolution angulaire.

        Le taper atténue les baselines les plus longues, ce qui améliore la
        sensibilité aux structures étendues au détriment de la résolution.
        Appelé sans argument, affiche ou désactive le taper actif.

        Parameters
        ----------
        gaussian_value : float, optional
            Amplitude du filtre gaussien (entre 0 et 1). ``0.0`` = aucun taper.
        gaussian_radius_wav : float, optional
            Rayon du filtre en longueurs d'onde. Définit à quelle distance
            dans le plan UV l'atténuation commence.

        Examples
        --------
        Appliquer un taper à partir de 50 Mλ :

        >>> session.imager.uvtaper(gaussian_value=0.3, gaussian_radius_wav=50e6)

        Désactiver le taper :

        >>> session.imager.uvtaper(0, 0)

        Afficher le taper actif :

        >>> session.imager.uvtaper()
        Taper actuel : Valeur = 0.3, Rayon = 50000000.0 longueurs d'onde
        """
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

        if self._native.uvtaper(val, rad / 1e6) != 0:
            raise DifmapError("Erreur lors de l'application de uvtaper.")
        
        # 3. Mise à jour de la mémoire et restauration de la grille C
        self._current_uvtaper = (val, rad)
        # self._reissue_mapsize_if_needed()  # Peut-être pas nécessaire pour uvtaper
        
        if val == 0.0 and rad == 0.0:
            print("Taper désactivé avec succès.")
        else:
            print(f"Taper appliqué : Valeur = {val}, Rayon = {rad} longueurs d'onde")
        
    def mapsize(self, size: int, cellsize: float, ny: int = None, cellsize_y: float = None) -> None:
        """
        Définit la grille d'imagerie.

        Doit être appelé avant ``invert()``. Par défaut la grille est carrée
        (``ny = size``, ``cellsize_y = cellsize``). Passer ``ny`` et/ou
        ``cellsize_y`` permet de créer une grille rectangulaire, comme le
        supporte la commande ``mapsize`` native de DIFMAP.

        Parameters
        ----------
        size : int
            Nombre de pixels sur l'axe X. Doit être une puissance de 2 (ex : 256, 512, 1024).
        cellsize : float
            Taille d'un pixel en milli-arcseconde (mas) sur l'axe X.
        ny : int, optional
            Nombre de pixels sur l'axe Y. Défaut : identique à ``size``.
        cellsize_y : float, optional
            Taille d'un pixel en mas sur l'axe Y. Défaut : identique à ``cellsize``.

        Raises
        ------
        DifmapError
            Si le moteur C ne peut pas allouer la grille.

        Examples
        --------
        >>> session.imager.mapsize(512, 0.1)              # grille carrée 512×512
        >>> session.imager.mapsize(512, 0.1, ny=256)      # grille rectangulaire 512×256
        """
        actual_ny = ny if ny is not None else 0
        actual_cy = cellsize_y if cellsize_y is not None else 0.0
        if self._native.mapsize(size, cellsize, actual_ny, actual_cy) != 0:
            raise DifmapError("Erreur lors de l'allocation de la grille (mapsize).")
        self._last_mapsize = size
        self._last_cellsize = cellsize
        self._last_ny = ny
        self._last_cellsize_y = cellsize_y

    def _capture_residual(self) -> None:
        """Sauvegarde une copie du buffer résiduel (état après clean(), avant restore())."""
        self._last_residual_map = self.get_map().copy()

    def invert(self) -> None:
        """
        Calcule la Dirty Map par transformée de Fourier inverse.

        Gridde les visibilités sur la grille définie par ``mapsize()``,
        puis applique la FFT inverse. Le résultat est stocké en mémoire C
        et accessible via ``get_map()``.

        Raises
        ------
        DifmapError
            Si la FFT échoue (grille non définie ou données absentes).

        Examples
        --------
        >>> session.imager.mapsize(512, 0.1)
        >>> session.imager.invert()
        >>> img_array = session.imager.get_map()
        """
        if self._native.invert() != 0:
            raise DifmapError("Échec de la transformée de Fourier (invert).")
        self._current_map_type = "dirty"

    def _display_map_data(self, map_data: np.ndarray, cellsize: float,
                          cellsize_y: float = None) -> tuple:
        """
        Applique le crop d'affichage Difmap en utilisant la géométrie unifiée.
        """
        return DifmapMapGeometry.crop_map_data(map_data, cellsize, cellsize_y)

    def _get_clean_windows(self) -> list:
        """Retourne la liste native des fenêtres CLEAN, avec fallback cache Python."""
        get_windows = getattr(self._native, 'get_windows', None)
        if get_windows is None:
            return list(self.active_windows)
        windows = [
            (min(xa, xb), max(xa, xb), min(ya, yb), max(ya, yb))
            for xa, xb, ya, yb in get_windows()
        ]
        self.active_windows = windows
        return windows
        
    def get_map_package(self, cellsize: float, cellsize_y: float = None) -> dict:
        """
        Rassemble l'image, le faisceau et les métadonnées dans un seul dictionnaire.

        Ce dictionnaire est le format attendu par ``Visualizer.plot_image()``.

        Parameters
        ----------
        cellsize : float
            Taille du pixel en mas sur l'axe X.
        cellsize_y : float, optional
            Taille du pixel en mas sur l'axe Y. Défaut : identique à ``cellsize``.

        Returns
        -------
        dict
            ``'data'`` : tableau 2D NumPy de la Dirty Map (Jy/beam).

            ``'beam_data'`` : tableau 2D NumPy du faisceau synthétique (PSF).

            ``'extent'`` : limites astrométriques ``[xmax, xmin, ymin, ymax]`` en mas,
            prêtes pour ``matplotlib.imshow()``.

            ``'info'`` : dict avec ``nx``, ``ny``, ``cellsize``, ``cellsize_y``,
            ``bmaj``, ``bmin``, ``bpa`` (dimensions et paramètres du faisceau).

        Examples
        --------
        >>> session.imager.mapsize(512, 0.1)
        >>> session.imager.invert()
        >>> img = session.imager.get_map_package(cellsize=0.1)
        >>> print(img["info"]["bmaj"])   # grand axe du faisceau en mas
        0.85
        """
        cy = cellsize_y if cellsize_y is not None else cellsize
        beam = self._native.get_beam_info()
        map_data = self.get_map()
        display_data, extent, nx_display, ny_display = self._display_map_data(
            map_data, cellsize, cy
        )
        
        map_type = self._current_map_type or "dirty"
        components = self._native.get_model_components() if map_type == "clean" else []
        return {
            "data": display_data,
            "beam_data": self._native.get_beam(),
            "map_type": map_type,
            "info": {
                "nx": nx_display,
                "ny": ny_display,
                "cellsize": cellsize,
                "cellsize_y": cy,
                "bmaj": beam.get('BMAJ', 0.0),
                "bmin": beam.get('BMIN', 0.0),
                "bpa": beam.get('BPA', 0.0),
                "rms": beam.get('RMS', 0.0),
                "map_type": map_type,
            },
            "extent": extent,
            "windows": self._get_clean_windows(),
            "model_components": components,
        }

    def get_residual_package(self, cellsize: float, cellsize_y: float = None) -> dict:
        """
        Retourne le package de la Residual Map capturée lors du dernier appel à ``restore()``.

        La Residual Map est le buffer **après** ``clean()`` et **avant** ``restore()`` :
        elle représente le résidu que CLEAN n'a pas réussi à déconvoluer.
        Contrairement à la Dirty Map, elle ne contient pas de lobes de synthèse
        autour des sources détectées.

        Returns
        -------
        dict
            Même structure que ``get_map_package()`` avec ``map_type="residual"``.

        Raises
        ------
        DifmapStateError
            Si ``restore()`` n'a pas encore été appelé (pas de résiduel capturé).
        """
        if self._last_residual_map is None:
            raise DifmapStateError(
                "Aucun résiduel disponible. Appelez make_clean_map() ou "
                "la séquence invert() → clean() → restore() d'abord."
            )
        cy = cellsize_y if cellsize_y is not None else cellsize
        beam = self._native.get_beam_info()
        display_data, extent, nx_display, ny_display = self._display_map_data(
            self._last_residual_map, cellsize, cy
        )
        # RMS calculé depuis la zone centrale des données résiduelles (pas depuis le beam)
        ny_d, nx_d = display_data.shape
        cy_d, cx_d = ny_d // 2, nx_d // 2
        margin = max(ny_d // 8, 4)
        rms_zone = display_data[cy_d - margin:cy_d + margin, cx_d - margin:cx_d + margin]
        actual_rms = float(np.sqrt(np.nanmean(rms_zone ** 2))) if rms_zone.size > 0 else 0.0
        return {
            "data": display_data,
            "beam_data": self._native.get_beam(),
            "map_type": "residual",
            "info": {
                "nx": nx_display,
                "ny": ny_display,
                "cellsize": cellsize,
                "cellsize_y": cy,
                "bmaj": beam.get('BMAJ', 0.0),
                "bmin": beam.get('BMIN', 0.0),
                "bpa": beam.get('BPA', 0.0),
                "rms": actual_rms,
            },
            "extent": extent,
            "windows": self._get_clean_windows(),
        }

    def clrmod(self) -> None:
        """
        Vide le modèle CLEAN côté C.
        
        Cette méthode doit être appelée avant chaque nouvelle opération clean()
        pour éviter l'accumulation des composantes des runs précédents.
        
        Raises
        ------
        DifmapError
            Si le moteur C retourne une erreur lors du vidage du modèle.
        """
        if self._native.clrmod() != 0:
            raise DifmapError("Échec du vidage du modèle CLEAN.")
        # Réinitialiser les flags pour permettre un nouveau invert
        self._native.reset_map_flags()

    def clean(self, niter: int = 100, gain: float = 0.05, cutoff: float = 0.0) -> None:
        """
        Déconvolue la Dirty Map par l'algorithme CLEAN natif.

        Doit être appelé après ``invert()``. Soustrait itérativement les
        composantes ponctuelles du lobe de synthèse et construit le modèle
        de sources propres.

        Parameters
        ----------
        niter : int, optional
            Nombre maximum d'itérations CLEAN. Par défaut 100.
            
            **Comportement spécial** : si ``niter < 0``, le CLEAN s'arrête
            au premier composant négatif détecté. Utile pour les sources
            compactes où l'on veut éviter de nettoyer les artefacts négatifs
            autour de la source (lobes latéraux). Par exemple ``niter=-100``
            permet jusqu'à 100 itérations mais s'arrête dès qu'un pixel
            négatif est sélectionné.
            
        gain : float, optional
            Gain de boucle CLEAN (entre 0 et 1). Par défaut 0.05.
            Valeurs typiques : 0.1 pour sources compactes, 0.05 pour
            structures étendues.
            
        cutoff : float, optional
            Seuil de flux résiduel pour arrêt automatique (Jy/beam).
            Par défaut 0.0 (pas de limite). Le CLEAN s'arrête quand le
            pic résiduel absolu tombe sous ce seuil. Utile pour :
            
            - Éviter de nettoyer sous le niveau du bruit
            - Contrôler finement la profondeur de déconvolution
            - Sources multi-échelles où l'émission diffuse a un flux
              plus faible que les sources ponctuelles

        Raises
        ------
        DifmapError
            Si le moteur C retourne une erreur (carte ou observation absente).

        Examples
        --------
        CLEAN standard pour source compacte :
        
        >>> session.imager.clean(niter=-200, gain=0.1)  # arrêt au 1er négatif
        
        CLEAN profond avec contrôle du bruit :
        
        >>> session.imager.clean(niter=1000, gain=0.05, cutoff=0.003)  # arrêt à 3 mJy
        """
        if self._native.clean(niter, gain, cutoff) != 0:
            raise DifmapError("Échec de la déconvolution CLEAN.")

    def restore(self) -> None:
        """
        Restaure la Clean Map en convoluant le modèle avec le faisceau propre.

        Doit être appelé après ``clean()``. Utilise automatiquement les
        paramètres du faisceau estimés lors du dernier ``invert()``.

        Raises
        ------
        DifmapError
            Si le moteur C retourne une erreur (modèle absent ou faisceau
            non estimé).
        """
        # Capture le résiduel AVANT l'écrasement par la convolution
        self._capture_residual()
        if self._native.restore() != 0:
            raise DifmapError("Échec de la restauration (restore).")
        self._current_map_type = "clean"

    def peak(self) -> dict:
        """
        Retourne les statistiques du pic de flux dans la carte courante.

        Équivalent à la commande ``peak`` de Difmap.

        Returns
        -------
        dict
            ``'flux'`` : valeur du pic en Jy/beam (peut être négative).

            ``'x'`` : position X en mas (positif = Est).

            ``'y'`` : position Y en mas (positif = Nord).

            ``'rms'`` : bruit RMS de la carte en Jy/beam.

            ``'snr'`` : rapport signal sur bruit.

        Raises
        ------
        DifmapStateError
            Si aucune carte n'est disponible en mémoire.

        Examples
        --------
        >>> session.imager.invert()
        >>> p = session.imager.peak()
        >>> print(f"Pic : {p['flux']:.3f} Jy/beam, SNR = {p['snr']:.1f}")
        """
        info = self._native.get_peak_info()
        if info["rms"] == 0.0 and info["flux"] == 0.0:
            raise DifmapStateError("Aucune carte disponible. Appelez invert() d'abord.")
        return info

    def addwin(self, xa: float, xb: float, ya: float, yb: float) -> None:
        """
        Ajoute une fenêtre CLEAN rectangulaire.

        Équivalent à la commande ``addwin`` de Difmap.
        Les coordonnées sont en milli-arcseconds (mas) depuis le centre de la carte.

        Parameters
        ----------
        xa : float
            Bord gauche de la fenêtre (RA, en mas).
        xb : float
            Bord droit de la fenêtre (RA, en mas).
        ya : float
            Bord bas de la fenêtre (Dec, en mas).
        yb : float
            Bord haut de la fenêtre (Dec, en mas).

        Examples
        --------
        >>> session.imager.addwin(-5, 5, -5, 5)   # fenêtre 10×10 mas centrée
        """
        if self._native.addwin(xa, xb, ya, yb) != 0:
            raise DifmapError("Erreur lors de l'ajout d'une fenêtre CLEAN.")
        self.active_windows = self._get_clean_windows()

    def delwin(self) -> None:
        """
        Supprime toutes les fenêtres CLEAN actives.

        Équivalent à la commande ``delwin`` de Difmap.
        """
        self._native.delwin()
        self.active_windows.clear()

    def peakwin(self, size: float = 1.0, doabs: bool = False) -> None:
        """
        Ajoute automatiquement une fenêtre CLEAN autour du pic de flux.

        Équivalent à la commande ``peakwin`` de Difmap : place une fenêtre
        centrée sur le pixel de valeur maximale avec une taille proportionnelle
        au faisceau synthétique.

        Parameters
        ----------
        size : float, optional
            Taille de la fenêtre relative à la taille FWHM du beam. Par défaut 1.0.
        doabs : bool, optional
            Si ``True``, cherche le pic en valeur absolue (max ou min).
            Par défaut ``False`` (pic positif).

        Raises
        ------
        DifmapError
            Si aucune carte n'est en mémoire.

        Examples
        --------
        >>> session.imager.invert()
        >>> session.imager.peakwin(size=2.0)   # fenêtre 2× le beam autour du pic
        >>> session.imager.clean(500, 0.05)
        """
        # Rafraîchir la carte si elle est marquée comme périmée
        self._refresh_map_if_needed()
        
        if self._native.peakwin(float(size), int(doabs)) != 0:
            raise DifmapError("Erreur peakwin : aucune carte disponible ou carte périmée.")
        self.active_windows = self._get_clean_windows()

    def _refresh_map_if_needed(self) -> None:
        """
        Rafraîchit la carte et le faisceau si nécessaire pour peakwin.
        
        Cette fonction met à jour les flags domap/dobeam pour que peakwin
        fonctionne correctement après des opérations comme CLEAN.
        """
        try:
            if hasattr(self._native, 'refresh_beam'):
                self._native.refresh_beam()
                if self._current_map_type != "clean":
                    self._current_map_type = "dirty"
        except:
            pass

    def get_elliptical_window(self, center_x: float, center_y: float, 
                             size: float = 1.0) -> Tuple[float, float, float, float]:
        """
        Calcule une fenêtre elliptique adaptée au beam comme Difmap.
        
        Utilise les paramètres BMAJ, BMIN, BPA du beam pour créer
        une fenêtre elliptique via el_define() comme dans Difmap.
        
        Parameters
        ----------
        center_x, center_y : float
            Centre de la fenêtre en mas
        size : float, optional
            Taille en multiples du FWHM. Par défaut 1.0
            
        Returns
        -------
        tuple
            (x_min, x_max, y_min, y_max) en mas pour la fenêtre elliptique
        """
        beam = self._native.get_beam_info()
        bmaj = beam.get('BMAJ', 1.0)  # mas
        bmin = beam.get('BMIN', bmaj)  # mas
        bpa = beam.get('BPA', 0.0)     # degrés
        
        # Conversion en radians pour le calcul
        bpa_rad = np.radians(bpa)
        
        # Demi-axes elliptiques
        a = size * bmaj / 2.0  # demi-grand axe
        b = size * bmin / 2.0  # demi-petit axe
        
        # Rectangle englobant de l'ellipse (approximation pour l'affichage)
        # Rotation de l'ellipse par rapport aux axes
        cos_pa = np.cos(bpa_rad)
        sin_pa = np.sin(bpa_rad)
        
        # Extrema en x et y après rotation
        dx = np.sqrt((a * cos_pa)**2 + (b * sin_pa)**2)
        dy = np.sqrt((a * sin_pa)**2 + (b * cos_pa)**2)
        
        x_min = center_x - dx
        x_max = center_x + dx
        y_min = center_y - dy
        y_max = center_y + dy
        
        return x_min, x_max, y_min, y_max

    def get_model_components(self) -> list:
        """
        Retourne la liste des composantes CLEAN du modèle courant.

        Disponible après ``clean()`` ou ``restore()``. Agrège les composantes
        établies (``model``) et tentatives (``newmod``) du moteur C.

        Returns
        -------
        list of dict
            Chaque dict contient ``'flux'`` (Jy), ``'x'`` (mas), ``'y'`` (mas),
            ``'major'`` (mas, 0 pour un delta), ``'ratio'``, ``'phi'`` (rad),
            ``'type'`` (``'delta'``, ``'gaussian'``, …).

        Examples
        --------
        >>> session.imager.clean(500, 0.05)
        >>> comps = session.imager.get_model_components()
        >>> print(f"{len(comps)} composantes, flux total = {sum(c['flux'] for c in comps):.3f} Jy")
        """
        return self._native.get_model_components()

    def selfcal(self, doamp: bool = False, dofloat: bool = False, solint: float = 0.0) -> None:
        """
        Applique une auto-calibration sur les visibilités.

        Équivalent à la commande ``selfcal`` de Difmap. Utilise le modèle
        CLEAN courant pour corriger les gains des antennes. La carte doit
        être recalculée (``invert()``) après cette opération.

        Parameters
        ----------
        doamp : bool, optional
            Si ``True``, calibration amplitude + phase. Par défaut ``False``
            (phase seule).
        dofloat : bool, optional
            Si ``True``, corrections d'amplitude non contraintes (flottantes).
            Par défaut ``False``.
        solint : float, optional
            Intervalle de solution en minutes. ``0.0`` = intégration par
            intégration. Par défaut ``0.0``.

        Raises
        ------
        DifmapError
            Si l'auto-calibration échoue (pas de modèle ou pas de données).

        Examples
        --------
        Boucle CLEAN + selfcal classique :

        >>> session.imager.invert()
        >>> session.imager.clean(200, 0.05)
        >>> session.imager.selfcal()          # phase seule
        >>> session.imager.invert()           # recalculer la carte résiduelle
        >>> session.imager.clean(500, 0.05)
        >>> session.imager.selfcal(doamp=True) # amplitude + phase
        """
        if self._native.selfcal(int(doamp), int(dofloat), float(solint)) != 0:
            raise DifmapError("Échec de l'auto-calibration (selfcal).")

    def make_clean_map(self, size: int, cellsize: float, niter: int = 100, gain: float = 0.05,
                       cutoff: float = 0.0, pol: Polarization = "I", ny: int = None, 
                       cellsize_y: float = None) -> dict:
        """
        Orchestre la création d'une Clean Map de A à Z.

        Capture automatiquement la Residual Map entre ``clean()`` et ``restore()``.
        Le résiduel est accessible via ``get_residual_package()`` après l'appel.
        
        Parameters
        ----------
        size, cellsize : int, float
            Dimensions de la grille (voir ``mapsize()``).
        niter : int
            Max d'itérations. Si négatif, arrêt au 1er composant négatif.
        gain : float
            Gain de boucle CLEAN (0 < gain < 1).
        cutoff : float
            Seuil de flux résiduel pour arrêt (Jy/beam). 0 = pas de limite.
        pol : str
            Polarisation à imager ("I", "RR", "LL", etc.).
        ny, cellsize_y : int, float, optional
            Pour grille rectangulaire.
        """
        self._session.obs.select(pol=pol)
        self.mapsize(size, cellsize, ny=ny, cellsize_y=cellsize_y)
        self.clrmod()
        self.invert()
        self.clean(niter, gain, cutoff)
        # _capture_residual() est appelé dans restore() automatiquement
        self.restore()
        return self.get_map_package(cellsize, cellsize_y=cellsize_y)

    def make_dirty_map(self, size: int, cellsize: float, pol: Polarization = "I",
                       ny: int = None, cellsize_y: float = None) -> dict:
        """
        Crée une Dirty Map en une seule commande.

        Enchaîne ``select()``, ``mapsize()`` et ``invert()``, puis retourne le
        package complet. Idéal pour une utilisation rapide dans un notebook.

        Parameters
        ----------
        size : int
            Nombre de pixels sur l'axe X (puissance de 2 recommandée).
        cellsize : float
            Taille du pixel en milli-arcseconde sur l'axe X.
        pol : Polarization, optional
            Polarisation à imager. Par défaut ``"I"`` (Stokes I).
        ny : int, optional
            Nombre de pixels sur l'axe Y. Défaut : identique à ``size``.
        cellsize_y : float, optional
            Taille du pixel en mas sur l'axe Y. Défaut : identique à ``cellsize``.

        Returns
        -------
        dict
            Même structure que ``get_map_package()`` :
            ``'data'``, ``'beam_data'``, ``'extent'``, ``'info'``.

        Examples
        --------
        >>> img = session.imager.make_dirty_map(512, 0.1, pol="RR")
        >>> session.vis.plot_image(img, title="Dirty Map RR")
        """
        self._session.obs.select(pol=pol)
        self.mapsize(size, cellsize, ny=ny, cellsize_y=cellsize_y)
        self.invert()
        return self.get_map_package(cellsize, cellsize_y=cellsize_y)
