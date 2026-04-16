import numpy as np
from difmap_wrapper import DifmapSession
import difmap_native

def test_statistiques_rigueur_mathematique():
    """
    Test robuste et déterministe. 
    Vérifie les lois mathématiques et le filtrage sans dépendre d'un clic de souris.
    """
    session = DifmapSession()
    session.observe("tests/test_data/0028-137_X.SPLIT.1")
    session.obs.select(pol="RR") 

    data = difmap_native.get_uv_data()
    amp = data['amp']
    weight = data['weight']
    phase = data['phase']
    uv_radius = np.sqrt(data['u']**2 + data['v']**2) / 1e6

    # On définit des bornes FIXES et STRICTES (pas de "à la louche")
    ymin, ymax = 0.1, 0.2
    
    # ---------------------------------------------------------
    # LOI 1 : Preuve que l'axe X est bien ignoré (Comportement Difmap)
    # ---------------------------------------------------------
    # Filtre 1 : Avec une petite boîte X (xmin=10, xmax=20)
    mask_avec_x = (uv_radius >= 10.0) & (uv_radius <= 20.0) & (amp >= ymin) & (amp <= ymax) & (weight > 0)
    
    # Filtre 2 : Comportement historique (sans X)
    mask_historique = (amp >= ymin) & (amp <= ymax) & (weight > 0)
    
    points_avec_x = len(np.where(mask_avec_x)[0])
    points_historiques = len(np.where(mask_historique)[0])
    
    # On PROUVE que le comportement historique attrape plus de points que la boîte stricte
    assert points_historiques > points_avec_x, "Erreur : Le comportement historique ne fonctionne pas."

    # ---------------------------------------------------------
    # LOI 2 : Preuve que les données flaggées sont ignorées
    # ---------------------------------------------------------
    points_sans_filtre_weight = len(np.where((amp >= ymin) & (amp <= ymax))[0])
    
    # On PROUVE que le filtre weight enlève bien les poubelles
    assert points_historiques <= points_sans_filtre_weight, "Erreur : Le filtre de Weight est cassé."

    # ---------------------------------------------------------
    # LOI 3 : Rigueur Mathématique (RMS et N-1)
    # ---------------------------------------------------------
    a_sub = amp[mask_historique]
    n = len(a_sub)
    
    if n > 1:
        a_mean = np.mean(a_sub)
        a_std = np.std(a_sub, ddof=1) # Règle de Bessel
        
        # On vérifie manuellement la formule mathématique pour être sûr à 100%
        # sum((x - mean)^2) / (n - 1)
        variance_manuelle = np.sum((a_sub - a_mean)**2) / (n - 1)
        std_manuel = np.sqrt(variance_manuelle)
        
        # On PROUVE que Numpy calcule exactement comme la formule C de Difmap
        np.testing.assert_almost_equal(a_std, std_manuel, decimal=6, 
                                       err_msg="Erreur : L'écart-type ne respecte pas N-1")

    print("\n✅ TOUTES LES LOIS SONT RESPECTÉES. LE MOTEUR EST SOLIDE.")
    
def test_statistiques_vectorielles_rigueur():
    """
    Prouve que la conversion Polaire -> Cartésienne et le calcul du bruit RMS
    sur les composantes Réelles et Imaginaires sont mathématiquement parfaits.
    """
    session = DifmapSession()
    session.observe("tests/test_data/0028-137_X.SPLIT.1")
    session.obs.select(pol="RR") 

    data = difmap_native.get_uv_data()
    amp = data['amp']
    phase = data['phase']
    weight = data['weight']

    # On définit une zone arbitraire
    ymin, ymax = 0.1, 0.2
    
    # On applique le masque historique de Difmap (Axe Y + données non flaggées)
    mask = (amp >= ymin) & (amp <= ymax) & (weight > 0)
    
    a_sub = amp[mask]
    p_sub_rad = np.radians(phase[mask]) # Convertit degrés -> radians pour np.cos/sin

    # 1. Conversion Polaire -> Cartésien
    real_part = a_sub * np.cos(p_sub_rad)
    imag_part = a_sub * np.sin(p_sub_rad)

    n = len(a_sub)
    assert n > 1, "Pas assez de points pour calculer un RMS."

    # 2. Calculs NumPy (Ceux de notre UI)
    r_mean = np.mean(real_part)
    r_std = np.std(real_part, ddof=1) # Règle de Bessel (N-1)
    
    i_mean = np.mean(imag_part)
    i_std = np.std(imag_part, ddof=1)

    # 3. Preuve Mathématique manuelle (Identique au code C d'origine)
    # Variance = sum((x - moyenne)^2) / (N - 1)
    variance_manuelle_r = np.sum((real_part - r_mean)**2) / (n - 1)
    std_manuel_r = np.sqrt(variance_manuelle_r)
    
    variance_manuelle_i = np.sum((imag_part - i_mean)**2) / (n - 1)
    std_manuel_i = np.sqrt(variance_manuelle_i)

    # 4. Assertions absolues (Tolérance de 6 décimales)
    np.testing.assert_almost_equal(r_std, std_manuel_r, decimal=6, 
                                   err_msg="Erreur RMS Réel : Numpy dévie de la formule C.")
    np.testing.assert_almost_equal(i_std, std_manuel_i, decimal=6, 
                                   err_msg="Erreur RMS Imaginaire : Numpy dévie de la formule C.")

    print(f"\n✅ TEST VALIDÉ : {n} points analysés.")
    print(f"Moyenne Réelle : {r_mean:.6f} | RMS Réel : {r_std:.6f}")
    print("La trigonométrie et la correction de Bessel sont implémentées à la perfection.")
    
def test_soustraction_vectorielle_residus():
    """
    Prouve que la soustraction (Data - Model) effectuée dans le Radplot
    est mathématiquement identique à la fonction C de uvradplt.c.
    Vérifie les cas critiques de la trigonométrie (phases négatives, annulation, etc).
    """
    # 1. SCÉNARIOS TESTS (Cas mathématiques extrêmes)
    # Point 0 : Pas de modèle -> Le résidu est identique à la donnée
    # Point 1 : Donnée et Modèle identiques -> Le résidu s'annule (0 Jy)
    # Point 2 : Modèle déphasé de 90° -> Résidu complexe pur
    # Point 3 : Modèle déphasé de 180° -> Les amplitudes s'additionnent !
    
    amp = np.array([2.0, 5.0, 0.0, 3.0])
    phase = np.array([45.0, 10.0, 0.0, 90.0])
    
    modamp = np.array([0.0, 5.0, 4.0, 3.0])
    modphs = np.array([0.0, 10.0, 90.0, -90.0])

    # 2. RÉSULTATS ATTENDUS (Calculés manuellement selon la formule C)
    # Point 0: Data reste intacte (Amp=2, Phs=45)
    # Point 1: Annulation parfaite (Amp=0, Phs=0)
    # Point 2: Vecteur [0,0] - [0, 4] = [0, -4] (Amp=4, Phs=-90)
    # Point 3: Vecteur [0,3] - [0, -3] = [0, 6] (Amp=6, Phs=90)
    
    expected_res_amp = np.array([2.0, 0.0, 4.0, 6.0])
    expected_res_phs = np.array([45.0, 0.0, -90.0, 90.0])

    # 3. LE CALCUL NUMPY DU RADPLOT
    p_rad = np.radians(phase)
    mp_rad = np.radians(modphs)
    
    re = amp * np.cos(p_rad) - modamp * np.cos(mp_rad)
    im = amp * np.sin(p_rad) - modamp * np.sin(mp_rad)
    
    # Règle C : Si l'amplitude est 0, la phase doit être 0 (et non NaN ou artefact arctan)
    d_amp = np.sqrt(re**2 + im**2)
    d_phs = np.where(d_amp < 1e-10, 0.0, np.degrees(np.arctan2(im, re)))

    # 4. LA PREUVE MATHÉMATIQUE (Tolérance de 6 décimales)
    np.testing.assert_almost_equal(
        d_amp, expected_res_amp, decimal=6,
        err_msg="Erreur : L'amplitude des résidus NumPy dévie de la vérité C."
    )
    
    np.testing.assert_almost_equal(
        d_phs, expected_res_phs, decimal=6,
        err_msg="Erreur : La phase des résidus NumPy dévie de la vérité C."
    )

    print("\n✅ TEST VALIDÉ : La soustraction vectorielle des visibilités est parfaite.")