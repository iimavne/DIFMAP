# tests/test_imaging.py
import pytest
from difmap_wrapper.imaging import DifmapImager
from difmap_wrapper.session import DifmapSession

import os

# Fixture locale temporaire si conftest ne répond pas
@pytest.fixture
def paths():
    base = os.path.dirname(os.path.abspath(__file__))
    return {
        "uv": os.path.join(base, "test_data/0003-066_X.SPLIT.1"),
        "fits": os.path.join(base, "test_data/verite_terrain_test.fits")
    }
    
def test_make_dirty_map_returns_correct_structure(paths):
    """Vérifie que l'Imager génère bien le dictionnaire avec data, header, beam et extent."""
    
    # Pré-requis : on utilise une session temporaire pour charger la donnée en C
    session = DifmapSession()
    session.load_observation(paths["uv"])
    
    # Paramètres de notre test
    test_size = 256
    test_cellsize = 1.0
    
    # Test réel de l'Imager
    result = DifmapImager.make_dirty_map(size=test_size, cellsize=test_cellsize)
    
    # 1. Vérifications de la structure (Présence des clés)
    assert "data" in result, "L'image n'a pas été retournée."
    assert "header" in result, "Les métadonnées (header) sont absentes."
    assert "beam" in result, "Le beam est absent."
    assert "extent" in result, "Le cadre d'affichage (extent) est absent." # <--- NOUVEAU
    
    # 2. Vérification des dimensions Numpy
    assert result["data"].shape == (test_size, test_size), "La taille de l'image est incorrecte."
    assert result["header"]["CDELT"] == pytest.approx(test_cellsize, rel=1e-6), "La taille de pixel est incorrecte."
    
    # 3. VÉRIFICATION MATHÉMATIQUE DU WCS (Le demi-pixel) # 
    # Si nx=256 et cellsize=1.0 :
    # demi_pixel = 0.5
    # gauche = (256/2)*1.0 + 0.5 = 128.5
    # droite = -(256/2)*1.0 + 0.5 = -127.5
    # bas = -(256/2)*1.0 - 0.5 = -128.5
    # haut = (256/2)*1.0 - 0.5 = 127.5
    
    expected_extent = [128.5, -127.5, -128.5, 127.5]
    
    # On compare chaque valeur de l'extent calculé avec notre résultat mathématique attendu
    assert result["extent"][0] == pytest.approx(expected_extent[0]), "Le bord Gauche (RA) est faux."
    assert result["extent"][1] == pytest.approx(expected_extent[1]), "Le bord Droit (RA) est faux."
    assert result["extent"][2] == pytest.approx(expected_extent[2]), "Le bord Bas (Dec) est faux."
    assert result["extent"][3] == pytest.approx(expected_extent[3]), "Le bord Haut (Dec) est faux."