import os
import subprocess as sp
from matplotlib import pyplot as plt
import pytest
import numpy as np
from astropy.io import fits
import difmap_native
from difmap_wrapper.session import DifmapSession

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
    
    with fits.open(chemin_fits) as hdul:
        img_fits = hdul[0].data.squeeze()

    with DifmapSession() as session:
        session.observe(chemin_uv)
        difmap_native.select("RR", 1, 0, 1, 0)
        difmap_native.mapsize(512, 1.0)
        difmap_native.invert()
        img_ram = difmap_native.get_map()
    
    h_fits, w_fits = img_fits.shape
    h_ram, w_ram = img_ram.shape
    y_start = (h_ram - h_fits) // 2
    x_start = (w_ram - w_fits) // 2
    img_ram_crop = img_ram[y_start:y_start+h_fits, x_start:x_start+w_fits]

    return nom_uv, img_fits, img_ram_crop


# =====================================================================
# LES TESTS AUTOMATIQUES (Image, Beam, et Métadonnées)
# =====================================================================

def test_dimensions_image(charger_images):
    nom_uv, img_fits, img_ram = charger_images
    assert img_ram.shape == img_fits.shape, "Les dimensions ne correspondent pas !"

def test_centre_galactique_parfait(charger_images):
    nom_uv, img_fits, img_ram = charger_images
    centre_y, centre_x = img_fits.shape[0]//2, img_fits.shape[1]//2
    assert np.isclose(img_fits[centre_y, centre_x], img_ram[centre_y, centre_x], atol=1e-5)

def test_ecart_attendu_bords(charger_images):
    nom_uv, img_fits, img_ram = charger_images
    assert np.max(np.abs(img_fits - img_ram)) < 1e-4

def test_generer_diagnostic_visuel(charger_images):
    nom_uv, img_fits, img_ram = charger_images
    difference = img_fits - img_ram
    err_max = np.max(np.abs(difference))
    rmse = np.sqrt(np.mean(difference**2))
    std_err = np.std(difference)

    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
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
    
    stats_text = f"Erreur Max: {err_max:.5f} Jy\nRMSE: {rmse:.5f} Jy\nÉcart-type: {std_err:.5f} Jy"
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

def test_validation_stricte_astropy(charger_images, tmp_path):
    nom_uv, _, _ = charger_images
    chemin_uv = os.path.join(dossier_tests, "test_data", nom_uv)
    fits_temp = str(tmp_path / "reference_auto.fits")
    
    with DifmapSession() as session:
        session.observe(chemin_uv)
        difmap_native.select("RR", 1, 0, 1, 0)
        difmap_native.wfits(fits_temp) 
        data_ram = difmap_native.get_uv_data()
        
        with fits.open(fits_temp) as hdul:
            matrice_poids = hdul[0].data['DATA'][..., 2] 
            nb_points_valides_fits = np.sum(matrice_poids > 0)
            
        assert len(data_ram['u']) == nb_points_valides_fits

# =====================================================================
# TESTS UV DE DIAGNOSTIC (Les Mathématiques & Les 3 Panneaux)
# =====================================================================

def test_validation_strict_uv_data(charger_images):
    nom_uv, _, _ = charger_images
    chemin_uv = os.path.join(dossier_tests, "test_data", nom_uv)
    fits_temp = f"debug_difmap_{nom_uv.replace('.SPLIT.1', '')}.fits"

    with DifmapSession() as session:
        session.observe(chemin_uv)
        difmap_native.select("RR", 1, 0, 1, 0)
        difmap_native.wfits(fits_temp)
        uv_data = difmap_native.get_uv_data()

    with fits.open(fits_temp) as hdul:
        data, header = hdul[0].data, hdul[0].header
        freq_ref = header.get('CRVAL4', 1.0)
        u_fits = data['UU'] * freq_ref  # Le Signe est standard !
        d_sq = data['DATA'].squeeze()
        amp_fits = np.sqrt(d_sq[..., 0]**2 + d_sq[..., 1]**2).flatten()

    if os.path.exists(fits_temp): os.remove(fits_temp)

def test_tests_diff_difmap_visuel(charger_images):
    """Test de l'amplitude (radplot) avec la lecture secrète AIPS FQ."""
    nom_uv, _, _ = charger_images
    chemin_uv = os.path.join(dossier_tests, "test_data", nom_uv)
    nom_base = nom_uv.replace('.SPLIT.1', '')
    fits_temp = f"diff_amp_{nom_base}.fits"

    with DifmapSession() as session:
        session.observe(chemin_uv)
        difmap_native.select("RR", 1, 0, 1, 0)
        difmap_native.wfits(fits_temp)
        data_wrapper = difmap_native.get_uv_data()

    with fits.open(fits_temp) as hdul:
        d, h = hdul[0].data, hdul[0].header
        
        # LA VRAIE LECTURE DES FRÉQUENCES IF (La table FQ)
        fq_data = hdul['AIPS FQ'].data
        if_offsets = fq_data['IF FREQ'][0] 
        freqs = h['CRVAL4'] + if_offsets
        
        # UU et VV dans le même sens que la RAM
        u_astro_2d = d['UU'][:, None] * freqs[None, :]
        v_astro_2d = d['VV'][:, None] * freqs[None, :]
        
        d_sq = d['DATA'].squeeze()
        amp_astro_2d = np.sqrt(d_sq[..., 0]**2 + d_sq[..., 1]**2)
        masque = d_sq[..., 2] > 0
        
        u_a, v_a, amp_a = u_astro_2d[masque], v_astro_2d[masque], amp_astro_2d[masque]

    u_w, v_w, amp_w = data_wrapper['u'], data_wrapper['v'], data_wrapper['amp']

    # On trie pour aligner (Robuste car on utilise les mêmes fréquences)
    idx_w = np.lexsort((np.round(v_w).astype(np.int64), np.round(u_w).astype(np.int64)))
    idx_a = np.lexsort((np.round(v_a).astype(np.int64), np.round(u_a).astype(np.int64)))

    u_w_tri, v_w_tri, amp_w_tri = u_w[idx_w], v_w[idx_w], amp_w[idx_w]
    u_a_tri, v_a_tri, amp_a_tri = u_a[idx_a], v_a[idx_a], amp_a[idx_a]

    diff = amp_w_tri - amp_a_tri

    print(f"\n\n{'='*75}")
    print(f"TABLEAU COMPARATIF RADPLOT (AMPLITUDE) : {nom_base}")
    print(f"{'='*75}")
    print(f"{'Métrique':<15} | {'FITS (Référence)':<18} | {'RAM (Wrapper)':<18} | {'Différence'}")
    print(f"{'-'*75}")
    print(f"{'Minimum':<15} | {np.min(amp_a_tri):<15.5f} Jy | {np.min(amp_w_tri):<15.5f} Jy | {np.min(diff):.2e} Jy")
    print(f"{'Maximum':<15} | {np.max(amp_a_tri):<15.5f} Jy | {np.max(amp_w_tri):<15.5f} Jy | {np.max(diff):.2e} Jy")
    print(f"{'Moyenne':<15} | {np.mean(amp_a_tri):<15.5f} Jy | {np.mean(amp_w_tri):<15.5f} Jy | {np.mean(diff):.2e} Jy")
    print(f"{'='*75}")

    fig, axes = plt.subplots(1, 3, figsize=(20, 6))
    fig.suptitle(f"Diagnostic Amplitude : {nom_base}", fontsize=16, fontweight='bold')
    r_w = np.sqrt(u_w_tri**2 + v_w_tri**2) / 1e6
    
    axes[0].scatter(r_w, amp_a_tri, s=0.5, color='black', alpha=0.5)
    axes[0].set_title("1. FITS (Vérité Terrain)")
    axes[0].set_ylabel("Amplitude (Jy)")

    axes[1].scatter(r_w, amp_w_tri, s=0.5, color='blue', alpha=0.5)
    axes[1].set_title("2. RAM (Zéro-Copie)")

    sc2 = axes[2].scatter(r_w, diff, s=2, c=diff, cmap='coolwarm', vmin=-1e-6, vmax=1e-6)
    axes[2].set_title("3. Résidus (RAM - FITS)")
    axes[2].axhline(0, color='black', linestyle='--')
    axes[2].set_ylim(-2e-6, 2e-6)
    fig.colorbar(sc2, ax=axes[2], label="Erreur (Jy)")

    for ax in axes:
        ax.set_xlabel(r"Rayon UV (M$\lambda$)")
        ax.grid(True, linestyle=':', alpha=0.6)

    plt.tight_layout()
    plt.savefig(os.path.join(dossier_tests, f"diag_3d_amp_{nom_base}.png"), dpi=150)
    plt.close()

    assert np.allclose(amp_w_tri, amp_a_tri, atol=1e-5)
    if os.path.exists(fits_temp): os.remove(fits_temp)


def test_tests_diff_uvplot_visuel(charger_images):
    nom_uv, _, _ = charger_images
    chemin_uv = os.path.join(dossier_tests, "test_data", nom_uv)
    nom_base = nom_uv.replace('.SPLIT.1', '')
    fits_temp = f"diff_uv_{nom_base}.fits"

    with DifmapSession() as session:
        session.observe(chemin_uv)
        difmap_native.select("RR", 1, 0, 1, 0)
        difmap_native.wfits(fits_temp)
        data_wrapper = difmap_native.get_uv_data()

    with fits.open(fits_temp) as hdul:
        d, h = hdul[0].data, hdul[0].header
        
        fq_data = hdul['AIPS FQ'].data
        if_offsets = fq_data['IF FREQ'][0]
        freqs = h['CRVAL4'] + if_offsets
        
        u_a_2d = d['UU'][:, None] * freqs[None, :]
        v_a_2d = d['VV'][:, None] * freqs[None, :]
        masque = d['DATA'].squeeze()[..., 2] > 0
        
        u_astro, v_astro = u_a_2d[masque], v_a_2d[masque]

    u_w, v_w = data_wrapper['u'], data_wrapper['v']

    idx_w = np.lexsort((np.round(v_w).astype(np.int64), np.round(u_w).astype(np.int64)))
    idx_a = np.lexsort((np.round(v_astro).astype(np.int64), np.round(u_astro).astype(np.int64)))

    u_w_tri, v_w_tri = u_w[idx_w], v_w[idx_w]
    u_a_tri, v_a_tri = u_astro[idx_a], v_astro[idx_a]

    diff_u = u_w_tri - u_a_tri
    diff_v = v_w_tri - v_a_tri

    print(f"\n\n{'='*75}")
    print(f"TABLEAU COMPARATIF UVPLOT (GEOMETRIE) : {nom_base}")
    print(f"{'='*75}")
    print(f"{'Métrique':<15} | {'FITS (Référence)':<18} | {'RAM (Wrapper)':<18} | {'Différence Max'}")
    print(f"{'-'*75}")
    print(f"{'U Maximum':<15} | {np.max(u_a_tri):<15.2e} | {np.max(u_w_tri):<15.2e} | ΔU: {np.max(np.abs(diff_u)):.2e}")
    print(f"{'V Maximum':<15} | {np.max(v_a_tri):<15.2e} | {np.max(v_w_tri):<15.2e} | ΔV: {np.max(np.abs(diff_v)):.2e}")
    print(f"{'='*75}")

    fig, axes = plt.subplots(1, 3, figsize=(20, 6))
    fig.suptitle(f"Diagnostic UVPLOT : {nom_base}", fontsize=16, fontweight='bold')
    
    axes[0].scatter(u_a_tri/1e6, v_a_tri/1e6, s=0.3, color='black', alpha=0.5)
    axes[0].set_title("1. FITS (Vérité Terrain)")
    
    axes[1].scatter(u_w_tri/1e6, v_w_tri/1e6, s=0.3, color='blue', alpha=0.5)
    axes[1].set_title("2. RAM (Zéro-Copie)")

    for ax in axes[:2]:
        ax.set_ylabel(r"V ($M\lambda$)")
        ax.axis('equal')
        ax.invert_xaxis()

    sc2 = axes[2].scatter(u_w_tri/1e6, diff_u, s=2, c=diff_u, cmap='coolwarm', vmin=-0.05, vmax=0.05)
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

    assert np.allclose(u_w_tri, u_a_tri, atol=1e-3)
    if os.path.exists(fits_temp): os.remove(fits_temp)