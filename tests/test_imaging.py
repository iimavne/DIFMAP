import pytest
from unittest.mock import patch, MagicMock
import numpy as np
from difmap_wrapper.imaging import DifmapImager
from difmap_wrapper.exceptions import DifmapError

# ---------------------------------------------------------
# 1. TESTS DE LA MÉTHODE make_dirty_map
# ---------------------------------------------------------

@patch("difmap_native.select")
@patch("difmap_native.mapsize")
@patch("difmap_native.invert")
@patch("difmap_native.get_header")
@patch("difmap_native.get_map")
@patch("difmap_native.get_beam")
def test_make_dirty_map_success(mock_beam, mock_map, mock_hdr, mock_invert, mock_msize, mock_select):
    """Vérifie le succès de la génération et le calcul de l'extent."""
    # ARRANGE
    mock_msize.return_value = 0
    mock_invert.return_value = 0
    mock_hdr.return_value = {"NX": 512, "NY": 512}
    mock_map.return_value = np.zeros((512, 512))
    mock_beam.return_value = {"bmaj": 1.0, "bmin": 1.0, "bpa": 0.0}
    
    size = 512
    cell = 0.1 # mas
    
    # ACT
    result = DifmapImager.make_dirty_map(size, cell, pol="I")
    
    # ASSERT
    # Vérification des appels au moteur C
    mock_select.assert_called_with("I")
    mock_msize.assert_called_with(size, cell)
    mock_invert.assert_called_once()
    
    # Vérification du calcul de l'astrométrie (Logic "0.5 pixel shift")
    # RA+ = (512/2 * 0.1) + (0.5 * 0.1) = 25.65
    expected_ra_max = 25.65
    assert abs(result["extent"][0] - expected_ra_max) < 1e-7
    assert "data" in result
    assert "beam" in result

@patch("difmap_native.mapsize")
def test_make_dirty_map_mapsize_error(mock_msize):
    """Vérifie la levée d'erreur si l'allocation échoue."""
    mock_msize.return_value = 1 # Code erreur C
    with pytest.raises(DifmapError, match="allocation de la grille"):
        DifmapImager.make_dirty_map(512, 0.1)

@patch("difmap_native.mapsize")
@patch("difmap_native.invert")
def test_make_dirty_map_invert_error(mock_invert, mock_msize):
    """Vérifie la levée d'erreur si la FFT (invert) échoue."""
    mock_msize.return_value = 0
    mock_invert.return_value = 1 # Code erreur C
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