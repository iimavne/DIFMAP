# difmap_wrapper/exceptions.py

class DifmapError(Exception):
    """
    Exception de base pour toutes les erreurs liées au moteur C de Difmap.
    
    Cette exception est levée lorsque le code natif (C/Cython) rencontre 
    un problème interne qu'il ne peut pas résoudre (ex: échec d'allocation 
    mémoire, erreur mathématique dans la FFT, fichier FITS introuvable). 
    C'est la classe parente de toutes les exceptions spécifiques du paquet.

    Examples
    --------
    Interception d'une erreur critique du moteur lors de l'automatisation 
    d'un pipeline de traitement :

    ```python
    from difmap_wrapper import DifmapSession
    from difmap_wrapper.exceptions import DifmapError

    with DifmapSession() as session:
        try:
            # Tentative de chargement d'un fichier corrompu ou inexistant
            session.load_observation("donnees_corrompues.fits")
            
        except DifmapError as e:
            print(f"Alerte : Le moteur C a rejeté l'opération. Détail : {e}")
            # Le script peut continuer à analyser la galaxie suivante 
            # sans s'arrêter net.
    ```
    """
    pass

class DifmapStateError(DifmapError):
    """
    Levée lorsqu'une action est tentée dans le mauvais ordre.
    
    Le moteur Difmap fonctionne comme un automate d'état strict. Cette 
    erreur est levée par la surcouche Python pour prévenir les crashs 
    violents (segfaults) du moteur C en bloquant les appels illogiques.
    
    Examples
    --------
    Typiquement levée si vous essayez de générer une image sans avoir 
    chargé de données UV au préalable :
    
    ```python
    from difmap_wrapper import DifmapSession
    from difmap_wrapper.exceptions import DifmapStateError
    
    with DifmapSession() as session:
        try:
            # Oups, on a oublié session.load_observation() !
            session.create_image()
        except DifmapStateError as e:
            print(f"Erreur d'état bloquée proprement : {e}")
    ```
    """
    pass