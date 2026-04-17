import difmap_native
from .exceptions import DifmapStateError, DifmapError
import numpy as np
        

class Observation:
    """
    Gère le filtrage, l'exploration et l'état des données UV chargées en mémoire.

    Cette classe n'est pas censée être instanciée manuellement. Elle est 
    accessible via l'attribut `obs` d'une instance de `DifmapSession`.

    Examples
    --------
    >>> with DifmapSession() as session:
    >>>     session.observe("data/0003-066.fits")
    >>>     print(session.obs.source)
    """
    
    def __init__(self, session):
        self._session = session
        self._native = difmap_native

    @property
    def source(self) -> str:
        """
        Récupère le nom de la source astronomique depuis la mémoire C.

        Returns
        -------
        str
            Le nom de la source (ex: "0003-066"). Retourne "Inconnue" si 
            aucune observation n'est chargée.
        """
        if not self._session.uv_loaded:
            return "Inconnue"
        return self._native.get_source()

    def nsub(self) -> int:
        """
        Affiche et retourne le nombre de sous-réseaux (Subarrays).

        Cette commande imite le comportement informatif de l'ancien Difmap 
        en affichant le résultat dans le terminal, tout en retournant l'entier 
        pour une utilisation algorithmique en Python.

        Returns
        -------
        int
            Le nombre de sous-réseaux détectés dans les données.

        Raises
        ------
        DifmapStateError
            Si aucune observation n'est chargée.
        DifmapError
            Si le moteur C rencontre une erreur lors de la lecture.
            
        Examples
        --------
        >>> n = session.obs.nsub()
        Nombre de sous-réseaux (Subarrays) : 1
        """
        # 1. Sécurité : Vérifie qu'un fichier est bien chargé
        if not self._session.uv_loaded:
            raise DifmapStateError("Aucune observation chargée.")
                
        # 2. Appel au moteur C
        res = self._native.nsub()
        if res < 0: 
            raise DifmapError("Erreur lors de la lecture des sous-réseaux.")
                
        # 3. Le comportement "Difmap classique" (Nouveau !)
        print(f"Nombre de sous-réseaux (Subarrays) : {res}")
            
        # 4. On retourne la valeur au cas où un script Python en aurait besoin
        return res

    def select(self, pol: str = "I", ifs: tuple = (1, 0), channels: tuple = (1, 0)):
        """
        Sélectionne le flux de données actif (Polarisation, IFs, Canaux).

        Permet de filtrer les visibilités qui seront utilisées pour les 
        prochaines opérations d'imagerie ou d'affichage.

        Parameters
        ----------
        pol : str, optional
            La polarisation souhaitée ("I", "RR", "LL", etc.). Par défaut "I".
        ifs : tuple of int, optional
            Plage des IFs à sélectionner sous la forme (debut, fin). Par défaut (1, 0) pour tous.
        channels : tuple of int, optional
            Plage des canaux spectraux sous la forme (debut, fin). Par défaut (1, 0) pour tous.

        Raises
        ------
        DifmapStateError
            Si aucune observation n'est chargée.
        DifmapError
            Si la sélection échoue (ex: polarisation inexistante).

        Examples
        --------
        >>> session.obs.select(pol="RR")
        """
        if not self._session.uv_loaded:
            raise DifmapStateError("Aucune observation chargée.")
            
        pol = pol.upper()
        if self._native.select(pol, ifs[0], ifs[1], channels[0], channels[1]) != 0:
            raise DifmapError(f"Échec de la sélection (Pol: {pol})")
        
    def flag_data(self, indices):
        """
        Reçoit une liste d'index depuis l'éditeur graphique et 
        demande au moteur C de les supprimer (flag 'bad').
        """
        # On s'assure que les indices sont bien au format attendu par le C (Entiers 32-bits continus)
        indices_c = np.asarray(indices, dtype=np.int32)
        
        if len(indices_c) > 0:
            # On passe la commande au moteur Cython
            return self._native.flag_data(indices_c)
        return 0 
        
    def unflag_data(self, indices):
        indices_c = np.asarray(indices, dtype=np.int32)
        if len(indices_c) > 0:
            return self._native.unflag_data(indices_c)
        return 0
    
    def save_wobs(self, filepath):
        """Sauvegarde l'observation avec les flags actuels dans un nouveau fichier FITS."""
        if not filepath.endswith('.fits'):
            filepath += '.fits' # Sécurité pour toujours avoir la bonne extension
        
        print(f"Sauvegarde en cours via Difmap...")
        self._native.save_wobs(filepath)
        return True
    
    