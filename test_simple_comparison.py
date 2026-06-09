import subprocess
import tempfile
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from astropy.io import fits
from pathlib import Path
from difmap_wrapper.core.session import DifmapSession

# --- CONFIGURATION ---
DIFMAP_BIN = "/usr/local/bin/difmap"
UV_FILE = "/home/mahssini/Bureau/difmap2.5q_mod/tests/test_data/0017+200_X.SPLIT.1"
POL = "RR"
MAPSIZE = 512
CELLSIZE = 0.1

def run_cli(script_lines, workdir):
    """Exécute un script bash contenant les commandes Difmap."""
    script_content = "\n".join(script_lines) + "\nexit\n"
    subprocess.run([DIFMAP_BIN], input=script_content.encode(), capture_output=True, cwd=workdir)

def read_map(fits_path):
    """Lit le fichier FITS et retourne la carte en float64."""
    with fits.open(fits_path) as hdul:
        data = hdul[0].data
        while data.ndim > 2: 
            data = data[0]
        return data.astype(np.float64)

def plot_comparison(map_cli, map_wrapper, title, out_filepath):
    """Génère la figure à 3 panneaux avec vmin/vmax contrôlés."""
    diff = map_cli - map_wrapper
    
    # Calcul des limites pour les cartes (pour avoir la même échelle sur A et B)
    map_vmin = min(map_cli.min(), map_wrapper.min())
    map_vmax = max(map_cli.max(), map_wrapper.max())
    
    # Calcul des limites pour la différence (centré sur 0 pour bien voir le bruit)
    max_abs_err = np.max(np.abs(diff))
    # Sécurité si la différence est rigoureusement zéro
    diff_vmax = max_abs_err if max_abs_err > 0 else 1e-16
    diff_vmin = -diff_vmax

    fig, axes = plt.subplots(1, 3, figsize=(18, 5), facecolor='white')
    fig.suptitle(title, fontsize=14)

    # A. Carte CLI
    im0 = axes[0].imshow(map_cli, origin="lower", cmap="magma", vmin=map_vmin, vmax=map_vmax)
    axes[0].set_title("A. Difmap CLI")
    fig.colorbar(im0, ax=axes[0], label="Jy/beam")

    # B. Carte Wrapper
    im1 = axes[1].imshow(map_wrapper, origin="lower", cmap="magma", vmin=map_vmin, vmax=map_vmax)
    axes[1].set_title("B. Python Wrapper")
    fig.colorbar(im1, ax=axes[1], label="Jy/beam")

    # C. Soustraction (Différence en niveaux de gris)
    im2 = axes[2].imshow(diff, origin="lower", cmap="gray", vmin=diff_vmin, vmax=diff_vmax)
    axes[2].set_title(f"C. Soustraction (CLI - Wrapper)\nErreur Max: {max_abs_err:.2e} Jy/beam")
    fig.colorbar(im2, ax=axes[2], label="Différence (Jy/beam)")

    for ax in axes:
        ax.set_xticks([])
        ax.set_yticks([])

    plt.tight_layout()
    plt.savefig(out_filepath, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Figure sauvegardée : {out_filepath} (Erreur max: {max_abs_err:.2e})")

# --- EXÉCUTION ---
if __name__ == "__main__":
    print("Démarrage de la validation...")

    # Création du dossier de destination
    out_dir = Path("resultat_validation")
    out_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        workdir = Path(tmpdir)
        
        # ---------------------------------------------------------
        # 1. DIRTY MAP
        # ---------------------------------------------------------
        cli_dirty = workdir / "cli_dirty.fits"
        wr_dirty = workdir / "wr_dirty.fits"
        
        run_cli([
            f"observe {UV_FILE}", f"select {POL}", f"mapsize {MAPSIZE},{CELLSIZE}",
            "invert", f"wdmap {cli_dirty.name}"
        ], workdir)
        
        with DifmapSession() as sess:
            sess.observe(UV_FILE)
            sess.obs.select(pol=POL)
            sess.imager.mapsize(MAPSIZE, CELLSIZE)
            sess.imager.invert()
            sess.imager.wdmap(str(wr_dirty))
            
        plot_comparison(read_map(cli_dirty), read_map(wr_dirty), 
                        "Comparaison : Dirty Map", 
                        out_dir / "validation_dirty_map.png")

        # ---------------------------------------------------------
        # 2. CLEAN MAP (avec selfcal)
        # ---------------------------------------------------------
        cli_clean = workdir / "cli_clean.fits"
        wr_clean = workdir / "wr_clean.fits"
        
        run_cli([
            f"observe {UV_FILE}", f"select {POL}", f"mapsize {MAPSIZE},{CELLSIZE}",
            "invert", "clean 200,0.05", "selfcal true,true,60", 
            "clean 500,0.05", "restore", f"wmap {cli_clean.name}"
        ], workdir)
        
        with DifmapSession() as sess:
            sess.observe(UV_FILE)
            sess.obs.select(pol=POL)
            sess.imager.mapsize(MAPSIZE, CELLSIZE)
            sess.imager.invert()
            sess.imager.clean(200, 0.05, 0.0)
            sess.imager.selfcal(doamp=True, dofloat=True, solint=60.0)
            sess.imager.invert()
            sess.imager.clean(500, 0.05, 0.0)
            sess.imager.restore()
            sess.imager.wmap(str(wr_clean))
            
        plot_comparison(read_map(cli_clean), read_map(wr_clean), 
                        "Comparaison : Clean Map (Invert -> Clean -> Selfcal -> Clean -> Restore)", 
                        out_dir / "validation_clean_map.png")

    print("Terminé. Les graphiques sont disponibles dans le dossier 'resultat_validation/'.")