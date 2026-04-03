import pytest
import os

@pytest.fixture(scope="session")
def dossier_data():
    """Retourne le chemin absolu vers le dossier test_data."""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_data")

@pytest.fixture
def fichier_valide(dossier_data):
    return os.path.join(dossier_data, "0003-066_X.SPLIT.1")

@pytest.fixture
def fichier_inexistant(dossier_data):
    return os.path.join(dossier_data, "chemin_qui_n_existe_pas.fits")

@pytest.fixture
def fichier_corrompu(tmp_path):
    """Crée dynamiquement un faux fichier FITS (juste du texte) pour tester les crashs."""
    faux_fichier = tmp_path / "corrompu.fits"
    faux_fichier.write_text("Ceci n'est pas un fichier FITS valide. C'est du texte.")
    return str(faux_fichier)