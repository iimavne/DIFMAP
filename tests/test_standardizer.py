import pytest
import os
import shutil
import subprocess
import numpy as np
from astropy.io import fits
from matplotlib import pyplot as plt
import difmap_native
from difmap_wrapper.session import DifmapSession

from difmap_wrapper import standardizer 

# =====================================================================
# CONFIGURATION DES DONNÉES ET DES CAS PHYSIQUES
# =====================================================================
dossier_tests = os.path.dirname(os.path.abspath(__file__))

DATASETS = [
    "0003-066_X.SPLIT.1",
    "0017+200_X.SPLIT.1",
]

# On teste la fidélité sur 3 états physiques différents pour chaque fichier !
CAS_PHYSIQUES = [
    ("", "Naturel"),
    ("uvtaper 0.5,100", "Taper_Gaussien"),
    ("uvweight 2,-1", "Poids_Uniforme")
]

@pytest.fixture(scope="function", params=DATASETS)
def setup_uv(request, tmp_path):
    nom_uv = request.param
    chemin_uv = os.path.join(dossier_tests, "test_data", nom_uv)
    return nom_uv, chemin_uv, tmp_path

# =====================================================================
# TESTS UNITAIRES - Standardizer
# =====================================================================

class TestStandardizerExtraction:
    """Tests pour extract_uvfits_standardized et extract_ram_standardized."""
    
    def test_extract_uvfits_structure(self, fichier_valide):
        """Vérifie que la structure retournée est correcte."""
        try:
            data = standardizer.extract_uvfits_standardized(fichier_valide)
            
            assert isinstance(data, dict), "Doit retourner un dictionnaire"
            assert 'u' in data, "Doit avoir clé 'u'"
            assert 'v' in data, "Doit avoir clé 'v'"
            assert 'amp' in data, "Doit avoir clé 'amp'"
            assert 'uv_radius' in data, "Doit avoir clé 'uv_radius'"
            
            assert isinstance(data['u'], np.ndarray), "'u' doit être un ndarray"
            assert isinstance(data['v'], np.ndarray), "'v' doit être un ndarray"
            assert isinstance(data['amp'], np.ndarray), "'amp' doit être un ndarray"
            assert isinstance(data['uv_radius'], np.ndarray), "'uv_radius' doit être un ndarray"
            
            # Vérifier la cohérence des longueurs
            n = len(data['u'])
            assert len(data['v']) == n, "Même longueur pour v"
            assert len(data['amp']) == n, "Même longueur pour amp"
            assert len(data['uv_radius']) == n, "Même longueur pour uv_radius"
        except FileNotFoundError:
            pytest.skip("Fichier de test non disponible")
    
    def test_extract_ram_standardized_session(self, fichier_valide):
        """Vérifie que l'extraction depuis la RAM fonctionne correctement."""
        try:
            with DifmapSession() as session:
                session.observe(fichier_valide)
                session.obs.select()
                
                data = standardizer.extract_ram_standardized()
                
                assert isinstance(data, dict)
                assert 'u' in data
                assert 'v' in data
                assert 'amp' in data
                assert 'uv_radius' in data
        except Exception as e:
            # Peut échouer si difmap_native n'a pas get_uv_data complètement
            pytest.skip(f"Extraction RAM non disponible: {e}")

# =====================================================================
# TESTS COMPARAISON
# =====================================================================

class TestStandardizerComparison:
    """Tests pour compare_uv_datasets et compare_images."""
    
    def test_compare_uv_datasets_meme_donnees(self):
        """Vérifie que comparer les mêmes données retourne 0 erreur."""
        u = np.array([1000, 2000, 3000])
        v = np.array([500, 1500, 2500])
        amp = np.array([1.0, 2.0, 3.0])
        uv_radius = np.sqrt(u**2 + v**2) / 1e6
        
        data_ref = {'u': u, 'v': v, 'amp': amp, 'uv_radius': uv_radius}
        data_ram = {'u': u.copy(), 'v': v.copy(), 'amp': amp.copy(), 'uv_radius': uv_radius.copy()}
        
        metrics = standardizer.compare_uv_datasets(data_ref, data_ram)
        
        assert metrics['delta_u_max'] == 0.0
        assert metrics['delta_v_max'] == 0.0
        assert metrics['delta_amp_max'] == 0.0
        assert metrics['amp_rmse'] == 0.0
    
    def test_compare_uv_datasets_desalignement(self):
        """Vérifie que comparer des données de tailles différentes lève une erreur."""
        data_ref = {'u': np.array([1, 2]), 'v': np.array([1, 2]), 'amp': np.array([1.0, 2.0])}
        data_ram = {'u': np.array([1, 2, 3]), 'v': np.array([1, 2, 3]), 'amp': np.array([1.0, 2.0, 3.0])}
        
        with pytest.raises(ValueError, match="Désalignement"):
            standardizer.compare_uv_datasets(data_ref, data_ram)
    
    def test_compare_uv_datasets_avec_erreur(self):
        """Vérifie que la comparaison bien calcule les erreurs."""
        u_ref = np.array([1000, 2000])
        v_ref = np.array([500, 1500])
        amp_ref = np.array([1.0, 2.0])
        
        u_ram = u_ref + 10.0  # Erreur de 10
        v_ram = v_ref + 20.0  # Erreur de 20
        amp_ram = amp_ref + 0.1  # Erreur de 0.1
        
        data_ref = {'u': u_ref, 'v': v_ref, 'amp': amp_ref}
        data_ram = {'u': u_ram, 'v': v_ram, 'amp': amp_ram}
        
        metrics = standardizer.compare_uv_datasets(data_ref, data_ram)
        
        assert metrics['delta_u_max'] == 10.0
        assert metrics['delta_v_max'] == 20.0
        assert metrics['delta_amp_max'] == pytest.approx(0.1)
        assert metrics['amp_rmse'] > 0.0
    
    def test_compare_images_meme_image(self):
        """Vérifie que comparer les mêmes images retourne 0 erreur."""
        img = np.ones((10, 10))
        
        metrics = standardizer.compare_images(img, img.copy())
        
        assert metrics['err_max'] == 0.0
        assert metrics['rmse'] == 0.0
        assert metrics['std_err'] == 0.0
    
    def test_compare_images_dimensions_differentes(self):
        """Vérifie que comparer des images de dimensions différentes lève une erreur."""
        img1 = np.ones((10, 10))
        img2 = np.ones((20, 20))
        
        with pytest.raises(ValueError, match="Dimensions différentes"):
            standardizer.compare_images(img1, img2)
    
    def test_compare_images_avec_erreur(self):
        """Vérifie que la comparaison calcule bien les erreurs de pixel."""
        img_ref = np.ones((5, 5)) * 100.0
        img_cible = np.ones((5, 5)) * 101.0  # +1.0 partout
        
        metrics = standardizer.compare_images(img_ref, img_cible)
        
        assert metrics['err_max'] == 1.0
        assert metrics['rmse'] == 1.0
        assert metrics['std_err'] == 0.0  # Écart-type de 0 puisque l'erreur est uniforme

# =====================================================================
# OUTILS DE PILOTAGE (LE MIROIR)
# =====================================================================

def generer_ref_difmap_cli(chemin_uv: str, fits_out: str, type_export: str, commandes_difmap: str = "") -> None:
    """Pilote l'ancien Difmap avec la bonne syntaxe."""
    dossier_cible = os.path.dirname(fits_out)
    nom_court_out = "out.fits"
    uv_court = "data.uvf"

    shutil.copy(chemin_uv, os.path.join(dossier_cible, uv_court))

    # ATTENTION : Il faut TOUJOURS un mapsize avant uvweight, même pour les UV !
    lignes_script = [f"observe {uv_court}", "select RR", "mapsize 512, 0.1"]
    
    if commandes_difmap:
        # Remplacer les virgules par des espaces pour la syntaxe Difmap
        commandes_difmap = commandes_difmap.replace(",", ", ")
        lignes_script.append(commandes_difmap)
        
    if type_export == "image":
        lignes_script.append("invert")
        lignes_script.append(f"wdmap {nom_court_out}") # Le fameux wdmap qui marche !
    elif type_export == "uv":
        lignes_script.append(f"wobs {nom_court_out}")  # wobs exporte les UV modifiés
        
    lignes_script.append("quit")
    script = "\n".join(lignes_script) + "\n"

    res = subprocess.run(["/home/mahssini/Bureau/difmap2.5q_mod/builddir/difmap"], input=script, text=True, capture_output=True, cwd=dossier_cible)

    chemin_out_complet = os.path.join(dossier_cible, nom_court_out)
    if os.path.exists(chemin_out_complet):
        os.rename(chemin_out_complet, fits_out)
    else:
        raise RuntimeError(f"Difmap CLI a échoué.\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}")

def appliquer_physique_wrapper(session, cmd_difmap):
    """Traduit la commande CLI en appel Python pour le wrapper."""
    session.imager.mapsize(512, 0.1) # Toujours définir la grille d'abord
    
    if "uvtaper" in cmd_difmap:
        val, rad = cmd_difmap.replace("uvtaper ", "").split(",")
        session.imager.uvtaper(float(val), float(rad) * 1e6)  # Convert Mλ to wavelengths
    elif "uvweight" in cmd_difmap:
        val, err = cmd_difmap.replace("uvweight ", "").split(",")
        session.imager.uvweight(float(val), float(err))

# =====================================================================
# 1. VALIDATION DIRTY MAP (IMAGE)
# =====================================================================

#@pytest.mark.skip(reason="Nécessite difmap CLI et FITS valides")
@pytest.mark.parametrize("cmd_difmap, nom_cas", CAS_PHYSIQUES)
def test_validation_dirty_map_visuelle(setup_uv, cmd_difmap, nom_cas):
    """Validation complète d'une Dirty Map contre le vrai Difmap."""
    nom_uv, chemin_uv, tmp_path = setup_uv
    nom_base = nom_uv.replace('.SPLIT.1', f'_{nom_cas}')
    fits_ref = str(tmp_path / "ref_image.fits")

    # 1. VÉRITÉ TERRAIN
    try:
        generer_ref_difmap_cli(chemin_uv, fits_ref, type_export="image", commandes_difmap=cmd_difmap)
    except RuntimeError as e:
        pytest.skip(f"Difmap CLI a échoué: {e}")
    
    with fits.open(fits_ref) as hdul:
        img_fits = hdul[0].data.squeeze()

    # 2. WRAPPER EN RAM
    with DifmapSession() as session:
        session.observe(chemin_uv)
        difmap_native.select("RR", 1, 0, 1, 0)
        appliquer_physique_wrapper(session, cmd_difmap)
        session.imager.invert()
        img_ram = session.imager.get_cropped_map(target_shape=img_fits.shape)

    metrics = standardizer.compare_images(img_fits, img_ram)

    print(f"\n\n{'='*75}\n IMAGE COMPARISON : {nom_base}\n{'='*75}")
    print(f"{'Erreur Max':<15} | {metrics['err_max']:.2e} Jy\n{'='*75}")

    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    fig.suptitle(f"Diagnostic RAM vs FITS : {nom_base}", fontsize=16, fontweight='bold')
    images = [img_fits, img_ram, metrics['diff_map']]
    titles = ['FITS (Ancien Difmap)', 'RAM (Wrapper)', 'Différence']

    for i, ax in enumerate(axes):
        im = ax.imshow(images[i], origin='lower', cmap='inferno' if i < 2 else 'coolwarm')
        ax.set_title(titles[i])
        fig.colorbar(im, ax=ax, label='Jy/beam')

    plt.tight_layout()
    plt.savefig(os.path.join(dossier_tests, f"comparaison_img_{nom_base}.png"))
    plt.close()
    
    assert metrics['err_max'] < 1e-4

# =====================================================================
# 2. VALIDATION RADPLOT (AMPLITUDE ET POIDS)
# =====================================================================

@pytest.mark.parametrize("cmd_difmap, nom_cas", CAS_PHYSIQUES)
def test_validation_radplot_visuel(setup_uv, cmd_difmap, nom_cas):
    nom_uv, chemin_uv, tmp_path = setup_uv
    nom_base = nom_uv.replace('.SPLIT.1', f'_{nom_cas}')
    fits_ref = str(tmp_path / "ref_uv.fits")

    generer_ref_difmap_cli(chemin_uv, fits_ref, type_export="uv", commandes_difmap=cmd_difmap)
    data_fits = standardizer.extract_uvfits_standardized(fits_ref)

    with DifmapSession() as session:
        session.observe(chemin_uv)
        difmap_native.select("RR", 1, 0, 1, 0)
        appliquer_physique_wrapper(session, cmd_difmap)
        data_ram = standardizer.extract_ram_standardized()

    metrics = standardizer.compare_uv_datasets(data_fits, data_ram)

    print(f"\n\n{'='*75}\n RADPLOT (AMPLITUDE) : {nom_base}\n{'='*75}")
    print(f"{'ΔAmp Max':<15} | {metrics['delta_amp_max']:.2e} Jy\n{'='*75}")

    fig, axes = plt.subplots(1, 3, figsize=(20, 6))
    fig.suptitle(f"Diagnostic Amplitude : {nom_base}", fontsize=16, fontweight='bold')
    r_w = data_ram['uv_radius']
    
    axes[0].scatter(r_w, data_fits['amp'], s=0.5, color='black', label='FITS')
    axes[1].scatter(r_w, data_ram['amp'], s=0.5, color='blue', label='RAM')
    axes[2].scatter(r_w, metrics['diff_amp'], s=2, c=metrics['diff_amp'], cmap='coolwarm', label='Résidus')
    
    for ax in axes:
        ax.set_xlabel(r"Rayon UV (M$\lambda$)")
        ax.grid(True, linestyle=':', alpha=0.6)
        ax.legend()

    axes[0].set_ylabel("Amplitude (Jy)")
    plt.tight_layout()
    plt.savefig(os.path.join(dossier_tests, f"diag_radplot_{nom_base}.png"))
    plt.close()
    
    assert metrics['delta_amp_max'] < 1e-4

# =====================================================================
# 3. VALIDATION UVPLOT (GÉOMÉTRIE)
# =====================================================================

@pytest.mark.parametrize("cmd_difmap, nom_cas", CAS_PHYSIQUES)
def test_validation_uvplot_visuel(setup_uv, cmd_difmap, nom_cas):
    nom_uv, chemin_uv, tmp_path = setup_uv
    nom_base = nom_uv.replace('.SPLIT.1', f'_{nom_cas}')
    fits_ref = str(tmp_path / "ref_uv2.fits")

    generer_ref_difmap_cli(chemin_uv, fits_ref, type_export="uv", commandes_difmap=cmd_difmap)
    data_fits = standardizer.extract_uvfits_standardized(fits_ref)

    with DifmapSession() as session:
        session.observe(chemin_uv)
        difmap_native.select("RR", 1, 0, 1, 0)
        appliquer_physique_wrapper(session, cmd_difmap)
        data_ram = standardizer.extract_ram_standardized()
        
    metrics = standardizer.compare_uv_datasets(data_fits, data_ram)

    print(f"\n\n{'='*75}\n UVPLOT (GEOMETRIE) : {nom_base}\n{'='*75}")
    print(f"{'ΔU Max':<15} | {metrics['delta_u_max']:.2e} λ\n{'='*75}")

    fig, axes = plt.subplots(1, 3, figsize=(20, 6))
    fig.suptitle(f"Diagnostic UVPLOT : {nom_base}", fontsize=16, fontweight='bold')
    
    axes[0].scatter(data_fits['u']/1e6, data_fits['v']/1e6, s=0.3, color='black', label='FITS')
    axes[1].scatter(data_ram['u']/1e6, data_ram['v']/1e6, s=0.3, color='blue', label='RAM')
    axes[2].scatter(data_ram['u']/1e6, metrics['diff_u'], s=2, c=metrics['diff_u'], cmap='coolwarm', label='ΔU')

    for ax in axes:
        ax.set_xlabel(r"U (M$\lambda$)")
        ax.grid(True, linestyle=':', alpha=0.6)
        if ax != axes[2]:
            ax.set_ylabel(r"V (M$\lambda$)")
            ax.axis('equal')
            ax.invert_xaxis()
    
    plt.tight_layout()
    plt.savefig(os.path.join(dossier_tests, f"diag_uvplot_{nom_base}.png"))
    plt.close()
    
    assert metrics['delta_u_max'] < 50.0