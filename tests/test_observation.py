import pytest
import os
from unittest.mock import patch
from difmap_wrapper.session import DifmapSession
from difmap_wrapper.observation import Observation
from difmap_wrapper.exceptions import DifmapStateError, DifmapError

# =====================================================================
# CONFIGURATION DES CHEMINS
# =====================================================================
dossier_tests = os.path.dirname(os.path.abspath(__file__))
FICHIER_VALIDE = os.path.join(dossier_tests, "test_data", "0003-066_X.SPLIT.1")

# =====================================================================
# TESTS UNITAIRES : Observation
# =====================================================================

def test_observation_etat_non_charge():
    """
    Vérifie que la classe bloque proprement les commandes 
    si l'utilisateur a oublié de faire session.observe().
    """
    with DifmapSession() as session:
        # On ne fait PAS session.observe()
        obs = Observation(session)
        
        # 1. La source doit être Inconnue, pas un crash
        assert obs.source == "Inconnue", "La source devrait être 'Inconnue' si rien n'est chargé."
        
        # 2. nsub() doit lever une erreur d'état
        with pytest.raises(DifmapStateError) as exc:
            obs.nsub()
        assert "Aucune observation chargée" in str(exc.value)
            
        # 3. select() doit lever une erreur d'état
        with pytest.raises(DifmapStateError):
            obs.select()

def test_observation_source_et_nsub():
    """Vérifie la lecture correcte des métadonnées de base du FITS."""
    with DifmapSession() as session:
        session.observe(FICHIER_VALIDE)
        obs = Observation(session)
        
        # Le nom de la source doit être lu depuis le C
        assert obs.source == "0003-066", f"Nom de source inattendu : {obs.source}"
        
        # Il doit y avoir au moins 1 sous-réseau
        assert obs.nsub() >= 1, "Le nombre de sous-réseaux (nsub) est invalide."

def test_observation_select_succes_et_echec():
    """Vérifie que select() envoie les bons arguments et gère les rejets du C."""
    with DifmapSession() as session:
        session.observe(FICHIER_VALIDE)
        obs = Observation(session)
        
        # 1. Test nominal (Doit passer silencieusement)
        try:
            obs.select(pol="RR")
        except Exception as e:
            pytest.fail(f"La sélection RR a échoué de manière inattendue : {e}")
            
        # 2. Test d'échec (Polarisation fantôme)
        with pytest.raises(DifmapError) as exc:
            obs.select(pol="ZZZ")
        assert "Échec de la sélection" in str(exc.value)

@patch("matplotlib.pyplot.show") # <-- LE MOCKING MAGIQUE EST ICI
def test_observation_plots_securite(mock_show):
    """
    Vérifie que les fonctions graphiques ne font pas crasher le programme, 
    qu'elles soient appelées avant ou après le select().
    """
    with DifmapSession() as session:
        session.observe(FICHIER_VALIDE)
        obs = Observation(session)
        
        # 1. Test AVANT select() : les listes U et V sont vides
        # Le code doit faire un 'print' et un 'return' propre sans crasher.
        obs.uvplot()
        obs.radplot()
        
        # plt.show n'a pas dû être appelé car on a 'return' avant
        assert mock_show.call_count == 0, "plt.show() ne doit pas être appelé si UV est vide."
        
        # 2. Test APRÈS select() : la RAM est remplie
        obs.select(pol="RR")
        
        # Les fonctions doivent extraire les données, dessiner, et appeler plt.show()
        obs.uvplot()
        obs.radplot()
        
        # On vérifie que Matplotlib a bien été déclenché 2 fois (sans ouvrir les fenêtres !)
        assert mock_show.call_count == 2, "Les deux graphiques n'ont pas appelé plt.show()."