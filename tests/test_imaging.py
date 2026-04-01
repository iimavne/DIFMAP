import pytest
import os
import numpy as np
from unittest.mock import patch
from difmap_wrapper.session import DifmapSession
from difmap_wrapper.imaging import DifmapImager
from difmap_wrapper.exceptions import DifmapError

# =====================================================================
# CONFIGURATION DES CHEMINS ET CONSTANTES
# =====================================================================
dossier_tests = os.path.dirname(os.path.abspath(__file__))
FICHIER_VALIDE = os.path.join(dossier_tests, "test_data", "0003-066_X.SPLIT.1")

# =====================================================================
# TESTS UNITAIRES : DifmapImager
# =====================================================================

def test_imager_modifiers_uv():
    """Vérifie que uvweight et uvtaper communiquent bien avec le C sans crash."""
    with DifmapSession() as session:
        session.observe(FICHIER_VALIDE)
        img = DifmapImager()
        
        # On doit d'abord faire un select (requis par Difmap avant de manipuler les poids)
        import difmap_native
        difmap_native.select("RR", 1, 0, 1, 0)
        
        try:
            img.uvweight(bin_size=2.0, err_power=0.0)
            img.uvtaper(gaussian_value=0.5, gaussian_radius_wav=100.0)
        except Exception as e:
            pytest.fail(f"Les modificateurs UV ont échoué : {e}")

def test_imager_get_map_et_cropping():
    """Vérifie l'extraction de la matrice RAM et la logique de recadrage."""
    with DifmapSession() as session:
        session.observe(FICHIER_VALIDE)
        img = DifmapImager()
        
        # FIX : Il faut sélectionner les données avant d'inverser !
        import difmap_native
        difmap_native.select("RR", 1, 0, 1, 0)
        
        img.mapsize(size=512, cellsize=1.0)
        img.invert()
        
        data_full = img.get_map()
        assert data_full.shape == (512, 512)
        
        target_size = (256, 256)
        data_crop = img.get_cropped_map(target_size)
        assert data_crop.shape == target_size
        assert data_crop[128, 128] == data_full[256, 256]

def test_imager_package_et_astrometrie():
    """Vérifie que get_map_package calcule correctement les coordonnées (extent)."""
    with DifmapSession() as session:
        session.observe(FICHIER_VALIDE)
        img = DifmapImager()
        
        # FIX : Sélection indispensable ici aussi
        import difmap_native
        difmap_native.select("RR", 1, 0, 1, 0)
        
        size = 512
        cell = 1.0
        img.mapsize(size, cell)
        img.invert()
        
        pkg = img.get_map_package(cellsize=cell)
        assert all(k in pkg for k in ["data", "beam_data", "info", "extent"])
        
        extent = pkg["extent"]
        assert extent[0] == (size / 2.0) * cell + (0.5 * cell)

def test_imager_make_dirty_map_complet():
    """Vérifie le fonctionnement de la méthode orchestratrice 'make_dirty_map'."""
    with DifmapSession() as session:
        session.observe(FICHIER_VALIDE)
        img = DifmapImager()
        
        # On teste l'appel haut niveau
        pkg = img.make_dirty_map(size=128, cellsize=0.5, pol="RR")
        
        assert pkg["data"].shape == (128, 128)
        assert pkg["info"]["cellsize"] == 0.5
        assert pkg["info"]["nx"] == 128

@patch("matplotlib.pyplot.show")
def test_imager_mapplot_et_alias(mock_show):
    """Vérifie que mapplot (alias de plot_image) fonctionne avec Matplotlib."""
    img = DifmapImager()
    
    # On simule un package d'image minimal
    fake_pkg = {
        "data": np.zeros((64, 64)),
        "extent": [10, -10, -10, 10]
    }
    
    # On appelle l'alias mapplot
    img.mapplot(fake_pkg, title="Test Unitaire", cmap='inferno')
    
    # On vérifie que Matplotlib a bien été appelé 1 fois
    assert mock_show.call_count == 1

def test_imager_erreurs_fatales():
    """Vérifie que l'Imager lève les bonnes erreurs en cas de mauvais paramètres."""
    img = DifmapImager()
    
    # 1. Erreur de dictionnaire pour plot_image
    with pytest.raises(KeyError):
        img.plot_image({"mauvais": "dictionnaire"})
        
    # 2. Erreur de taille pour le cropping
    img_bidon = np.zeros((10, 10))
    # On mocke get_map pour ce test précis sans charger de FITS
    with patch.object(DifmapImager, 'get_map', return_value=img_bidon):
        with pytest.raises(ValueError) as exc:
            img.get_cropped_map((20, 20)) # Plus grand que la source !
        assert "plus grande que l'image en RAM" in str(exc.value)