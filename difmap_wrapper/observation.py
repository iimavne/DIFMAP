import difmap_native
from .exceptions import DifmapStateError, DifmapError
import matplotlib.pyplot as plt
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
    
    def uvplot(self) -> None:
        """
        Affiche un graphique de la couverture du plan UV (U vs V).

        Les coordonnées sont automatiquement converties en Méga-longueurs 
        d'onde (Mλ). Affiche un message d'avertissement si les données 
        n'ont pas été préalablement sélectionnées.

        Examples
        --------
        >>> session.obs.select(pol="I")
        >>> session.obs.uvplot()
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
        Affiche l'amplitude des visibilités en fonction du rayon UV.

        Le rayon UV représente la distance de la ligne de base au centre du plan, 
        exprimée en Méga-longueurs d'onde (Mλ).

        Parameters
        ----------
        color : str, optional
            Couleur des points du graphique Matplotlib. Par défaut 'black'.
        alpha : float, optional
            Transparence des points (0.0 à 1.0). Par défaut 0.5.
        s : int or float, optional
            Taille des points (scatter size). Par défaut 1.

        Examples
        --------
        >>> session.obs.radplot(color='blue', s=0.5)
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