import pytest
from unittest.mock import patch, MagicMock
import numpy as np
from difmap_wrapper.imaging import DifmapImager
from difmap_wrapper.exceptions import DifmapError

# ---------------------------------------------------------
# 1. TESTS DE LA MÉTHODE make_dirty_map
# ---------------------------------------------------------

# Astuce : On mocke TOUT le module difmap_native d'un coup, c'est beaucoup plus propre !
@patch("difmap_wrapper.imaging.difmap_native")
def test_make_dirty_map_success(mock_native):
    """Vérifie le succès de la génération et le calcul de l'extent."""
    
    # ARRANGE : Configuration du faux module C
    mock_native.select.return_value = 0
    mock_native.mapsize.return_value = 0
    mock_native.invert.return_value = 0
    
    # On simule les retours des fonctions C "Zéro-Copie"
    mock_native.get_native_map_nx.return_value = 512
    mock_native.get_native_map_ny.return_value = 512
    mock_native.get_native_map_data.return_value = np.zeros((512, 512))
    mock_native.get_native_beam_data.return_value = np.zeros((512, 512))
    mock_native.get_native_bmaj.return_value = 1.0
    mock_native.get_native_bmin.return_value = 1.0
    mock_native.get_native_bpa.return_value = 0.0
    
    size = 512
    cell = 0.1 # mas
    
    # ACT
    result = DifmapImager.make_dirty_map(size, cell, pol="I")
    
    # ASSERT
    # Vérification des 5 arguments passés au select
    mock_native.select.assert_called_with("I", 1, 0, 1, 0) 
    mock_native.mapsize.assert_called_with(size, cell)
    mock_native.invert.assert_called_once()
    
    # Vérification du calcul de l'astrométrie (Décalage du demi-pixel)
    expected_ra_max = 25.65
    assert abs(result["extent"][0] - expected_ra_max) < 1e-7
    assert "data" in result
    assert "beam_data" in result
    assert "info" in result
    assert result["info"]["nx"] == 512

@patch("difmap_wrapper.imaging.difmap_native")
def test_make_dirty_map_mapsize_error(mock_native):
    """Vérifie la levée d'erreur si l'allocation échoue."""
    mock_native.select.return_value = 0
    mock_native.mapsize.return_value = 1 # Code erreur C simulé pour mapsize
    
    with pytest.raises(DifmapError, match="allocation de la grille"):
        DifmapImager.make_dirty_map(512, 0.1)

@patch("difmap_wrapper.imaging.difmap_native")
def test_make_dirty_map_invert_error(mock_native):
    """Vérifie la levée d'erreur si la FFT (invert) échoue."""
    mock_native.select.return_value = 0
    mock_native.mapsize.return_value = 0
    mock_native.invert.return_value = 1 # Code erreur C simulé pour invert
    
    with pytest.raises(DifmapError, match="Échec de la transformée"):
        DifmapImager.make_dirty_map(512, 0.1)

# ---------------------------------------------------------
# 2. TESTS DE LA MÉTHODE plot_image
# ---------------------------------------------------------

@patch("matplotlib.pyplot.show")
@patch("matplotlib.pyplot.imshow")
@patch("matplotlib.pyplot.figure")
def test_plot_image_success(mock_fig, mock_imshow, mock_show):
    """Vérifie que la fonction de dessin appelle bien les méthodes Matplotlib."""
    # ARRANGE
    fake_img = {
        "data": np.zeros((128, 128)),
        "extent": [10, -10, -10, 10]
    }
    
    # ACT
    DifmapImager.plot_image(fake_img, title="Test Plot", cmap="plasma")
    
    # ASSERT
    mock_imshow.assert_called_once()
    # On vérifie que les arguments passent bien
    args, kwargs = mock_imshow.call_args
    assert kwargs['cmap'] == "plasma"
    assert kwargs['extent'] == fake_img["extent"]
    mock_show.assert_called_once()

def test_plot_image_missing_keys():
    """Vérifie qu'une erreur est levée si le dictionnaire est incomplet."""
    bad_dict = {"data": "no_extent_here"}
    with pytest.raises(KeyError):
        DifmapImager.plot_image(bad_dict)