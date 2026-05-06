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
        
        # Ajustement pour indices Python (xb, yb sont exclusifs)
        xb_adj = xb - 1
        yb_adj = yb - 1
        
        # Calcul des coordonnées mondiales (lignes 476-491)
        if xinc > 0:
            wxa = (xa - xcent) * xinc
            wxb = (xb_adj - xcent) * xinc
        else:
            wxa = (xb_adj - xcent) * xinc
            wxb = (xa - xcent) * xinc
            
        if yinc > 0:
            wya = (ya - ycent) * yinc
            wyb = (yb_adj - ycent) * yinc
        else:
            wya = (yb_adj - ycent) * yinc
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
        ny, nx = map_data.shape
        cy = cellsize_y if cellsize_y is not None else cellsize
        
        # Conversion en radians
        xinc = cellsize * 1e-3 * np.pi / (180.0 * 3600.0)
        yinc = cy * 1e-3 * np.pi / (180.0 * 3600.0)
        
        if xmin is None or xmax is None or ymin is None or ymax is None:
            # Zone par défaut
            xa, xb, ya, yb = DifmapMapGeometry.get_default_area(nx, ny)
        else:
            # Zone personnalisée
            xa, xb, ya, yb = DifmapMapGeometry.world_to_pixel_coords(
                xmin * 1e-3 * np.pi / (180.0 * 3600.0),
                xmax * 1e-3 * np.pi / (180.0 * 3600.0),
                ymin * 1e-3 * np.pi / (180.0 * 3600.0),
                ymax * 1e-3 * np.pi / (180.0 * 3600.0),
                xinc, yinc, nx, ny
            )
        
        # Application du crop
        cropped_data = map_data[ya:yb, xa:xb]
        
        # Calcul de l'extent pour Matplotlib
        extent = DifmapMapGeometry.pixel_to_world_extent(
            xa, xb, ya, yb, xinc, yinc, nx, ny
        )
        
        # Conversion en mas
        extent = [val * 180.0 * 3600.0 * 1000.0 / np.pi for val in extent]
        
        return cropped_data, extent, cropped_data.shape[1], cropped_data.shape[0]


