# tests/test_session.py
import pytest
from difmap_wrapper.session import DifmapSession
from difmap_wrapper.exceptions import DifmapStateError

def test_cannot_create_image_without_data():
    """Vérifie que le wrapper empêche de faire 'invert' si on n'a pas fait 'observe'."""
    session = DifmapSession()
    
    # On s'attend à ce que cette ligne lève une erreur précise :
    with pytest.raises(DifmapStateError):
        session.create_image()

def test_full_workflow(paths):
    """Teste le flux normal d'un utilisateur."""
    session = DifmapSession()
    session.load_observation(paths["uv"])
    img = session.create_image(size=128, cellsize=1.0)
    
    assert img is not None
    assert session.uv_loaded is True