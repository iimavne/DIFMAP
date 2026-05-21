"""
Module de géométrie des cartes Difmap.

Ce module implémente la traduction exacte de l'algorithme PGPLOT de Difmap
pour garantir une cohérence parfaite entre tous les affichages GUI.
"""

import numpy as np
from typing import Tuple, List, Optional


class DifmapMapGeometry:
    """
    Gestionnaire de géométrie des cartes Difmap.
    
    Implémente la traduction de setarea() dans difmap_src/maplot.c
    pour garantir des coordonnées identiques à PGPLOT.
    """
    
    @staticmethod
    def get_default_area(nx: int, ny: int) -> Tuple[int, int, int, int]:
        """
        Retourne la zone d'affichage par défaut de Difmap/PGPLOT.
        
        Correspond aux limites dans maplot.c:setarea() lignes 404-407:
        - ixmin = mb->nx/4
        - iymin = mb->ny/4  
        - ixmax = 3*ixmin - 1
        - iymax = 3*iymin - 1
        
        Parameters
        ----------
        nx, ny : int
            Dimensions complètes du buffer FFT
            
        Returns
        -------
        tuple
            (x_start, x_end, y_start, y_end) pour slicing Python
        """
        x_start = nx // 4
        y_start = ny // 4
        x_end = 3 * x_start - 1  # -1 car indices PGPLOT sont inclusifs
        y_end = 3 * y_start - 1
        
        # Conversion pour slicing Python (borne exclusive)
        return x_start, x_end + 1, y_start, y_end + 1
    
    @staticmethod
    def world_to_pixel_coords(xmin: float, xmax: float, ymin: float, ymax: float,
                             xinc: float, yinc: float, nx: int, ny: int) -> Tuple[int, int, int, int]:
        """
        Convertit coordonnées mondiales en pixels selon setarea().
        
        Implémente les lignes 421-433 de maplot.c:setarea():
        - Conversion en pixels par rapport au centre
        - Ajout des offsets pour inclure les pixels dont les centres sont dans la fenêtre
        
        Parameters
        ----------
        xmin, xmax, ymin, ymax : float
            Limites mondiales en radians
        xinc, yinc : float
            Taille des pixels en radians
        nx, ny : int
            Dimensions du buffer
            
        Returns
        -------
        tuple
            (xa, xb, ya, yb) indices de pixels pour slicing Python
        """
        xcent = nx // 2
        ycent = ny // 2
        
        # Conversion en coordonnées pixel par rapport au centre (lignes 421-424)
        wxa = xmin / xinc
        wxb = xmax / xinc
        wya = ymin / yinc
        wyb = ymax / yinc
        
        # Conversion en indices de pixels (lignes 430-433)
        xa = xcent + int(wxa + (0.0 if wxa < 0 else 1.0))
        xb = xcent + int(wxb - (1.0 if wxb < 0 else 0.0))
        ya = ycent + int(wya + (0.0 if wya < 0 else 1.0))
        yb = ycent + int(wyb - (1.0 if wyb < 0 else 0.0))
        
        # Application des limites par défaut (lignes 437-444)
        ixmin, ixmax, iymin, iymax = DifmapMapGeometry.get_default_area(nx, ny)
        
        xa = max(xa, ixmin)
        ya = max(ya, iymin)
        xb = min(xb, ixmax)
        yb = min(yb, iymax)
        
        # Conversion pour slicing Python
        return xa, xb + 1, ya, yb + 1
    
    @staticmethod
    def pixel_to_world_extent(xa: int, xb: int, ya: int, yb: int,
                             xinc: float, yinc: float, nx: int, ny: int) -> List[float]:
        """
        Convertit indices de pixels en limites mondiales pour Matplotlib.
        
        Implémente les lignes 476-491 de maplot.c:setarea()
        avec adaptation pour les conventions Matplotlib.
        
        Parameters
        ----------
        xa, xb, ya, yb : int
            Indices de pixels (xb, yb sont exclusifs pour slicing Python)
        xinc, yinc : float
            Taille des pixels en radians  
        nx, ny : int
            Dimensions du buffer
            
        Returns
        -------
        list
            [x_max, x_min, y_min, y_max] pour imshow()
        """
        xcent = nx // 2
        ycent = ny // 2

        # Calcul des coordonnées mondiales : on travaille sur les BORDS de pixels.
        # Avec slicing Python, xb/yb sont EXCLUSIFS : ils correspondent naturellement
        # au bord supérieur de la dernière colonne/ligne incluse.
        if xinc > 0:
            wxa = (xa - xcent) * xinc
            wxb = (xb - xcent) * xinc
        else:
            wxa = (xb - xcent) * xinc
            wxb = (xa - xcent) * xinc
            
        if yinc > 0:
            wya = (ya - ycent) * yinc
            wyb = (yb - ycent) * yinc
        else:
            wya = (yb - ycent) * yinc
            wyb = (ya - ycent) * yinc
        
        # Conversion pour Matplotlib : [xmax, xmin, ymin, ymax]
        return [wxb, wxa, wya, wyb]
    
    @staticmethod
    def get_pgplot_transformation_matrix(xinc: float, yinc: float, nx: int, ny: int) -> List[float]:
        """
        Retourne la matrice de transformation PGPLOT.
        
        Implémente les lignes 495-500 de maplot.c:setarea().
        Utile pour comparaison avec d'autres outils.
        
        Parameters
        ----------
        xinc, yinc : float
            Taille des pixels en radians
        nx, ny : int
            Dimensions du buffer
            
        Returns
        -------
        list
            Matrice de transformation [tr0, tr1, tr2, tr3, tr4, tr5]
        """
        xcent = nx // 2
        ycent = ny // 2
        
        tr = [
            -xinc * (xcent + 1),  # tr[0]
            xinc,                 # tr[1]
            0.0,                  # tr[2]
            -yinc * (ycent + 1),  # tr[3]
            0.0,                  # tr[4]
            yinc                  # tr[5]
        ]
        
        return tr
    
    @staticmethod
    def crop_map_data(map_data: np.ndarray, cellsize: float, 
                     cellsize_y: Optional[float] = None,
                     xmin: Optional[float] = None, xmax: Optional[float] = None,
                     ymin: Optional[float] = None, ymax: Optional[float] = None) -> Tuple[np.ndarray, List[float], int, int]:
        """
        Applique le crop Difmap et retourne données + extent + dimensions.
        
        Fonction principale unifiée pour tous les affichages GUI.
        
        Parameters
        ----------
        map_data : np.ndarray
            Buffer de carte complet (ny, nx)
        cellsize : float
            Taille pixel en mas (axe X)
        cellsize_y : float, optional
            Taille pixel en mas (axe Y). Défaut: cellsize
        xmin, xmax, ymin, ymax : float, optional
            Limites personnalisées en mas. Si None, utilise zone par défaut
            
        Returns
        -------
        tuple
            (data_crop, extent, nx_crop, ny_crop)
        """
        # cellsize est en mas (unités de carte par défaut de Difmap).
        # Facteur de conversion mas → radians : rad = mas * MAS_TO_RAD
        _MAS_TO_RAD = np.pi / (180.0 * 3600.0 * 1000.0)
        _RAD_TO_MAS = 1.0 / _MAS_TO_RAD

        ny, nx = map_data.shape
        cy = cellsize_y if cellsize_y is not None else cellsize

        xinc = cellsize * _MAS_TO_RAD
        yinc = cy * _MAS_TO_RAD

        if xmin is None or xmax is None or ymin is None or ymax is None:
            # Crop par défaut de Difmap: quart central (nx/4 à 3*nx/4)
            # Voir maplot.c:setarea()
            xa, xb, ya, yb = DifmapMapGeometry.get_default_area(nx, ny)
        else:
            xa, xb, ya, yb = DifmapMapGeometry.world_to_pixel_coords(
                xmin * _MAS_TO_RAD,
                xmax * _MAS_TO_RAD,
                ymin * _MAS_TO_RAD,
                ymax * _MAS_TO_RAD,
                xinc, yinc, nx, ny
            )

        # Application du crop
        cropped_data = map_data[ya:yb, xa:xb]

        # Calcul de l'extent pour Matplotlib (en mas)
        extent = DifmapMapGeometry.pixel_to_world_extent(
            xa, xb, ya, yb, xinc, yinc, nx, ny
        )
        extent = [val * _RAD_TO_MAS for val in extent]
        
        return cropped_data, extent, cropped_data.shape[1], cropped_data.shape[0]


def get_difmap_contour_levels(
    peak: float,
    mode: str = 'pct',
    min_pct: float = 1.0,
    max_pct: float = 64.0,
    factor: float = 2.0,
) -> List[float]:
    """
    Calcule les niveaux de contours selon les conventions Difmap.

    Parameters
    ----------
    peak : float
        Valeur de pic de la carte (Jy/beam).
    mode : str
        ``'pct'`` – niveaux par défaut Difmap ([-1,1,2,4,8,16,32,64] % du pic).
        ``'log'`` – niveaux logarithmiques de min_pct à max_pct avec facteur multiplicatif.
    min_pct, max_pct : float
        Bornes en pourcentage du pic (mode ``'log'`` uniquement).
    factor : float
        Facteur multiplicatif entre niveaux consécutifs (mode ``'log'`` uniquement).

    Returns
    -------
    list of float
        Niveaux de contours en unités absolues (même unité que peak).
    """
    if mode == 'pct':
        pcts = [-1.0, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0]
        return [p / 100.0 * peak for p in pcts]

    # mode == 'log'
    positive: List[float] = []
    level = min_pct
    while level <= max_pct + 1e-9:
        positive.append(level / 100.0 * peak)
        level *= factor
    return ([-positive[0]] + positive) if positive else []

