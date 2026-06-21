#!/usr/bin/env python3
"""
Test script pour vérifier la cohérence géométrique entre DIFMAP et le wrapper matplotlib.
"""

import numpy as np
import matplotlib.pyplot as plt
from difmap_wrapper.map_geometry import DifmapMapGeometry
from difmap_wrapper.gui.map_widget import CleanMapPlotWidget

def create_test_map(nx=512, ny=512, cellsize=1.0):
    """Crée une carte de test avec une source gaussienne au centre."""
    cy = cellsize  # cellsize_y = cellsize par défaut
    
    # Grille de coordonnées en mas
    x = np.linspace(-nx*cellsize/2, nx*cellsize/2, nx)
    y = np.linspace(-ny*cy/2, ny*cy/2, ny)
    X, Y = np.meshgrid(x, y)
    
    # Source gaussienne centrée
    sigma = 5.0  # mas
    data = 1.0 * np.exp(-(X**2 + Y**2) / (2*sigma**2))
    
    # Ajouter un peu de bruit
    noise = np.random.normal(0, 0.01, data.shape)
    data += noise
    
    return data

def test_geometry_consistency():
    """Test la cohérence de la géométrie DIFMAP."""
    print("Test de cohérence géométrique DIFMAP...")
    
    # Paramètres de test
    nx, ny = 512, 512
    cellsize = 1.0  # mas
    
    # Créer une carte de test
    map_data = create_test_map(nx, ny, cellsize)
    
    # Tester le crop par défaut
    cropped_data, extent, nx_crop, ny_crop = DifmapMapGeometry.crop_map_data(
        map_data, cellsize
    )
    
    print(f"Dimensions originales : {ny} × {nx}")
    print(f"Dimensions après crop DIFMAP : {ny_crop} × {nx_crop}")
    print(f"Extent : [{extent[0]:.1f}, {extent[1]:.1f}, {extent[2]:.1f}, {extent[3]:.1f}] mas")
    
    # Vérifier que l'extent est correct (RA inversé)
    expected_x_range = nx_crop * cellsize / 2
    expected_y_range = ny_crop * cellsize / 2
    
    print(f"Range X attendu : ±{expected_x_range:.1f} mas")
    print(f"Range Y attendu : ±{expected_y_range:.1f} mas")
    
    # Vérifier les valeurs
    assert abs(extent[0] - expected_x_range) < 0.1, f"Erreur extent[0]: {extent[0]} vs {expected_x_range}"
    assert abs(extent[1] + expected_x_range) < 0.1, f"Erreur extent[1]: {extent[1]} vs {-expected_x_range}"
    assert abs(extent[2] + expected_y_range) < 0.1, f"Erreur extent[2]: {extent[2]} vs {-expected_y_range}"
    assert abs(extent[3] - expected_y_range) < 0.1, f"Erreur extent[3]: {extent[3]} vs {expected_y_range}"
    
    print("✓ Cohérence géométrique vérifiée")
    return map_data, extent

def test_widget_display():
    """Test l'affichage avec le widget CleanMap."""
    print("\nTest d'affichage avec CleanMapPlotWidget...")
    
    # Créer les données de test
    map_data, extent = test_geometry_consistency()
    
    # Créer le widget
    widget = CleanMapPlotWidget()
    
    # Préparer les infos de beam
    beam_info = {
        'bmaj': 5.0,
        'bmin': 3.0,
        'bpa': 45.0
    }
    
    # Afficher la carte
    widget.plot_map(
        map_data=map_data,
        cellsize=1.0,
        cellsize_y=1.0,
        beam_info=beam_info,
        contour_mode='pct',
        extent=extent
    )
    
    print("✓ Widget CleanMap affiché avec succès")
    return widget

def test_contour_levels():
    """Test le calcul des niveaux de contours."""
    print("\nTest des niveaux de contours...")
    
    from difmap_wrapper.map_geometry import get_difmap_contour_levels
    
    peak = 1.0  # Jy/beam
    
    # Test mode pct (défaut DIFMAP)
    levels_pct = get_difmap_contour_levels(peak, 'pct')
    print(f"Niveaux PCT ({len(levels_pct)}): {levels_pct}")
    
    # Test mode log
    levels_log = get_difmap_contour_levels(peak, 'log', 1.0, 100.0, 2.0)
    print(f"Niveaux LOG ({len(levels_log)}): {levels_log}")
    
    # Vérifier les niveaux par défaut
    expected_pct = [-0.01, 0.01, 0.02, 0.04, 0.08, 0.16, 0.32, 0.64]
    np.testing.assert_array_almost_equal(levels_pct, expected_pct, decimal=3)
    
    print("✓ Niveaux de contours corrects")

if __name__ == "__main__":
    print("=" * 60)
    print("TEST DE GÉOMÉTRIE DIFMAP-MATPLOTLIB")
    print("=" * 60)
    
    try:
        # Test des contours
        test_contour_levels()
        
        # Test de géométrie
        test_geometry_consistency()
        
        # Test d'affichage
        widget = test_widget_display()
        
        print("\n" + "=" * 60)
        print("TOUS LES TESTS RÉUSSIS ✓")
        print("=" * 60)
        
        # Afficher la figure
        if hasattr(widget, 'fig'):
            plt.show()
            
    except Exception as e:
        print(f"\nERREUR: {e}")
        import traceback
        traceback.print_exc()
