import os
import numpy as np
import pytest

# ---> IMPORT À ADAPTER selon le nom de ta classe principale <---
# Par exemple : from difmap_wrapper.session import Session
from difmap_wrapper import DifmapSession as Session 

def test_sauvegarde_et_comparaison_stricte(tmp_path):
    """
    Test complet de bout-en-bout :
    Charge le brut -> Coupe -> Sauvegarde -> Charge le nouveau -> Compare.
    """
    fichier_origine = "tests/test_data/0003-066_X.SPLIT.1"
    assert os.path.exists(fichier_origine), "Fichier de test introuvable !"

    # ==========================================
    # 1. CHARGER LE FICHIER BRUT (via la Session)
    # ==========================================
    session_brute = Session()  # Remplace 'Session()' par le nom de ta classe principale
    session_brute.observe(fichier_origine)
    session_brute.obs.select('RR')
    
    data_brute = session_brute.obs._native.get_uv_data()
    nb_points_bruts = len(data_brute['u'])
    assert nb_points_bruts > 10, "Le fichier FITS est trop petit pour le test."

    # On isole un "point témoin" (le 6ème point, index 5). 
    u_temoin = data_brute['u'][5]
    v_temoin = data_brute['v'][5]
    flux_temoin = data_brute['amp'][5]
    time_temoin = data_brute['time'][5]

    # ==========================================
    # 2. FAIRE LES COMMANDES (Coupure)
    # ==========================================
    indices_a_couper = np.array([0, 1, 2, 3, 4], dtype=np.int32)
    session_brute.obs.flag_data(indices_a_couper)

    # ==========================================
    # 3. SAUVEGARDER
    # ==========================================
    nouveau_fichier = str(tmp_path / "obs_test_save.fits")
    session_brute.obs.save_wobs(nouveau_fichier)
    assert os.path.exists(nouveau_fichier), "Le fichier FITS n'a pas été généré."

    # ==========================================
    # 4. CHARGER LE NOUVEAU FICHIER ET COMPARER
    # ==========================================
    session_nettoyee = Session()
    session_nettoyee.observe(nouveau_fichier)
    session_nettoyee.obs.select('RR')
    
    data_nettoyee = session_nettoyee.obs._native.get_uv_data()
    nb_points_finaux = len(data_nettoyee['u'])

    # --- Vérification A : La quantité ---
    assert nb_points_finaux == (nb_points_bruts - 5), \
        f"Le compte est mauvais ! Brut: {nb_points_bruts}, Nettoyé: {nb_points_finaux}"

    # --- Vérification B : L'intégrité des données restantes ---
    # Le point témoin (ancien index 5) doit maintenant être à l'index 0
    assert data_nettoyee['time'][0] == time_temoin, "Le timestamp a été altéré !"
    assert data_nettoyee['u'][0] == u_temoin, "La coordonnée U a été altérée !"
    assert data_nettoyee['v'][0] == v_temoin, "La coordonnée V a été altérée !"
    assert data_nettoyee['amp'][0] == flux_temoin, "L'amplitude a été altérée !"

    print("\n✅ SUCCÈS : Le fichier a été proprement amputé de ses 5 points !")