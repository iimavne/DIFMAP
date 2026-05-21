import logging
import numpy as np
from ctypes import Structure, c_char_p, c_int, c_float, c_double, POINTER, byref
from typing import Optional, Tuple, List, Dict, Any, Union
import difmap_native
from ..types import Polarization

from ..utils.map_geometry import DifmapMapGeometry
from ..utils.exceptions import DifmapError, DifmapStateError

logger = logging.getLogger("difmap.imaging")

# Mirror of MAP state enum in difmap.c:637-639
_MAP_IS_MAP   = 0  # dirty or residual (C can't distinguish the two)
_MAP_IS_STALE = 1  # nothing useful — needs reinvert
_MAP_IS_CLEAN = 2  # after restore()

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
        # Display-only copies of C state — used by uvtaper()/uvweight()/selfcal_taper()
        # interrogation mode only. C is authoritative; never use these as guards.
        self._current_uvtaper = None
        self._current_uvweight = None
        self._current_selfcal_taper = None
        # _current_map_type tracks dirty/residual distinction C cannot make (both MAP_IS_MAP=0).
        # Validated against vlbmap->domap by _assert_map_state_coherent() on every get_map_package().
        self._current_map_type = None
        self.active_windows = []     # registre Python des fenêtres CLEAN actives [(xa,xb,ya,yb) en mas]
        self._last_residual_map = None  # copie du buffer résiduel capturée entre clean() et restore()
        self._last_residual_rms = None  # maprms natif au moment de la capture du résiduel

    def reset_state(self) -> None:
        """Remet à zéro l'état Python du DifmapImager après le chargement d'un nouveau fichier.

        Le moteur C remet invpar/respar/slfpar à leurs valeurs par défaut via
        native_observe() → invpar=invdef.  Cette méthode synchronise les
        miroirs Python en conséquence.  À appeler immédiatement après
        session.observe() dans le pipeline GUI.
        """
        self._last_cellsize = None
        self._last_mapsize = None
        self._last_ny = None
        self._last_cellsize_y = None
        self._current_uvtaper = None
        self._current_uvweight = None
        self._current_selfcal_taper = None
        self._current_map_type = None
        self.active_windows.clear()
        self._last_residual_map = None
        self._last_residual_rms = None

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
        except Exception:
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

        # native_uvweight clamps invalids : uvbin<0→0, 0<uvbin<1→1, errpow>0→0.
        # Pas besoin de lever une exception ici ; la valeur effectivement utilisée
        # est celle que difmap aurait choisie.
        # native_uvweight ne touche pas la grille (seulement invpar + domap=STALE),
        # donc pas besoin de _reissue_mapsize_if_needed().
        dorad = 1 if r else 0
        if self._native.uvweight(b, e, dorad) != 0:
            raise DifmapError("Erreur lors de l'application de uvweight.")

        # 3. Mise à jour de la mémoire
        self._current_uvweight = (b, e, r)
        
        rad_str = "Oui" if r else "Non"
        print(f"Nouvelle pondération appliquée : bin_size={b}, err_power={e}, radial={rad_str}")
        
    def uvtaper(self, gaussian_value: float = None, gaussian_radius_wav: float = None) -> None:
        """
        Applique un filtre gaussien (taper) pour réduire la résolution angulaire.

        Le taper atténue les baselines les plus longues, ce qui améliore la
        sensibilité aux structures étendues au détriment de la résolution.
        Appelé sans argument, affiche le taper actif sans modifier l'état.

        Parameters
        ----------
        gaussian_value : float, optional
            Amplitude du filtre gaussien (entre 0 et 1). ``0.0`` = aucun taper.
        gaussian_radius_wav : float, optional
            Rayon du filtre en unités UV courantes (Mλ par défaut, identique
            à la commande native ``uvtaper`` de Difmap). Le moteur C applique
            la conversion interne via ``uvtowav()``.

        Examples
        --------
        Appliquer un taper à partir de 50 Mλ :

        >>> session.imager.uvtaper(gaussian_value=0.3, gaussian_radius_wav=50)

        Désactiver le taper :

        >>> session.imager.uvtaper(0, 0)

        Afficher le taper actif (sans modifier l'état) :

        >>> session.imager.uvtaper()
        Taper actuel : Valeur = 0.3, Rayon = 50 unités UV courantes
        """
        # 1. Mode "Interrogation" — lecture seule, aucun appel au moteur C
        if gaussian_value is None and gaussian_radius_wav is None:
            if self._current_uvtaper in [None, (0.0, 0.0)]:
                print("Taper actuel : Aucun (Désactivé)")
            else:
                val, rad = self._current_uvtaper
                print(f"Taper actuel : Valeur = {val}, Rayon = {rad} unités UV courantes")
            return

        # 2. Mode "Application"
        val = float(gaussian_value) if gaussian_value is not None else 0.0
        rad = float(gaussian_radius_wav) if gaussian_radius_wav is not None else 0.0

        # Le C appelle uvtowav() en interne — passer la valeur en unités UV
        # courantes (Mλ par défaut), sans diviser par 1e6 côté Python.
        if self._native.uvtaper(val, rad) != 0:
            raise DifmapError("Erreur lors de l'application de uvtaper.")

        self._current_uvtaper = (val, rad)

        if val == 0.0 and rad == 0.0:
            print("Taper désactivé avec succès.")
        else:
            print(f"Taper appliqué : Valeur = {val}, Rayon = {rad} unités UV courantes")
        
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
            Taille d'un pixel en unités angulaires courantes (mas par défaut).
            Le moteur C applique ``xytorad()`` en interne, qui dépend des unités
            actives via ``skyunits()``. Ne pas diviser manuellement par un facteur.
        ny : int, optional
            Nombre de pixels sur l'axe Y. Défaut : identique à ``size``.
        cellsize_y : float, optional
            Taille d'un pixel en unités angulaires courantes sur l'axe Y.
            Défaut : identique à ``cellsize``.

        Raises
        ------
        DifmapError
            Si le moteur C ne peut pas allouer la grille.

        Examples
        --------
        >>> session.imager.mapsize(512, 0.1)              # grille carrée 512×512
        >>> session.imager.mapsize(512, 0.1, ny=256)      # grille rectangulaire 512×256
        """
        if ny is not None or cellsize_y is not None:
            actual_ny = ny if ny is not None else 0
            actual_cy = cellsize_y if cellsize_y is not None else 0.0
            result = self._native.mapsize(size, cellsize, actual_ny, actual_cy)
        else:
            result = self._native.mapsize(size, cellsize)
        if result != 0:
            raise DifmapError("Erreur lors de l'allocation de la grille (mapsize).")
        self._last_mapsize = size
        self._last_cellsize = cellsize
        self._last_ny = ny
        self._last_cellsize_y = cellsize_y

    def _capture_residual(self) -> None:
        """Sauvegarde le buffer résiduel et le maprms natif (état après clean(), avant restore())."""
        self._last_residual_map = self.get_map().copy()
        self._last_residual_rms = float(self._native.get_beam_info()["RMS"])

    def snapshot_residual_from_current_map(self) -> None:
        """Capture un snapshot du buffer carte courant comme "résiduel".

        Utilisé par la GUI juste après un ``invert()`` (Dirty Map) pour rendre
        l'onglet Residual immédiatement disponible, même avant tout CLEAN.

        Notes
        -----
        - Ne modifie pas ``_current_map_type``.
        - Ne dépend pas de ``restore()``.
        """
        self._last_residual_map = self.get_map().copy()
        try:
            self._last_residual_rms = float(self._native.get_beam_info().get("RMS", 0.0))
        except Exception:
            self._last_residual_rms = None

    def uvrange(
        self,
        uvmin_wav: float = None,
        uvmax_wav: float = None,
    ) -> None:
        """
        Définit la plage UV utilisée lors du prochain ``invert()``.

        Équivalent à la commande ``uvrange`` de Difmap. Persistant : le filtre
        reste actif jusqu'à ce qu'il soit explicitement réinitialisé.

        Parameters
        ----------
        uvmin_wav : float, optional
            Rayon UV minimum (en longueurs d'onde, unités courantes Mλ par défaut).
            ``None`` ou ``0`` signifie aucune limite inférieure.
        uvmax_wav : float, optional
            Rayon UV maximum. ``None`` ou ``0`` signifie aucune limite supérieure.

        Notes
        -----
        **Limite inférieure seule impossible** : le moteur C annule le filtre
        si ``uvmin >= uvmax`` ou ``uvmax <= 0``. Pour filtrer uniquement en
        dessous d'un rayon, utilisez ``uvmax`` avec ``uvmin=0``.

        Appeler sans arguments réinitialise à la plage complète.

        Examples
        --------
        >>> session.imager.uvrange(uvmax_wav=500)       # exclure baselines > 500 Mλ
        >>> session.imager.uvrange(uvmin_wav=10, uvmax_wav=800)  # exclure courtes baselines
        >>> session.imager.uvrange()                    # réinitialiser (plage complète)
        >>> session.imager.invert()                     # utilise le filtre précédent
        """
        vmin = float(uvmin_wav) if uvmin_wav is not None else 0.0
        vmax = float(uvmax_wav) if uvmax_wav is not None else 0.0
        if self._native.uvrange(vmin, vmax) != 0:
            raise DifmapError("Échec de la configuration uvrange().")

    def uvhwhm(self, uvhwhm_pix: float) -> None:
        """
        Applique un taper gaussien à la grille UV (demi-largeur en pixels).

        Équivalent à la commande ``uvhwhm`` de Difmap. Persistant entre
        les appels à ``invert()``.

        Parameters
        ----------
        uvhwhm_pix : float
            Demi-largeur à mi-hauteur de la gaussienne, en pixels de grille.
            ``0`` pour désactiver.

        Examples
        --------
        >>> session.imager.uvhwhm(2.0)   # taper gaussien
        >>> session.imager.invert()
        """
        if self._native.uvhwhm(float(uvhwhm_pix)) != 0:
            raise DifmapError("Échec de la configuration uvhwhm().")

    def invert(
        self,
        uvmin_wav: float = None,
        uvmax_wav: float = None,
        uvhwhm_pix: float = None,
    ) -> None:
        """
        Calcule la Dirty Map par transformée de Fourier inverse.

        Gridde les visibilités sur la grille définie par ``mapsize()``,
        puis applique la FFT inverse. Le résultat est stocké en mémoire C
        et accessible via ``get_map()``.

        Parameters
        ----------
        uvmin_wav : float, optional
            Si fourni, configure ``uvrange`` avant d'inverter.
            ``None`` (défaut) respecte le dernier ``uvrange()`` appelé.
        uvmax_wav : float, optional
            Idem. Passer ``uvmax_wav=0`` réinitialise la coupure maximale.
        uvhwhm_pix : float, optional
            Si fourni, configure ``uvhwhm`` avant d'inverter.

        Notes
        -----
        ``uvrange`` et ``uvhwhm`` sont persistants dans le moteur C : les
        appeler via ``invert()`` ou en standalone via ``session.imager.uvrange()``
        est strictement équivalent. Préférez la forme standalone pour les
        workflows pas-à-pas.

        Examples
        --------
        Workflow purist (séparé) :

        >>> session.imager.uvrange(uvmax_wav=500)
        >>> session.imager.invert()

        Workflow compact (inline) :

        >>> session.imager.invert(uvmax_wav=500)

        Max seulement, sans min :

        >>> session.imager.invert(uvmax_wav=500)          # uvmin=0 implicite
        >>> session.imager.invert(uvmin_wav=0, uvmax_wav=500)  # identique

        Réinitialiser le filtre et inverter :

        >>> session.imager.invert(uvmin_wav=0, uvmax_wav=0)   # plage complète
        """
        # Appeler uvrange() seulement si au moins un paramètre est explicitement fourni.
        # Quand None/None : respecter l'état C courant (uvrange préalablement fixé ou défaut).
        if uvmin_wav is not None or uvmax_wav is not None:
            vmin = float(uvmin_wav) if uvmin_wav is not None else 0.0
            vmax = float(uvmax_wav) if uvmax_wav is not None else 0.0
            if self._native.uvrange(vmin, vmax) != 0:
                raise DifmapError("Échec de la configuration uvrange().")
        if uvhwhm_pix is not None:
            if self._native.uvhwhm(float(uvhwhm_pix)) != 0:
                raise DifmapError("Échec de la configuration uvhwhm().")

        if self._native.invert() != 0:
            raise DifmapError("Échec de la transformée de Fourier (invert).")
        self._current_map_type = "dirty"
        # invert() met à jour invpar (uvmin/uvmax) et recalcule la grille UV.
        # Le cache obs contient modamp/modphs calculés par l_extract_uv() qui
        # utilise les anciens invpar — invalider pour que radplot() lise des
        # valeurs fraîches au prochain appel.
        self._session.obs.invalidate_cache()

    def _display_map_data(self, map_data: np.ndarray, cellsize: float,
                          cellsize_y: float = None) -> tuple:
        """
        Applique le crop d'affichage Difmap en utilisant la géométrie unifiée.
        """
        return DifmapMapGeometry.crop_map_data(map_data, cellsize, cellsize_y)

    def _get_clean_windows(self) -> list:
        """Retourne la liste native des fenêtres CLEAN depuis le moteur C.

        Lecture seule — ne modifie pas ``active_windows`` (qui conserve les
        coordonnées Python d'origine pour éviter la dérive float32 lors des
        re-addwin successifs).
        """
        get_windows = getattr(self._native, 'get_windows', None)
        if get_windows is None:
            return list(self.active_windows)
        return [
            (min(xa, xb), max(xa, xb), min(ya, yb), max(ya, yb))
            for xa, xb, ya, yb in get_windows()
        ]
        
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
        self._assert_map_state_coherent()
        cy = cellsize_y if cellsize_y is not None else cellsize
        # vlbmap->bmaj/bmin/bpa sont mis à 0 à l'init (mapmem.c:124) et
        # seulement setés par mapres() pendant restore(). Pour dirty/residual,
        # on utilise le beam estimé par invert() (vlbmap->e_bmaj/e_bmin/e_bpa).
        # Pour clean, on utilise le beam réel de la restauration.
        map_type = self._current_map_type if self._current_map_type is not None else "dirty"
        if map_type == "clean":
            beam = self._native.get_beam_info()
        else:
            beam = self._native.get_estimated_beam_info()
        rms = float(beam.get('RMS', 0.0))

        map_data = self.get_map()
        display_data, extent, nx_display, ny_display = self._display_map_data(
            map_data, cellsize, cy
        )
        beam_display, _, _, _ = self._display_map_data(self._native.get_beam(), cellsize, cy)

        components = self._native.get_model_components() if map_type in ("clean", "residual") else []
        return {
            "data": display_data,
            "beam_data": beam_display,
            "map_type": map_type,
            "info": {
                "nx": nx_display,
                "ny": ny_display,
                "cellsize": cellsize,
                "cellsize_y": cy,
                "bmaj": beam.get('BMAJ', 0.0),
                "bmin": beam.get('BMIN', 0.0),
                "bpa": beam.get('BPA', 0.0),
                "rms": rms,
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
        # Beam estimé par invert() (e_bmaj/e_bmin/e_bpa) : c'est le beam de
        # référence du résiduel, qui est créé par clean() avant restore().
        # vlbmap->bmaj/bmin/bpa (clean beam) correspond à la restauration,
        # pas au résiduel.
        beam = self._native.get_estimated_beam_info()
        display_data, extent, nx_display, ny_display = self._display_map_data(
            self._last_residual_map, cellsize, cy
        )
        beam_display, _, _, _ = self._display_map_data(self._native.get_beam(), cellsize, cy)
        # RMS natif DIFMAP (maprms = sqrt(mean((pixel-mean)²)) sur zone cleanable),
        # capturé au moment du résiduel — avant restore() qui modifie maprms.
        residual_rms = self._last_residual_rms if self._last_residual_rms is not None else float(self._native.get_beam_info().get('RMS', 0.0))
        return {
            "data": display_data,
            "beam_data": beam_display,
            "map_type": "residual",
            "info": {
                "nx": nx_display,
                "ny": ny_display,
                "cellsize": cellsize,
                "cellsize_y": cy,
                "bmaj": beam.get('BMAJ', 0.0),
                "bmin": beam.get('BMIN', 0.0),
                "bpa": beam.get('BPA', 0.0),
                "rms": residual_rms,
            },
            "extent": extent,
            "windows": self._get_clean_windows(),
            "model_components": self._native.get_model_components(),
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
            raise DifmapError("Échec du CLEAN (carte ou observation absente).")
        self._current_map_type = "residual"
        # Rendre le résiduel disponible immédiatement (avant restore()).
        # Indispensable pour le CLEAN chunké en GUI (pause_after): on veut afficher
        # l'état après chaque tranche d'itérations.
        try:
            self._capture_residual()
        except Exception:
            # Ne pas faire échouer le CLEAN si la capture échoue — la carte reste valide.
            pass
        # clean() met à jour le modèle C : modamp (calculé par moddif dans
        # l_extract_uv) sera périmé dans le cache. On invalide pour que
        # radplot() obtienne des valeurs fraîches au prochain appel.
        self._session.obs.invalidate_cache()

    def restore(
        self,
        beam: tuple[float, float, float] | None = None,
        noresid: bool = False,
        dosm: bool = True,
    ) -> None:
        """
        Restaure la Clean Map en convoluant le modèle avec le faisceau propre.

        Doit être appelé après ``clean()``. Utilise automatiquement les
        paramètres du faisceau estimés lors du dernier ``invert()``.

        Parameters
        ----------
        beam : tuple of (bmaj, bmin, bpa), optional
            Faisceau explicite en mas/mas/degrés. Si omis, utilise le faisceau
            estimé par ``invert()``.
        noresid : bool, optional
            Si ``True``, efface la carte résiduelle avant restauration
            (produit uniquement le modèle convolu, sans résidus).
            Défaut ``False`` (comportement DIFMAP standard).
        dosm : bool, optional
            Si ``True`` (défaut), lisse les résiduels avant restauration
            (convolue avec le faisceau propre). Identique au défaut DIFMAP.

        Raises
        ------
        DifmapError
            Si le moteur C retourne une erreur (modèle absent ou faisceau
            non estimé).
        """
        if self._current_map_type == "residual":
            try:
                self._capture_residual()
            except Exception:
                pass

        nr = int(bool(noresid))
        ds = int(bool(dosm))

        if beam is None:
            if self._native.restore(nr, ds) != 0:
                raise DifmapError("Échec de la restauration (restore).")
        else:
            bmaj_mas, bmin_mas, bpa_deg = beam
            if self._native.restore_beam(float(bmaj_mas), float(bmin_mas), float(bpa_deg), nr, ds) != 0:
                raise DifmapError("Échec de la restauration (restore) avec faisceau explicite.")
        self._current_map_type = "clean"

    def peak(self, doabs: bool = True) -> dict:
        """
        Retourne les statistiques du pic de flux dans la carte courante.

        Équivalent à la commande ``peak`` de Difmap.

        Parameters
        ----------
        doabs : bool, optional
            Si ``True`` (défaut), cherche le pic en valeur absolue (max ou min).
            Identique au comportement natif de la commande ``peak`` de DIFMAP
            (difmap.c:4558). Si ``False``, cherche uniquement le pic positif.

        Returns
        -------
        dict
            ``'flux'`` : valeur du pic en Jy/beam (peut être négative si doabs=True).

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
        if not self.has_map_data():
            raise DifmapStateError("Aucune carte disponible. Appelez invert() d'abord.")
        return self._native.get_peak_info(int(doabs))

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
        # Conserver les coordonnées Python d'origine (pas le round-trip C radtoxy).
        # Indispensable pour que delete-last + re-addwin ne dérive pas par arrondi float32.
        self.active_windows.append((xa, xb, ya, yb))

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
        # native_peakwin() (difmap.c:8578) gère MAP_IS_CLEAN en promouvant
        # temporairement domap vers MAP_IS_MAP. Après clean(), le buffer contient
        # le résiduel avec domap=MAP_IS_MAP. Pas de re-invert Python nécessaire.
        self._refresh_map_if_needed()
        
        old_count = len(self.active_windows)
        if self._native.peakwin(float(size), int(doabs)) != 0:
            raise DifmapError("Erreur peakwin : aucune carte disponible ou carte périmée.")
        # Appender uniquement la nouvelle fenêtre calculée par C (position inconnue
        # avant l'appel C — readback inévitable). Les fenêtres existantes conservent
        # leurs coordonnées Python d'origine 
        for w in self._get_clean_windows()[old_count:]:
            self.active_windows.append(w)

    def _assert_map_state_coherent(self) -> None:
        """Réconcilie _current_map_type avec vlbmap->domap lu depuis le C.

        Corrige silencieusement les divergences dues à des invert() implicites
        (ex : peakwin() appelle invert() en interne) ou à des select() qui
        invalident le buffer. Sans cette garde, get_map_package() utiliserait
        get_beam_info() (bmaj/bmin réels) sur une carte dirty, retournant 0.
        """
        try:
            c_state = self._native.get_map_state()
        except AttributeError:
            return  # module non recompilé — dégradation gracieuse
        if c_state < 0:
            return  # vlbmap == NULL, pas de carte
        if c_state == _MAP_IS_STALE:
            self._current_map_type = None
        elif c_state == _MAP_IS_CLEAN and self._current_map_type != "clean":
            self._current_map_type = "clean"
        elif c_state == _MAP_IS_MAP and self._current_map_type == "clean":
            # invert() appelé implicitement (peakwin, select…) : buffer n'est plus clean
            logger.warning(
                "_current_map_type='clean' mais vlbmap->domap=MAP_IS_MAP — "
                "invert() appelé implicitement, type corrigé en 'dirty'."
            )
            self._current_map_type = "dirty"

    def _refresh_map_if_needed(self) -> None:
        """Vérifie qu'une carte est en mémoire avant peakwin()."""
        if not self.has_map_data():
            raise DifmapError("Aucune carte disponible pour peakwin(). Appelez invert() d'abord.")

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
        # vlbmap->bmaj/bmin/bpa = 0 avant le premier restore() (mapmem.c:124).
        # Pour dirty/residual, utiliser le beam estimé par invert() comme
        # get_map_package() le fait.
        if self._current_map_type == "clean":
            beam = self._native.get_beam_info()
        else:
            beam = self._native.get_estimated_beam_info()
        bmaj = beam.get('BMAJ', 1.0)  # mas
        bmin = beam.get('BMIN', bmaj)  # mas
        bpa = beam.get('BPA', 0.0)     # degrés
        
        # Conversion en radians pour le calcul
        bpa_rad = np.radians(bpa)
        
        # Demi-axes elliptiques
        a = size * bmaj / 2.0  # demi-grand axe
        b = size * bmin / 2.0  # demi-petit axe
        
        # Rectangle englobant de l'ellipse.
        # BPA est l'angle depuis le Nord (axe Y), pas depuis l'axe X.
        # Pour dx (étendue E-W) : composante = a*sin(bpa) + b*cos(bpa)
        # Pour dy (étendue N-S) : composante = a*cos(bpa) + b*sin(bpa)
        cos_pa = np.cos(bpa_rad)
        sin_pa = np.sin(bpa_rad)

        dx = np.sqrt((a * sin_pa)**2 + (b * cos_pa)**2)
        dy = np.sqrt((a * cos_pa)**2 + (b * sin_pa)**2)
        
        x_min = center_x - dx
        x_max = center_x + dx
        y_min = center_y - dy
        y_max = center_y + dy
        
        return x_min, x_max, y_min, y_max

    def wmap(self, filepath: str) -> None:
        """
        Exporte la clean map courante en FITS image.

        Doit être appelé après ``restore()``. Le buffer doit être en état
        ``MAP_IS_CLEAN`` — appeler ``restore()`` d'abord.

        Parameters
        ----------
        filepath : str
            Chemin de sortie (extension ``.fits`` recommandée).

        Raises
        ------
        DifmapStateError
            Si ``restore()`` n'a pas encore été appelé (map non clean).
        DifmapError
            Si l'écriture FITS échoue.
        """
        ret = self._native.wmap(filepath)
        if ret == -2:
            raise DifmapStateError(
                "wmap() requiert une clean map : appelez restore() d'abord."
            )
        if ret != 0:
            raise DifmapError(f"Échec de l'écriture wmap : {filepath}")

    def wbeam(self, filepath: str) -> None:
        """
        Exporte le dirty beam courant en FITS image.

        Doit être appelé après ``invert()``.

        Parameters
        ----------
        filepath : str
            Chemin de sortie.

        Raises
        ------
        DifmapStateError
            Si le beam n'est pas disponible.
        DifmapError
            Si l'écriture FITS échoue.
        """
        ret = self._native.wbeam(filepath)
        if ret == -2:
            raise DifmapStateError(
                "wbeam() requiert un beam valide : appelez invert() d'abord."
            )
        if ret != 0:
            raise DifmapError(f"Échec de l'écriture wbeam : {filepath}")

    def wdmap(self, filepath: str) -> None:
        """
        Exporte la carte dirty ou résiduelle courante en FITS image.

        Doit être appelé après ``invert()`` (pour la dirty map) ou après
        ``clean()`` (pour la residual map). Ne fonctionne pas sur une clean map.

        Parameters
        ----------
        filepath : str
            Chemin de sortie.

        Raises
        ------
        DifmapStateError
            Si la carte n'est pas dans l'état dirty/résiduel (MAP_IS_MAP).
        DifmapError
            Si l'écriture FITS échoue.
        """
        ret = self._native.wdmap(filepath)
        if ret == -2:
            raise DifmapStateError(
                "wdmap() requiert une dirty/résiduelle map (MAP_IS_MAP) : "
                "la carte est soit périmée (appelez invert()) soit clean (appelez invert() pour recréer la dirty)."
            )
        if ret != 0:
            raise DifmapError(f"Échec de l'écriture wdmap : {filepath}")

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

    def selfcal_taper(self, gaussian_value: float = None, gaussian_radius_wav: float = None) -> None:
        """
        Configure le taper gaussien spécifique à l'auto-calibration.

        Équivalent à la commande ``staper`` de Difmap. Ce taper est indépendant
        du taper d'inversion (``uvtaper``) : il pondère les visibilités utilisées
        pour résoudre les gains, sans affecter la carte.

        Appelé sans argument, affiche le taper selfcal actif sans modifier l'état.

        Parameters
        ----------
        gaussian_value : float, optional
            Amplitude du filtre gaussien (entre 0 et 1). ``0.0`` = aucun taper.
        gaussian_radius_wav : float, optional
            Rayon en unités UV courantes (Mλ par défaut), identique à ``uvtaper()``.
            Le moteur C applique ``uvtowav()`` en interne.

        Examples
        --------
        Taper selfcal à 50 Mλ :

        >>> session.imager.selfcal_taper(0.3, 50)

        Désactiver :

        >>> session.imager.selfcal_taper(0, 0)
        """
        if gaussian_value is None and gaussian_radius_wav is None:
            if self._current_selfcal_taper in [None, (0.0, 0.0)]:
                print("Taper selfcal : Aucun (Désactivé)")
            else:
                val, rad = self._current_selfcal_taper
                print(f"Taper selfcal : Valeur = {val}, Rayon = {rad} unités UV courantes")
            return

        val = float(gaussian_value) if gaussian_value is not None else 0.0
        rad = float(gaussian_radius_wav) if gaussian_radius_wav is not None else 0.0

        if self._native.staper(val, rad) != 0:
            raise DifmapError("Erreur lors de l'application du taper selfcal.")

        self._current_selfcal_taper = (val, rad)
        if val == 0.0 and rad == 0.0:
            print("Taper selfcal désactivé.")
        else:
            print(f"Taper selfcal appliqué : Valeur = {val}, Rayon = {rad} unités UV courantes")

    def selfcal(
        self,
        doamp: bool = False,
        dofloat: bool = False,
        solint: float = 0.0,
        maxamp: float = 0.0,
        maxphs: float = 0.0,
        p_mintel: int = 3,
        a_mintel: int = 4,
        doflag: bool = True,
        clip: bool = False,
    ) -> None:
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
        # slfpar est remis à slfdef uniquement au chargement d'une observation
        # (difmap.c:834). Entre deux selfcal() sur la même observation, le C
        # conserve l'état précédent. On envoie toujours les trois groupes pour
        # garantir que chaque appel part d'un état connu, indépendamment de
        # l'historique.
        if self._native.selfcal_limits(float(maxamp), float(maxphs)) != 0:
            raise DifmapError("Échec de la configuration selfcal_limits().")
        if self._native.selfcal_mintel(int(p_mintel), int(a_mintel)) != 0:
            raise DifmapError("Échec de la configuration selfcal_mintel().")
        if self._native.selfcal_flags(int(bool(doflag)), int(bool(clip))) != 0:
            raise DifmapError("Échec de la configuration selfcal_flags().")

        if self._native.selfcal(int(doamp), int(dofloat), float(solint)) != 0:
            raise DifmapError("Échec de l'auto-calibration (selfcal).")
        # Selfcal modifie les poids (et phases) des visibilités côté C.
        # Le cache Python doit être invalidé pour que get_data() renvoie
        # les données corrigées, et les éditeurs graphiques notifiés.
        self._session.obs.invalidate_cache()
        self._session.obs.notify_data_changed()

    def make_clean_map(self, size: int, cellsize: float, niter: int = 100, gain: float = 0.05,
                       cutoff: float = 0.0, pol: Polarization = "I", ny: int = None,
                       cellsize_y: float = None,
                       windows: list = None) -> dict:
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
        windows : list of (xa, xb, ya, yb), optional
            Fenêtres CLEAN en mas. Si omis, CLEAN opère sur toute la zone
            imageable (comportement natif de Difmap sans fenêtre).
            Exemple : ``windows=[(-5, 5, -5, 5)]``.
        """
        self._session.obs.select(pol=pol)
        self.mapsize(size, cellsize, ny=ny, cellsize_y=cellsize_y)
        self.clrmod()
        self.invert()
        if windows:
            self.delwin()
            for xa, xb, ya, yb in windows:
                self.addwin(xa, xb, ya, yb)
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
