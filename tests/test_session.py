"""
Tests unitaires : DifmapSession

Chaque test reçoit une session propre via le fixture `session`.
Le singleton est réinitialisé automatiquement avant et après chaque test.
"""
import pytest
from difmap_wrapper.session import DifmapSession
from difmap_wrapper.exceptions import DifmapStateError, DifmapError
from difmap_wrapper.visualizer import Visualizer
from difmap_wrapper.observation import Observation
from difmap_wrapper.imaging import DifmapImager


@pytest.fixture
def session():
    """Fournit une session propre et la nettoie après le test."""
    s = DifmapSession()
    yield s
    s.cleanup()


# ─── Cas nominaux ─────────────────────────────────────────────────────────────

def test_initialisation_session(session):
    """À la création, aucune donnée n'est chargée et les sous-objets sont créés."""
    assert session.uv_loaded is False
    assert isinstance(session.obs, Observation)
    assert isinstance(session.imager, DifmapImager)
    assert isinstance(session.vis, Visualizer)


def test_sous_objets_recoivent_session(session):
    """Chaque sous-objet doit garder une référence à la session parente."""
    assert session.obs._session is session
    assert session.imager._session is session
    assert session.vis._session is session


def test_context_manager_cleanup(fichier_valide):
    """Le bloc `with` doit appeler cleanup() automatiquement à sa sortie."""
    with DifmapSession() as session:
        session.observe(fichier_valide)
        assert session.uv_loaded is True
    assert session.uv_loaded is False


def test_observe_charge_fichier(session, fichier_valide):
    """Après observe(), uv_loaded passe à True."""
    session.observe(fichier_valide)
    assert session.uv_loaded is True


def test_observe_rechargement(session, fichier_valide):
    """Charger un deuxième fichier remplace proprement le premier."""
    session.observe(fichier_valide)
    assert session.uv_loaded is True
    session.observe(fichier_valide)
    assert session.uv_loaded is True


# ─── Cas limites ──────────────────────────────────────────────────────────────

def test_cleanup_manuel_puis_with(fichier_valide):
    """cleanup() manuel dans un bloc `with` ne doit pas faire crasher la sortie."""
    with DifmapSession() as session:
        session.observe(fichier_valide)
        session.cleanup()
        assert session.uv_loaded is False
    # Le __exit__ appelle cleanup() une deuxième fois — ça ne doit pas planter


def test_sessions_sequentielles(fichier_valide):
    """
    Deux sessions créées l'une après l'autre (jamais simultanément)
    fonctionnent chacune de façon indépendante.
    """
    session1 = DifmapSession()
    session1.observe(fichier_valide)
    assert session1.uv_loaded is True
    session1.cleanup()

    # Le slot singleton est libéré : une nouvelle session est possible
    assert DifmapSession._instance is None

    session2 = DifmapSession()
    assert session2.uv_loaded is False
    session2.observe(fichier_valide)
    assert session2.uv_loaded is True
    session2.cleanup()


def test_deuxieme_session_apres_cleanup(fichier_valide):
    """Après cleanup(), une nouvelle session démarre avec un état vierge."""
    session1 = DifmapSession()
    obs1 = session1.obs
    session1.cleanup()

    session2 = DifmapSession()
    assert session2.obs is not obs1, "La nouvelle session doit avoir un nouvel objet Observation"
    assert session2.uv_loaded is False
    session2.cleanup()


# ─── Singleton ────────────────────────────────────────────────────────────────

def test_singleton_interdit_double_instanciation(session):
    """Créer une deuxième session pendant qu'une est active doit lever DifmapStateError."""
    with pytest.raises(DifmapStateError):
        DifmapSession()


def test_singleton_libere_apres_cleanup():
    """Après cleanup(), le slot singleton est vide et une nouvelle session est possible."""
    s = DifmapSession()
    s.cleanup()
    assert DifmapSession._instance is None
    s2 = DifmapSession()
    s2.cleanup()


# ─── Gestion des erreurs ──────────────────────────────────────────────────────

def test_observe_fichier_inexistant(session, fichier_inexistant):
    """Un fichier introuvable doit lever une exception sans corrompre l'état."""
    with pytest.raises(Exception):
        session.observe(fichier_inexistant)
    assert session.uv_loaded is False


def test_observe_fichier_corrompu(session, fichier_corrompu):
    """Un fichier non-FITS doit lever une exception et laisser la session propre."""
    with pytest.raises(Exception):
        session.observe(fichier_corrompu)
    assert session.uv_loaded is False
