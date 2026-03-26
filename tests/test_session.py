# tests/test_session.py
import pytest
from difmap_wrapper.session import DifmapSession
from difmap_wrapper.exceptions import DifmapStateError

import os
import pytest

# Fixture locale temporaire si conftest ne répond pas
@pytest.fixture
def paths():
    base = os.path.dirname(os.path.abspath(__file__))
    return {
        "uv": os.path.join(base, "test_data/0003-066_X.SPLIT.1"),
        "fits": os.path.join(base, "test_data/verite_terrain_test.fits")
    }
    
def test_cannot_create_image_without_loading_data():
    """
    Test de Sécurité : Vérifie que le wrapper lève une erreur PROPRE 
    si l'utilisateur tente de générer une image sans avoir chargé de données.
    """
    session = DifmapSession()
    
    # On s'attend à ce que l'erreur 'DifmapStateError' soit levée
    with pytest.raises(DifmapStateError) as exc_info:
        session.create_image(size=128, cellsize=1.0)
    
    # On vérifie que le message d'erreur est bien explicite pour l'utilisateur
    assert "Vous devez charger une observation" in str(exc_info.value)

def test_full_user_workflow(paths):
    """
    Test du workflow complet : Chargement -> Création d'image.
    C'est ce que fera un chercheur dans son Notebook.
    """
    session = DifmapSession()
    
    # 1. Chargement
    session.load_observation(paths["uv"])
    assert session.uv_loaded is True
    
    # 2. Création de l'image
    img_dict = session.create_image(size=128, cellsize=1.0)
    assert session.current_image is not None
    assert img_dict["data"].shape == (128, 128)