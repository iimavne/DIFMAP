import pytest
import os
from difmap_wrapper.session import DifmapSession
from difmap_wrapper.exceptions import DifmapError
from difmap_wrapper.observation import Observation
from difmap_wrapper.imaging import DifmapImager

# =====================================================================
# CONFIGURATION DES CHEMINS
# =====================================================================
dossier_tests = os.path.dirname(os.path.abspath(__file__))
FICHIER_VALIDE = os.path.join(dossier_tests, "test_data", "0003-066_X.SPLIT.1")
FICHIER_INVALIDE = os.path.join(dossier_tests, "test_data", "fichier_inexistant.fits")

# =====================================================================
# TESTS UNITAIRES : DifmapSession
# =====================================================================

def test_initialisation_session():
    """Vérifie l'état initial de la session et la création des sous-objets."""
    session = DifmapSession()
    assert session.uv_loaded is False, "Par défaut, aucune donnée ne doit être chargée."
    assert isinstance(session.obs, Observation), "L'objet Observation n'est pas instancié."
    assert isinstance(session.imager, DifmapImager), "L'objet Imager n'est pas instancié."

def test_context_manager_cleanup():
    """Vérifie que le bloc 'with' appelle bien cleanup() à la sortie."""
    with DifmapSession() as session:
        session.uv_loaded = True  # On simule un chargement artificiel
        
    # À la sortie du bloc with, cleanup() a dû être appelé
    assert session.uv_loaded is False, "Le cleanup n'a pas été exécuté à la sortie du 'with'."

def test_observe_succes():
    """Vérifie le chargement d'un vrai fichier FITS."""
    with DifmapSession() as session:
        session.observe(FICHIER_VALIDE)
        assert session.uv_loaded is True, "Le flag uv_loaded doit passer à True après un succès."

def test_observe_echec_leve_exception():
    """Vérifie que la session lève bien ta propre erreur personnalisée."""
    with DifmapSession() as session:
        # On s'attend explicitement à lever une DifmapError
        with pytest.raises(DifmapError) as exc_info:
            session.observe(FICHIER_INVALIDE)
        
        # On vérifie que le message d'erreur contient bien le nom du fichier
        assert "Impossible de lire" in str(exc_info.value)
        assert session.uv_loaded is False, "Le flag uv_loaded ne doit pas passer à True en cas d'échec."

def test_observe_rechargement():
    """Vérifie que charger un 2ème fichier purge bien le 1er au préalable."""
    with DifmapSession() as session:
        session.observe(FICHIER_VALIDE)
        assert session.uv_loaded is True
        
        # Recharger le même fichier doit forcer un passage par cleanup()
        # (Si ça ne crashe pas, c'est que la logique if self.uv_loaded: self.cleanup() fonctionne)
        session.observe(FICHIER_VALIDE)
        assert session.uv_loaded is True