import pytest
import os
import numpy as np
from astropy.io import fits
from matplotlib import pyplot as plt
import difmap_native
from difmap_wrapper.session import DifmapSession
from difmap_wrapper import standardizer 
from difmap_wrapper.imaging import DifmapImager

# =====================================================================
# CONFIGURATION DES DONNÉES DE RÉFÉRENCE
# =====================================================================
dossier_tests = os.path.dirname(os.path.abspath(__file__))

DATASETS = [
    ("0003-066_X.SPLIT.1", "verite_terrain_test.fits"),
    ("0017+200_X.SPLIT.1", "test_wrapper_strict.fits"),
]

@pytest.fixture(scope="function", params=DATASETS, ids=[d[0] for d in DATASETS])
def setup_comparaison(request):
    nom_uv, nom_fits = request.param
    chemin_uv = os.path.join(dossier_tests, "test_data", nom_uv)
    chemin_fits = os.path.join(dossier_tests, "test_data", nom_fits)
    return nom_uv, chemin_uv, chemin_fits

# =====================================================================
# 1. VALIDATION DIRTY MAP (IMAGE)
# =====================================================================

def test_validation_dirty_map_visuelle(setup_comparaison):
    nom_uv, chemin_uv, chemin_fits = setup_comparaison
    nom_base = nom_uv.replace('.SPLIT.1', '')

    with DifmapSession() as session:
        session.observe(chemin_uv)
        difmap_native.select("RR", 1, 0, 1, 0)
        difmap_native.mapsize(512, 1.0)
        difmap_native.invert()

        with fits.open(chemin_fits) as hdul:
            img_fits = hdul[0].data.squeeze()

        img_ram = session.imager.get_cropped_map(target_shape=img_fits.shape)
        metrics = standardizer.compare_images(img_fits, img_ram)

        # --- TABLEAU TERMINAL ---
        print(f"\n\n{'='*75}\n🖼️  IMAGE COMPARISON : {nom_base}\n{'='*75}")
        print(f"{'Erreur Max':<15} | {metrics['err_max']:.2e} Jy\n{'RMSE':<15} | {metrics['rmse']:.2e} Jy\n{'='*75}")

        # --- RENDU GRAPHIQUE ---
        fig, axes = plt.subplots(1, 3, figsize=(18, 6))
        fig.suptitle(f"Diagnostic RAM vs FITS : {nom_uv}", fontsize=16, fontweight='bold')

        titles = ['FITS (Référence)', 'RAM (Wrapper)', 'Différence (FITS - RAM)']
        images = [img_fits, img_ram, metrics['diff_map']]

        for i, ax in enumerate(axes):
            im = ax.imshow(images[i], origin='lower', cmap='inferno' if i < 2 else 'coolwarm')
            ax.set_title(titles[i])
            ax.grid(True, linestyle=':', alpha=0.4, color='white' if i < 2 else 'black')
            ax.set_axisbelow(True)
            fig.colorbar(im, ax=ax, label='Jy/beam')

        plt.tight_layout()
        plt.savefig(os.path.join(dossier_tests, f"comparaison_visuelle_{nom_base}.png"))
        plt.close()
        assert metrics['err_max'] < 1e-4

# =====================================================================
# 2. VALIDATION RADPLOT (AMPLITUDE)
# =====================================================================

def test_validation_radplot_visuel(setup_comparaison, tmp_path):
    nom_uv, chemin_uv, _ = setup_comparaison
    nom_base = nom_uv.replace('.SPLIT.1', '')
    fits_temp = str(tmp_path / "temp.fits")

    with DifmapSession() as session:
        session.observe(chemin_uv)
        difmap_native.select("RR", 1, 0, 1, 0)
        difmap_native.wfits(fits_temp)
        
        data_ram = standardizer.extract_ram_standardized()
        data_fits = standardizer.extract_uvfits_standardized(fits_temp)
        metrics = standardizer.compare_uv_datasets(data_fits, data_ram)

        print(f"\n\n{'='*75}\n📊 RADPLOT (AMPLITUDE) : {nom_base}\n{'='*75}")
        print(f"{'Points':<15} | {metrics['points_valides']}\n{'ΔAmp Max':<15} | {metrics['delta_amp_max']:.2e} Jy\n{'='*75}")

        fig, axes = plt.subplots(1, 3, figsize=(20, 6))
        fig.suptitle(f"Diagnostic Amplitude : {nom_base}", fontsize=16, fontweight='bold')
        r_w = data_ram['uv_radius']
        
        # Ajout des labels pour la légende
        axes[0].scatter(r_w, data_fits['amp'], s=0.5, color='black', alpha=0.5, label='FITS Reference')
        axes[1].scatter(r_w, data_ram['amp'], s=0.5, color='blue', alpha=0.5, label='RAM Wrapper')
        axes[2].scatter(r_w, metrics['diff_amp'], s=2, c=metrics['diff_amp'], cmap='coolwarm', label='Résidus')
        
        for ax in axes:
            ax.set_xlabel(r"Rayon UV (M$\lambda$)")
            ax.grid(True, linestyle=':', alpha=0.6)
            ax.set_axisbelow(True)
            ax.legend(loc='upper right', markerscale=5) # AFFICHAGE LEGENDE

        axes[0].set_ylabel("Amplitude (Jy)")
        axes[2].axhline(0, color='black', linestyle='--')
        
        plt.tight_layout()
        plt.savefig(os.path.join(dossier_tests, f"diag_3d_amp_{nom_base}.png"))
        plt.close()
        assert metrics['delta_amp_max'] < 1e-4

# =====================================================================
# 3. VALIDATION UVPLOT (GÉOMÉTRIE)
# =====================================================================

def test_validation_uvplot_visuel(setup_comparaison, tmp_path):
    nom_uv, chemin_uv, _ = setup_comparaison
    nom_base = nom_uv.replace('.SPLIT.1', '')
    fits_temp = str(tmp_path / "temp_uv.fits")

    with DifmapSession() as session:
        session.observe(chemin_uv)
        difmap_native.select("RR", 1, 0, 1, 0)
        difmap_native.wfits(fits_temp)
        
        data_ram = standardizer.extract_ram_standardized()
        data_fits = standardizer.extract_uvfits_standardized(fits_temp)
        metrics = standardizer.compare_uv_datasets(data_fits, data_ram)

        print(f"\n\n{'='*75}\n🌍 UVPLOT (GEOMETRIE) : {nom_base}\n{'='*75}")
        print(f"{'ΔU Max':<15} | {metrics['delta_u_max']:.2e} λ\n{'ΔV Max':<15} | {metrics['delta_v_max']:.2e} λ\n{'='*75}")

        fig, axes = plt.subplots(1, 3, figsize=(20, 6))
        fig.suptitle(f"Diagnostic UVPLOT : {nom_base}", fontsize=16, fontweight='bold')
        
        axes[0].scatter(data_fits['u']/1e6, data_fits['v']/1e6, s=0.3, color='black', label='FITS')
        axes[1].scatter(data_ram['u']/1e6, data_ram['v']/1e6, s=0.3, color='blue', label='RAM')
        axes[2].scatter(data_ram['u']/1e6, metrics['diff_u'], s=2, c=metrics['diff_u'], cmap='coolwarm', label='ΔU')

        for ax in axes:
            ax.set_xlabel(r"U (M$\lambda$)")
            ax.grid(True, linestyle=':', alpha=0.6)
            ax.set_axisbelow(True)
            ax.legend(loc='upper right', markerscale=10) # AFFICHAGE LEGENDE
            if ax != axes[2]:
                ax.set_ylabel(r"V (M$\lambda$)")
                ax.axis('equal')
                ax.invert_xaxis()
        
        plt.tight_layout()
        plt.savefig(os.path.join(dossier_tests, f"diag_3d_uvplot_{nom_base}.png"))
        plt.close()
        assert metrics['delta_u_max'] < 50.0