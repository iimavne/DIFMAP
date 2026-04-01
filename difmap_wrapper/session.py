# difmap_wrapper/session.py
import difmap_native
from difmap_wrapper.imaging import DifmapImager
from difmap_wrapper.observation import Observation
from .exceptions import DifmapStateError, DifmapError

class DifmapSession:
    """
    Façade principale pour piloter l'environnement Difmap en toute sécurité.
    
    Cette classe gère le cycle de vie des données (chargement, nettoyage) 
    et fait le pont avec le moteur C sous-jacent. Elle est conçue pour être 
    utilisée comme un Context Manager (`with DifmapSession() as session:`) 
    afin de garantir l'absence de fuites mémoire (RAM).
    """
    
    def __init__(self):
        self.uv_loaded = False
        self._native = difmap_native
        # On instancie les sous-objets en leur passant la session
        self.obs = Observation(self)
        self.imager = DifmapImager()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()

    def observe(self, filepath: str):
        """Charge un fichier FITS."""
        if self.uv_loaded:
            self.cleanup()
            self.imager.uvtaper(0, 0)
        if self._native.observe(filepath) != 0:
            raise DifmapError(f"Impossible de lire : {filepath}")
        self.uv_loaded = True

    def cleanup(self):
        """Libère les ressources."""
        self.uv_loaded = False