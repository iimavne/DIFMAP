from asyncio import subprocess
import os
from matplotlib import pyplot as plt
import pytest
import numpy as np
from astropy.io import fits
import subprocess as sp
import difmap_native
from difmap_wrapper.session import DifmapSession

# =====================================================================
# CONFIGURATION DES CHEMINS ET DES DONNÉES DE TEST
# =====================================================================

dossier_tests = os.path.dirname(os.path.abspath(__file__))

# AJOUTE des nouvelles données !
# Format : ("fichier_uv_source", "fichier_fits_de_reference_wdmap")
DATASETS = [
    ("0003-066_X.SPLIT.1", "verite_terrain_test.fits"),
    ("0017+200_X.SPLIT.1", "test_wrapper_strict.fits"),
    #("0028-137_X.SPLIT.1", "verite_terrain_test.fits")
    # ("ma_troisieme_galaxie.uvf", "ma_troisieme_verite.fits"),
]

# =====================================================================
# LA FIXTURE (Le moteur qui charge chaque dataset)
# =====================================================================

@pytest.fixture(scope="function", params=DATASETS, ids=[d[0] for d in DATASETS])
def charger_images(request):
    """
    Cette fixture est appelée avant chaque test, pour CHAQUE galaxie définie dans DATASETS.
    L'argument 'ids' permet d'avoir le nom de la galaxie dans les logs de pytest.
    """
    nom_uv, nom_fits = request.param
    chemin_uv = os.path.join(dossier_tests, "test_data", nom_uv)
    chemin_fits = os.path.join(dossier_tests, "test_data", nom_fits)
    
    # 1. Charger la vérité terrain (FITS)
    with fits.open(chemin_fits) as hdul:
        img_fits = hdul[0].data.squeeze()

    # 2. Exécuter notre binding natif
    difmap_native.observe(chemin_uv)
    difmap_native.select("RR", 1, 0, 1, 0)  # Stokes I, comme le FITS par défaut
    difmap_native.mapsize(512, 1.0)
    difmap_native.invert()
    img_ram = difmap_native.get_map()
    
    # 3. Recadrage au centre (Difmap exporte seulement le quart central de la map)
    h_fits, w_fits = img_fits.shape
    h_ram, w_ram = img_ram.shape
    y_start = (h_ram - h_fits) // 2
    x_start = (w_ram - w_fits) // 2
    img_ram_crop = img_ram[y_start:y_start+h_fits, x_start:x_start+w_fits]

    # On retourne aussi le nom UV pour pouvoir nommer les images PNG
    return nom_uv, img_fits, img_ram_crop


# =====================================================================
# LES TESTS AUTOMATIQUES (Exécutés sur chaque galaxie)
# =====================================================================

def test_dimensions_image(charger_images):
    nom_uv, img_fits, img_ram = charger_images
    assert img_ram.shape == img_fits.shape, "Les dimensions ne correspondent pas !"

def test_centre_galactique_parfait(charger_images):
    nom_uv, img_fits, img_ram = charger_images
    
    centre_y, centre_x = img_fits.shape[0]//2, img_fits.shape[1]//2
    
    valeur_fits = img_fits[centre_y, centre_x]
    valeur_ram = img_ram[centre_y, centre_x]
    
    assert np.isclose(valeur_fits, valeur_ram, atol=1e-5), \
        f"Le centre est faux pour {nom_uv}! FITS: {valeur_fits}, RAM: {valeur_ram}"

def test_ecart_attendu_bords(charger_images):
    nom_uv, img_fits, img_ram = charger_images
    erreur_max = np.max(np.abs(img_fits - img_ram))
    
    print(f"\n[{nom_uv}] Erreur Max (Zero-Copy vs FITS) : {erreur_max:.8f} Jy")
    assert erreur_max < 1e-4, f"Différence inexpliquée pour {nom_uv} : {erreur_max}"
        
def test_generer_diagnostic_visuel(charger_images):
    import matplotlib.pyplot as plt
    
    nom_uv, img_fits, img_ram = charger_images
    difference = img_fits - img_ram
    
    err_max = np.max(np.abs(difference))
    rmse = np.sqrt(np.mean(difference**2))
    std_err = np.std(difference)

    fig, axes = plt.subplots(1, 3, figsize=(18, 6))

    # Titre global avec le nom de la galaxie
    fig.suptitle(f"Diagnostic RAM vs FITS : {nom_uv}", fontsize=16, fontweight='bold')

    im0 = axes[0].imshow(img_fits, origin='lower', cmap='inferno')
    axes[0].set_title(f'FITS (Max: {np.max(img_fits):.3f} Jy)')
    fig.colorbar(im0, ax=axes[0], fraction=0.046, pad=0.04)

    im1 = axes[1].imshow(img_ram, origin='lower', cmap='inferno')
    axes[1].set_title(f'RAM (Max: {np.max(img_ram):.3f} Jy)')
    fig.colorbar(im1, ax=axes[1], fraction=0.046, pad=0.04)

    im2 = axes[2].imshow(difference, origin='lower', cmap='coolwarm')
    axes[2].set_title('Différence (FITS - RAM)')
    fig.colorbar(im2, ax=axes[2], fraction=0.046, pad=0.04)
    
    stats_text = (f"Erreur Max: {err_max:.5f} Jy\n"
                  f"RMSE: {rmse:.5f} Jy\n"
                  f"Écart-type: {std_err:.5f} Jy")
    
    axes[2].text(0.5, -0.25, stats_text, transform=axes[2].transAxes, 
                 ha="center", fontsize=11, fontweight='bold',
                 bbox=dict(boxstyle="round", facecolor='white', alpha=0.8))

    plt.tight_layout()

    # Sauvegarde UNIQUE par galaxie
    nom_fichier_png = f"comparaison_visuelle_{nom_uv.replace('.SPLIT.1', '')}.png"
    chemin_image = os.path.join(dossier_tests, nom_fichier_png)
    plt.savefig(chemin_image, dpi=150, bbox_inches='tight')
    plt.close()

    print(f"\n[{nom_uv}] Diagnostic sauvegardé : {nom_fichier_png}")
    assert os.path.exists(chemin_image)

def test_beam_proprietes(charger_images):
    # La fixture charge l'image en RAM, donc le beam est calculé !
    nom_uv, _, _ = charger_images 
    beam = difmap_native.get_beam()
    assert beam is not None
    
    val_max = np.max(beam)
    assert np.isclose(val_max, 1.0, atol=1e-3), f"Pic incorrect : {val_max}"
    
    pos_y, pos_x = np.unravel_index(np.argmax(beam), beam.shape)
    centre_theorique = beam.shape[0] // 2
    
    assert abs(pos_y - centre_theorique) <= 1, f"Pic décalé en Y : {pos_y}"
    assert abs(pos_x - centre_theorique) <= 1, f"Pic décalé en X : {pos_x}"

def test_header_metadonnees(charger_images):
    nom_uv, _, _ = charger_images
    hdr = difmap_native.get_header()
    assert hdr is not None, "Le header est vide !"
    assert np.isclose(hdr['CDELT'], 1.0, atol=1e-5), f"Erreur CDELT: {hdr['CDELT']}"
    assert hdr['NX'] == 512 and hdr['NY'] == 512
    
    
def test_extract_uv_zero_copy(charger_images):
    """Vérifie l'extraction Zéro-Copie complète (U, V, Amp, Wgt)."""
    nom_uv, _, _ = charger_images
    
    # Appel de la nouvelle fonction SOA
    data = difmap_native.get_uv_data()
    
    # Vérifications
    assert isinstance(data, dict), "L'extraction doit renvoyer un dictionnaire"
    for key in ['u', 'v', 'amp', 'weight']:
        assert key in data, f"Clé {key} manquante dans les données UV"
        assert isinstance(data[key], np.ndarray), f"{key} n'est pas un tableau Numpy"
    
    assert len(data['u']) > 0, "Le tableau est vide !"
    assert len(data['u']) == len(data['amp']), "Incohérence de taille entre U et Amplitude"
    
    print(f"\n[{nom_uv}] Succès SOA : {len(data['u'])} visibilités extraites.")
    
def test_validation_stricte_astropy(tmp_path):
    import numpy as np
    from astropy.io import fits
    from difmap_wrapper.session import DifmapSession
    import difmap_native

    mon_fichier_test = "tests/test_data/0017+200_X.SPLIT.1" 
    fits_temp = str(tmp_path / "reference_auto.fits")
    
    with DifmapSession() as session:
        session.observe(mon_fichier_test)
        difmap_native.wfits(fits_temp) 
        
        # 1. --- DONNÉES DU WRAPPER (RAM) ---
        data_ram = difmap_native.get_uv_data()
        nb_points_wrapper = len(data_ram['u'])
        
        # 2. --- DONNÉES DU FITS (Astropy) ---
        with fits.open(fits_temp) as hdul:
            data = hdul[0].data
            # Dans le format UVFITS, 'DATA' contient [Réel, Imaginaire, Poids]
            # On extrait uniquement la matrice des Poids (le 3ème élément, index 2)
            matrice_poids = data['DATA'][..., 2] 
            
            # On compte tous les poids qui sont strictement positifs (les données non-flagguées)
            nb_points_valides_fits = np.sum(matrice_poids > 0)
            
        # 3. --- LA PREUVE ABSOLUE ---
        print(f"\nPoints extraits par le Wrapper : {nb_points_wrapper}")
        print(f"Points valides cachés dans le FITS : {nb_points_valides_fits}")
        
        assert nb_points_wrapper == nb_points_valides_fits, \
            "Le nombre de points ne correspond pas !"
            
        print("✅ Preuve validée : Le Wrapper extrait EXACTEMENT les données valides du FITS !")

import subprocess as sp  # On lui donne le surnom 'sp' pour éviter tout conflit
import os

def generer_fits_via_executable(chemin_split, chemin_sortie_fits):
    DIFMAP_BIN = "/home/mahssini/Bureau/difmap2.5q_mod/builddir/difmap"
    
    if os.path.exists(chemin_sortie_fits):
        os.remove(chemin_sortie_fits)

    script_difmap = f"""
    observe "{chemin_split}"
    wfits "{chemin_sortie_fits}"
    quit
    """

    print("🤖 Lancement du vrai Difmap en arrière-plan...")
    
    # --- ON UTILISE L'ALIAS 'sp' ICI ---
    result = sp.run(
        [DIFMAP_BIN], 
        input=script_difmap, 
        text=True, 
        capture_output=True
    )

    if os.path.exists(chemin_sortie_fits):
        print(f"✅ Fichier {chemin_sortie_fits} généré avec succès par l'exécutable !")
    else:
        print("❌ Erreur de génération. Voici ce que Difmap a répondu :")
        print(result.stdout)
        print(result.stderr)

# --- UTILISATION ---
generer_fits_via_executable(
    chemin_split="tests/test_data/0017+200_X.SPLIT.1", 
    chemin_sortie_fits="reference_diag.fits"
)

def test_validation_strict_uv_data(tmp_path):

    REAL_FITS_FILE = "tests/test_data/0017+200_X.SPLIT.1"
    FITS_TEMP = "debug_difmap.fits"

    print("DÉMARRAGE DU DIAGNOSTIC CHIRURGICAL...")

    with DifmapSession() as session:
        session.observe(REAL_FITS_FILE)
        difmap_native.wfits(FITS_TEMP)
        
        # 1. Données du Wrapper
        uv_data = difmap_native.get_uv_data()
        u_wrap = uv_data['u']
        v_wrap = uv_data['v']
        amp_wrap = uv_data['amp']

    # 2. Données FITS (Astropy)
    with fits.open(FITS_TEMP) as hdul:
        data = hdul[0].data
        header = hdul[0].header
        
        freq_ref = header.get('CRVAL4', 1.0)
        print(f"\n Fréquence de référence lue dans le header : {freq_ref:.2e} Hz")
        
        # On prend juste la première ligne de base pour l'analyse
        u_fits = data['UU'] * freq_ref
        v_fits = data['VV'] * freq_ref
        
        # On tente d'extraire l'amplitude de la première IF et première pol
        try:
            reel = data['DATA'][:, 0, 0, 0, 0, 0]
            imag = data['DATA'][:, 0, 0, 0, 0, 1]
        except IndexError:
            reel = data['DATA'][..., 0].flatten()[:len(u_fits)]
            imag = data['DATA'][..., 1].flatten()[:len(u_fits)]
            
        amp_fits = np.sqrt(reel**2 + imag**2)

    # 3. ANALYSE STATISTIQUE COMPARATIVE
    print("\n" + "="*50)
    print(f"{'MÉTRIQUE':<15} | {'WRAPPER (RAM)':<15} | {'FITS (ASTROPY)':<15}")
    print("="*50)

    # Comparaison des U
    print(f"U min           | {np.min(u_wrap):<15.4e} | {np.min(u_fits):<15.4e}")
    print(f"U max           | {np.max(u_wrap):<15.4e} | {np.max(u_fits):<15.4e}")

    # Comparaison des V
    print(f"V min           | {np.min(v_wrap):<15.4e} | {np.min(v_fits):<15.4e}")
    print(f"V max           | {np.max(v_wrap):<15.4e} | {np.max(v_fits):<15.4e}")

    # Comparaison des Amplitudes
    print(f"Amp min         | {np.min(amp_wrap):<15.4f} | {np.min(amp_fits):<15.4f}")
    print(f"Amp max         | {np.max(amp_wrap):<15.4f} | {np.max(amp_fits):<15.4f}")
    print("="*50)

    # 4. CALCUL DU RATIO (Le facteur d'échelle manquant)
    ratio_u = np.max(np.abs(u_wrap)) / np.max(np.abs(u_fits))
    ratio_amp = np.mean(amp_wrap) / np.mean(amp_fits)

    print("\n RECHERCHE DE FACTEURS D'ÉCHELLE :")
    print(f"Différence d'échelle sur les UV : Le Wrapper est {ratio_u:.2e} fois plus grand/petit que le FITS.")
    print(f"Différence d'échelle sur l'Amp  : Le Wrapper est {ratio_amp:.2f} fois plus grand/petit que le FITS.")

    if os.path.exists(FITS_TEMP):
        os.remove(FITS_TEMP)

def test_tests_diff_difmap(charger_images):

    mon_fichier_test = "tests/test_data/0017+200_X.SPLIT.1" 
    fits_temp = "TESTTTTT.fits"

    # ==========================================
    # 1. EXTRACTION WRAPPER (LA CIBLE)
    # ==========================================
    with DifmapSession() as session:
        session.observe(mon_fichier_test)
        difmap_native.wfits(fits_temp)
        data_wrapper = difmap_native.get_uv_data()

    u_wrap = data_wrapper['u']
    v_wrap = data_wrapper['v']
    amp_wrap = data_wrapper['amp']

    # ==========================================
    # 2. EXTRACTION ASTROPY (LA RÉFÉRENCE PHYSIQUE)
    # ==========================================
    u_astro_list, v_astro_list, amp_astro_list = [], [], []

    with fits.open(fits_temp) as hdul:
        data = hdul[0].data
        header = hdul[0].header
        
        # Paramètres de fréquences du FITS pour calculer les IFs
        freq_ref = header['CRVAL4']
        freq_inc = header['CDELT4']
        ref_pix = header['CRPIX4']
        n_ifs = data['DATA'].shape[3]
        
        for if_idx in range(n_ifs):
            # Calcul de la vraie fréquence de l'IF actuel
            freq_if = freq_ref + (if_idx + 1 - ref_pix) * freq_inc
            
            # Coordonnées UV multipliées par CETTE fréquence
            u_if = data['UU'] * freq_if
            v_if = data['VV'] * freq_if
            
            # Amplitudes et Poids pour CETTE fréquence (1ère polarisation)
            # On isole les données de l'IF actuel
            # Le .squeeze() écrase tous les "axes fantômes" de taille 1 (Stokes, etc.)
            data_if = data['DATA'][:, 0, 0, if_idx].squeeze()
            
            # data_if est maintenant proprement réduit à (N_vis, 3) 
            # Les 3 dernières valeurs sont TOUJOURS : 0=Réel, 1=Imaginaire, 2=Poids
            reel = data_if[..., 0]
            imag = data_if[..., 1]
            poids = data_if[..., 2]
            
            # On jette les poubelles comme Difmap le fait
            masque = poids > 0
            
            u_astro_list.extend(u_if[masque])
            v_astro_list.extend(v_if[masque])
            amp_astro_list.extend(np.sqrt(reel**2 + imag**2)[masque])

    u_astro = np.array(u_astro_list)
    v_astro = np.array(v_astro_list)
    amp_astro = np.array(amp_astro_list)

    # ==========================================
    # 3. ALIGNEMENT (TRI) POUR SOUTRACTION
    # ==========================================
    print(f"Points Wrapper : {len(u_wrap)} | Points Astropy : {len(u_astro)}")

    # On trie les deux ensembles par U puis par V pour être sûr de comparer le même point
    idx_wrap = np.lexsort((v_wrap, u_wrap))
    idx_astro = np.lexsort((v_astro, u_astro))

    u_wrap_sorted = u_wrap[idx_wrap]
    v_wrap_sorted = v_wrap[idx_wrap]
    amp_wrap_sorted = amp_wrap[idx_wrap]

    u_astro_sorted = u_astro[idx_astro]
    v_astro_sorted = v_astro[idx_astro]
    amp_astro_sorted = amp_astro[idx_astro]

    # ==========================================
    # 4. LE CALCUL DE LA DIFFÉRENCE (RÉSIDUS)
    # ==========================================
    diff_u = u_wrap_sorted - u_astro_sorted
    diff_v = v_wrap_sorted - v_astro_sorted
    diff_amp = amp_wrap_sorted - amp_astro_sorted

    erreur_max_u = np.max(np.abs(diff_u))
    erreur_max_v = np.max(np.abs(diff_v))
    erreur_max_amp = np.max(np.abs(diff_amp))

    print("\n📊 RÉSULTAT DE LA SOUSTRACTION (ERREUR MAXIMALE) :")
    print(f"Différence max sur U : {erreur_max_u:.2e} longueurs d'onde")
    print(f"Différence max sur V : {erreur_max_v:.2e} longueurs d'onde")
    print(f"Différence max sur Amplitude : {erreur_max_amp:.2e} Jy")

def test_tests_diff_difmap_visuel(charger_images):
    import numpy as np
    import matplotlib.pyplot as plt
    import os
    from astropy.io import fits
    from difmap_wrapper.session import DifmapSession
    import difmap_native

    mon_fichier_test = "tests/test_data/0017+200_X.SPLIT.1"
    fits_temp = "diff_absolue_visu.fits"
    nom_base = "0017+200_X"

    # ==========================================
    # 1. EXTRACTION WRAPPER (LA CIBLE)
    # ==========================================
    with DifmapSession() as session:
        session.observe(mon_fichier_test)
        # On demande au moteur de Difmap d'écrire la vérité terrain officielle
        difmap_native.wfits(fits_temp)
        # On extrait la RAM de ton wrapper
        data_wrapper = difmap_native.get_uv_data()

    u_wrap = data_wrapper['u']
    v_wrap = data_wrapper['v']
    amp_wrap = data_wrapper['amp']

    # ==========================================
    # 2. EXTRACTION ASTROPY (LA RÉFÉRENCE PHYSIQUE)
    # ==========================================
    u_astro_list, v_astro_list, amp_astro_list = [], [], []

    # On utilise la méthode ROBUST "squeeze" qu'on a validée ensemble
    with fits.open(fits_temp) as hdul:
        data = hdul[0].data
        header = hdul[0].header
        freq_ref = header['CRVAL4']
        freq_inc = header['CDELT4']
        ref_pix = header['CRPIX4']
        n_ifs = data['DATA'].shape[3]
        
        for if_idx in range(n_ifs):
            freq_if = freq_ref + (if_idx + 1 - ref_pix) * freq_inc
            u_if = data['UU'] * freq_if
            v_if = data['VV'] * freq_if
            
            # --- NOUVEAU CODE ROBUSTE --- Isoler IF actuel et écraser axes fantômes
            data_if = data['DATA'][:, 0, 0, if_idx].squeeze()
            
            reel = data_if[..., 0]
            imag = data_if[..., 1]
            poids = data_if[..., 2]
            
            masque = poids > 0
            
            u_astro_list.extend(u_if[masque])
            v_astro_list.extend(v_if[masque])
            amp_astro_list.extend(np.sqrt(reel**2 + imag**2)[masque])

    u_astro = np.array(u_astro_list)
    v_astro = np.array(v_astro_list)
    amp_astro = np.array(amp_astro_list)

    # ==========================================
    # 3. ALIGNEMENT (TRI) POUR SOUTRACTION
    # ==========================================
    print(f"\n[{nom_base}] Points Wrapper : {len(u_wrap)} | Points Astropy : {len(u_astro)}")

    # On trie les deux ensembles par U puis par V pour être sûr de comparer le même point
    idx_wrap = np.lexsort((v_wrap, u_wrap))
    idx_astro = np.lexsort((v_astro, u_astro))

    u_wrap_sorted = u_wrap[idx_wrap]
    v_wrap_sorted = v_wrap[idx_wrap]
    amp_wrap_sorted = amp_wrap[idx_wrap]

    u_astro_sorted = u_astro[idx_astro]
    v_astro_sorted = v_astro[idx_astro]
    amp_astro_sorted = amp_astro[idx_astro]

    # ==========================================
    # 4. LE CALCUL DE LA DIFFÉRENCE ET VISU 3D
    # ==========================================
    # Résidus
    diff_amp = amp_wrap_sorted - amp_astro_sorted
    
    # Calcul du rayon UV pour le graphique
    rayon_astro_sorted = np.sqrt(u_astro_sorted**2 + v_astro_sorted**2)
    rayon_wrap_sorted = np.sqrt(u_wrap_sorted**2 + v_wrap_sorted**2)
    
    # Statistiques d'erreur
    erreur_max_amp = np.max(np.abs(diff_amp))
    rmse_amp = np.sqrt(np.mean(diff_amp**2))

    # --- GÉNÉRATION DU GRAPHIQUE 3 PANNEAUX ---
    # On convertit en Mégau-lambda pour l'affichage (plus lisible)
    facteur_echelle = 1e6

    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    fig.suptitle(f"Diagnostic Visuel UV (3 étapes) : {nom_base}", fontsize=16, fontweight='bold')

    # Panneau 1 : Référence (FITS) - EN ROUGE
    axes[0].scatter(rayon_astro_sorted / facteur_echelle, amp_astro_sorted, s=0.5, color='red', alpha=0.5)
    axes[0].set_title("1. Référence (FITS Officiel)")
    axes[0].set_ylabel("Amplitude (Jy)")
    axes[0].set_xlim(left=0)
    axes[0].set_ylim(bottom=0)
    axes[0].grid(True, linestyle=':', alpha=0.6)

    # Panneau 2 : Wrapper C (RAM) - EN BLEU
    axes[1].scatter(rayon_wrap_sorted / facteur_echelle, amp_wrap_sorted, s=0.5, color='blue', alpha=0.5)
    axes[1].set_title("2. Ton Wrapper C (RAM)")
    axes[1].set_xlim(left=0)
    axes[1].set_ylim(bottom=0)
    axes[1].grid(True, linestyle=':', alpha=0.6)

    # Panneau 3 : La Différence (RAM - FITS) - EN VERT
    # Utilisation d'une échelle "coolwarm" pour bien voir si ça oscille autour de zéro
    axes[2].scatter(rayon_wrap_sorted / facteur_echelle, diff_amp, s=1, color='green', alpha=0.7)
    axes[2].set_title("3. Différence (RAM - FITS)")
    axes[2].set_ylabel("Résidus Amplitude (Jy)")
    
    # On ajoute une ligne pointillée rouge à zéro
    axes[2].axhline(0, color='red', linestyle='--', linewidth=2)
    
    # On resserre l'échelle Y pour voir l'erreur microscopique (1e-6)
    axes[2].set_ylim(-2e-6, 2e-6) 
    axes[2].grid(True, linestyle=':', alpha=0.6)
    
    # Texte des stats
    stats_text = f"Erreur Max Amp: {erreur_max_amp:.1e} Jy\nRMSE: {rmse_amp:.1e} Jy"
    axes[2].text(0.5, -0.25, stats_text, transform=axes[2].transAxes, 
                 ha="center", fontsize=11, fontweight='bold',
                 bbox=dict(boxstyle="round", facecolor='white', alpha=0.8))

    # Libellé commun pour l'axe X
    for ax in axes:
        ax.set_xlabel(f"Rayon UV (M$\lambda$)")

    plt.tight_layout()

    # Sauvegarde
    nom_fichier_png = f"diagnostic_visuel_3d_uv_{nom_base}.png"
    chemin_image = os.path.join(dossier_tests, nom_fichier_png)
    plt.savefig(chemin_image, dpi=150, bbox_inches='tight')
    plt.close()

    print(f"\n📊 Image 3-D sauvegardée : {chemin_image}")
    
    # --- LES VERDICTS MATHÉMATIQUES (N'oublie pas de les garder !) ---
    # On tolère une erreur d'arrondi de float -> double
    atol_amp = 1e-6 
    
    assert np.allclose(amp_wrap_sorted, amp_astro_sorted, atol=atol_amp), \
        f"Les amplitudes diffèrent pour {nom_base}! Max Error: {erreur_max_amp:.2e}"
    assert np.allclose(u_wrap_sorted, u_astro_sorted, rtol=1e-5, atol=1e-5), \
        f"Incohérence physique détectée sur U pour {nom_base} !"

    print("✅ Preuve validée : Le Wrapper est identique au FITS physiquement et visuellement !")

    # Nettoyage
    if os.path.exists(fits_temp):
        os.remove(fits_temp)
def test_tests_diff_difmap_visuel(charger_images):
    import numpy as np
    import matplotlib.pyplot as plt
    import os
    from astropy.io import fits
    from difmap_wrapper.session import DifmapSession
    import difmap_native

    # --- RÉCUPÉRATION DYNAMIQUE VIA LA FIXTURE ---
    nom_uv, _, _ = charger_images
    mon_fichier_test = os.path.join(dossier_tests, "test_data", nom_uv)
    nom_base = nom_uv.replace('.SPLIT.1', '')
    fits_temp = f"diff_amp_{nom_base}.fits"

    # 1. Extraction Wrapper (RAM)
    with DifmapSession() as session:
        session.observe(mon_fichier_test)
        difmap_native.wfits(fits_temp)
        data_wrapper = difmap_native.get_uv_data()

    u_wrap, v_wrap, amp_wrap = data_wrapper['u'], data_wrapper['v'], data_wrapper['amp']

    # 2. Extraction Astropy INTERLAVÉE (Comme en C)
    with fits.open(fits_temp) as hdul:
        data = hdul[0].data
        h = hdul[0].header
        
        # Calcul de la grille de fréquences (Toutes les IFs)
        freqs = np.array([h['CRVAL4'] + (i + 1 - h['CRPIX4']) * h['CDELT4'] for i in range(data['DATA'].shape[3])])
        
        # Calcul UV et Amplitude sur toute la grille d'un coup
        # UU[:, None] * freqs[None, :] crée une matrice (Baselines x IFs)
        u_astro_2d = -(data['UU'][:, None] * freqs[None, :]) 
        v_astro_2d = data['VV'][:, None] * freqs[None, :]
        
        d_sq = data['DATA'].squeeze() # (N_baselines, N_IFs, 3)
        amp_astro_2d = np.sqrt(d_sq[..., 0]**2 + d_sq[..., 1]**2)
        poids_2d = d_sq[..., 2]

        # Aplatissement (Ordre C par défaut : Baseline par Baseline)
        u_astro = u_astro_2d.flatten()
        v_astro = v_astro_2d.flatten()
        amp_astro = amp_astro_2d.flatten()
        masque = poids_2d.flatten() > 0
        
        # On ne garde que les valides
        u_a, v_a, amp_a = u_astro[masque], v_astro[masque], amp_astro[masque]

    # 3. Comparaison (Sans tri ! L'ordre est déjà identique)
    diff_amp = amp_wrap - amp_a
    err_max = np.max(np.abs(diff_amp))

    # --- GÉNÉRATION DU GRAPHIQUE ---
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    fig.suptitle(f"Diagnostic Amplitude (3 étapes) : {nom_base}", fontsize=16)
    r_a = np.sqrt(u_a**2 + v_a**2) / 1e6
    r_w = np.sqrt(u_wrap**2 + v_wrap**2) / 1e6

    axes[0].scatter(r_a, amp_a, s=0.5, color='red')
    axes[1].scatter(r_w, amp_wrap, s=0.5, color='blue')
    axes[2].scatter(r_w, diff_amp, s=1, color='green')
    axes[2].set_ylim(-1e-6, 1e-6) # Zoom sur l'erreur
    
    plt.savefig(os.path.join(dossier_tests, f"diag_3d_amp_{nom_base}.png"))
    plt.close()

    assert np.allclose(amp_wrap, amp_a, atol=1e-5), f"Erreur sur {nom_base}: {err_max}"
    if os.path.exists(fits_temp): os.remove(fits_temp)


def test_tests_diff_uvplot_visuel(charger_images):
    import numpy as np
    import matplotlib.pyplot as plt
    import os
    from astropy.io import fits
    from difmap_wrapper.session import DifmapSession
    import difmap_native

    nom_uv, _, _ = charger_images
    mon_fichier_test = os.path.join(dossier_tests, "test_data", nom_uv)
    nom_base = nom_uv.replace('.SPLIT.1', '')
    fits_temp = f"diff_uv_{nom_base}.fits"

    with DifmapSession() as session:
        session.observe(mon_fichier_test)
        difmap_native.wfits(fits_temp)
        data_wrapper = difmap_native.get_uv_data()

    u_wrap, v_wrap = data_wrapper['u'], data_wrapper['v']

    with fits.open(fits_temp) as hdul:
        data = hdul[0].data
        h = hdul[0].header
        freqs = np.array([h['CRVAL4'] + (i + 1 - h['CRPIX4']) * h['CDELT4'] for i in range(data['DATA'].shape[3])])
        
        # --- LA CORRECTION EST ICI : signe "-" pour UU ---
        u_astro = -(data['UU'][:, None] * freqs[None, :]).flatten()
        v_astro = (data['VV'][:, None] * freqs[None, :]).flatten()
        poids = data['DATA'].squeeze()[..., 2].flatten()
        
        masque = poids > 0
        u_astro, v_astro = u_a[masque], v_a[masque]

    # Résidus
    diff_u = u_wrap - u_astro
    err_u = np.max(np.abs(diff_u))

    # --- GRAPH UV ---
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    fig.suptitle(f"Diagnostic UVPLOT (3 étapes) : {nom_base}", fontsize=16)
    axes[0].scatter(u_astro/1e6, v_astro/1e6, s=0.3, color='red')
    axes[1].scatter(u_wrap/1e6, v_wrap/1e6, s=0.3, color='blue')
    axes[2].scatter(u_wrap/1e6, diff_u, s=1, color='green')
    axes[2].set_ylim(-0.1, 0.1) # Erreur attendue proche de 0

    plt.savefig(os.path.join(dossier_tests, f"diag_3d_uv_{nom_base}.png"))
    plt.close()

    assert np.allclose(u_wrap, u_astro, atol=1e-3), f"Erreur UV sur {nom_base}: {err_u}"
    if os.path.exists(fits_temp): os.remove(fits_temp)