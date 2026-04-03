import pytest
from difmap_wrapper.session import DifmapSession
from difmap_wrapper.exceptions import DifmapError
from difmap_wrapper.observation import Observation
from difmap_wrapper.imaging import DifmapImager

# =====================================================================
# TESTS UNITAIRES : DifmapSession
# =====================================================================

# ---------------------------------------------------------------------
# CAS NOMINAUX 
# ---------------------------------------------------------------------

def test_initialisation_session():
    """Vérifie l'état initial de la session et la création des sous-objets."""
    session = DifmapSession()
    assert session.uv_loaded is False, "Par défaut, aucune donnée ne doit être chargée."
    assert isinstance(session.obs, Observation), "L'objet Observation n'est pas instancié."
    assert isinstance(session.imager, DifmapImager), "L'objet Imager n'est pas instancié."

def test_context_manager_cleanup(fichier_valide):
    """Vérifie que le bloc 'with' charge puis appelle bien cleanup() à la sortie."""
    with DifmapSession() as session:
        session.observe(fichier_valide)
        assert session.uv_loaded is True, "Le fichier aurait dû être chargé."
        
    # À la sortie du bloc with, cleanup() a dû être appelé automatiquement
    assert session.uv_loaded is False, "Le cleanup n'a pas été exécuté à la sortie du 'with'."

def test_observe_rechargement(fichier_valide):
    """Vérifie que charger un 2ème fichier purge bien le 1er au préalable."""
    with DifmapSession() as session:
        session.observe(fichier_valide)
        assert session.uv_loaded is True
        
        # Recharger le même fichier force un passage par cleanup() sans crasher
        session.observe(fichier_valide)
        assert session.uv_loaded is True


# ---------------------------------------------------------------------
# CAS LIMITES 
# ---------------------------------------------------------------------

def test_nettoyage_manuel_pendant_session(fichier_valide):
    """Vérifie qu'appeler cleanup() manuellement ne fait pas crasher la sortie du 'with'."""
    with DifmapSession() as session:
        session.observe(fichier_valide)
        session.cleanup()  # L'utilisateur force le nettoyage
        
        assert session.uv_loaded is False
        # À la fin du bloc with, un 2ème cleanup() automatique va se lancer. 
        # Ça ne doit pas planter.

def test_double_instanciation_simultanee(fichier_valide):
    """Vérifie que créer deux sessions successives fonctionne sans emmêler les variables."""
    session1 = DifmapSession()
    session1.observe(fichier_valide)
    
    session2 = DifmapSession()
    assert session2.uv_loaded is False, "La nouvelle session doit s'initialiser vierge."
    
    session2.observe(fichier_valide)  # Va écraser la mémoire globale du C proprement
    assert session2.uv_loaded is True
    
    # Nettoyage manuel (puisqu'on n'utilise pas le bloc with ici)
    session1.cleanup()
    session2.cleanup()


# ---------------------------------------------------------------------
# GESTION DES ERREURS 
# ---------------------------------------------------------------------

def test_observe_fichier_inexistant(fichier_inexistant):
    """Vérifie qu'un fichier introuvable lève ta DifmapError personnalisée."""
    with DifmapSession() as session:
        with pytest.raises(DifmapError) as exc_info:
            session.observe(fichier_inexistant)
        
        # On s'assure que le message indique la vraie raison
        assert "Impossible de lire" in str(exc_info.value)
        # On s'assure que la mémoire est restée propre
        assert session.uv_loaded is False

def test_observe_fichier_corrompu(fichier_corrompu):
    """Vérifie qu'un fichier texte (non FITS) lève une erreur et sécurise l'état."""
    with DifmapSession() as session:
        with pytest.raises(DifmapError):
            session.observe(fichier_corrompu)
        
        # L'état ne doit pas être marqué comme chargé si la lecture a planté
        assert session.uv_loaded is False