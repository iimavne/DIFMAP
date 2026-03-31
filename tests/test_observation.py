import os
import pytest
from unittest.mock import patch
from difmap_wrapper.session import DifmapSession
from difmap_wrapper.exceptions import DifmapStateError, DifmapError

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
REAL_FITS_FILE = os.path.join(TEST_DIR, "test_data", "0003-066_X.SPLIT.1")

@pytest.fixture
def real_fits_file():
    """Fournit le chemin du fichier FITS, et saute le test s'il n'existe pas."""
    if not os.path.exists(REAL_FITS_FILE):
        pytest.skip("Fichier de données test manquant")
    return REAL_FITS_FILE

# ---------------------------------------------------------
# 1. TESTS UNITAIRES (La classe Observation)
# ---------------------------------------------------------

def test_nsub_fails_if_not_loaded():
    """Vérifie la barrière de sécurité."""
    session = DifmapSession() # uv_loaded est False
    with pytest.raises(DifmapStateError, match="Aucune observation chargée"):
        session.obs.nsub()

def test_select_fails_if_not_loaded():
    """Vérifie la barrière de sécurité."""
    session = DifmapSession()
    with pytest.raises(DifmapStateError, match="Aucune observation chargée"):
        session.obs.select(pol="I")

@patch("difmap_wrapper.observation.difmap_native")
def test_nsub_success(mock_native):
    """Vérifie que l'appel au C est correct."""
    mock_native.nsub.return_value = 1
    session = DifmapSession()
    session.uv_loaded = True # On triche pour passer la sécurité
    
    res = session.obs.nsub()
    assert res == 1
    mock_native.nsub.assert_called_once()

@patch("difmap_wrapper.observation.difmap_native")
def test_select_success(mock_native):
    """Vérifie que les 5 arguments sont bien transmis au C."""
    mock_native.select.return_value = 0
    session = DifmapSession()
    session.uv_loaded = True
    
    session.obs.select(pol="rr", ifs=(2, 3), channels=(10, 20))
    # Vérifie la mise en majuscule automatique et l'extraction des tuples
    mock_native.select.assert_called_once_with("RR", 2, 3, 10, 20)

# ---------------------------------------------------------
# 2. TEST INTÉGRATION RÉELLE (Workflow complet)
# ---------------------------------------------------------

def test_workflow_observe_nsub_select(real_fits_file):
    """Test l'enchaînement complet sur le vrai moteur C."""
    with DifmapSession() as session:
        
        # 1. Chargement
        session.observe(real_fits_file)
        assert session.uv_loaded is True

        # 2. Test NSUB via l'objet Observation
        nb_subarrays = session.obs.nsub()
        assert nb_subarrays > 0, "Difmap n'a trouvé aucun sous-réseau"

        # 3. Test SELECT via l'objet Observation
        # Si le moteur C valide sans lever DifmapError, la plomberie est parfaite !
        session.obs.select(pol="I", ifs=(1, 1))