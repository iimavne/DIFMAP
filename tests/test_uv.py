# tests/test_uv.py
import os
import subprocess
from matplotlib import pyplot as plt
import pytest
from astropy.io import fits
import numpy as np
from difmap_wrapper import DifmapSession
from difmap_wrapper.exceptions import DifmapStateError

# --- DÉFINITION DU CHEMIN DYNAMIQUE ---
TEST_DIR = os.path.dirname(os.path.abspath(__file__))
REAL_FITS_FILE = os.path.join(TEST_DIR, "test_data", "0003-066_X.SPLIT.1")

# --- FIXTURES ---
@pytest.fixture
def session():
    """Fournit une session vierge, qui sera nettoyée à la fin."""
    with DifmapSession() as s:
        yield s

@pytest.fixture
def session_with_data(session):
    """Fournit une session avec des données déjà chargées en utilisant le chemin absolu."""
    session.load_observation(REAL_FITS_FILE)
    return session

# --- TESTS ---

def test_get_uv_data_fails_without_observation(session):
    """
    Test de sécurité : on ne doit pas pouvoir demander des données UV 
    si aucun fichier FITS n'a été chargé.
    """
    with pytest.raises(DifmapStateError, match="Vous devez charger une observation"):
        session.get_uv_data()

def test_get_uv_data_structure(session_with_data):
    """
    Test du format de retour : on vérifie que la méthode renvoie bien
    un dictionnaire contenant des tableaux NumPy 1D de même taille.
    """
    # 1. Action : on demande les données
    uv_data = session_with_data.get_uv_data()
    
    # 2. Vérification du type global
    assert isinstance(uv_data, dict), "La fonction doit renvoyer un dictionnaire"
    
    # 3. Vérification de la présence des clés essentielles
    expected_keys = ["u", "v", "amp", "weight"]
    for key in expected_keys:
        assert key in uv_data, f"La clé '{key}' est manquante dans les données UV"
        
        # On vérifie que c'est bien du Zéro-Copie (ou du moins un tableau numpy)
        assert isinstance(uv_data[key], np.ndarray), f"La donnée '{key}' n'est pas un numpy.ndarray"
        assert uv_data[key].ndim == 1, f"Le tableau '{key}' doit être en 1D (aplati)"
        
    # 4. Vérification de la cohérence mathématique (tous les tableaux ont la même taille)
    n_points = len(uv_data["u"])
    assert n_points > 0, "Le tableau de données UV est vide"
    assert len(uv_data["v"]) == n_points, "Incohérence de taille entre 'u' et 'v'"
    assert len(uv_data["amp"]) == n_points, "Incohérence de taille avec 'amp'"
    assert len(uv_data["weight"]) == n_points, "Incohérence de taille avec 'weight'"
    

DIFMAP_BIN = "/home/mahssini/Bureau/difmap2.5q_mod/builddir/difmap" 
TEST_DIR = os.path.dirname(os.path.abspath(__file__))
REAL_FITS_FILE = os.path.join(TEST_DIR, "test_data", "0003-066_X.SPLIT.1")

@pytest.mark.skipif(not os.path.exists(REAL_FITS_FILE), reason="Fichier test manquant")
def test_regression_uv_data_vs_astropy():
    """
    Test de régression UV en 6 panneaux : Original vs Wrapper vs Différence.
    """
    import matplotlib.pyplot as plt

    # =========================================================
    # 1. EXTRACTION VIA TON WRAPPER
    # =========================================================
    with DifmapSession() as session:
        session.load_observation(REAL_FITS_FILE)
        uv_data = session.get_uv_data()
        
    u_wrapper = uv_data['u']
    v_wrapper = uv_data['v']
    amp_wrapper = uv_data['amp']

    # =========================================================
    # 2. EXTRACTION VIA ASTROPY (FITS Original)
    # =========================================================
    with fits.open(REAL_FITS_FILE) as hdul:
        data = hdul[0].data
        parnames = data.parnames
        nom_colonne_u = next(p for p in parnames if p.startswith('UU'))
        nom_colonne_v = next(p for p in parnames if p.startswith('VV'))
        
        u_astropy_base = data.par(nom_colonne_u)
        v_astropy_base = data.par(nom_colonne_v) 
        
        vis_matrix = data.data 
        n_ifs = vis_matrix.shape[3] 
        
        u_astropy = np.repeat(u_astropy_base, n_ifs)
        v_astropy = np.repeat(v_astropy_base, n_ifs)
        
        reel = vis_matrix[..., 0].flatten()
        imag = vis_matrix[..., 1].flatten()
        poids = vis_matrix[..., 2].flatten()
        
        amp_astropy = np.sqrt(reel**2 + imag**2)

    masque_valide = poids > 0
    u_astropy_valide = u_astropy[masque_valide]
    v_astropy_valide = v_astropy[masque_valide]
    amp_astropy_valide = amp_astropy[masque_valide]

    # =========================================================
    # 3. ALIGNEMENT ET SOUSTRACTION (Calcul des résidus)
    # =========================================================
    idx_wrapper = np.lexsort((v_wrapper, u_wrapper))
    idx_astropy = np.lexsort((v_astropy_valide, u_astropy_valide))
    
    u_wrap_sorted = u_wrapper[idx_wrapper]
    v_wrap_sorted = v_wrapper[idx_wrapper]
    amp_wrap_sorted = amp_wrapper[idx_wrapper]
    
    u_astro_sorted = u_astropy_valide[idx_astropy]
    v_astro_sorted = v_astropy_valide[idx_astropy]
    amp_astro_sorted = amp_astropy_valide[idx_astropy]
    
    diff_u = u_wrap_sorted - u_astro_sorted
    diff_v = v_wrap_sorted - v_astro_sorted
    diff_amp = amp_wrap_sorted - amp_astro_sorted

    erreur_max_u = np.max(np.abs(diff_u))
    erreur_max_v = np.max(np.abs(diff_v))
    erreur_max_amp = np.max(np.abs(diff_amp))

    # =========================================================
    # 4. LE CONTRÔLE VISUEL EN 6 PANNEAUX
    # =========================================================
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))

    # ---------------- LIGNE 1 : COUVERTURE UV ----------------
    # 1.A Astropy (Original)
    axes[0, 0].scatter(u_astropy_valide, v_astropy_valide, s=0.5, color='red')
    axes[0, 0].scatter(-u_astropy_valide, -v_astropy_valide, s=0.5, color='red')
    axes[0, 0].set_title("1. Couverture UV (FITS Original)")
    axes[0, 0].set_aspect('equal', adjustable='datalim')
    axes[0, 0].invert_xaxis()
    axes[0, 0].grid(True, linestyle=':', alpha=0.5)

    # 1.B Wrapper C
    axes[0, 1].scatter(u_wrapper, v_wrapper, s=0.5, color='blue')
    axes[0, 1].scatter(-u_wrapper, -v_wrapper, s=0.5, color='blue')
    axes[0, 1].set_title("2. Couverture UV (Wrapper C)")
    axes[0, 1].set_aspect('equal', adjustable='datalim')
    axes[0, 1].invert_xaxis()
    axes[0, 1].grid(True, linestyle=':', alpha=0.5)

    # 1.C Différence (Résidus U et V)
    axes[0, 2].scatter(range(len(diff_u)), diff_u, s=2, color='red', label='Erreur U', alpha=0.7)
    axes[0, 2].scatter(range(len(diff_v)), diff_v, s=2, color='blue', label='Erreur V', alpha=0.7)
    axes[0, 2].set_title(f"3. Différence Spatiale (Max U:{erreur_max_u:.1e}, V:{erreur_max_v:.1e})")
    axes[0, 2].axhline(0, color='black', linestyle='--', linewidth=2)
    axes[0, 2].set_ylim(-0.1, 0.1) 
    axes[0, 2].legend()
    axes[0, 2].grid(True, linestyle=':', alpha=0.5)

    # ---------------- LIGNE 2 : RADPLOT ----------------
    rayon_uv_astropy = np.sqrt(u_astropy_valide**2 + v_astropy_valide**2)
    rayon_uv_wrapper = np.sqrt(u_wrapper**2 + v_wrapper**2)

    # 2.A Astropy (Original)
    axes[1, 0].scatter(rayon_uv_astropy, amp_astropy_valide, s=1, color='red', alpha=0.5)
    axes[1, 0].set_title("4. Radplot (FITS Original)")
    axes[1, 0].set_ylabel("Amplitude (Jy)")
    axes[1, 0].grid(True, linestyle=':', alpha=0.5)

    # 2.B Wrapper C
    axes[1, 1].scatter(rayon_uv_wrapper, amp_wrapper, s=1, color='blue', alpha=0.5)
    axes[1, 1].set_title("5. Radplot (Wrapper C)")
    axes[1, 1].set_ylabel("Amplitude (Jy)")
    axes[1, 1].grid(True, linestyle=':', alpha=0.5)

    # 2.C Différence (Résidus Amplitude)
    axes[1, 2].scatter(range(len(diff_amp)), diff_amp, s=2, color='green', alpha=0.7)
    axes[1, 2].set_title(f"6. Différence d'Amplitude (Max: {erreur_max_amp:.1e})")
    axes[1, 2].set_ylabel("Delta Amplitude (Jy)")
    axes[1, 2].axhline(0, color='black', linestyle='--', linewidth=2)
    axes[1, 2].grid(True, linestyle=':', alpha=0.5)

    plt.tight_layout()
    chemin_visuel_uv = os.path.join(TEST_DIR, "controle_regression_uv_6_panneaux.png")
    plt.savefig(chemin_visuel_uv, dpi=150)
    plt.close(fig)
    print(f"\n Grille de 6 graphiques sauvegardée : {chemin_visuel_uv}")

    # =========================================================
    # 5. LE VERDICT MATHÉMATIQUE
    # =========================================================
    assert len(u_wrapper) == len(u_astropy_valide), "Le nombre de points diffère !"
    assert np.allclose(u_wrap_sorted, u_astro_sorted, atol=1e-5), f"Écart de coordonnées U détecté (Max: {erreur_max_u})"
    assert np.allclose(amp_wrap_sorted, amp_astro_sorted, atol=1e-3), f"Écart d'amplitude détecté (Max: {erreur_max_amp})"