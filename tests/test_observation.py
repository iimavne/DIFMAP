import pytest
from unittest.mock import patch
from difmap_wrapper.session import DifmapSession
from difmap_wrapper.exceptions import DifmapStateError, DifmapError

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
        except Exception as e:
            pytest.fail(f"Un select valide a provoqué une erreur inattendue : {e}")

@patch("matplotlib.pyplot.show") # Bloque l'ouverture de la fenêtre pendant le test
def test_observation_plots_nominaux(mock_show, fichier_valide):
    """Vérifie que uvplot et radplot exécutent bien Matplotlib si les données sont prêtes."""
    with DifmapSession() as session:
        session.observe(fichier_valide)
        session.obs.select(pol="RR") # Indispensable avant de plotter
        
        session.obs.uvplot()
        session.obs.radplot(color='red', s=3)
        
        assert mock_show.call_count == 2, "Les deux graphiques auraient dû être générés."


# ---------------------------------------------------------------------
# CAS LIMITES 
# ---------------------------------------------------------------------

def test_observation_source_sans_fichier():
    """Vérifie qu'interroger la source avant l'observation ne crashe pas."""
    session = DifmapSession()
    assert session.obs.source == "Inconnue", "Une session vide doit renvoyer 'Inconnue'."

def test_observation_plots_sans_selection(fichier_valide, capsys):
    """Vérifie que tracer sans 'select' annule le plot sans crasher."""
    with DifmapSession() as session:
        session.observe(fichier_valide)
        # /!\ On ne fait pas de select ici !
        
        session.obs.uvplot()
        session.obs.radplot()
        
        sortie_terminal = capsys.readouterr().out
        assert "Aucune donnée UV. Appelez select()" in sortie_terminal
        
def test_observation_select_valide(fichier_valide):
    """Vérifie qu'une sélection standard et complexe passe au moteur C sans erreur."""
    with DifmapSession() as session:
        session.observe(fichier_valide)
        try:
            # 1. Sélection par défaut (Tout)
            session.obs.select() 
            # 2. Sélection basique (Polarisation seule)
            session.obs.select(pol="RR")
            # 3. Sélection ultra-précise (Pol + IFs + Canaux) - LE CAS MANQUANT
            session.obs.select(pol="LL", ifs=(1, 1), channels=(1, 10))
        except Exception as e:
            pytest.fail(f"Un select valide a provoqué une erreur inattendue : {e}")


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