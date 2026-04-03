import os
import pytest
import numpy as np
import numpy.testing as npt
from unittest.mock import patch, MagicMock
from astropy.io import fits

from difmap_wrapper.session import DifmapSession
from difmap_wrapper.imaging import DifmapImager
from difmap_wrapper.exceptions import DifmapError, DifmapStateError

# --- Remplacer par le vrai chemin de tes données de test ---
TEST_UV_FILE = os.path.join(os.path.dirname(__file__), "test_data", "0003-066_X.SPLIT.1")

# =====================================================================
# 1. TESTS DE PLOMBERIE ET SÉCURITÉS (Logique Python Pure)
# =====================================================================

class TestImagerPlomberie:
    def test_initialisation(self):
        """Vérifie que les variables d'état sont bien initialisées à None."""
        imager = DifmapImager()
        assert imager._last_cellsize is None
        assert imager._current_uvtaper is None
        assert imager._current_uvweight is None

    def test_get_cropped_map_logique(self):
        """Vérifie le calcul de découpage d'une matrice (sans faire appel au C)."""
        imager = DifmapImager()
        # On simule une image 10x10 en mémoire
        imager.get_map = MagicMock(return_value=np.ones((10, 10)))
        
        # Recadrage en 4x4
        crop = imager.get_cropped_map((4, 4))
        assert crop.shape == (4, 4)

    def test_get_cropped_map_erreur_taille(self):
        """Vérifie que le recadrage échoue si on demande plus grand que l'image."""
        imager = DifmapImager()
        imager.get_map = MagicMock(return_value=np.ones((10, 10)))
        
        with pytest.raises(ValueError, match="est plus grande que l'image"):
            imager.get_cropped_map((20, 20))

    def test_mapplot_securites(self):
        """Vérifie les deux filets de sécurité de mapplot."""
        imager = DifmapImager()
        
        # 1er filet : mapsize n'a pas été appelé (_last_cellsize est None)
        with pytest.raises(DifmapStateError, match="mapsize"):
            imager.mapplot()
            
        # 2ème filet : invert n'a pas été appelé (get_map renvoie None ou vide)
        imager._last_cellsize = 1.0
        imager.get_map = MagicMock(return_value=np.array([]))
        with pytest.raises(DifmapStateError, match="invert"):
            imager.mapplot()

# =====================================================================
# 2. TESTS VISUELS MATPLOTLIB (Mocks)
# =====================================================================

class TestImagerAffichage:
    @patch("matplotlib.pyplot.show")
    @patch("matplotlib.pyplot.colorbar")
    @patch("matplotlib.pyplot.imshow")
    def test_plot_image(self, mock_imshow, mock_colorbar, mock_show):
        """Vérifie que les données sont bien envoyées à matplotlib sans afficher."""
        imager = DifmapImager()
        fake_dict = {"data": np.zeros((10, 10)), "extent": [5, -5, -5, 5]}
        
        imager.plot_image(fake_dict, title="Test", cmap="plasma")
        
        # Vérifie qu'imshow a reçu l'extent et la colormap
        mock_imshow.assert_called_once()
        _, kwargs = mock_imshow.call_args
        assert kwargs["extent"] == [5, -5, -5, 5]
        assert kwargs["cmap"] == "plasma"
        
        mock_colorbar.assert_called_once()
        mock_show.assert_called_once()

    def test_plot_image_cles_manquantes(self):
        """Vérifie l'erreur si le package image est incomplet."""
        bad_dict = {"data": np.zeros((5,5))} # Manque 'extent'
        imager = DifmapImager()
        with pytest.raises(KeyError, match="doit contenir les clés"):
            imager.plot_image(bad_dict)

# =====================================================================
# 3. TESTS DE FIDÉLITÉ PHYSIQUE (Le "Miroir" avec le vrai fichier UV)
# =====================================================================

class TestImagerPhysique:
    
    def test_make_dirty_map_extent_astrometrie(self):
        """Vérifie les mathématiques de calcul des bords du champ de vue."""
        with DifmapSession() as session:
            session.observe(TEST_UV_FILE)
            pkg = session.imager.make_dirty_map(size=256, cellsize=1.0, pol="RR")
            
            ra_max, ra_min, dec_min, dec_max = pkg["extent"]
            # Vérification de la symétrie à 1.0 près (le cellsize)
            assert abs(ra_max + ra_min) <= 1.0
            assert abs(dec_max + dec_min) <= 1.0
            assert pkg["data"].shape == (256, 256)

    def test_uvweight_feedback(self, capsys):
        """Vérifie que la fonction met bien à jour sa mémoire et affiche l'état."""
        with DifmapSession() as session:
            session.observe(TEST_UV_FILE)
            session.imager._native.select("RR", 1, 0, 1, 0)
            
            # Application
            session.imager.uvweight(2.0, -1.0, False)
            assert session.imager._current_uvweight == (2.0, -1.0, False)
            
            # Interrogation (Doit afficher l'état)
            session.imager.uvweight()
            captured = capsys.readouterr()
            assert "bin_size=2.0" in captured.out
            assert "err_power=-1.0" in captured.out

    def test_uvtaper_feedback(self, capsys):
        """Vérifie l'activation et la désactivation du taper."""
        with DifmapSession() as session:
            session.observe(TEST_UV_FILE)
            session.imager._native.select("RR", 1, 0, 1, 0)
            
            # Activation
            session.imager.uvtaper(0.5, 100.0)
            assert session.imager._current_uvtaper == (0.5, 100.0)
            
            # Désactivation
            session.imager.uvtaper(0, 0)
            assert session.imager._current_uvtaper == (0.0, 0.0)
            captured = capsys.readouterr()
            assert "Taper désactivé avec succès" in captured.out