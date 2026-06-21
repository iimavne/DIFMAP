import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
from difmap_wrapper.core.session import DifmapSession

UV_FILE = "/home/mahssini/Bureau/difmap2.5q_mod/tests/test_data/0017+200_X.SPLIT.1"
POL = "RR"
MAPSIZE = 512
CELLSIZE = 0.1
BORDER = 32  # largeur du bord (pixels) pour estimer le rms

out_path = Path("resultat_validation/clean_map_0017.png")
out_path.parent.mkdir(parents=True, exist_ok=True)

import tempfile
with tempfile.TemporaryDirectory() as tmpdir:
    fits_path = Path(tmpdir) / "clean.fits"

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
        sess.imager.wmap(str(fits_path))

    from astropy.io import fits as astrofits
    with astrofits.open(fits_path) as hdul:
        data = hdul[0].data
        while data.ndim > 2:
            data = data[0]
        data = data.astype(np.float64)

# Bord : masque les 4 bandes périphériques
border_mask = np.zeros(data.shape, dtype=bool)
border_mask[:BORDER, :] = True
border_mask[-BORDER:, :] = True
border_mask[:, :BORDER] = True
border_mask[:, -BORDER:] = True

rms = np.std(data[border_mask])
peak = data.max()
snr = peak / rms

fig, axes = plt.subplots(1, 2, figsize=(12, 5), facecolor='white')
fig.suptitle(
    f"Carte CLEAN  —  0017+200_X.SPLIT.1\n"
    f"Peak: {peak*1e3:.2f} mJy/beam   RMS: {rms*1e3:.3f} mJy/beam   SNR: {snr:.0f}",
    fontsize=13
)

im0 = axes[0].imshow(data, origin="lower", cmap="magma")
axes[0].set_title("Échelle automatique")
fig.colorbar(im0, ax=axes[0], label="Jy/beam")

im1 = axes[1].imshow(data, origin="lower", cmap="magma", vmin=-rms, vmax=5 * rms)
axes[1].set_title(f"vmax = 5 × RMS  ({5*rms*1e3:.3f} mJy/beam)")
fig.colorbar(im1, ax=axes[1], label="Jy/beam")

for ax in axes:
    ax.set_xticks([])
    ax.set_yticks([])

plt.tight_layout()
plt.savefig(out_path, dpi=150, bbox_inches='tight')
plt.close()
print(f"Figure sauvegardée : {out_path}")
print(f"Peak: {peak*1e3:.2f} mJy/beam  |  RMS: {rms*1e3:.3f} mJy/beam  |  SNR: {snr:.0f}")
