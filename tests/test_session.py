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