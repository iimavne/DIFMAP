"""
Tests unitaires : Observation

Chaque test reçoit une session propre via le fixture `session`.
Le singleton est réinitialisé automatiquement avant et après chaque test.
"""
import pytest
import numpy as np
from unittest.mock import MagicMock, patch

from difmap_wrapper.session import DifmapSession
from difmap_wrapper.exceptions import DifmapStateError, DifmapError


@pytest.fixture
def session():
    s = DifmapSession()
    yield s
    s.cleanup()


@pytest.fixture
def session_avec_donnees(session, fichier_valide):
    """Session déjà chargée et sélectionnée sur RR."""
    session.observe(fichier_valide)
    session.obs.select(pol="RR")
    return session


# ─── source ───────────────────────────────────────────────────────────────────

def test_source_apres_chargement(session, fichier_valide):
    """Le nom de la source est extrait correctement après observe()."""
    session.observe(fichier_valide)
    assert isinstance(session.obs.source, str)
    assert len(session.obs.source.strip()) > 0


def test_source_sans_chargement(session):
    """Sans fichier chargé, source retourne 'Inconnue' sans crasher."""
    assert session.obs.source == "Inconnue"


# ─── nsub ─────────────────────────────────────────────────────────────────────

def test_nsub_retourne_entier_positif(session, fichier_valide, caplog):
    """nsub() retourne le nombre de sous-réseaux et loggue un message."""
    session.observe(fichier_valide)
    import logging
    with caplog.at_level(logging.INFO, logger="difmap.observation"):
        nb = session.obs.nsub()
    assert isinstance(nb, int)
    assert nb > 0
    assert any("sous-réseaux" in m or str(nb) in m for m in caplog.messages)


def test_nsub_sans_chargement(session):
    """nsub() sans fichier chargé doit lever DifmapStateError."""
    with pytest.raises(DifmapStateError):
        session.obs.nsub()


# ─── select ───────────────────────────────────────────────────────────────────

def test_select_standard(session, fichier_valide):
    """select() avec une polarisation valide ne doit pas lever d'exception."""
    session.observe(fichier_valide)
    session.obs.select(pol="RR")
    session.obs.select()
    session.obs.select(pol="I", ifs=(1, 0), channels=(1, 0))


def test_select_remet_masque_a_zero(session, fichier_valide):
    """Après select(), le masque de flagging doit être réinitialisé."""
    session.observe(fichier_valide)
    session.obs.select(pol="RR")
    data = session.obs.get_data()
    n = len(data["u"])
    assert session.obs.masque_flagges is not None
    assert len(session.obs.masque_flagges) == n
    assert not session.obs.masque_flagges.any(), "Le masque doit être à False après select"


def test_select_sans_chargement(session):
    """select() sans fichier chargé doit lever DifmapStateError."""
    with pytest.raises(DifmapStateError):
        session.obs.select()


def test_select_polarisations_multiples(session, fichier_valide):
    """select() avec différentes polarisations ne doit pas crasher."""
    session.observe(fichier_valide)
    for pol in ["I", "RR", "LL", "RL", "LR"]:
        try:
            session.obs.select(pol=pol)
        except DifmapError:
            pass  # Polarisation absente des données : comportement attendu


# ─── get_data ─────────────────────────────────────────────────────────────────

def test_get_data_retourne_toutes_les_cles(session_avec_donnees):
    """get_data() doit retourner un dict avec les clés attendues."""
    data = session_avec_donnees.obs.get_data()
    cles_attendues = {"u", "v", "amp", "weight"}
    assert cles_attendues.issubset(data.keys())


def test_get_data_tableaux_meme_longueur(session_avec_donnees):
    """Tous les tableaux de get_data() doivent avoir la même longueur."""
    data = session_avec_donnees.obs.get_data()
    longueurs = {k: len(v) for k, v in data.items() if hasattr(v, '__len__')}
    assert len(set(longueurs.values())) == 1, f"Longueurs incohérentes : {longueurs}"


def test_get_data_sans_chargement(session):
    """get_data() sans observation chargée doit lever DifmapStateError."""
    with pytest.raises(DifmapStateError):
        session.obs.get_data()


def test_get_data_initialise_masque(session, fichier_valide):
    """get_data() doit initialiser masque_flagges si ce n'est pas encore fait."""
    session.observe(fichier_valide)
    session.obs.select(pol="RR")
    session.obs.masque_flagges = None
    data = session.obs.get_data()
    assert session.obs.masque_flagges is not None
    assert len(session.obs.masque_flagges) == len(data["u"])


# ─── flag_data / unflag_data ──────────────────────────────────────────────────

def test_flag_indices_vides(session, fichier_valide):
    """flag_data([]) et unflag_data([]) doivent retourner 0 sans appeler le moteur C."""
    session.observe(fichier_valide)
    session.obs._native.flag_data = MagicMock(return_value=0)
    session.obs._native.unflag_data = MagicMock(return_value=0)

    assert session.obs.flag_data([]) == 0
    assert session.obs.unflag_data([]) == 0
    session.obs._native.flag_data.assert_not_called()
    session.obs._native.unflag_data.assert_not_called()


def test_flag_indices_valides_appelle_moteur(session, fichier_valide):
    """flag_data avec des indices doit appeler le moteur C exactement une fois."""
    session.observe(fichier_valide)
    session.obs._native.flag_data = MagicMock(return_value=3)

    result = session.obs.flag_data(np.array([0, 1, 2]))
    assert result == 3
    session.obs._native.flag_data.assert_called_once()


def test_unflag_indices_valides_appelle_moteur(session, fichier_valide):
    """unflag_data avec des indices doit appeler le moteur C exactement une fois."""
    session.observe(fichier_valide)
    session.obs._native.unflag_data = MagicMock(return_value=2)

    result = session.obs.unflag_data(np.array([0, 1]))
    assert result == 2
    session.obs._native.unflag_data.assert_called_once()


# ─── reset_flags ─────────────────────────────────────────────────────────────

def test_reset_flags_remet_masque_a_zero(session, fichier_valide):
    """reset_flags() doit créer un masque tout-False de la bonne taille."""
    session.observe(fichier_valide)
    session.obs.reset_flags(100)
    assert session.obs.masque_flagges is not None
    assert len(session.obs.masque_flagges) == 100
    assert not session.obs.masque_flagges.any()
    assert session.obs.historique_coupes == []


# ─── save_wobs ────────────────────────────────────────────────────────────────

def test_save_wobs_ajoute_extension(session, fichier_valide):
    """save_wobs() doit ajouter .fits si l'extension est absente."""
    session.observe(fichier_valide)
    session.obs._native.save_wobs = MagicMock()

    session.obs.save_wobs("sortie")
    session.obs._native.save_wobs.assert_called_with("sortie.fits", False)


def test_save_wobs_conserve_extension(session, fichier_valide):
    """save_wobs() ne doit pas doubler l'extension .fits."""
    session.observe(fichier_valide)
    session.obs._native.save_wobs = MagicMock()

    session.obs.save_wobs("sortie.fits")
    session.obs._native.save_wobs.assert_called_with("sortie.fits", False)


def test_save_wobs_retourne_true(session, fichier_valide):
    """save_wobs() doit retourner True en cas de succès."""
    session.observe(fichier_valide)
    session.obs._native.save_wobs = MagicMock()
    assert session.obs.save_wobs("sortie.fits") is True


# ─── session_reference ───────────────────────────────────────────────────────

def test_obs_reference_session(session, fichier_valide):
    """obs._session doit pointer vers la session parente."""
    session.observe(fichier_valide)
    assert session.obs._session is session
    assert session.obs._session.uv_loaded is True
    assert session.obs._session.imager is not None
