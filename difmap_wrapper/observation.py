import difmap_native
from .exceptions import DifmapStateError, DifmapError

class Observation:
    """Gère le filtrage et l'état des données UV chargées."""
    
    def __init__(self, session):
        self._session = session
        self._native = difmap_native

    def nsub(self) -> int:
        """Retourne le nombre de sous-réseaux (Subarrays)."""
        if not self._session.uv_loaded:
            raise DifmapStateError("Aucune observation chargée.")
        res = self._native.nsub()
        if res < 0: 
            raise DifmapError("Erreur lors de la lecture des sous-réseaux.")
        return res

    def select(self, pol: str = "I", ifs: tuple = (1, 0), channels: tuple = (1, 0)):
        """Sélectionne le flux de données (Polarisation, IFs, Canaux)."""
        if not self._session.uv_loaded:
            raise DifmapStateError("Aucune observation chargée.")
            
        pol = pol.upper()
        # Appel de la version non-bridée (5 arguments)
        if self._native.select(pol, ifs[0], ifs[1], channels[0], channels[1]) != 0:
            raise DifmapError(f"Échec de la sélection (Pol: {pol})")
    
    def uvplot(self) -> None:
        """
        Affiche la couverture du plan UV automatique.
        Les coordonnées extraites sont déjà en longueurs d'onde.
        """
        import matplotlib.pyplot as plt
        import numpy as np
        
        # 1. Extraction (les data['u'] et data['v'] sont déjà en lambda !)
        data = self._native.get_uv_data()
        if not data:
            return

        u, v = data['u'], data['v']
        
        # 2. Affichage
        plt.figure(figsize=(8, 8))
        # On trace u,v et -u,-v pour la symétrie
        plt.scatter(u, v, s=1, color='blue', alpha=0.5)
        plt.scatter(-u, -v, s=1, color='blue', alpha=0.5)
        
        plt.xlabel(r"$U$ ($\lambda$)")
        plt.ylabel(r"$V$ ($\lambda$)")
        plt.title(f"Couverture UV : {self.source}")
        plt.axis('equal')
        plt.grid(True, linestyle=':', alpha=0.6)
        plt.show()