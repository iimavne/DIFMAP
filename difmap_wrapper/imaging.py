import numpy as np
import difmap_native
import matplotlib.pyplot as plt
from .exceptions import DifmapError, DifmapStateError

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
        self._last_mapsize = None    # <-- AJOUT : Mémorisation de la taille
        self._current_uvtaper = None
        self._current_uvweight = None

    def _reissue_mapsize_if_needed(self):
        """Restaure la grille si elle a été annulée par un changement de pondération."""
        if self._last_mapsize is not None and self._last_cellsize is not None:
            self._native.mapsize(self._last_mapsize, self._last_cellsize)
            
    def get_map(self) -> np.ndarray:
        """
        Retourne l'image courante depuis la mémoire C (tableau 2D, float).

        Returns
        -------
        np.ndarray
            Matrice 2D de taille ``(ny, nx)`` en Jy/beam.
        """
        return self._native.get_map()

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
        """
        Définit la grille d'imagerie.

        Doit être appelé avant ``invert()``. La taille totale du champ de vue
        est ``size × cellsize`` (mas).

        Parameters
        ----------
        size : int
            Nombre de pixels sur chaque côté de l'image. Doit être une puissance
            de 2 pour la FFT (ex : 256, 512, 1024).
        cellsize : float
            Taille d'un pixel en milli-arcseconde (mas). Choisir environ
            un tiers à un cinquième de la résolution du faisceau.

        Raises
        ------
        DifmapError
            Si le moteur C ne peut pas allouer la grille.

        Examples
        --------
        >>> session.imager.mapsize(512, 0.1)   # champ 51.2 mas, pixel 0.1 mas
        """
        if self._native.mapsize(size, cellsize) != 0:
            raise DifmapError("Erreur lors de l'allocation de la grille (mapsize).")
        self._last_cellsize = cellsize
        self._last_mapsize = size

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
        
    def get_map_package(self, cellsize: float) -> dict:
        """
        Rassemble l'image, le faisceau et les métadonnées dans un seul dictionnaire.

        Ce dictionnaire est le format attendu par ``Visualizer.plot_image()``.

        Parameters
        ----------
        cellsize : float
            Taille du pixel en mas (doit correspondre à celle passée à ``mapsize()``).

        Returns
        -------
        dict
            ``'data'`` : tableau 2D NumPy de la Dirty Map (Jy/beam).

            ``'beam_data'`` : tableau 2D NumPy du faisceau synthétique (PSF).

            ``'extent'`` : limites astrométriques ``[xmax, xmin, ymin, ymax]`` en mas,
            prêtes pour ``matplotlib.imshow()``.

            ``'info'`` : dict avec ``nx``, ``ny``, ``cellsize``, ``bmaj``, ``bmin``, ``bpa``
            (dimensions et paramètres du faisceau).

        Examples
        --------
        >>> session.imager.mapsize(512, 0.1)
        >>> session.imager.invert()
        >>> img = session.imager.get_map_package(cellsize=0.1)
        >>> print(img["info"]["bmaj"])   # grand axe du faisceau en mas
        0.85
        """
        hdr = self._native.get_header()
        beam = self._native.get_beam_info()
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
                "bmaj": beam.get('BMAJ', 0.0),
                "bmin": beam.get('BMIN', 0.0),
                "bpa": beam.get('BPA', 0.0),
                "rms": beam.get('RMS', 0.0)
            },
            "extent": extent_corrige
        }

    def clean(self, niter: int = 100, gain: float = 0.05) -> None:
        """
        Déconvolue la Dirty Map par l'algorithme CLEAN de Högbom/Clark natif.

        Doit être appelé après ``invert()``. Soustrait itérativement les
        composantes ponctuelles du lobe de synthèse et construit le modèle
        de sources propres.

        Parameters
        ----------
        niter : int, optional
            Nombre maximum d'itérations CLEAN. Par défaut 100.
        gain : float, optional
            Gain de boucle CLEAN (entre 0 et 1). Par défaut 0.05.

        Raises
        ------
        DifmapError
            Si le moteur C retourne une erreur (carte ou observation absente).
        """
        if self._native.clean(niter, gain) != 0:
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
        if self._native.restore() != 0:
            raise DifmapError("Échec de la restauration (restore).")

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

    def delwin(self) -> None:
        """
        Supprime toutes les fenêtres CLEAN actives.

        Équivalent à la commande ``delwin`` de Difmap.
        """
        self._native.delwin()

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
        if self._native.peakwin(float(size), int(doabs)) != 0:
            raise DifmapError("Erreur peakwin : aucune carte disponible.")

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

    def make_clean_map(self, size: int, cellsize: float, niter: int = 100, gain: float = 0.05, pol: str = "I") -> dict:
        """Orchestre la création d'une Clean Map de A à Z."""
        self._session.obs.select(pol=pol)
        self.mapsize(size, cellsize)
        self.invert()          
        self.clean(niter, gain) 
        self.restore()         
        return self.get_map_package(cellsize) 

    def make_dirty_map(self, size: int, cellsize: float, pol: str = "I") -> dict:
        """
        Crée une Dirty Map en une seule commande.

        Enchaîne ``select()``, ``mapsize()`` et ``invert()``, puis retourne le
        package complet. Idéal pour une utilisation rapide dans un notebook.

        Parameters
        ----------
        size : int
            Nombre de pixels sur chaque côté (puissance de 2 recommandée).
        cellsize : float
            Taille du pixel en milli-arcseconde.
        pol : str, optional
            Polarisation à imager. Par défaut ``"I"`` (Stokes I).

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
        self.mapsize(size, cellsize)
        self.invert()
        return self.get_map_package(cellsize)