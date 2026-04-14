# difmap_wrapper/session.py
import difmap_native
from .imaging import DifmapImager
from .observation import Observation
from .exceptions import DifmapStateError, DifmapError
from .visualizer import Visualizer

class DifmapSession:
    """
    Façade principale pour piloter l'environnement Difmap en toute sécurité.
    
    Cette classe gère le cycle de vie des données (chargement, nettoyage) 
    et fait le pont avec le moteur C sous-jacent. Elle est conçue pour être 
    utilisée comme un Context Manager afin de garantir l'absence de fuites mémoire.

    Examples
    --------
    >>> from difmap_wrapper.session import DifmapSession
    >>> with DifmapSession() as session:
    >>>     session.observe("data/0003-066.fits")
    >>>     # Traitement des données ici...
    """
    
    
    def __init__(self):
        from .visualizer import Visualizer  # Import local pour éviter circular import
        
        self.uv_loaded = False
        self._native = difmap_native
        # On instancie les sous-objets en leur passant la session
        self.obs = Observation(self)
        self.imager = DifmapImager(self)
        self.vis = Visualizer(self)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()

    def observe(self, filepath: str):
        """
    Charge un fichier FITS contenant des visibilités dans la mémoire du moteur C.

    Si une observation est déjà chargée, cette méthode nettoie la mémoire 
    et réinitialise les filtres (comme le taper) avant de charger le nouveau fichier.

    Parameters
    ----------
    filepath : str
        Le chemin absolu ou relatif vers le fichier FITS (ex: '.SPLIT.1' ou '.fits').

    Raises
    ------
    DifmapError
        Si le fichier est introuvable, corrompu, ou illisible par le moteur C.

    Examples
    --------
    >>> with DifmapSession() as session:
    >>>     session.observe("data/0003-066.fits")
    >>>     print(session.uv_loaded)
    True
    """
        if self.uv_loaded:
            self.cleanup()
            self.imager.uvtaper(0, 0)
            
        # 1. On lance le moteur C. 
        # Il va renvoyer un code d'avertissement (les dates), mais on l'ignore 
        # car on sait que c'est un faux positif lié aux vieux fichiers.
        self._native.observe(filepath)
        
        # /!\ Attention : On ne peut pas vérifier les données avec get_uv_data() ici !
        # Le moteur C a besoin d'un appel à select() avant d'exposer la mémoire.
        self.uv_loaded = True

    def cleanup(self):
        """
    Libère les ressources mémoire et réinitialise l'état de la session.

    Cette méthode est appelée automatiquement à la sortie du bloc `with`. 
    Il est rare de devoir l'appeler manuellement, sauf si la session est 
    gérée hors d'un Context Manager.

    Examples
    --------
    >>> session = DifmapSession()
    >>> session.observe("data/0003-066.fits")
    >>> session.cleanup()
    >>> print(session.uv_loaded)
    False
    """
        self.uv_loaded = False