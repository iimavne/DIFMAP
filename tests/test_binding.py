import os
import pytest
import numpy as np
from astropy.io import fits
import difmap_native

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
    difmap_native.select("RR")  # Stokes I, comme le FITS par défaut
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