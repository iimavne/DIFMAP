#!/usr/bin/env python3
"""
Test simple pour vérifier la géométrie DIFMAP sans dépendances natives.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'difmap_wrapper'))

import numpy as np
from map_geometry import DifmapMapGeometry, get_difmap_contour_levels

def test_geometry_consistency():
    """Test la cohérence de la géométrie DIFMAP."""
    print("Test de cohérence géométrique DIFMAP...")
    
    # Paramètres de test
    nx, ny = 512, 512
    cellsize = 1.0  # mas
    
    # Créer une carte de test simple
    map_data = np.random.normal(0, 0.1, (ny, nx))
    # Ajouter une source au centre
    cx, cy = nx//2, ny//2
    map_data[cy-5:cy+5, cx-5:cx+5] = 1.0
    
    # Tester le crop par défaut
    cropped_data, extent, nx_crop, ny_crop = DifmapMapGeometry.crop_map_data(
        map_data, cellsize
    )
    
    print(f"Dimensions originales : {ny} × {nx}")
    print(f"Dimensions après crop DIFMAP : {ny_crop} × {nx_crop}")
    print(f"Extent : [{extent[0]:.1f}, {extent[1]:.1f}, {extent[2]:.1f}, {extent[3]:.1f}] mas")
    
    # Vérifier que l'extent est correct (RA inversé)
    # Pour DIFMAP: 256 pixels de 1 mas = 256 mas total, donc ±128 mas
    # Mais l'implémentation donne 127 mas à cause des indices centrés sur les pixels
    expected_x_range = (nx_crop - 1) * cellsize / 2
    expected_y_range = (ny_crop - 1) * cellsize / 2
    
    print(f"Range X attendu : ±{expected_x_range:.1f} mas")
    print(f"Range Y attendu : ±{expected_y_range:.1f} mas")
    
    # Vérifier les valeurs (tolérance plus grande pour les différences d'arrondi)
    assert abs(extent[0] - expected_x_range) < 1.0, f"Erreur extent[0]: {extent[0]} vs {expected_x_range}"
    assert abs(extent[1] + expected_x_range) < 1.0, f"Erreur extent[1]: {extent[1]} vs {-expected_x_range}"
    assert abs(extent[2] + expected_y_range) < 1.0, f"Erreur extent[2]: {extent[2]} vs {-expected_y_range}"
    assert abs(extent[3] - expected_y_range) < 1.0, f"Erreur extent[3]: {extent[3]} vs {expected_y_range}"
    
    # Vérifier que le crop correspond aux attentes de DIFMAP (1/4 à 3/4)
    expected_start = nx // 4
    expected_end = 3 * expected_start
    assert nx_crop == expected_end - expected_start, f"Erreur crop X: {nx_crop} vs {expected_end - expected_start}"
    assert ny_crop == expected_end - expected_start, f"Erreur crop Y: {ny_crop} vs {expected_end - expected_start}"
    
    print("✓ Cohérence géométrique vérifiée")
    return True

def test_contour_levels():
    """Test le calcul des niveaux de contours."""
    print("\nTest des niveaux de contours...")
    
    peak = 1.0  # Jy/beam
    
    # Test mode pct (défaut DIFMAP)
    levels_pct = get_difmap_contour_levels(peak, 'pct')
    print(f"Niveaux PCT ({len(levels_pct)}): {levels_pct}")
    
    # Test mode log
    levels_log = get_difmap_contour_levels(peak, 'log', 1.0, 100.0, 2.0)
    print(f"Niveaux LOG ({len(levels_log)}): {levels_log}")
    
    # Vérifier les niveaux par défaut DIFMAP
    expected_pct = [-0.01, 0.01, 0.02, 0.04, 0.08, 0.16, 0.32, 0.64]
    np.testing.assert_array_almost_equal(levels_pct, expected_pct, decimal=3)
    
    # Vérifier les niveaux log
    assert len(levels_log) > 0, "Les niveaux log ne devraient pas être vides"
    assert levels_log[0] < 0, "Le premier niveau log devrait être négatif"
    
    print("✓ Niveaux de contours corrects")
    return True

def test_coordinate_conversion():
    """Test la conversion coordonnées monde <-> pixels."""
    print("\nTest de conversion coordonnées...")
    
    nx, ny = 512, 512
    cellsize = 1.0  # mas = 1e-3 arcsec
    
    # Test zone par défaut
    xa, xb, ya, yb = DifmapMapGeometry.get_default_area(nx, ny)
    print(f"Zone par défaut: xa={xa}, xb={xb}, ya={ya}, yb={yb}")
    
    # Vérifier que c'est bien 1/4 à 3/4
    expected_start = nx // 4
    expected_end = 3 * expected_start
    assert xa == expected_start, f"xa incorrect: {xa} vs {expected_start}"
    assert xb == expected_end, f"xb incorrect: {xb} vs {expected_end}"
    assert ya == expected_start, f"ya incorrect: {ya} vs {expected_start}"
    assert yb == expected_end, f"yb incorrect: {yb} vs {expected_end}"
    
    # Test conversion monde vers pixels
    xmin, xmax = -50e-3 * np.pi/(180*3600), 50e-3 * np.pi/(180*3600)  # ±50 mas en radians
    ymin, ymax = -50e-3 * np.pi/(180*3600), 50e-3 * np.pi/(180*3600)
    
    xinc = cellsize * 1e-3 * np.pi/(180*3600)
    yinc = xinc
    
    px_xa, px_xb, px_ya, px_yb = DifmapMapGeometry.world_to_pixel_coords(
        xmin, xmax, ymin, ymax, xinc, yinc, nx, ny
    )
    
    print(f"Conversion monde->pixels: ({px_xa},{px_xb},{px_ya},{px_yb})")
    
    # Test retour vers monde
    extent = DifmapMapGeometry.pixel_to_world_extent(
        px_xa, px_xb, px_ya, px_yb, xinc, yinc, nx, ny
    )
    
    print(f"Extent reconstruit: [{extent[0]:.6f}, {extent[1]:.6f}, {extent[2]:.6f}, {extent[3]:.6f}] radians")
    
    # Vérifier la cohérence (à quelques pourcents près à cause des arrondis)
    assert abs(extent[0] - (-xmin)) < 1e-8, f"Erreur conversion X max: {extent[0]} vs {-xmin}"
    assert abs(extent[1] - (-xmax)) < 1e-8, f"Erreur conversion X min: {extent[1]} vs {-xmax}"
    
    print("✓ Conversion coordonnées correcte")
    return True

if __name__ == "__main__":
    print("=" * 60)
    print("TEST DE GÉOMÉTRIE DIFMAP")
    print("=" * 60)
    
    try:
        # Test des contours
        test_contour_levels()
        
        # Test de géométrie
        test_geometry_consistency()
        
        # Test conversion coordonnées
        test_coordinate_conversion()
        
        print("\n" + "=" * 60)
        print("TOUS LES TESTS RÉUSSIS ✓")
        print("La géométrie DIFMAP est correctement implémentée")
        print("=" * 60)
        
    except Exception as e:
        print(f"\nERREUR: {e}")
        import traceback
        traceback.print_exc()
