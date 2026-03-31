import pytest
from unittest.mock import patch
from difmap_wrapper.session import DifmapSession
from difmap_wrapper.exceptions import DifmapError

# ---------------------------------------------------------
# 1. TEST DU CYCLE DE VIE
# ---------------------------------------------------------

def test_session_initial_state():
    """Vérifie que la session est vierge à la création."""
    session = DifmapSession()
    assert session.uv_loaded is False
    assert session.obs is not None
    assert session.imager is not None

def test_session_context_manager():
    """Vérifie que le block 'with' fonctionne et nettoie à la sortie."""
    with patch.object(DifmapSession, 'cleanup') as mock_cleanup:
        with DifmapSession() as session:
            assert isinstance(session, DifmapSession)
        mock_cleanup.assert_called_once()

def test_cleanup_resets_state():
    """Vérifie que cleanup remet les compteurs à zéro."""
    session = DifmapSession()
    session.uv_loaded = True
    session.cleanup()
    assert session.uv_loaded is False

# ---------------------------------------------------------
# 2. TEST DU CHARGEMENT (observe)
# ---------------------------------------------------------

@patch("difmap_wrapper.session.difmap_native.observe")
def test_observe_success(mock_observe):
    """Cas nominal : le fichier est chargé avec succès."""
    mock_observe.return_value = 0  # Succès côté C
    session = DifmapSession()
    session.observe("test.fits")
    
    assert session.uv_loaded is True
    mock_observe.assert_called_with("test.fits")

@patch("difmap_wrapper.session.difmap_native.observe")
def test_observe_failure(mock_observe):
    """Cas d'erreur : le moteur C rejette le fichier."""
    mock_observe.return_value = 1  # Erreur côté C
    session = DifmapSession()
    
    with pytest.raises(DifmapError, match="Impossible de lire"):
        session.observe("bad.fits")
    assert session.uv_loaded is False
    
@patch("difmap_wrapper.session.difmap_native.observe")
def test_observe_cleans_previous(mock_observe):
    """Vérifie qu'un nouveau chargement nettoie l'ancien pour éviter les fuites."""
    mock_observe.return_value = 0
    session = DifmapSession()
    session.uv_loaded = True 
    
    with patch.object(session, 'cleanup') as mock_cleanup:
        session.observe("new.fits")
        mock_cleanup.assert_called_once()