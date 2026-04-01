import difmap_native
from .exceptions import DifmapStateError, DifmapError
import matplotlib.pyplot as plt
import numpy as np
        

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
            """
            Affiche et retourne le nombre de sous-réseaux (Subarrays).
            Imite le comportement informatif de l'ancien Difmap.
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

    def radplot(self, color='black', alpha=0.5, s=1) -> None:
        """
        Affiche l'amplitude des visibilités en fonction du rayon UV (Radplot).
        L'axe X représente la distance de la ligne de base en Méga-longueurs d'onde.
        """        
        data = self._native.get_uv_data()
        if not data or len(data.get('u', [])) == 0:
            print("Aucune donnée UV. Appelez select() avant radplot().")
            return

        # Récupération des données brutes
        u = data['u']
        v = data['v']
        amp = data['amp']
        
        # Calcul du rayon UV (distance au centre) converti en Méga-lambda
        uv_radius = np.sqrt(u**2 + v**2) / 1e6
        
        # Création du graphique
        plt.figure(figsize=(10, 6))
        plt.scatter(uv_radius, amp, s=s, color=color, alpha=alpha)
        
        # Formatage scientifique
        plt.xlabel(r"Rayon UV ($M\lambda$)")
        plt.ylabel("Amplitude (Jy)")
        plt.title(f"Radplot (Amplitude vs Rayon UV) : {self.source}")
        
        # Limite basse à 0 pour l'amplitude (une amplitude ne peut pas être négative)
        plt.ylim(bottom=0)
        plt.grid(True, linestyle=':', alpha=0.6)
        plt.show()