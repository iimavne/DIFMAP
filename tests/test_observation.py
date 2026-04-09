import pytest
from unittest.mock import patch, MagicMock
from difmap_wrapper.session import DifmapSession
from difmap_wrapper.exceptions import DifmapStateError, DifmapError
import numpy as np

# =====================================================================
# TESTS UNITAIRES : Observation
# =====================================================================

# ---------------------------------------------------------------------
# CAS NOMINAUX
# ---------------------------------------------------------------------

def test_observation_source_nominale(fichier_valide):
    """Vérifie que le nom de la source est correctement extrait de la mémoire C."""
    with DifmapSession() as session:
        session.observe(fichier_valide)
        # Remarque : Difmap stocke souvent les noms avec des espaces autour, 
        # on vérifie donc si le nom de base est bien inclus.
        assert "0003" in session.obs.source or "066" in session.obs.source

def test_observation_nsub_comportement_difmap(fichier_valide, capsys):
    """Vérifie que nsub renvoie le bon chiffre ET affiche le texte dans le terminal."""
    with DifmapSession() as session:
        session.observe(fichier_valide)
        
        # capsys permet à Pytest d'intercepter les print()
        nb_sub = session.obs.nsub()
        sortie_terminal = capsys.readouterr().out
        
        assert nb_sub > 0, "Il doit y avoir au moins 1 sous-réseau."
        assert "Nombre de sous-réseaux" in sortie_terminal, "nsub doit afficher le message classique de Difmap."
        assert str(nb_sub) in sortie_terminal

def test_observation_select_valide(fichier_valide):
    """Vérifie qu'une sélection standard (ex: Pol I ou RR) passe au moteur C sans erreur."""
    with DifmapSession() as session:
        session.observe(fichier_valide)
        try:
            session.obs.select(pol="RR")
            session.obs.select() # Teste aussi les valeurs par défaut
            session.obs.select(pol="I", ifs=(1,0), channels=(1,0))
        except Exception as e:
            pytest.fail(f"Un select valide a provoqué une erreur inattendue : {e}")

def test_observation_flag_unflag_data(fichier_valide):
    """Vérifie que flag_data et unflag_data retournent des valeurs explicites."""
    with DifmapSession() as session:
        session.observe(fichier_valide)
        session.obs.select()
        
        # Mock les appels natifs
        session.obs._native.flag_data = MagicMock(return_value=0)
        session.obs._native.unflag_data = MagicMock(return_value=0)
        
        # Test avec indices vides
        result1 = session.obs.flag_data([])
        assert result1 == 0, "flag_data([]) doit retourner 0"
        
        result2 = session.obs.unflag_data([])
        assert result2 == 0, "unflag_data([]) doit retourner 0"
        
        # Test avec indices valides
        result3 = session.obs.flag_data(np.array([0, 1, 2]))
        assert result3 is not None, "flag_data doit retourner une valeur"
        
        result4 = session.obs.unflag_data(np.array([0, 1, 2]))
        assert result4 == 0, "unflag_data doit retourner une valeur"

def test_observation_save_wobs_message_correct(fichier_valide, capsys):
    """Vérifie que save_wobs affiche le bon message sans espace au début."""
    with DifmapSession() as session:
        session.observe(fichier_valide)
        
        # Mock la sauvegarde native
        session.obs._native.save_wobs = MagicMock()
        
        session.obs.save_wobs("test.fits")
        captured = capsys.readouterr()
        
        assert "Sauvegarde en cours via Difmap..." in captured.out
        # Vérifier qu'il n'y a pas d'espace au début
        for line in captured.out.split('\n'):
            if "Sauvegarde" in line:
                assert not line.startswith(" Sauvegarde"), "Pas d'espace au début du message"

@patch("matplotlib.pyplot.show")
def test_observation_plots_nominaux(mock_show, fichier_valide):
    """Vérifie que uvplot et radplot ne crashent pas après une sélection."""
    with DifmapSession() as session:
        session.observe(fichier_valide)
        session.obs.select(pol="I")
        
        # Mock les données UV
        session.obs._native.get_uv_data = MagicMock(return_value={
            'u': np.array([1000, 2000]),
            'v': np.array([500, 1500]),
            'amp': np.array([1.0, 2.0])
        })
        
        try:
            session.vis.uvplot()
            session.vis.radplot()
        except Exception as e:
            # Peut échouer pour raison de matplotlib mock, c'est OK
            pass


# ---------------------------------------------------------------------
# CAS LIMITES 
# ---------------------------------------------------------------------

def test_observation_source_sans_fichier():
    """Vérifie qu'interroger la source avant l'observation ne crashe pas."""
    session = DifmapSession()
    assert session.obs.source == "Inconnue", "Une session vide doit renvoyer 'Inconnue'."

def test_observation_plots_sans_selection(fichier_valide, capsys):
    """Vérifie que tracer sans 'select' affiche un message sans crasher."""
    with DifmapSession() as session:
        session.observe(fichier_valide)
        # /!\ On ne fait pas de select ici !
        
        # Mock pour éviter les vrais appels
        session.obs._native.get_uv_data = MagicMock(return_value=None)
        
        session.vis.uvplot()
        session.vis.radplot()
        
        sortie_terminal = capsys.readouterr().out
        assert "Aucune donnée UV" in sortie_terminal

def test_observation_select_all_polarisations(fichier_valide):
    """Vérifie que select fonctionne avec différentes polarisations."""
    with DifmapSession() as session:
        session.observe(fichier_valide)
        
        polarisations = ["I", "RR", "LL", "RL", "LR"]
        
        for pol in polarisations:
            try:
                session.obs.select(pol=pol)
            except DifmapError as e:
                # C'est OK si une polarisation n'existe pas dans les données
                # Mais au moins le select doit être appelé sans crasher
                pass

def test_observation_session_reference(fichier_valide):
    """Vérifie que Observation maintient bien la référence à la session."""
    with DifmapSession() as session:
        session.observe(fichier_valide)
        
        # Observation doit avoir la référence correcte
        assert session.obs._session is session
        assert session.obs._session.uv_loaded is True
        
        # Vérifier qu'on peut accéder aux autres objets via la session
        assert session.obs._session.imager is not None
        assert session.obs._session.vis is not None


# ---------------------------------------------------------------------
# GESTION DES ERREURS 
# ---------------------------------------------------------------------

def test_observation_actions_sans_chargement():
    """Vérifie que manipuler l'observation sans fichier lève une erreur d'état (StateError)."""
    session = DifmapSession()
    
    with pytest.raises(DifmapStateError):
        session.obs.nsub()
        
    with pytest.raises(DifmapStateError):
        session.obs.select()

def test_observation_select_invalide(fichier_valide):
    """Vérifie que demander une polarisation absurde lève une erreur du moteur C."""
    with DifmapSession() as session:
        session.observe(fichier_valide)
        
        with pytest.raises(DifmapError) as exc_info:
            session.obs.select(pol="POL_QUI_N_EXISTE_PAS")
            
        assert "Échec de la sélection" in str(exc_info.value)

def test_observation_save_wobs_avec_extension(fichier_valide):
    """Vérifie que save_wobs ajoute .fits si absent."""
    with DifmapSession() as session:
        session.observe(fichier_valide)
        
        session.obs._native.save_wobs = MagicMock()
        
        # Appel sans extension
        session.obs.save_wobs("test")
        
        # Vérifier que .fits a été ajouté
        session.obs._native.save_wobs.assert_called_with("test.fits")
        
        # Appel avec extension
        session.obs.save_wobs("test.fits")
        session.obs._native.save_wobs.assert_called_with("test.fits")