import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
from difmap_wrapper.core.session import DifmapSession

UV_FILE = "/home/mahssini/Bureau/difmap2.5q_mod/tests/test_data/0017+200_X.SPLIT.1"
OUT = Path("validation_output/figures/precision_numerique.png")

with DifmapSession() as sess:
    sess.observe(UV_FILE)
    sess.obs.select(pol="RR")
    sess.imager.mapsize(512, 0.1)
    sess.imager.invert()
    carte = sess.imager.get_cropped_map((512, 512))

carte_f64 = carte.astype(np.float64)
carte_f32 = carte.astype(np.float32).astype(np.float64)
diff = carte_f64 - carte_f32

err_max = np.max(np.abs(diff))
rmse = np.sqrt(np.mean(diff ** 2))
diff_lim = err_max if err_max > 0 else 1e-16

fig, axes = plt.subplots(1, 3, figsize=(18, 5), facecolor="white")

im0 = axes[0].imshow(carte_f64, origin="lower", cmap="inferno")
axes[0].set_title(f"Float64 (référence)\npeak = {carte_f64.max():.4e} Jy/beam")
fig.colorbar(im0, ax=axes[0], label="Jy/beam")

im1 = axes[1].imshow(carte_f32, origin="lower", cmap="inferno")
axes[1].set_title(f"Float32\npeak = {carte_f32.max():.4e} Jy/beam")
fig.colorbar(im1, ax=axes[1], label="Jy/beam")

im2 = axes[2].imshow(diff, origin="lower", cmap="RdBu_r", vmin=-diff_lim, vmax=diff_lim)
axes[2].set_title(
    f"Différence float64 − float32\n"
    f"err_max = {err_max:.2e}   RMSE = {rmse:.2e}   Jy/beam"
)
fig.colorbar(im2, ax=axes[2], label="Jy/beam")

for ax in axes:
    ax.set_xticks([])
    ax.set_yticks([])

plt.tight_layout()
OUT.parent.mkdir(parents=True, exist_ok=True)
plt.savefig(OUT, dpi=150, bbox_inches="tight")
plt.close()
print(f"Sauvegardé : {OUT}")
print(f"err_max = {err_max:.2e}   RMSE = {rmse:.2e}   Jy/beam")
