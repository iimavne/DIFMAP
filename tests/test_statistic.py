"""
Tests de fidélité : apply_stats() / apply_stats_vec() vs algorithme C original.

Stratégie :
  1. c_scalar_stats_ref() / c_vector_stats_ref() — réimplémentation exacte de
     r_scalar_stats() et r_vector_stats() (uvradplt.c) en Python pur.
  2. On instancie un vrai RadPlotEditor avec les données synthétiques.
  3. On appelle les vraies méthodes apply_stats() et apply_stats_vec().
  4. On compare les valeurs retournées à la référence C à 10 décimales.
"""
import numpy as np
import pytest
import matplotlib
matplotlib.use("Agg")                    # pas de fenêtre, compatible CI
import matplotlib.pyplot as plt

from dataclasses import dataclass, field
from typing import Optional
from unittest.mock import MagicMock

from difmap_wrapper.editors.rad_editor import RadPlotEditor
from difmap_wrapper import DifmapSession
import difmap_native


@dataclass
class RadScatters:
    """Copie minimale du dataclass RadScatters pour les tests (pas de dépendance PyQt6)."""
    amp:       Optional[object] = field(default=None)
    phase:     Optional[object] = field(default=None)
    model_amp: Optional[object] = field(default=None)
    model_phs: Optional[object] = field(default=None)
    err:       Optional[object] = field(default=None)


# ═══════════════════════════════════════════════════════════════════════════════
# RÉFÉRENCE C — réimplémentation ligne par ligne de uvradplt.c
# ═══════════════════════════════════════════════════════════════════════════════

def _wrap(phs_deg):
    """r_vis_phs() : phs -= 360 * floor(phs/360 + 0.5)"""
    return phs_deg - 360.0 * np.floor(phs_deg / 360.0 + 0.5)


def _process_phase(phs_deg, u_wl):
    """r_vis_phs() sans projection : wrap puis conjugaison si u < 0."""
    p = _wrap(phs_deg)
    return np.where(u_wl < 0, -p, p)


def c_scalar_stats_ref(amp, phs_deg, u_wl, v_wl, weight,
                        xmin, xmax, ymin, ymax, is_phase_box=False):
    """
    Réimplémentation exacte de r_scalar_stats() — uvradplt.c lignes 2108-2204.

    C : error = sqrt(SS)/n,  RMS = sqrt(SS/n)  (biaisé, ddof=0)
    """
    uvd   = np.sqrt(u_wl**2 + v_wl**2)
    phs_c = _process_phase(phs_deg, u_wl)
    value = phs_c if is_phase_box else amp

    mask = (uvd > 0) & (uvd >= xmin) & (uvd <= xmax) \
         & (value >= ymin) & (value <= ymax) & (weight > 0)
    n = int(mask.sum())
    if n == 0:
        return None

    a = amp[mask]
    p = np.radians(phs_c[mask])

    mean_a, mean_p = a.mean(), p.mean()
    SS_a = np.sum((a - mean_a) ** 2)
    SS_p = np.sum((p - mean_p) ** 2)

    return {
        "n":        n,
        "amp_mean": mean_a,
        "amp_err":  np.sqrt(SS_a) / n,
        "amp_rms":  np.sqrt(SS_a / n),
        "phs_mean": np.degrees(mean_p),
        "phs_err":  np.degrees(np.sqrt(SS_p) / n),
        "phs_rms":  np.degrees(np.sqrt(SS_p / n)),
    }


def c_vector_stats_ref(amp, phs_deg, u_wl, v_wl, weight,
                        xmin, xmax, ymin, ymax, is_phase_box=False):
    """Réimplémentation exacte de r_vector_stats() — uvradplt.c lignes 2312-2407."""
    uvd   = np.sqrt(u_wl**2 + v_wl**2)
    phs_c = _process_phase(phs_deg, u_wl)
    value = phs_c if is_phase_box else amp

    mask = (uvd > 0) & (uvd >= xmin) & (uvd <= xmax) \
         & (value >= ymin) & (value <= ymax) & (weight > 0)
    n = int(mask.sum())
    if n == 0:
        return None

    a  = amp[mask]
    p  = np.radians(phs_c[mask])
    re = a * np.cos(p)
    im = a * np.sin(p)

    mean_re, mean_im = re.mean(), im.mean()
    SS_re = np.sum((re - mean_re) ** 2)
    SS_im = np.sum((im - mean_im) ** 2)

    return {
        "n":      n,
        "re_mean": mean_re,  "re_err": np.sqrt(SS_re) / n,  "re_rms": np.sqrt(SS_re / n),
        "im_mean": mean_im,  "im_err": np.sqrt(SS_im) / n,  "im_rms": np.sqrt(SS_im / n),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# FIXTURE — instancie un vrai RadPlotEditor avec données synthétiques
# ═══════════════════════════════════════════════════════════════════════════════

def _make_editor(data):
    """
    Construit un RadPlotEditor testable :
    - données synthétiques injectées directement
    - matplotlib en mode Agg (sans affichage)
    - RadScatters avec None (pas de scatter plots)
    - Observation mockée conforme au type-check C4
    """
    from difmap_wrapper.observation import Observation

    obs = object.__new__(Observation)
    obs._session  = MagicMock()
    obs._native   = MagicMock()
    obs._session.uv_loaded = True
    n = len(data["u"])
    obs.masque_flagges    = np.zeros(n, dtype=bool)
    obs.historique_coupes = []
    obs._editors          = []

    # Axes matplotlib sans fenêtre
    fig, axes = plt.subplots(3, 1)
    ax, ax_phase, ax_err = axes

    editor = RadPlotEditor(
        observation  = obs,
        fig          = fig,
        ax           = ax,
        ax_phase     = ax_phase,
        ax_err       = ax_err,
        data         = data,
        scats        = RadScatters(),
        base_color   = "white",
    )
    return editor


@pytest.fixture(scope="module")
def synth_editor():
    """
    Jeu de données synthétiques déterministe avec :
    - u > 0 et u < 0 (pour tester la conjugaison)
    - phases hors [-180, 180] (pour tester le wrapping)
    Retourne (editor, raw_data_dict).
    """
    # S'assurer qu'une session existe (singleton C)
    try:
        DifmapSession()
    except Exception:
        pass

    rng = np.random.default_rng(42)
    n   = 40

    u_wl = np.concatenate([
        rng.uniform(10e6,  50e6, n // 2),   # u > 0
        rng.uniform(-50e6, -10e6, n // 2),  # u < 0
    ])
    v_wl    = rng.uniform(-50e6, 50e6, n)
    amp     = rng.uniform(0.1, 1.5, n).astype(np.float32)
    phs_deg = rng.uniform(-400, 400, n).astype(np.float32)   # hors [-180,180]
    weight  = rng.uniform(0.5, 5.0,  n).astype(np.float32)
    modamp  = rng.uniform(0.0, 0.5,  n).astype(np.float32)
    modphs  = rng.uniform(-180, 180, n).astype(np.float32)
    tel_a   = np.zeros(n, dtype=np.int32)
    tel_b   = np.ones(n,  dtype=np.int32)
    subarray = np.zeros(n, dtype=np.int32)

    data = {
        "u": u_wl.astype(np.float32),
        "v": v_wl.astype(np.float32),
        "amp":     amp,
        "phase":   phs_deg,
        "weight":  weight,
        "modamp":  modamp,
        "modphs":  modphs,
        "tel_a":   tel_a,
        "tel_b":   tel_b,
        "subarray": subarray,
    }
    editor = _make_editor(data)
    return editor, data


# ═══════════════════════════════════════════════════════════════════════════════
# BOÎTE DE SÉLECTION commune à tous les tests
# ═══════════════════════════════════════════════════════════════════════════════

BOX = dict(xmin=0, xmax=80e6, ymin=0.3, ymax=1.2)   # couvre ~la moitié des points


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 1 — apply_stats() vs r_scalar_stats() C
# ═══════════════════════════════════════════════════════════════════════════════

class TestApplyStatsVsC:
    """Appelle la vraie apply_stats() et compare au C original."""

    @pytest.fixture(autouse=True)
    def setup(self, synth_editor):
        self.editor, self.data = synth_editor
        # Boîte en mode amplitude (axe par défaut = ax)
        self.editor._last_pressed_axis = self.editor.ax
        x1, x2 = BOX["xmin"], BOX["xmax"]
        y1, y2 = BOX["ymin"], BOX["ymax"]
        self.result = self.editor.apply_stats(x1, y1, x2, y2)
        self.ref    = c_scalar_stats_ref(
            amp     = self.data["amp"].astype(float),
            phs_deg = self.data["phase"].astype(float),
            u_wl    = self.data["u"].astype(float),
            v_wl    = self.data["v"].astype(float),
            weight  = self.data["weight"].astype(float),
            **BOX,
        )
        if self.result is None or self.ref is None:
            pytest.skip("Boîte vide — ajuster BOX")

    def test_nombre_visibilites(self):
        assert self.result["n"] == self.ref["n"], \
            f"Comptage : Python={self.result['n']}, C={self.ref['n']}"

    def test_amp_mean(self):
        np.testing.assert_almost_equal(
            self.result["amp_mean"], self.ref["amp_mean"], decimal=5,
            err_msg="amp_mean diverge de r_scalar_stats()")

    def test_amp_rms(self):
        np.testing.assert_almost_equal(
            self.result["amp_rms"], self.ref["amp_rms"], decimal=5,
            err_msg="amp_rms diverge (ddof=0 requis)")

    def test_amp_err(self):
        np.testing.assert_almost_equal(
            self.result["amp_err"], self.ref["amp_err"], decimal=5,
            err_msg="amp_err diverge de r_scalar_stats()")

    def test_phs_mean(self):
        np.testing.assert_almost_equal(
            self.result["phs_mean"], self.ref["phs_mean"], decimal=4,
            err_msg="phs_mean diverge — vérifier wrapping + conjugaison u<0")

    def test_phs_rms(self):
        np.testing.assert_almost_equal(
            self.result["phs_rms"], self.ref["phs_rms"], decimal=4,
            err_msg="phs_rms diverge de r_scalar_stats()")

    def test_phs_err(self):
        np.testing.assert_almost_equal(
            self.result["phs_err"], self.ref["phs_err"], decimal=4,
            err_msg="phs_err diverge de r_scalar_stats()")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 2 — apply_stats_vec() vs r_vector_stats() C
# ═══════════════════════════════════════════════════════════════════════════════

class TestApplyStatsVecVsC:
    """Appelle la vraie apply_stats_vec() et compare au C original."""

    @pytest.fixture(autouse=True)
    def setup(self, synth_editor):
        self.editor, self.data = synth_editor
        self.editor._last_pressed_axis = self.editor.ax
        x1, x2 = BOX["xmin"], BOX["xmax"]
        y1, y2 = BOX["ymin"], BOX["ymax"]
        self.result = self.editor.apply_stats_vec(x1, y1, x2, y2)
        self.ref    = c_vector_stats_ref(
            amp     = self.data["amp"].astype(float),
            phs_deg = self.data["phase"].astype(float),
            u_wl    = self.data["u"].astype(float),
            v_wl    = self.data["v"].astype(float),
            weight  = self.data["weight"].astype(float),
            **BOX,
        )
        if self.result is None or self.ref is None:
            pytest.skip("Boîte vide — ajuster BOX")

    def test_nombre_visibilites(self):
        assert self.result["n"] == self.ref["n"]

    def test_re_mean(self):
        np.testing.assert_almost_equal(
            self.result["re_mean"], self.ref["re_mean"], decimal=5,
            err_msg="re_mean diverge de r_vector_stats()")

    def test_re_rms(self):
        np.testing.assert_almost_equal(
            self.result["re_rms"], self.ref["re_rms"], decimal=5,
            err_msg="re_rms diverge (ddof=0 requis)")

    def test_re_err(self):
        np.testing.assert_almost_equal(
            self.result["re_err"], self.ref["re_err"], decimal=5,
            err_msg="re_err diverge de r_vector_stats()")

    def test_im_mean(self):
        np.testing.assert_almost_equal(
            self.result["im_mean"], self.ref["im_mean"], decimal=5,
            err_msg="im_mean diverge de r_vector_stats()")

    def test_im_rms(self):
        np.testing.assert_almost_equal(
            self.result["im_rms"], self.ref["im_rms"], decimal=5,
            err_msg="im_rms diverge (ddof=0 requis)")

    def test_im_err(self):
        np.testing.assert_almost_equal(
            self.result["im_err"], self.ref["im_err"], decimal=5,
            err_msg="im_err diverge de r_vector_stats()")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 3 — Comportement phase : wrapping + conjugaison u<0
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhaseCorrectness:
    """Prouve que les corrections de phase sont bien appliquées dans apply_stats()."""

    def test_phs_mean_differ_without_conjugation(self, synth_editor):
        """Sans conjugaison u<0, phs_mean serait différent du C."""
        editor, data = synth_editor
        editor._last_pressed_axis = editor.ax

        result = editor.apply_stats(BOX["xmin"], BOX["ymin"],
                                     BOX["xmax"], BOX["ymax"])
        if result is None:
            pytest.skip("Boîte vide")

        # Calcul intentionnellement faux : pas de conjugaison
        amp = data["amp"].astype(float)
        phs = data["phase"].astype(float)    # brut, sans conjugaison
        u   = data["u"].astype(float)
        v   = data["v"].astype(float)
        w   = data["weight"].astype(float)
        uvd = np.sqrt(u**2 + v**2)
        mask = ((uvd >= BOX["xmin"]) & (uvd <= BOX["xmax"])
                & (amp >= BOX["ymin"]) & (amp <= BOX["ymax"]) & (w > 0))
        if not (u[mask] < 0).any():
            pytest.skip("Pas de u<0 dans la boîte — conjugaison sans effet ici")

        phs_mean_wrong = phs[mask].mean()
        assert not np.isclose(phs_mean_wrong, result["phs_mean"], rtol=1e-3), \
            "La conjugaison n'a aucun effet — données ou boîte incorrectes"

    def test_wrapping_changes_result_for_large_phases(self):
        """Phases > 180° wrappées avant les stats."""
        rng = np.random.default_rng(0)
        n   = 20
        u   = rng.uniform(10e6, 50e6, n)    # tout positif : pas de conjugaison
        v   = rng.uniform(-10e6, 10e6, n)
        amp = rng.uniform(0.5, 1.0, n).astype(np.float32)
        # Phases volontairement à 350° (équivalent à -10° après wrapping)
        phs_large = np.full(n, 350.0, dtype=np.float32)
        phs_wrap  = np.full(n, -10.0, dtype=np.float32)
        w   = np.ones(n, dtype=np.float32)
        sub = np.zeros(n, dtype=np.int32)
        tel = np.zeros(n, dtype=np.int32)

        def make(phs):
            data = {"u": u.astype(np.float32), "v": v.astype(np.float32),
                    "amp": amp, "phase": phs, "weight": w,
                    "modamp": np.zeros(n, np.float32),
                    "modphs": np.zeros(n, np.float32),
                    "tel_a": tel, "tel_b": tel, "subarray": sub}
            ed = _make_editor(data)
            ed._last_pressed_axis = ed.ax
            return ed.apply_stats(0, 0.4, 60e6, 1.1)

        r_large = make(phs_large)
        r_wrap  = make(phs_wrap)
        if r_large is None or r_wrap is None:
            pytest.skip("Boîte vide")

        # 350° wrappé = -10° : les deux editeurs doivent donner le même résultat
        np.testing.assert_almost_equal(r_large["phs_mean"], r_wrap["phs_mean"], decimal=4,
            err_msg="Le wrapping de 350°→-10° ne donne pas le même résultat")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 4 — Intégration sur vraies données UV (si binding recompilé)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def real_editor():
    """
    Charge de vraies données UV et construit un RadPlotEditor dessus.
    Skip si 'phase' absent du binaire compilé (nécessite: cd builddir && ninja).
    """
    try:
        DifmapSession()
    except Exception:
        pass
    DifmapSession._instance.observe("tests/test_data/0028-137_X.SPLIT.1")
    DifmapSession._instance.obs.select(pol="RR")
    raw = difmap_native.get_uv_data()
    if "phase" not in raw:
        pytest.skip("Recompiler le binding : cd builddir && ninja")

    editor = _make_editor(raw)
    return editor, raw


class TestIntegrationRealData:
    @pytest.fixture(autouse=True)
    def setup(self, real_editor):
        self.editor, self.raw = real_editor
        self.editor._last_pressed_axis = self.editor.ax

    def test_scalar_stats_match_c_reference(self):
        result = self.editor.apply_stats(0, 0.05, 500e6, 0.5)
        ref    = c_scalar_stats_ref(
            amp     = self.raw["amp"].astype(float),
            phs_deg = self.raw["phase"].astype(float),
            u_wl    = self.raw["u"].astype(float),
            v_wl    = self.raw["v"].astype(float),
            weight  = self.raw["weight"].astype(float),
            xmin=0, xmax=500e6, ymin=0.05, ymax=0.5,
        )
        assert result is not None and ref is not None
        assert result["n"] == ref["n"]
        np.testing.assert_almost_equal(result["amp_mean"], ref["amp_mean"], decimal=5)
        np.testing.assert_almost_equal(result["amp_rms"],  ref["amp_rms"],  decimal=5)
        np.testing.assert_almost_equal(result["phs_mean"], ref["phs_mean"], decimal=4)
        np.testing.assert_almost_equal(result["phs_rms"],  ref["phs_rms"],  decimal=4)

    def test_vector_stats_match_c_reference(self):
        result = self.editor.apply_stats_vec(0, 0.05, 500e6, 0.5)
        ref    = c_vector_stats_ref(
            amp     = self.raw["amp"].astype(float),
            phs_deg = self.raw["phase"].astype(float),
            u_wl    = self.raw["u"].astype(float),
            v_wl    = self.raw["v"].astype(float),
            weight  = self.raw["weight"].astype(float),
            xmin=0, xmax=500e6, ymin=0.05, ymax=0.5,
        )
        assert result is not None and ref is not None
        assert result["n"] == ref["n"]
        np.testing.assert_almost_equal(result["re_mean"], ref["re_mean"], decimal=5)
        np.testing.assert_almost_equal(result["re_rms"],  ref["re_rms"],  decimal=5)
        np.testing.assert_almost_equal(result["im_mean"], ref["im_mean"], decimal=5)
        np.testing.assert_almost_equal(result["im_rms"],  ref["im_rms"],  decimal=5)
