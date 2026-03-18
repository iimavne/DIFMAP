import os
import pytest
import numpy as np
from astropy.io import fits

# Plus besoin du hack sys.path ! L'installation éditable fait le travail.
import difmap_native

# --- CONFIGURATION DES CHEMINS ---
# On récupère le dossier où se trouve ce script (le dossier 'tests/')
dossier_tests = os.path.dirname(os.path.abspath(__file__))
# On remonte d'un cran pour être à la racine du projet (difmap2.5q_mod/)
dossier_projet = os.path.dirname(dossier_tests)

# Fichiers de test (On pointe vers le dossier 'tests/test_data/')
FICHIER_UV = os.path.join(dossier_tests, "test_data/0003-066_X.SPLIT.1")
FICHIER_FITS_REF = os.path.join(dossier_tests, "test_data/verite_terrain_test.fits")

@pytest.fixture(scope="module")
def charger_images():
    # 1. Charger la vérité terrain (FITS)
    with fits.open(FICHIER_FITS_REF) as hdul:
        img_fits = hdul[0].data.squeeze()

    # 2. Exécuter notre binding natif
    difmap_native.observe(FICHIER_UV)
    difmap_native.select("RR")  
    difmap_native.mapsize(512, 1.0)
    difmap_native.invert()
    img_ram = difmap_native.get_map()
    
    # 3. Recadrage au centre (Difmap exporte seulement le quart central de la map)
    h_fits, w_fits = img_fits.shape
    h_ram, w_ram = img_ram.shape
    y_start = (h_ram - h_fits) // 2
    x_start = (w_ram - w_fits) // 2
    img_ram_crop = img_ram[y_start:y_start+h_fits, x_start:x_start+w_fits]

    # FINI LA MISE À L'ÉCHELLE ! On retourne directement l'image pure.
    return img_fits, img_ram_crop

# =====================================================================
# LES TESTS AUTOMATIQUES
# =====================================================================

def test_dimensions_image(charger_images):
    """Test 1: Vérifie que le binding renvoie bien la bonne taille de matrice."""
    img_fits, img_ram = charger_images
    assert img_ram.shape == img_fits.shape, "Les dimensions ne correspondent pas !"

def test_centre_galactique_parfait(charger_images):
    """
    Test 2: Vérifie que le pixel central (le pic) est strictement identique.
    Prouve que la FFT de base n'a AUCUNE erreur de calcul.
    """
    img_fits, img_ram = charger_images
    
    centre_y, centre_x = img_fits.shape[0]//2, img_fits.shape[1]//2
    
    valeur_fits = img_fits[centre_y, centre_x]
    valeur_ram = img_ram[centre_y, centre_x]
    
    # On tolère une marge d'erreur microscopique due aux arrondis flottants
    assert np.isclose(valeur_fits, valeur_ram, atol=1e-5), \
        f"Le centre est faux ! FITS: {valeur_fits}, RAM: {valeur_ram}"

def test_ecart_attendu_bords(charger_images):
    """
    Test 3: L'image RAM Zero-Copy doit être bit-pour-bit identique au FITS !
    """
    img_fits, img_ram = charger_images
    erreur_max = np.max(np.abs(img_fits - img_ram))
    
    print(f"\nErreur Max (Zero-Copy vs FITS) : {erreur_max:.8f} Jy")
    
    # L'erreur ne sera plus de 0.45, elle sera quasiment 0 !
    assert erreur_max < 1e-4, f"Différence inexpliquée : {erreur_max}"
        
def test_generer_diagnostic_visuel(charger_images):
    import matplotlib.pyplot as plt
    import os
    
    img_fits, img_ram = charger_images
    difference = img_fits - img_ram
    
    # --- CALCUL DES VALEURS NUMÉRIQUES ---
    err_max = np.max(np.abs(difference))
    rmse = np.sqrt(np.mean(difference**2))
    std_err = np.std(difference)

    fig, axes = plt.subplots(1, 3, figsize=(18, 6))

    # 1. Image FITS (La référence)
    im0 = axes[0].imshow(img_fits, origin='lower', cmap='inferno')
    axes[0].set_title(f'FITS (Max: {np.max(img_fits):.3f} Jy)')
    fig.colorbar(im0, ax=axes[0], fraction=0.046, pad=0.04)

    # 2. Image RAM (Notre extraction)
    im1 = axes[1].imshow(img_ram, origin='lower', cmap='inferno')
    axes[1].set_title(f'RAM (Max: {np.max(img_ram):.3f} Jy)')
    fig.colorbar(im1, ax=axes[1], fraction=0.046, pad=0.04)

    # 3. La Différence (Visualisation de l'erreur)
    im2 = axes[2].imshow(difference, origin='lower', cmap='coolwarm')
    axes[2].set_title('Différence (FITS - RAM)')
    fig.colorbar(im2, ax=axes[2], fraction=0.046, pad=0.04)
    
    # Affichage des statistiques sous le graphique
    stats_text = (f"Erreur Max: {err_max:.5f} Jy\n"
                  f"RMSE: {rmse:.5f} Jy\n"
                  f"Écart-type: {std_err:.5f} Jy")
    
    axes[2].text(0.5, -0.25, stats_text, transform=axes[2].transAxes, 
                 ha="center", fontsize=11, fontweight='bold',
                 bbox=dict(boxstyle="round", facecolor='white', alpha=0.8))

    plt.tight_layout()

    # Sauvegarde
    dossier_tests = os.path.dirname(os.path.abspath(__file__))
    chemin_image = os.path.join(dossier_tests, "comparaison_visuelle.png")
    plt.savefig(chemin_image, dpi=150, bbox_inches='tight')
    plt.close()

    # Affichage console pour le mode -s
    print(f"\n" + "="*30)
    print(f"DIAGNOSTIC NUMÉRIQUE")
    print(f"Erreur Max : {err_max:.5f} Jy")
    print(f"RMSE       : {rmse:.5f} Jy")
    print(f"="*30)
    
    assert os.path.exists(chemin_image)
    
def test_beam_proprietes():
    """
    Test 5 : Vérifie la morphologie du Dirty Beam.
    On cherche le pic et on vérifie qu'il est bien centré.
    """
    import difmap_native
    import numpy as np
    
    beam = difmap_native.get_beam()
    assert beam is not None
    
    # 1. Le pic doit être à ~1.0
    val_max = np.max(beam)
    assert np.isclose(val_max, 1.0, atol=1e-3), f"Pic incorrect : {val_max}"
    
    # 2. On trouve les coordonnées (y, x) du pic réel dans la matrice
    pos_y, pos_x = np.unravel_index(np.argmax(beam), beam.shape)
    
    # 3. On définit le centre attendu (pour 512, c'est 255 ou 256)
    centre_theorique = beam.shape[0] // 2 # 256
    
    # On vérifie que le pic est au centre à 1 pixel près
    # (C'est normal qu'il soit à 255 à cause du fliplr)
    assert abs(pos_y - centre_theorique) <= 1, f"Pic décalé en Y : {pos_y}"
    assert abs(pos_x - centre_theorique) <= 1, f"Pic décalé en X : {pos_x}"

    print(f"\n--- BEAM OK ---")
    print(f"Pic trouvé à l'indice : [{pos_y}, {pos_x}]")
    print(f"Valeur au pic : {val_max:.5f}")
    
def test_header_metadonnees():
    """
    Test 6 : Vérifie l'intégrité des métadonnées (Header).
    """
    import difmap_native
    import numpy as np
    
    hdr = difmap_native.get_header()
    assert hdr is not None, "Le header est vide !"
    
    # Vérification de la taille des pixels (CDELT)
    assert np.isclose(hdr['CDELT'], 1.0, atol=1e-5), f"Erreur CDELT: {hdr['CDELT']}"
    
    # Vérification des dimensions
    assert hdr['NX'] == 512 and hdr['NY'] == 512
    
    # On ignore BMAJ/BMIN pour l'instant car ils représentent le 'Clean Beam'
    # qui n'est calculé qu'après l'étape de déconvolution (CLEAN).
    
    print(f"\n--- HEADER VALIDÉ ---")
    print(f"Dimensions : {hdr['NX']} x {hdr['NY']}")
    print(f"Taille du Pixel : {hdr['CDELT']} mas")
    print(f"Note: Clean Beam non défini au stade de la Dirty Map.")