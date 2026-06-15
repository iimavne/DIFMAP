"""
Validation CLI vs Wrapper au format LOFAR complet.
Haut : Profils superposés (rouge/bleu = magenta si identiques)
Bas : Bruit numérique superposé (rouge/bleu = magenta si identiques)
"""

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
    """Exécute un script Difmap."""
    script_content = "\n".join(script_lines) + "\nexit\n"
    subprocess.run(
        [DIFMAP_BIN], 
        input=script_content.encode(), 
        capture_output=True, 
        cwd=str(workdir)
    )

def read_map(fits_path):
    """Lit le fichier FITS."""
    with fits.open(fits_path) as hdul:
        data = hdul[0].data
        while data.ndim > 2: 
            data = data[0]
        return data.astype(np.float64)


def plot(map_cli, map_wrapper, title, out_filepath):
    diff = map_cli - map_wrapper
    err_max = np.max(np.abs(diff))
    rmse = np.sqrt(np.mean(diff ** 2))

    vmin1, vmax1 = map_cli.min(),     map_cli.max()
    vmin2, vmax2 = map_wrapper.min(), map_wrapper.max()

    # Sous-échantillon pour les scatter (max 8000 points)
    flat_cli = map_cli.ravel()
    flat_wr  = map_wrapper.ravel()
    flat_diff = diff.ravel()
    rng = np.random.default_rng(0)
    idx = rng.choice(len(flat_cli), size=min(8000, len(flat_cli)), replace=False)
    idx = idx[np.argsort(flat_cli[idx])]   # trié par valeur CLI pour la lisibilité

    fig, axes = plt.subplots(2, 2, figsize=(14, 11), facecolor='white')
    fig.suptitle(title, fontsize=13, fontweight='bold')

    # A. imshow CLI
    im0 = axes[0, 0].imshow(map_cli, origin="lower", cmap="magma", vmin=vmin1, vmax=vmax1)
    axes[0, 0].set_title(f"A. CLI Difmap\nvmin={vmin1:.2e}  vmax={vmax1:.2e}  Jy/beam")
    axes[0, 0].set_xticks([]); axes[0, 0].set_yticks([])
    fig.colorbar(im0, ax=axes[0, 0], label="Jy/beam")

    # B. imshow Wrapper
    im1 = axes[0, 1].imshow(map_wrapper, origin="lower", cmap="magma", vmin=vmin2, vmax=vmax2)
    axes[0, 1].set_title(f"B. Wrapper Python\nvmin={vmin2:.2e}  vmax={vmax2:.2e}  Jy/beam")
    axes[0, 1].set_xticks([]); axes[0, 1].set_yticks([])
    fig.colorbar(im1, ax=axes[0, 1], label="Jy/beam")

    # C. Scatter superposé CLI (rouge) + Wrapper (bleu)
    ax_c = axes[1, 0]
    ax_c.scatter(idx, flat_cli[idx],  s=6, color='red',  alpha=0.5, label='CLI',     linewidths=0)
    ax_c.scatter(idx, flat_wr[idx],   s=6, color='blue', alpha=0.5, label='Wrapper', linewidths=0)
    ax_c.set_xlabel("Index pixel (trié par valeur CLI)")
    ax_c.set_ylabel("Amplitude (Jy/beam)")
    ax_c.set_title("C. Superposition CLI (rouge) / Wrapper (bleu)\n[overlap = violet si identiques]")
    ax_c.legend(fontsize=9, markerscale=2)
    ax_c.grid(True, alpha=0.3)

    # D. Scatter résidus |CLI − Wrapper| vs valeur pixel
    ax_d = axes[1, 1]
    abs_diff_sub = np.maximum(np.abs(flat_diff[idx]), 1e-30)
    ax_d.scatter(flat_cli[idx], abs_diff_sub, s=5, color='black', alpha=0.3, linewidths=0)
    ax_d.axhline(y=np.finfo(np.float32).eps * vmax1, color='red',  linestyle='--',
                 linewidth=1.2, label=f'ε_f32 × peak = {np.finfo(np.float32).eps * vmax1:.1e}')
    ax_d.set_xlabel("Valeur pixel CLI (Jy/beam)")
    ax_d.set_ylabel("|CLI − Wrapper| (Jy/beam)")
    ax_d.set_title(f"D. Dispersion des résidus\nerr_max = {err_max:.3e}   RMSE = {rmse:.3e}   Jy/beam")
    ax_d.set_yscale('log')
    ax_d.grid(True, which='both', alpha=0.3)
    ax_d.legend(fontsize=9)

    plt.tight_layout()
    plt.savefig(out_filepath, dpi=150, bbox_inches='tight')
    plt.close()

    print(f"✓ {out_filepath.name}")
    print(f"  err_max = {err_max:.3e}   RMSE = {rmse:.3e}   Jy/beam")
    return {"err_max": err_max, "rmse": rmse}


# --- EXÉCUTION ---
if __name__ == "__main__":
    print("\n" + "="*70)
    print("  VALIDATION CLI vs WRAPPER (Format LOFAR)")
    print("  Précision numérique : Rouge (CLI) + Bleu (Wrapper) = Magenta si identiques")
    print("="*70 + "\n")
    
    out_dir = Path("resultat_validation")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        workdir = Path(tmpdir)
        
        # ─────────────────────────────────────────────────────────────
        # DIRTY MAP
        # ─────────────────────────────────────────────────────────────
        print("[ DIRTY MAP ]")
        cli_dirty = workdir / "cli_dirty.fits"
        wr_dirty = workdir / "wr_dirty.fits"
        
        print("  CLI...", end=" ")
        run_cli([
            f"observe {UV_FILE}", f"select {POL}", f"mapsize {MAPSIZE},{CELLSIZE}",
            "invert", f"wdmap {cli_dirty.name}"
        ], workdir)
        print("✓")
        
        print("  Wrapper...", end=" ")
        with DifmapSession() as sess:
            sess.observe(UV_FILE)
            sess.obs.select(pol=POL)
            sess.imager.mapsize(MAPSIZE, CELLSIZE)
            sess.imager.invert()
            sess.imager.wdmap(str(wr_dirty))
        print("✓")
        
        print("  Figure...", end=" ")
        m_dirty = plot(
            read_map(cli_dirty), read_map(wr_dirty),
            "Dirty Map : CLI vs Wrapper",
            out_dir / "01_dirty_map_lofar.png"
        )
        
        # ─────────────────────────────────────────────────────────────
        # CLEAN MAP
        # ─────────────────────────────────────────────────────────────
        print("\n[ CLEAN MAP ]")
        cli_clean = workdir / "cli_clean.fits"
        wr_clean = workdir / "wr_clean.fits"
        
        print("  CLI...", end=" ")
        run_cli([
            f"observe {UV_FILE}", f"select {POL}", f"mapsize {MAPSIZE},{CELLSIZE}",
            "invert", "clean 200,0.05", "selfcal true,true,60",
            "clean 500,0.05", "restore", f"wmap {cli_clean.name}"
        ], workdir)
        print("✓")
        
        print("  Wrapper...", end=" ")
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
        print("✓")
        
        print("  Figure...", end=" ")
        m_clean = plot(
            read_map(cli_clean), read_map(wr_clean),
            "Clean Map (invert→clean→selfcal→clean→restore) : CLI vs Wrapper",
            out_dir / "02_clean_map_lofar.png"
        )
        
        # ─────────────────────────────────────────────────────────────
        # RÉSUMÉ
        # ─────────────────────────────────────────────────────────────
        print("\n" + "="*70)
        print("  RÉSUMÉ")
        print("="*70)
        print(f"\n  Dirty map : err_max = {m_dirty['err_max']:.3e}")
        print(f"  Clean map : err_max = {m_clean['err_max']:.3e}")
        print(f"\n  Figures LOFAR :")
        print(f"    - Panneau haut  : Profils CLI (rouge) + Wrapper (bleu)")
        print(f"    - Panneau bas   : Bruit numérique CLI (rouge) + Wrapper (bleu)")
        print(f"    - Overlap       : Magenta/rose = identiques")
        print(f"\n  Figures dans : {out_dir.absolute()}")
        print("\n" + "="*70 + "\n")