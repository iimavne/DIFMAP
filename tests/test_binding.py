import os
import subprocess as sp
from matplotlib import pyplot as plt
import pytest
import numpy as np
from astropy.io import fits
import difmap_native
from difmap_wrapper.session import DifmapSession
from difmap_wrapper import standardizer

# =====================================================================
# CONFIGURATION DES CHEMINS ET DES DONNÉES DE TEST
# =====================================================================

dossier_tests = os.path.dirname(os.path.abspath(__file__))

DATASETS = [
    ("0003-066_X.SPLIT.1", "verite_terrain_test.fits"),
    ("0017+200_X.SPLIT.1", "test_wrapper_strict.fits"),
]

# =====================================================================
# LA FIXTURE
# =====================================================================

@pytest.fixture(scope="function", params=DATASETS, ids=[d[0] for d in DATASETS])
def charger_images(request):
    nom_uv, nom_fits = request.param
    chemin_uv = os.path.join(dossier_tests, "test_data", nom_uv)
    chemin_fits = os.path.join(dossier_tests, "test_data", nom_fits)
    
    # 1. On charge la vérité terrain
    with fits.open(chemin_fits) as hdul:
        img_fits = hdul[0].data.squeeze()

    # 2. On utilise la Session et l'Imager proprement !
    with DifmapSession() as session:
        session.observe(chemin_uv)
        difmap_native.select("RR", 1, 0, 1, 0)
        difmap_native.mapsize(512, 1.0)
        difmap_native.invert()
        
        # L'intelligence est encapsulée, le test est propre :
        img_ram_crop = session.imager.get_cropped_map(target_shape=img_fits.shape)

    return nom_uv, img_fits, img_ram_crop


# =====================================================================
# LES TESTS AUTOMATIQUES (Image, Beam, et Métadonnées)
# =====================================================================

def test_dimensions_image(charger_images):
    nom_uv, img_fits, img_ram = charger_images
    assert img_ram.shape == img_fits.shape, "Les dimensions ne correspondent pas !"

def test_validation_dirty_map_visuelle(charger_images):
    """
    Vérifie la Dirty Map sur l'ensemble de ses pixels (centre et bords) 
    via l'outil de comparaison métier, et génère le diagnostic visuel.
    """
    nom_uv, img_fits, img_ram = charger_images
    
    # 1. Appel Métier : on laisse le standardizer faire les maths
    metrics = standardizer.compare_images(img_fits, img_ram)
    diff_map = metrics['diff_map']

    # 2. Assertions scientifiques
    # Si l'erreur max globale est inférieure à 1e-4, alors le centre et les bords sont justes !
    assert metrics['err_max'] < 1e-4, f"L'image RAM dévie de la vérité FITS de {metrics['err_max']} Jy"

    # 3. Tracé du graphique (Génération du rapport visuel)
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    fig.suptitle(f"Diagnostic RAM vs FITS : {nom_uv}", fontsize=16, fontweight='bold')

    im0 = axes[0].imshow(img_fits, origin='lower', cmap='inferno')
    axes[0].set_title(f'FITS (Max: {np.max(img_fits):.3f} Jy)')
    fig.colorbar(im0, ax=axes[0], fraction=0.046, pad=0.04)

    im1 = axes[1].imshow(img_ram, origin='lower', cmap='inferno')
    axes[1].set_title(f'RAM (Max: {np.max(img_ram):.3f} Jy)')
    fig.colorbar(im1, ax=axes[1], fraction=0.046, pad=0.04)

    im2 = axes[2].imshow(diff_map, origin='lower', cmap='coolwarm')
    axes[2].set_title('Différence (FITS - RAM)')
    fig.colorbar(im2, ax=axes[2], fraction=0.046, pad=0.04)
    
    stats_text = f"Erreur Max: {metrics['err_max']:.5f} Jy\nRMSE: {metrics['rmse']:.5f} Jy\nÉcart-type: {metrics['std_err']:.5f} Jy"
    axes[2].text(0.5, -0.25, stats_text, transform=axes[2].transAxes, 
                 ha="center", fontsize=11, fontweight='bold',
                 bbox=dict(boxstyle="round", facecolor='white', alpha=0.8))

    plt.tight_layout()
    chemin_image = os.path.join(dossier_tests, f"comparaison_visuelle_{nom_uv.replace('.SPLIT.1', '')}.png")
    plt.savefig(chemin_image, dpi=150, bbox_inches='tight')
    plt.close()
    
def test_beam_proprietes(charger_images):
    nom_uv, _, _ = charger_images 
    chemin_uv = os.path.join(dossier_tests, "test_data", nom_uv)
    
    with DifmapSession() as session:
        session.observe(chemin_uv)
        difmap_native.select("RR", 1, 0, 1, 0)
        difmap_native.mapsize(512, 1.0)
        difmap_native.invert()
        beam = difmap_native.get_beam()
        
    assert beam is not None
    assert np.isclose(np.max(beam), 1.0, atol=1e-3)

def test_header_metadonnees(charger_images):
    nom_uv, _, _ = charger_images
    chemin_uv = os.path.join(dossier_tests, "test_data", nom_uv)
    
    with DifmapSession() as session:
        session.observe(chemin_uv)
        difmap_native.select("RR", 1, 0, 1, 0)
        difmap_native.mapsize(512, 1.0)
        hdr = difmap_native.get_header()
        
    assert hdr['NX'] == 512 and hdr['NY'] == 512
    
def test_extract_uv_zero_copy(charger_images):
    nom_uv, _, _ = charger_images
    chemin_uv = os.path.join(dossier_tests, "test_data", nom_uv)
    
    with DifmapSession() as session:
        session.observe(chemin_uv)
        difmap_native.select("RR", 1, 0, 1, 0)
        data = difmap_native.get_uv_data()
    
    assert isinstance(data, dict)
    assert 'u' in data
    assert len(data['u']) > 0

# =====================================================================
# TESTS UV DE DIAGNOSTIC (Les Mathématiques & Les 3 Panneaux)
# =====================================================================

def test_validation_stricte_astropy(charger_images, tmp_path):
    """
    Vérifie que l'extraction RAM Zéro-Copie récupère exactement le même 
    nombre de points valides (non-flaggués) que l'extraction FITS standardisée.
    """
    nom_uv, _, _ = charger_images
    chemin_uv = os.path.join(dossier_tests, "test_data", nom_uv)
    fits_temp = str(tmp_path / "reference_auto.fits")
    
    # 1. Arrange & Act (Préparation via la Session)
    with DifmapSession() as session:
        session.observe(chemin_uv)
        difmap_native.select("RR", 1, 0, 1, 0)
        difmap_native.wfits(fits_temp) 
        data_ram = standardizer.extract_ram_standardized()
        
    # 2. Extraction via l'outil métier (qui filtre automatiquement les poids > 0)
    data_fits = standardizer.extract_uvfits_standardized(fits_temp)
    
    # 3. Assert
    assert len(data_ram['u']) == len(data_fits['u']), \
        f"Déséquilibre : RAM={len(data_ram['u'])} vs FITS={len(data_fits['u'])}"
        
def test_tests_diff_difmap_visuel(charger_images):
    """Test de l'amplitude (radplot) en utilisant l'API d'ingénierie."""
    nom_uv, _, _ = charger_images
    chemin_uv = os.path.join(dossier_tests, "test_data", nom_uv)
    nom_base = nom_uv.replace('.SPLIT.1', '')
    fits_temp = f"diff_amp_{nom_base}.fits"

    # 1. Extraction propre via le module de validation
    with DifmapSession() as session:
        session.observe(chemin_uv)
        difmap_native.select("RR", 1, 0, 1, 0)
        difmap_native.wfits(fits_temp)
        data_ram = standardizer.extract_ram_standardized()

    data_fits = standardizer.extract_uvfits_standardized(fits_temp)

    # 2. Appel métier pour extraire toutes les statistiques et les résidus d'un coup
    metrics = standardizer.compare_uv_datasets(data_fits, data_ram)

    print(f"\n\n{'='*75}")
    print(f"📊 TABLEAU COMPARATIF RADPLOT (AMPLITUDE) : {nom_base}")
    print(f"{'='*75}")
    print(f"{'Métrique':<15} | Erreur Max: {metrics['delta_amp_max']:.2e} Jy | RMSE: {metrics['amp_rmse']:.2e} Jy")
    print(f"{'='*75}")

    # --- Tracé du graphique ---
    fig, axes = plt.subplots(1, 3, figsize=(20, 6))
    fig.suptitle(f"Diagnostic Amplitude : {nom_base}", fontsize=16, fontweight='bold')
    
    # On utilise directement le rayon pré-calculé par le standardizer !
    r_w = data_ram['uv_radius']
    diff_amp = metrics['diff_amp']
    
    axes[0].scatter(r_w, data_fits['amp'], s=0.5, color='black', alpha=0.5)
    axes[0].set_title("1. FITS (Vérité Terrain)")
    axes[0].set_ylabel("Amplitude (Jy)")

    axes[1].scatter(r_w, data_ram['amp'], s=0.5, color='blue', alpha=0.5)
    axes[1].set_title("2. RAM (Zéro-Copie)")

    sc2 = axes[2].scatter(r_w, diff_amp, s=2, c=diff_amp, cmap='coolwarm', vmin=-1e-6, vmax=1e-6)
    axes[2].set_title("3. Résidus (RAM - FITS)")
    axes[2].axhline(0, color='black', linestyle='--')
    axes[2].set_ylim(-2e-6, 2e-6) # Borné volontairement à l'erreur float32
    fig.colorbar(sc2, ax=axes[2], label="Erreur (Jy)")

    for ax in axes:
        ax.set_xlabel(r"Rayon UV (M$\lambda$)")
        ax.grid(True, linestyle=':', alpha=0.6)

    plt.tight_layout()
    plt.savefig(os.path.join(dossier_tests, f"diag_3d_amp_{nom_base}.png"), dpi=150)
    plt.close()

    # Tolérance fixée à la limite de précision des flottants 32 bits
    assert metrics['delta_amp_max'] < 1e-4, f"Divergence d'amplitude : {metrics['delta_amp_max']}"
    
    if os.path.exists(fits_temp): 
        os.remove(fits_temp)
        
def test_tests_diff_uvplot_visuel(charger_images):
    """
    Test de la géométrie (uvplot) en utilisant l'API d'ingénierie.
    Génère les graphiques spatiaux et vérifie l'erreur de quantification float32.
    """
    nom_uv, _, _ = charger_images
    chemin_uv = os.path.join(dossier_tests, "test_data", nom_uv)
    nom_base = nom_uv.replace('.SPLIT.1', '')
    fits_temp = f"diff_uv_{nom_base}.fits"

    # 1. Arrange & Act (Extraction propre via le module de validation)
    with DifmapSession() as session:
        session.observe(chemin_uv)
        difmap_native.select("RR", 1, 0, 1, 0)
        difmap_native.wfits(fits_temp)
        data_ram = standardizer.extract_ram_standardized()

    data_fits = standardizer.extract_uvfits_standardized(fits_temp)

    # 2. Appel métier pour extraire les métriques et les résidus
    metrics = standardizer.compare_uv_datasets(data_fits, data_ram)

    # On récupère les tableaux de différences pré-calculés
    diff_u = metrics['diff_u']

    print(f"\n\n{'='*75}")
    print(f"🌍 TABLEAU COMPARATIF UVPLOT (GEOMETRIE) : {nom_base}")
    print(f"{'='*75}")
    print(f"{'Métrique':<15} | ΔU Max: {metrics['delta_u_max']:.2e} λ | ΔV Max: {metrics['delta_v_max']:.2e} λ")
    print(f"{'='*75}")

    # 3. Tracé du graphique
    fig, axes = plt.subplots(1, 3, figsize=(20, 6))
    fig.suptitle(f"Diagnostic UVPLOT : {nom_base}", fontsize=16, fontweight='bold')
    
    axes[0].scatter(data_fits['u']/1e6, data_fits['v']/1e6, s=0.3, color='black', alpha=0.5)
    axes[0].set_title("1. FITS (Vérité Terrain)")
    
    axes[1].scatter(data_ram['u']/1e6, data_ram['v']/1e6, s=0.3, color='blue', alpha=0.5)
    axes[1].set_title("2. RAM (Zéro-Copie)")

    for ax in axes[:2]:
        ax.set_ylabel(r"V ($M\lambda$)")
        ax.axis('equal')
        ax.invert_xaxis()

    sc2 = axes[2].scatter(data_ram['u']/1e6, diff_u, s=2, c=diff_u, cmap='coolwarm', vmin=-0.05, vmax=0.05)
    axes[2].set_title("3. Résidus sur l'axe U")
    axes[2].axhline(0, color='black', linestyle='--')
    axes[2].set_ylabel(r"Erreur U ($\lambda$ brutes)")
    fig.colorbar(sc2, ax=axes[2], label=r"Erreur U ($\lambda$)")

    for ax in axes:
        ax.set_xlabel(r"U ($M\lambda$)")
        ax.grid(True, linestyle=':', alpha=0.6)

    plt.tight_layout()
    plt.savefig(os.path.join(dossier_tests, f"diag_3d_uvplot_{nom_base}.png"), dpi=150)
    plt.close()

    # 4. Assert : Tolérance fixée à la limite de précision des flottants 32 bits (~50 lambda sur 300 millions)
    assert metrics['delta_u_max'] < 50.0, f"Erreur de géométrie anormale sur U : {metrics['delta_u_max']}"
    assert metrics['delta_v_max'] < 50.0, f"Erreur de géométrie anormale sur V : {metrics['delta_v_max']}"

    if os.path.exists(fits_temp): 
        os.remove(fits_temp)