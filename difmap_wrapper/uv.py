# difmap_wrapper/uv.py
import matplotlib.pyplot as plt
import numpy as np

class DifmapUV:
    """
    Boîte à outils statique pour l'analyse et la visualisation 
    des données du plan UV (visibilités).
    """

    @staticmethod
    def plot_coverage(uv_data: dict, title: str = "Couverture UV", figsize: tuple = (7, 7), **kwargs):
        """
        Génère la carte de couverture UV (équivalent de 'uvplot' basique).
        
        En radioastronomie, l'espace de Fourier est Hermitien. Chaque ligne de base 
        mesurée (u, v) implique mathématiquement la connaissance du point (-u, -v).
        Cette fonction trace automatiquement ces deux points symétriques.
        """
        plt.figure(figsize=figsize)
        
        # Extraction
        u = uv_data['u']
        v = uv_data['v']
        
        # Configuration par défaut des points (kwargs permet à l'utilisateur de les surcharger)
        plot_params = {'s': 0.5, 'color': 'blue', 'alpha': 0.7}
        plot_params.update(kwargs)
        
        # Tracé des points mesurés (u, v) et de leurs conjugués (-u, -v)
        plt.scatter(u, v, **plot_params)
        plt.scatter(-u, -v, **plot_params)
        
        # Esthétique scientifique
        plt.title(title)
        plt.xlabel(r"$u$ (longueurs d'onde)")
        plt.ylabel(r"$v$ (longueurs d'onde)")
        
        # L'espace UV doit toujours avoir un ratio 1:1 pour ne pas déformer la géométrie
        plt.gca().set_aspect('equal', adjustable='box')
        plt.grid(True, linestyle=':', alpha=0.6)
        
        # Inversion de l'axe X (convention en astronomie : l'Est est à gauche)
        plt.gca().invert_xaxis()
        
        plt.tight_layout()
        plt.show()

    @staticmethod
    def plot_radplot(uv_data: dict, title: str = "Amplitude vs Rayon UV", figsize: tuple = (9, 5), **kwargs):
        """
        Génère le graphique de l'amplitude en fonction de la distance UV.
        C'est l'équivalent moderne de la commande 'radplot' de Difmap.
        """
        plt.figure(figsize=figsize)
        
        # Calcul du rayon UV mathématique : r = sqrt(u^2 + v^2)
        uv_radius = np.sqrt(uv_data['u']**2 + uv_data['v']**2)
        amp = uv_data['amp']
        
        # Configuration des points
        plot_params = {'s': 1.0, 'color': 'black', 'alpha': 0.5}
        plot_params.update(kwargs)
        
        plt.scatter(uv_radius, amp, **plot_params)
        
        # Esthétique
        plt.title(title)
        plt.xlabel("Rayon UV (longueurs d'onde)")
        plt.ylabel("Amplitude (Jy)")
        plt.grid(True, linestyle=':', alpha=0.6)
        
        plt.tight_layout()
        plt.show()