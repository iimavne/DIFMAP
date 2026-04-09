import pytest
import os
import sys

# Ajouter builddir au sys.path pour que difmap_native soit trouvable
# Cela doit être fait avant que pytest collecte les tests
builddir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "builddir")
if os.path.exists(builddir) and builddir not in sys.path:
    sys.path.insert(0, builddir)

# Vérifier que difmap_native peut être importé
try:
    import difmap_native
    print(f"✓ difmap_native loaded from: {difmap_native.__file__ if hasattr(difmap_native, '__file__') else 'built-in'}")
except ImportError as e:
    print(f"✗ Failed to import difmap_native: {e}")


@pytest.fixture(scope="session", autouse=True)
def setup_paths():
    """Fixture autouse pour s'assurer que les paths sont correctement configurés."""
    builddir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "builddir")
    if os.path.exists(builddir) and builddir not in sys.path:
        sys.path.insert(0, builddir)


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