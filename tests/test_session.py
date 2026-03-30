import pytest
from unittest.mock import patch, MagicMock
from difmap_wrapper.session import DifmapSession
from difmap_wrapper.exceptions import DifmapStateError, DifmapError

# ---------------------------------------------------------
# 1. TEST DU CYCLE DE VIE (Init, Enter, Exit, Cleanup)
# ---------------------------------------------------------

def test_session_initial_state():
    """Vérifie que la session est vierge à la création."""
    session = DifmapSession()
    assert session.uv_loaded is False
    assert session.current_image is None

def test_session_context_manager():
    """Vérifie que le block 'with' fonctionne et nettoie à la sortie."""
    with patch.object(DifmapSession, 'cleanup') as mock_cleanup:
        with DifmapSession() as session:
            assert isinstance(session, DifmapSession)
        # Vérifie que cleanup() est appelé automatiquement à la sortie
        mock_cleanup.assert_called_once()

def test_cleanup_resets_state():
    """Vérifie que cleanup remet les compteurs à zéro."""
    session = DifmapSession()
    session.uv_loaded = True
    session.current_image = {"data": "fake"}
    
    session.cleanup()
    
    assert session.uv_loaded is False
    assert session.current_image is None

# ---------------------------------------------------------
# 2. TEST DU CHARGEMENT (load_observation)
# ---------------------------------------------------------

@patch("difmap_native.observe")
def test_load_observation_success(mock_observe):
    """Cas nominal : le fichier est chargé avec succès."""
    mock_observe.return_value = 0  # Succès côté C
    session = DifmapSession()
    
    session.load_observation("test.fits")
    
    assert session.uv_loaded is True
    mock_observe.assert_called_with("test.fits")

@patch("difmap_native.observe")
def test_load_observation_failure(mock_observe):
    """Cas d'erreur : le moteur C rejette le fichier."""
    mock_observe.return_value = 1  # Erreur côté C
    session = DifmapSession()
    
    with pytest.raises(DifmapError, match="Impossible de lire le fichier"):
        session.load_observation("bad.fits")
    assert session.uv_loaded is False

@patch("difmap_native.observe")
def test_load_observation_cleans_previous(mock_observe):
    """Vérifie qu'un nouveau chargement nettoie l'ancien pour éviter les fuites."""
    mock_observe.return_value = 0
    session = DifmapSession()
    session.uv_loaded = True # On simule une observation déjà là
    
    with patch.object(session, 'cleanup') as mock_cleanup:
        session.load_observation("new.fits")
        mock_cleanup.assert_called_once()

# ---------------------------------------------------------
# 3. TEST DE LA CRÉATION D'IMAGE (create_image)
# ---------------------------------------------------------

import os
import numpy as np

# ---------------------------------------------------------
# 4. TESTS D'INTÉGRATION (AVEC LE VRAI MOTEUR C)
# ---------------------------------------------------------

# On définit le chemin vers ton vrai fichier de test
# (Assure-toi que ce chemin correspond à ton arborescence)
REAL_FITS_FILE = "tests/test_data/0003-066_X.SPLIT.1"

# Cette décoration "skipif" est magique : si le fichier FITS n'est pas sur le PC 
# (par exemple si tu lances les tests sur Github Actions), il ignorera le test 
# au lieu de le faire planter bêtement.
@pytest.mark.skipif(not os.path.exists(REAL_FITS_FILE), reason="Fichier FITS de test introuvable")
def test_integration_load_real_file():
    """Test le chargement d'un vrai fichier dans la RAM du moteur C."""
    with DifmapSession() as session:
        # Pas de @patch ! On appelle le vrai moteur C
        session.load_observation(REAL_FITS_FILE)
        
        # Si on arrive ici sans que Python ne crashe (Segfault), c'est déjà un succès !
        assert session.uv_loaded is True


@pytest.mark.skipif(not os.path.exists(REAL_FITS_FILE), reason="Fichier FITS de test introuvable")
def test_integration_create_real_image():
    """Test la création d'une Dirty Map entière via la FFT du moteur C."""
    with DifmapSession() as session:
        session.load_observation(REAL_FITS_FILE)
        
        # On demande au moteur C de calculer la FFT
        size = 256
        cellsize = 0.5
        img_package = session.create_image(size=size, cellsize=cellsize, pol="I")
        
        # --- VÉRIFICATIONS DES DONNÉES RÉELLES ---
        
        # 1. Vérification des clés
        assert "data" in img_package
        assert "extent" in img_package
        assert "header" in img_package
        assert "beam" in img_package
        
        # 2. Vérification de la matrice (Zéro-Copie depuis le C)
        data = img_package["data"]
        assert isinstance(data, np.ndarray), "Les données doivent être un tableau NumPy"
        assert data.shape == (size, size), f"L'image devrait faire {size}x{size} pixels"
        
        # 3. Vérification mathématique basique (la carte ne doit pas être vide)
        assert np.max(data) != 0.0, "La carte générée est complètement vide (que des zéros) !"
        
        # 4. Vérification de l'astrométrie (l'extent doit avoir 4 valeurs)
        assert len(img_package["extent"]) == 4
        

def test_create_image_fails_if_not_loaded():
    """Vérifie la barrière de sécurité (DifmapStateError)."""
    session = DifmapSession()
    with pytest.raises(DifmapStateError, match="Vous devez charger une observation"):
        session.create_image()

def test_create_image_invalid_polarization():
    """Vérifie la validation de la polarisation (ValueError)."""
    session = DifmapSession()
    session.uv_loaded = True
    with pytest.raises(ValueError, match="n'existe pas"):
        session.create_image(pol="Z")

@patch("difmap_wrapper.imaging.DifmapImager.make_dirty_map")
def test_create_image_success(mock_make_map):
    """Vérifie que create_image délègue bien le travail et stocke le résultat."""
    # Simulation du retour de l'Imager
    fake_img = {"data": "matrix", "extent": [0,1,0,1]}
    mock_make_map.return_value = fake_img
    
    session = DifmapSession()
    session.uv_loaded = True
    
    result = session.create_image(size=256, cellsize=0.5, pol="I")
    
    # Vérifications
    assert result == fake_img
    assert session.current_image == fake_img
    mock_make_map.assert_called_once_with(size=256, cellsize=0.5, pol="I")
    
    