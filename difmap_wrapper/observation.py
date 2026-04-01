import difmap_native
from .exceptions import DifmapStateError, DifmapError

class Observation:
    """Gère le filtrage et l'état des données UV chargées."""
    
    def __init__(self, session):
        self._session = session
        self._native = difmap_native

    @property
    def source(self) -> str:
        """Récupère le nom de la source astronomique depuis la mémoire C."""
        if not self._session.uv_loaded:
            return "Inconnue"
        return self._native.get_source()

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
        if self._native.select(pol, ifs[0], ifs[1], channels[0], channels[1]) != 0:
            raise DifmapError(f"Échec de la sélection (Pol: {pol})")
    
    def uvplot(self) -> None:
        """
        Affiche la couverture du plan UV.
        Les coordonnées extraites (RAM) sont déjà en longueurs d'onde.
        """
        import matplotlib.pyplot as plt
        import numpy as np
        
        data = self._native.get_uv_data()
        if not data or len(data.get('u', [])) == 0:
            print("Aucune donnée UV. Appelez select() avant uvplot().")
            return

        u = data['u'] / 1e6
        v = data['v'] / 1e6
        
        plt.figure(figsize=(8, 8))
        plt.scatter(u, v, s=1, color='blue', alpha=0.5)
        plt.scatter(-u, -v, s=1, color='blue', alpha=0.5)
        
        plt.xlabel(r"$U$ ($M\lambda$)")
        plt.ylabel(r"$V$ ($M\lambda$)")
        plt.title(f"Couverture UV : {self.source}")
        
        plt.gca().invert_xaxis()
        plt.axis('equal')
        plt.grid(True, linestyle=':', alpha=0.6)
        plt.show()