"""
Module d'annotations pour les cartes Difmap.

Implémente les annotations complètes affichées par Difmap/PGPLOT :
- Source + fréquence + date
- Type de carte + polarisation + array/stations  
- Centre RA/Dec réel
- Range ou peak
- Niveaux de contours formatés
- Beam FWHM
- Wedge couleur PGPLOT
"""

import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime


class DifmapMapAnnotations:
    """
    Gestionnaire des annotations de cartes Difmap.
    
    Reproduit les informations affichées par PGPLOT dans maplot.c
    pour une compatibilité visuelle complète.
    """
    
    def __init__(self, observation_data: Optional[Dict] = None):
        """
        Initialise les annotations avec les données d'observation.
        
        Parameters
        ----------
        observation_data : dict, optional
            Dictionnaire contenant les métadonnées de l'observation
        """
        self.obs_data = observation_data or {}
    
    def get_header_info(self, map_info: Dict) -> List[str]:
        """
        Génère les lignes d'en-tête comme Difmap.
        
        Parameters
        ----------
        map_info : dict
            Informations sur la carte (nx, ny, cellsize, etc.)
            
        Returns
        -------
        list[str]
            Lignes d'en-tête formatées
        """
        lines = []
        
        # Source + fréquence + date
        source = self.obs_data.get('source', 'Unknown')
        freq = self.obs_data.get('frequency', 0.0)  # GHz
        date = self.obs_data.get('date', datetime.now().strftime('%Y-%m-%d'))
        
        if freq > 0:
            lines.append(f"{source}  {freq:.3f} GHz  {date}")
        else:
            lines.append(f"{source}  {date}")
        
        # Type de carte + polarisation + array
        map_type = map_info.get('map_type', 'dirty')
        pol = self.obs_data.get('polarization', 'XX')
        array = self.obs_data.get('array', 'VLBA')
        stations = self.obs_data.get('stations', [])
        
        if stations:
            stations_str = ','.join(stations[:3])  # Limiter l'affichage
            if len(stations) > 3:
                stations_str += f"...({len(stations)})"
            lines.append(f"{map_type.upper()}  {pol}  {array} [{stations_str}]")
        else:
            lines.append(f"{map_type.upper()}  {pol}  {array}")
        
        # Centre RA/Dec
        ra = self.obs_data.get('ra', '00:00:00.0')
        dec = self.obs_data.get('dec', '+00:00:00.0')
        lines.append(f"Center:  RA={ra}  Dec={dec}")
        
        return lines
    
    def get_statistics_info(self, map_data: np.ndarray, map_info: Dict) -> List[str]:
        """
        Génère les informations statistiques.
        
        Parameters
        ----------
        map_data : np.ndarray
            Données de la carte
        map_info : dict
            Informations sur la carte
            
        Returns
        -------
        list[str]
            Lignes statistiques formatées
        """
        lines = []
        
        # Peak et RMS
        peak = float(np.max(np.abs(map_data)))
        rms = map_info.get('rms', 0.0)
        
        if rms > 0:
            lines.append(f"Peak: {peak:.4f} Jy/beam  RMS: {rms:.4f} Jy/beam  ({peak/rms:.1f}σ)")
        else:
            lines.append(f"Peak: {peak:.4f} Jy/beam")
        
        # Range si disponible
        if 'range_min' in map_info and 'range_max' in map_info:
            lines.append(f"Range: {map_info['range_min']:.4f} to {map_info['range_max']:.4f} Jy/beam")
        
        # Dimensions et cellsize
        nx = map_info.get('nx', 0)
        ny = map_info.get('ny', 0)
        cellsize = map_info.get('cellsize', 0.0)
        cellsize_y = map_info.get('cellsize_y', cellsize)
        
        lines.append(f"Map: {nx}×{ny} pixels  Cell: {cellsize:.3f}×{cellsize_y:.3f} mas")
        
        return lines
    
    def get_beam_info(self, map_info: Dict) -> List[str]:
        """
        Génère les informations sur le faisceau synthétique.
        
        Parameters
        ----------
        map_info : dict
            Informations sur la carte
            
        Returns
        -------
        list[str]
            Lignes sur le faisceau formatées
        """
        lines = []
        
        bmaj = map_info.get('bmaj', 0.0)
        bmin = map_info.get('bmin', bmaj)
        bpa = map_info.get('bpa', 0.0)
        
        if bmaj > 0:
            lines.append(f"Beam: {bmaj:.3f}×{bmin:.3f} mas at {bpa:.1f}°")
        else:
            lines.append("Beam: Not available")
        
        return lines
    
    def get_contour_info(self, contour_levels: List[float], peak: float) -> List[str]:
        """
        Génère les informations sur les contours.
        
        Parameters
        ----------
        contour_levels : list[float]
            Niveaux de contours utilisés
        peak : float
            Valeur maximale dans la carte
            
        Returns
        -------
        list[str]
            Lignes de contours formatées
        """
        lines = []
        
        if contour_levels:
            # Formater les niveaux comme Difmap
            n_levels = len(contour_levels)
            if n_levels > 8:
                levels_str = ", ".join([f"{lvl:.2f}" for lvl in contour_levels[:4]]) + "..."
                levels_str += ", ".join([f"{lvl:.2f}" for lvl in contour_levels[-4:]])
            else:
                levels_str = ", ".join([f"{lvl:.2f}" for lvl in contour_levels])
            
            lines.append(f"Contours ({n_levels} levels): {levels_str}")
            
            # Pourcentage du pic si applicable
            if peak > 0:
                pct_levels = [lvl/peak*100 for lvl in contour_levels]
                pct_str = ", ".join([f"{pct:.1f}%" for pct in pct_levels])
                lines.append(f"  [{pct_str}]")
        
        return lines
    
    def get_color_wedge_info(self, vmin: float, vmax: float, scale: str = 'linear') -> List[str]:
        """
        Génère les informations pour la wedge couleur.
        
        Parameters
        ----------
        vmin, vmax : float
            Limites de l'échelle de couleur
        scale : str
            Type d'échelle ('linear' ou 'log')
            
        Returns
        -------
        list[str]
            Informations sur la wedge
        """
        lines = []
        
        if scale == 'log':
            lines.append(f"Color scale: Log {vmin:.3e} to {vmax:.3e} Jy/beam")
        else:
            lines.append(f"Color scale: Linear {vmin:.3f} to {vmax:.3f} Jy/beam")
        
        return lines
    
    def format_full_annotation(self, map_data: np.ndarray, map_info: Dict,
                             contour_levels: Optional[List[float]] = None,
                             color_limits: Optional[Tuple[float, float]] = None,
                             color_scale: str = 'linear') -> str:
        """
        Génère l'annotation complète formatée pour la carte.
        
        Parameters
        ----------
        map_data : np.ndarray
            Données de la carte
        map_info : dict
            Informations sur la carte
        contour_levels : list[float], optional
            Niveaux de contours
        color_limits : tuple[float, float], optional
            Limites de l'échelle de couleur (vmin, vmax)
        color_scale : str
            Type d'échelle de couleur
            
        Returns
        -------
        str
            Annotation complète formatée
        """
        all_lines = []
        
        # En-tête
        all_lines.extend(self.get_header_info(map_info))
        all_lines.append("")  # Ligne vide
        
        # Statistiques
        all_lines.extend(self.get_statistics_info(map_data, map_info))
        
        # Faisceau
        all_lines.extend(self.get_beam_info(map_info))
        
        # Contours
        if contour_levels:
            all_lines.extend(self.get_contour_info(contour_levels, np.max(np.abs(map_data))))
        
        # Échelle de couleur
        if color_limits:
            all_lines.extend(self.get_color_wedge_info(color_limits[0], color_limits[1], color_scale))
        
        return "\n".join(all_lines)
    
    def get_annotation_position(self, map_extent: List[float], 
                              position: str = 'top-left') -> Tuple[float, float]:
        """
        Calcule la position optimale pour les annotations.
        
        Parameters
        ----------
        map_extent : list[float]
            Limites de la carte [xmax, xmin, ymin, ymax]
        position : str
            Position souhaitée ('top-left', 'top-right', 'bottom-left', 'bottom-right')
            
        Returns
        -------
        tuple[float, float]
            Position (x, y) en coordonnées monde
        """
        xmin, xmax = min(map_extent[0], map_extent[1]), max(map_extent[0], map_extent[1])
        ymin, ymax = min(map_extent[2], map_extent[3]), max(map_extent[2], map_extent[3])
        
        # Marges (5% de la taille)
        x_margin = (xmax - xmin) * 0.05
        y_margin = (ymax - ymin) * 0.05
        
        if position == 'top-left':
            return xmin + x_margin, ymax - y_margin
        elif position == 'top-right':
            return xmax - x_margin, ymax - y_margin
        elif position == 'bottom-left':
            return xmin + x_margin, ymin + y_margin
        elif position == 'bottom-right':
            return xmax - x_margin, ymin + y_margin
        else:
            return xmin + x_margin, ymax - y_margin  # Défaut


def create_pgplot_style_annotations(map_data: np.ndarray, map_info: Dict,
                                 observation_data: Optional[Dict] = None,
                                 contour_levels: Optional[List[float]] = None,
                                 color_limits: Optional[Tuple[float, float]] = None) -> Dict[str, Any]:
    """
    Crée un dictionnaire complet d'annotations style PGPLOT.
    
    Parameters
    ----------
    map_data : np.ndarray
        Données de la carte
    map_info : dict
        Informations sur la carte
    observation_data : dict, optional
        Données d'observation
    contour_levels : list[float], optional
        Niveaux de contours
    color_limits : tuple[float, float], optional
        Limites de l'échelle de couleur
        
    Returns
    -------
    dict
        Dictionnaire d'annotations complet
    """
    annotator = DifmapMapAnnotations(observation_data)
    
    # Annotation principale
    main_text = annotator.format_full_annotation(
        map_data, map_info, contour_levels, color_limits
    )
    
    # Position
    position = annotator.get_annotation_position(
        map_info.get('extent', [-1, 1, -1, 1]), 'top-left'
    )
    
    return {
        'main_text': main_text,
        'position': position,
        'header_lines': annotator.get_header_info(map_info),
        'stats_lines': annotator.get_statistics_info(map_data, map_info),
        'beam_lines': annotator.get_beam_info(map_info),
        'contour_lines': (annotator.get_contour_info(contour_levels, np.max(np.abs(map_data))) 
                         if contour_levels else []),
        'color_wedge_lines': (annotator.get_color_wedge_info(color_limits[0], color_limits[1]) 
                              if color_limits else [])
    }
