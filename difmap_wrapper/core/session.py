# difmap_wrapper/session.py
import threading
import difmap_native

from .imaging import DifmapImager
from .observation import Observation
from ..utils.exceptions import DifmapStateError, DifmapError


class _SingletonMeta(type):
    """Empêche la création de deux sessions simultanées (le moteur C est global)."""
    _instance = None
    _lock = threading.Lock()

    def __call__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is not None:
                raise DifmapStateError(
                    "Une instance DifmapSession est déjà active dans ce processus. "
                    "Le moteur C utilise des variables globales : deux sessions "
                    "simultanées causeraient une corruption mémoire (segfault).\n"
                    "→ Réutilisez l'instance existante, ou appelez session.cleanup() "
                    "avant d'en créer une nouvelle."
                )
            instance = super().__call__(*args, **kwargs)
            cls._instance = instance
        return instance

    def force_reset(cls) -> None:
        """
        Libère le verrou singleton sans passer par l'instance.

        À utiliser uniquement dans un notebook Jupyter quand le kernel a planté
        et que l'instance précédente est inaccessible. N'appelle aucun destructeur
        C — les ressources natives sont perdues (acceptable après un crash kernel).

        Examples
        --------
        >>> DifmapSession.force_reset()
        >>> session = DifmapSession()   # OK
        """
        cls._instance = None


class DifmapSession(metaclass=_SingletonMeta):
    """
    Point d'entrée principal pour analyser des données radio-interférométriques.

    Charge des fichiers de visibilités FITS/UVFITS et donne accès aux données
    brutes, à l'imagerie et aux graphiques. Une seule instance peut être active
    à la fois (le moteur C utilise une mémoire globale).

    S'utilise de préférence comme gestionnaire de contexte pour garantir
    la libération des ressources.

    Attributes
    ----------
    obs : Observation
        Données UV, sélection de polarisation, flagging.
    imager : DifmapImager
        Imagerie : grille, pondération, transformée de Fourier.
    vis : Visualizer
        Graphiques statiques (couverture UV, radplot, carte).

    Examples
    --------
    Chargement et accès aux données avec gestionnaire de contexte :

    >>> with DifmapSession() as session:
    ...     session.observe("data/source.uvfits")
    ...     session.obs.select(pol="RR")
    ...     data = session.obs.get_data()
    ...     print(data["amp"].mean())
    0.312

    Utilisation sans `with` — cleanup manuel obligatoire :

    >>> session = DifmapSession()
    >>> session.observe("data/source.uvfits")
    >>> # ... travail ...
    >>> session.cleanup()
    """

    def __init__(self):
        self.uv_loaded = False
        self._native = difmap_native
        self.obs = Observation(self)
        self.imager = DifmapImager(self)

        from .visualizer import Visualizer
        self.vis = Visualizer(self)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()

    def observe(self, filepath: str) -> None:
        """
        Charge un fichier de visibilités en mémoire.

        Si une observation était déjà active, elle est remplacée proprement.
        Après cet appel, ``session.obs.select()`` doit être appelé pour
        choisir la polarisation et activer les données.

        Parameters
        ----------
        filepath : str
            Chemin vers le fichier FITS ou UVFITS.
            Exemple : ``"data/source.uvfits"``.

        Raises
        ------
        DifmapError
            Si le fichier est introuvable, corrompu ou dans un format
            non reconnu.

        Examples
        --------
        >>> session.observe("data/source.uvfits")
        >>> print(session.obs.source)
        'J0003-066'
        """
        import os
        if not os.path.isfile(filepath):
            raise DifmapError(f"Fichier introuvable : {filepath}")
        if self.uv_loaded:
            self._native_cleanup()
        ret = self._native.observe(filepath)
        if ret != 0:
            raise DifmapError(f"Échec du chargement : {filepath} (format non reconnu ou fichier corrompu)")
        self.uv_loaded = True

    def _native_cleanup(self) -> None:
        """Libère les buffers C et remet à zéro l'état Python avant un rechargement."""
        self.uv_loaded = False
        # Déconnecter les éditeurs AVANT de libérer les buffers C pour éviter
        # tout accès C depuis un callback résiduel pendant la transition
        for editor in list(self.obs._editors):
            try:
                editor.cleanup()
            except Exception:
                pass
        self.obs._editors.clear()
        self._native.cleanup()
        # Réinitialiser l'état Python pour ne pas garder en RAM les données de l'ancien fichier
        self.imager._last_residual_map = None
        self.imager._last_mapsize = None
        self.imager._last_cellsize = None
        self.imager._last_ny = None
        self.imager._last_cellsize_y = None
        self.imager._current_map_type = None
        self.imager._current_uvtaper = None
        self.imager._current_uvweight = None
        self.imager.active_windows = []
        self.obs.masque_flagges = None
        self.obs.historique_coupes.clear()
        self.obs.invalidate_cache()

    def cleanup(self) -> None:
        """
        Libère les ressources et permet de créer une nouvelle session.

        Appelé automatiquement à la sortie d'un bloc ``with``.
        Après cet appel, une nouvelle ``DifmapSession()`` peut être instanciée.

        Examples
        --------
        >>> session.cleanup()
        >>> session2 = DifmapSession()   # OK, le slot est libéré
        """
        if self.uv_loaded:
            self._native_cleanup()
        with type(self)._lock:
            type(self)._instance = None
