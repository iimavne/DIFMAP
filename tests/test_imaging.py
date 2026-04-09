import os
import pytest
import numpy as np
import numpy.testing as npt
from unittest.mock import patch, MagicMock

from difmap_wrapper.session import DifmapSession
from difmap_wrapper.exceptions import DifmapError, DifmapStateError

# --- Remplacer par le vrai chemin de tes données de test ---
TEST_UV_FILE = os.path.join(os.path.dirname(__file__), "test_data", "0003-066_X.SPLIT.1")

# =====================================================================
# 1. TESTS D'ARCHITECTURE (Session passée à DifmapImager)
# =====================================================================

class TestImagerArchitecture:
    def test_initialisation_avec_session(self):
        """Vérifie que DifmapImager reçoit et stocke la session."""
        session = DifmapSession()

        assert session.imager._session is session
        assert hasattr(session.imager, '_native')
        assert hasattr(session.imager, '_last_cellsize')
        assert hasattr(session.imager, '_current_uvtaper')
        assert hasattr(session.imager, '_current_uvweight')

    def test_make_dirty_map_appelle_session_obs_select(self, fichier_valide):
        """Vérifie que make_dirty_map() utilise session.obs.select() et non un appel direct."""
        with DifmapSession() as session:
            session.observe(fichier_valide)

            original_select = session.obs.select
            call_count = [0]

            def select_spy(*args, **kwargs):
                call_count[0] += 1
                return original_select(*args, **kwargs)

            session.obs.select = select_spy

            try:
                session.imager.make_dirty_map(size=256, cellsize=1.0, pol="I")
            except Exception:
                pass

            assert call_count[0] >= 1, "make_dirty_map() doit appeler session.obs.select()"

# =====================================================================
# 2. TESTS DE PLOMBERIE ET SÉCURITÉS (Logique Python Pure)
# =====================================================================

class TestImagerPlomberie:
    def test_initialisation(self):
        """Vérifie que les variables d'état sont bien initialisées à None."""
        session = DifmapSession()
        assert session.imager._last_cellsize is None
        assert session.imager._current_uvtaper is None
        assert session.imager._current_uvweight is None

    def test_get_cropped_map_logique(self):
        """Vérifie le calcul de découpage d'une matrice (sans faire appel au C)."""
        session = DifmapSession()
        session.imager.get_map = MagicMock(return_value=np.ones((10, 10)))

        crop = session.imager.get_cropped_map((4, 4))
        assert crop.shape == (4, 4)

    def test_get_cropped_map_erreur_taille(self):
        """Vérifie que le recadrage échoue si on demande plus grand que l'image."""
        session = DifmapSession()
        session.imager.get_map = MagicMock(return_value=np.ones((10, 10)))

        with pytest.raises(ValueError, match="est plus grande que l'image"):
            session.imager.get_cropped_map((20, 20))

# =====================================================================
# 3. TESTS UVWEIGHT ET UVTAPER (Impact physique et feedback)
# =====================================================================

class TestImagerWeightAndTaper:
    def test_uvweight_mode_interrogation(self, capsys):
        session = DifmapSession()
        session.imager.uvweight()
        captured = capsys.readouterr()
        assert "Pondération actuelle" in captured.out

    def test_uvtaper_mode_interrogation(self, capsys):
        session = DifmapSession()
        session.imager.uvtaper()
        captured = capsys.readouterr()
        assert "Taper actuel" in captured.out

    def test_uvtaper_desactivation(self, capsys):
        session = DifmapSession()
        session.imager._native.uvtaper = MagicMock(return_value=0)
        session.imager.uvtaper(0, 0)
        captured = capsys.readouterr()
        assert "Taper désactivé" in captured.out

    def test_uvtaper_logique_python(self):
        """Vérifie que le wrapper Python envoie bien la commande au moteur C et mémorise l'état."""
        session = DifmapSession()
        # On intercepte l'appel vers le C pour vérifier que le Python fait son job
        session.imager._native.uvtaper = MagicMock(return_value=0)
        
        # Application du taper
        session.imager.uvtaper(0.5, 10.0)
        
        # Vérifications strictes : le Wrapper a-t-il appelé la bonne fonction C avec les bons arguments ?
        session.imager._native.uvtaper.assert_called_once_with(0.5, 10.0)
        # Vérification que le Wrapper a bien mis à jour sa mémoire interne
        assert session.imager._current_uvtaper == (0.5, 10.0)

    def test_uvweight_impact_reel_sur_dirty_map(self, fichier_valide):
        """Vérifie que le changement de pondération modifie RÉELLEMENT l'image."""
        # Ce test physique est conservé car uvweight vide correctement le cache de Difmap !
        with DifmapSession() as session:
            session.observe(fichier_valide)
            session.obs.select(pol="RR")
            
            session.imager.mapsize(512, 0.1)

            session.imager.invert()
            map_avant = session.imager.get_map().copy()

            session.imager.uvweight(bin_size=2.0, err_power=-1.0)
            session.imager.invert()
            map_apres = session.imager.get_map().copy()

            assert not np.allclose(map_avant, map_apres), "La pondération n'a eu aucun effet !"
            
# =====================================================================
# 4. TESTS GET_MAP_PACKAGE (Corrigé le bug du 10x10 vs 256x256)
# =====================================================================

class TestImagerGetMapPackage:
    def test_get_map_package_structure(self):
        """Vérifie que get_map_package retourne un dictionnaire avec les bonnes clés."""
        session = DifmapSession()

        session.imager.get_map = MagicMock(return_value=np.ones((256, 256)))
        session.imager._native.get_beam = MagicMock(return_value=np.ones((256, 256)))
        session.imager._native.get_header = MagicMock(return_value={
            'NX': 256,
            'NY': 256,
            'BMAJ': 0.5,
            'BMIN': 0.4,
            'BPA': 45.0
        })

        pkg = session.imager.get_map_package(cellsize=1.0)

        assert 'data' in pkg
        assert 'beam_data' in pkg
        assert 'info' in pkg
        assert 'extent' in pkg
        assert len(pkg['extent']) == 4

        ra_max, ra_min, dec_min, dec_max = pkg["extent"]
        assert abs(ra_max + ra_min) <= 1.0
        assert abs(dec_max + dec_min) <= 1.0
        assert pkg["data"].shape == (256, 256)

# =====================================================================
# 5. TESTS MAPSIZE ET INVERT (Avec mocks du C)
# =====================================================================

class TestImagerMapsize:
    def test_mapsize_stocke_cellsize(self):
        session = DifmapSession()
        session.imager._native.mapsize = MagicMock(return_value=0)
        session.imager.mapsize(512, 1.5)

        assert session.imager._last_cellsize == 1.5
        session.imager._native.mapsize.assert_called_once_with(512, 1.5)

    def test_mapsize_erreur_c(self):
        session = DifmapSession()
        session.imager._native.mapsize = MagicMock(return_value=-1)
        with pytest.raises(DifmapError, match="mapsize"):
            session.imager.mapsize(512, 1.0)

class TestImagerInvert:
    def test_invert_appel_c(self):
        session = DifmapSession()
        session.imager._native.invert = MagicMock(return_value=0)
        session.imager.invert()
        session.imager._native.invert.assert_called_once()

    def test_invert_erreur_c(self):
        session = DifmapSession()
        session.imager._native.invert = MagicMock(return_value=-1)
        with pytest.raises(DifmapError, match="Fourier"):
            session.imager.invert()

# =====================================================================
# 6. TESTS VISUELS MATPLOTLIB (En attendant test_visualizer.py)
# =====================================================================

class TestImagerAffichage:
    @patch("matplotlib.pyplot.show")
    @patch("matplotlib.pyplot.colorbar")
    @patch("matplotlib.pyplot.imshow")
    def test_plot_image(self, mock_imshow, mock_colorbar, mock_show):
        session = DifmapSession()
        fake_dict = {"data": np.zeros((10, 10)), "extent": [5, -5, -5, 5]}

        session.vis.plot_image(fake_dict, title="Test", cmap="plasma")

        mock_imshow.assert_called_once()
        _, kwargs = mock_imshow.call_args
        assert kwargs["extent"] == [5, -5, -5, 5]
        assert kwargs["cmap"] == "plasma"
        mock_colorbar.assert_called_once()
        mock_show.assert_called_once()

    def test_plot_image_cles_manquantes(self):
        session = DifmapSession()
        bad_dict = {"data": np.zeros((5, 5))}
        with pytest.raises(KeyError, match="doit contenir les clés"):
            session.vis.plot_image(bad_dict)