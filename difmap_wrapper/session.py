# difmap_wrapper/session.py
import difmap_native
from .exceptions import DifmapStateError, DifmapError
from .imaging import DifmapImager

class DifmapSession:
    """
    Façade principale pour piloter l'environnement Difmap en toute sécurité.
    
    Cette classe gère le cycle de vie des données (chargement, nettoyage) 
    et fait le pont avec le moteur C sous-jacent. Elle est conçue pour être 
    utilisée comme un Context Manager (`with DifmapSession() as session:`) 
    afin de garantir l'absence de fuites mémoire (RAM).

    Examples
    --------
    Voici le workflow standard recommandé pour analyser une observation :
    
    ```python
    from difmap_wrapper import DifmapSession
    
    # Le 'with' garantit que la RAM est vidée à la fin
    with DifmapSession() as session:
        session.load_observation("ma_galaxie.fits")
        img = session.create_image(size=512, cellsize=0.1)
        
        print(f"Image générée : {img['data'].shape}")
    ```
    """
    
    def __init__(self):
        """
        Initialise une nouvelle session vierge.

        Examples
        --------
        ```python
        session = DifmapSession()
        print(session.uv_loaded)  # Affiche: False
        ```
        """
        self.uv_loaded = False
        self.current_image = None

    # --- AJOUT DU CONTEXT MANAGER ---
    def __enter__(self) -> "DifmapSession":
        """
        Initialise le bloc 'with' et retourne l'instance de la session.
        
        Returns
        -------
        DifmapSession
            L'instance courante prête à l'emploi.

        Examples
        --------
        ```python
        # __enter__ est appelé automatiquement au début du bloc 'with'
        with DifmapSession() as session:
            pass 
        ```
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Garantit la libération des ressources à la sortie du bloc 'with'.
        Même en cas de crash dans le script Python, cette méthode sera appelée
        pour vider la RAM allouée par le C.

        Examples
        --------
        ```python
        with DifmapSession() as session:
            raise ValueError("Crash imprévu !")
        # __exit__ est quand même exécuté ici, la RAM du C est libérée.
        ```
        """
        self.cleanup()

    def cleanup(self) -> None:
        """
        Force la fermeture de l'observation et libère la RAM du moteur C.
        
        Cette méthode réinitialise l'automate d'état. Elle est appelée 
        automatiquement si vous utilisez le Context Manager, mais peut 
        aussi être appelée manuellement si besoin.

        Examples
        --------
        Nettoyage manuel si vous n'utilisez pas de bloc 'with' :
        
        ```python
        session = DifmapSession()
        session.load_observation("data.fits")
        
        # ... traitements ...
        
        # Libération explicite de la mémoire à la fin du script
        session.cleanup()
        ```
        """
        if self.uv_loaded:
            self.uv_loaded = False
            self.current_image = None

    # --- LOGIQUE MÉTIER ---
    def load_observation(self, filepath: str) -> None:
        """
        Charge les données visibilités (fichiers UV FITS) dans la mémoire du moteur C.
        
        Si une observation était déjà chargée dans cette session, elle est 
        automatiquement nettoyée avant le nouveau chargement pour éviter 
        les conflits en RAM.

        Parameters
        ----------
        filepath : str
            Le chemin absolu ou relatif vers le fichier .fits à analyser.

        Raises
        ------
        DifmapError
            Si le fichier est introuvable, corrompu, ou rejeté par le moteur C.
            
        Examples
        --------
        ```python
        session.load_observation("./data/0003-066_X.SPLIT.1")
        ```
        """
        # Sécurité : on nettoie avant de charger une nouvelle observation
        if self.uv_loaded:
            self.cleanup()
            
        if difmap_native.observe(filepath) != 0:
            raise DifmapError(f"Impossible de lire le fichier {filepath}")
        self.uv_loaded = True
        
    def create_image(self, size: int = 512, cellsize: float = 1.0) -> dict:
        """
        Orchestre la création d'une carte brute (Dirty Map) à partir des visibilités.
        
        Cette fonction délègue le calcul mathématique lourd au module spécialisé 
        `DifmapImager`. Elle nécessite qu'une observation ait été préalablement chargée.

        Parameters
        ----------
        size : int, default=512
            La taille de la grille d'image en pixels (ex: 512 pour 512x512). 
            Il est recommandé d'utiliser des puissances de 2 pour optimiser la FFT.
        cellsize : float, default=1.0
            La résolution d'un pixel en millisecondes d'arc (mas).

        Returns
        -------
        dict
            Le dictionnaire contenant les données de l'image générée (data, extent, etc.).

        Raises
        ------
        DifmapStateError
            Si la méthode est appelée avant `load_observation()`.
            
        Examples
        --------
        ```python
        # Création d'une grille HD
        img = session.create_image(size=2048, cellsize=0.05)
        ```
        """
        if not self.uv_loaded:
            raise DifmapStateError(
                "Vous devez charger une observation (load_observation) avant de créer une image."
            )
        
        # Délégation à la classe spécialisée (Pôle 2)
        self.current_image = DifmapImager.make_dirty_map(size, cellsize)
        return self.current_image