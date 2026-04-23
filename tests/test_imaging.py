import os
import shutil
import subprocess
import pytest
import numpy as np
import numpy.testing as npt
from unittest.mock import patch, MagicMock, call

from astropy.io import fits

from difmap_wrapper.session import DifmapSession
from difmap_wrapper.exceptions import DifmapError, DifmapStateError
from difmap_wrapper import standardizer

# --- Remplacer par le vrai chemin de tes données de test ---
TEST_UV_FILE = os.path.join(os.path.dirname(__file__), "test_data", "0003-066_X.SPLIT.1")

# =====================================================================
# 1. TESTS D'ARCHITECTURE (Session passée à DifmapImager)
# =====================================================================

class TestImagerArchitecture:
    def test_initialisation_avec_session(self):
        """Vérifie que DifmapImager reçoit et stocke la session."""
        session = DifmapSession()

        assert session.imager._session is session
        assert hasattr(session.imager, '_native')
        assert hasattr(session.imager, '_last_cellsize')
        assert hasattr(session.imager, '_current_uvtaper')
        assert hasattr(session.imager, '_current_uvweight')

    def test_make_dirty_map_appelle_session_obs_select(self, fichier_valide):
        """Vérifie que make_dirty_map() utilise session.obs.select() et non un appel direct."""
        with DifmapSession() as session:
            session.observe(fichier_valide)

            original_select = session.obs.select
            call_count = [0]

            def select_spy(*args, **kwargs):
                call_count[0] += 1
                return original_select(*args, **kwargs)

            session.obs.select = select_spy

            try:
                session.imager.make_dirty_map(size=256, cellsize=1.0, pol="I")
            except Exception:
                pass

            assert call_count[0] >= 1, "make_dirty_map() doit appeler session.obs.select()"

# =====================================================================
# 2. TESTS DE PLOMBERIE ET SÉCURITÉS (Logique Python Pure)
# =====================================================================

class TestImagerPlomberie:
    def test_initialisation(self):
        """Vérifie que les variables d'état sont bien initialisées à None."""
        session = DifmapSession()
        assert session.imager._last_cellsize is None
        assert session.imager._current_uvtaper is None
        assert session.imager._current_uvweight is None

    def test_get_cropped_map_logique(self):
        """Vérifie le calcul de découpage d'une matrice (sans faire appel au C)."""
        session = DifmapSession()
        session.imager.get_map = MagicMock(return_value=np.ones((10, 10)))

        crop = session.imager.get_cropped_map((4, 4))
        assert crop.shape == (4, 4)

    def test_get_cropped_map_erreur_taille(self):
        """Vérifie que le recadrage échoue si on demande plus grand que l'image."""
        session = DifmapSession()
        session.imager.get_map = MagicMock(return_value=np.ones((10, 10)))

        with pytest.raises(ValueError, match="est plus grande que l'image"):
            session.imager.get_cropped_map((20, 20))

# =====================================================================
# 3. TESTS UVWEIGHT ET UVTAPER (Impact physique et feedback)
# =====================================================================

class TestImagerWeightAndTaper:
    def test_uvweight_mode_interrogation(self, capsys):
        session = DifmapSession()
        session.imager.uvweight()
        captured = capsys.readouterr()
        assert "Pondération actuelle" in captured.out

    def test_uvtaper_mode_interrogation(self, capsys):
        session = DifmapSession()
        session.imager.uvtaper()
        captured = capsys.readouterr()
        assert "Taper actuel" in captured.out

    def test_uvtaper_desactivation(self, capsys):
        session = DifmapSession()
        session.imager._native.uvtaper = MagicMock(return_value=0)
        session.imager.uvtaper(0, 0)
        captured = capsys.readouterr()
        assert "Taper désactivé" in captured.out

    def test_uvtaper_logique_python(self):
        """Vérifie que le wrapper Python envoie bien la commande au moteur C et mémorise l'état."""
        session = DifmapSession()
        # On intercepte l'appel vers le C pour vérifier que le Python fait son job
        session.imager._native.uvtaper = MagicMock(return_value=0)
        
        # Application du taper
        session.imager.uvtaper(0.5, 10.0)
        
        # Vérifications strictes : le Wrapper a-t-il appelé la bonne fonction C avec les bons arguments ?
        session.imager._native.uvtaper.assert_called_once_with(0.5, 10.0)
        # Vérification que le Wrapper a bien mis à jour sa mémoire interne
        assert session.imager._current_uvtaper == (0.5, 10.0)

    def test_uvweight_impact_reel_sur_dirty_map(self, fichier_valide):
        """Vérifie que le changement de pondération modifie RÉELLEMENT l'image."""
        # Ce test physique est conservé car uvweight vide correctement le cache de Difmap !
        with DifmapSession() as session:
            session.observe(fichier_valide)
            session.obs.select(pol="RR")
            
            session.imager.mapsize(512, 0.1)

            session.imager.invert()
            map_avant = session.imager.get_map().copy()

            session.imager.uvweight(bin_size=2.0, err_power=-1.0)
            session.imager.invert()
            map_apres = session.imager.get_map().copy()

            assert not np.allclose(map_avant, map_apres), "La pondération n'a eu aucun effet !"
            
# =====================================================================
# 4. TESTS GET_MAP_PACKAGE (Corrigé le bug du 10x10 vs 256x256)
# =====================================================================

class TestImagerGetMapPackage:
    def test_get_map_package_structure(self):
        """Vérifie que get_map_package retourne un dictionnaire avec les bonnes clés."""
        import difmap_native as dn
        session = DifmapSession()

        session.imager.get_map = MagicMock(return_value=np.ones((256, 256)))
        with patch.object(dn, 'get_beam', return_value=np.ones((256, 256))), \
             patch.object(dn, 'get_header', return_value={
                 'NX': 256, 'NY': 256,
                 'BMAJ': 0.5, 'BMIN': 0.4, 'BPA': 45.0
             }):
            pkg = session.imager.get_map_package(cellsize=1.0)

        assert 'data' in pkg
        assert 'beam_data' in pkg
        assert 'info' in pkg
        assert 'extent' in pkg
        assert len(pkg['extent']) == 4

        ra_max, ra_min, dec_min, dec_max = pkg["extent"]
        assert abs(ra_max + ra_min) <= 1.0
        assert abs(dec_max + dec_min) <= 1.0
        assert pkg["data"].shape == (256, 256)

# =====================================================================
# 5. TESTS MAPSIZE ET INVERT (Avec mocks du C)
# =====================================================================

class TestImagerMapsize:
    def test_mapsize_stocke_cellsize(self):
        import difmap_native as dn
        session = DifmapSession()
        with patch.object(dn, 'mapsize', return_value=0) as mock_ms:
            session.imager.mapsize(512, 1.5)
        assert session.imager._last_cellsize == 1.5
        mock_ms.assert_called_once_with(512, 1.5)

    def test_mapsize_erreur_c(self):
        import difmap_native as dn
        session = DifmapSession()
        with patch.object(dn, 'mapsize', return_value=-1):
            with pytest.raises(DifmapError, match="mapsize"):
                session.imager.mapsize(512, 1.0)

class TestImagerInvert:
    def test_invert_appel_c(self):
        import difmap_native as dn
        session = DifmapSession()
        with patch.object(dn, 'invert', return_value=0) as mock_inv:
            session.imager.invert()
        mock_inv.assert_called_once()

    def test_invert_erreur_c(self):
        import difmap_native as dn
        session = DifmapSession()
        with patch.object(dn, 'invert', return_value=-1):
            with pytest.raises(DifmapError, match="Fourier"):
                session.imager.invert()

# =====================================================================
# 6. TESTS VISUELS MATPLOTLIB (En attendant test_visualizer.py)
# =====================================================================

class TestImagerAffichage:
    @patch("matplotlib.pyplot.show")
    @patch("matplotlib.pyplot.colorbar")
    @patch("matplotlib.pyplot.imshow")
    @patch("matplotlib.pyplot.figure")
    def test_plot_image(self, mock_figure, mock_imshow, mock_colorbar, mock_show):
        session = DifmapSession()
        fake_dict = {"data": np.zeros((10, 10)), "extent": [5, -5, -5, 5]}

        session.vis.plot_image(fake_dict, title="Test", cmap="plasma")

        mock_imshow.assert_called_once()
        _, kwargs = mock_imshow.call_args
        assert kwargs["extent"] == [5, -5, -5, 5]
        assert kwargs["cmap"] == "plasma"
        mock_colorbar.assert_called_once()
        mock_show.assert_called_once()

    def test_plot_image_cles_manquantes(self):
        session = DifmapSession()
        bad_dict = {"data": np.zeros((5, 5))}
        with pytest.raises(KeyError, match="doit contenir les clés"):
            session.vis.plot_image(bad_dict)


# =====================================================================
# 7. TESTS CLEAN, RESTORE ET MAKE_CLEAN_MAP
# =====================================================================

def _generer_ref_clean_cli(chemin_uv: str, fits_out: str) -> None:
    """Pilote le vrai Difmap CLI pour produire une Clean Map de référence."""
    dossier = os.path.dirname(fits_out)
    shutil.copy(chemin_uv, os.path.join(dossier, "data.uvf"))
    script = (
        "observe data.uvf\n"
        "select RR\n"
        "mapsize 512,0.1\n"
        "invert\n"
        "clean 100,0.05\n"
        "restore\n"
        "wmap out.fits\n"
        "quit\n"
    )
    res = subprocess.run(
        ["difmap"], input=script, text=True,
        capture_output=True, cwd=dossier, timeout=120
    )
    out_path = os.path.join(dossier, "out.fits")
    if os.path.exists(out_path):
        os.rename(out_path, fits_out)
    else:
        raise RuntimeError(
            f"Difmap CLI a échoué.\nSTDOUT:\n{res.stdout[-2000:]}"
        )


class TestCleanAndRestore:
    """
    Validation complète de clean(), restore() et make_clean_map().

    Trois niveaux :
      1. Unitaires (mocks) — vérifient la plomberie Python.
      2. Intégration (moteur C réel) — prouvent la validité physique.
      3. Formel (CLI Difmap) — comparaison pixel à pixel contre la vérité terrain.
    """

    # ------------------------------------------------------------------
    # 7.1  Tests unitaires (mocks — zéro appel C)
    #
    # IMPORTANT : tous les patches se font via patch.object() utilisé comme
    # context manager, ce qui garantit la restauration automatique des
    # attributs du module difmap_native après chaque test. Ne jamais écrire
    # session.imager._native.xxx = MagicMock(...) sans context manager, car
    # difmap_native est un singleton de module Python et le mock persisterait
    # dans tous les tests suivants.
    # ------------------------------------------------------------------

    def test_clean_transmet_bons_parametres_au_c(self):
        """clean() doit appeler native.clean avec niter et gain corrects."""
        import difmap_native as dn
        session = DifmapSession()
        with patch.object(dn, 'clean', return_value=0) as mock_clean:
            session.imager.clean(niter=200, gain=0.1)
        mock_clean.assert_called_once_with(200, 0.1)

    def test_clean_valeurs_par_defaut(self):
        """clean() doit utiliser niter=100 et gain=0.05 par défaut."""
        import difmap_native as dn
        session = DifmapSession()
        with patch.object(dn, 'clean', return_value=0) as mock_clean:
            session.imager.clean()
        mock_clean.assert_called_once_with(100, 0.05)

    def test_clean_leve_difmaperror_si_moteur_echoue(self):
        """clean() doit lever DifmapError quand le moteur C retourne -1."""
        import difmap_native as dn
        session = DifmapSession()
        with patch.object(dn, 'clean', return_value=-1):
            with pytest.raises(DifmapError, match="CLEAN"):
                session.imager.clean()

    def test_restore_appelle_moteur_c(self):
        """restore() doit appeler native.restore() exactement une fois."""
        import difmap_native as dn
        session = DifmapSession()
        with patch.object(dn, 'restore', return_value=0) as mock_restore:
            session.imager.restore()
        mock_restore.assert_called_once()

    def test_restore_leve_difmaperror_si_moteur_echoue(self):
        """restore() doit lever DifmapError quand le moteur C retourne -1."""
        import difmap_native as dn
        session = DifmapSession()
        with patch.object(dn, 'restore', return_value=-1):
            with pytest.raises(DifmapError, match="restore"):
                session.imager.restore()

    def test_make_clean_map_orchestre_pipeline_dans_le_bon_ordre(self):
        """
        make_clean_map() doit appeler les 4 étapes dans l'ordre strict :
        mapsize → invert → clean → restore → get_map_package.

        Le patch s'effectue sur les méthodes Python de DifmapImager (et non
        sur le module C difmap_native) pour éviter toute contamination entre
        tests.
        """
        session = DifmapSession()
        call_order = []

        with patch.object(session.imager, 'mapsize',
                          side_effect=lambda *a, **kw: call_order.append("mapsize")), \
             patch.object(session.imager, 'invert',
                          side_effect=lambda: call_order.append("invert")), \
             patch.object(session.imager, 'clean',
                          side_effect=lambda *a, **kw: call_order.append("clean")), \
             patch.object(session.imager, 'restore',
                          side_effect=lambda: call_order.append("restore")), \
             patch.object(session.imager, 'get_map_package', return_value={}):
            session.obs.select = MagicMock()
            session.imager.make_clean_map(size=4, cellsize=1.0, niter=50, gain=0.1, pol="I")

        assert call_order == ["mapsize", "invert", "clean", "restore"], (
            f"Ordre incorrect des étapes : {call_order}"
        )

    def test_make_clean_map_passe_les_parametres_clean(self):
        """make_clean_map() doit transmettre niter et gain à clean()."""
        session = DifmapSession()

        with patch.object(session.imager, 'mapsize'), \
             patch.object(session.imager, 'invert'), \
             patch.object(session.imager, 'clean') as mock_clean, \
             patch.object(session.imager, 'restore'), \
             patch.object(session.imager, 'get_map_package', return_value={}):
            session.obs.select = MagicMock()
            session.imager.make_clean_map(size=4, cellsize=1.0, niter=77, gain=0.03)

        mock_clean.assert_called_once_with(77, 0.03)

    # ------------------------------------------------------------------
    # 7.2  Tests d'intégration (moteur C réel, pas de CLI externe)
    # ------------------------------------------------------------------

    def test_make_clean_map_retourne_structure_valide(self, fichier_valide):
        """make_clean_map() doit retourner un dict avec les clés attendues."""
        with DifmapSession() as session:
            session.observe(fichier_valide)
            pkg = session.imager.make_clean_map(512, 0.1, niter=50, pol="RR")

        assert isinstance(pkg, dict), "Le retour doit être un dictionnaire"
        for cle in ("data", "beam_data", "info", "extent"):
            assert cle in pkg, f"Clé manquante : '{cle}'"

        assert isinstance(pkg["data"], np.ndarray)
        assert pkg["data"].ndim == 2
        assert len(pkg["extent"]) == 4
        info = pkg["info"]
        for champ in ("nx", "ny", "cellsize", "bmaj", "bmin", "bpa"):
            assert champ in info, f"Champ info manquant : '{champ}'"

    def test_make_clean_map_sans_nan_ni_inf(self, fichier_valide):
        """
        Preuve mathématique : la Clean Map ne doit contenir ni NaN ni Inf.

        Un NaN ou Inf indiquerait une corruption de la mémoire C lors de
        la convolution (mapres) ou de la soustraction de composantes (mapclean).
        """
        with DifmapSession() as session:
            session.observe(fichier_valide)
            pkg = session.imager.make_clean_map(512, 0.1, niter=100, pol="RR")
            img = pkg["data"]

        assert not np.any(np.isnan(img)), (
            f"La Clean Map contient {np.isnan(img).sum()} pixel(s) NaN"
        )
        assert not np.any(np.isinf(img)), (
            f"La Clean Map contient {np.isinf(img).sum()} pixel(s) Inf"
        )

    def test_clean_reduit_le_bruit_par_rapport_a_la_dirty_map(self, fichier_valide):
        """
        Preuve physique de déconvolution : le CLEAN doit réduire le bruit.

        L'algorithme de Högbom soustrait itérativement les lobes secondaires
        du faisceau sale. Le RMS global de la Clean Map DOIT être inférieur
        au RMS de la Dirty Map sur la même zone, prouvant que la déconvolution
        a eu lieu et a été correctement appliquée par le moteur C natif.
        """
        with DifmapSession() as session:
            session.observe(fichier_valide)

            # Dirty Map
            session.obs.select(pol="RR")
            session.imager.mapsize(512, 0.1)
            session.imager.invert()
            dirty_map = session.imager.get_map().copy()

            # Clean Map (même observation, même grille)
            session.obs.select(pol="RR")
            session.imager.mapsize(512, 0.1)
            session.imager.invert()
            session.imager.clean(niter=100, gain=0.05)
            session.imager.restore()
            clean_map = session.imager.get_map().copy()

        rms_dirty = float(np.std(dirty_map))
        rms_clean = float(np.std(clean_map))

        assert rms_clean < rms_dirty, (
            f"Le CLEAN n'a pas réduit le bruit : "
            f"RMS dirty={rms_dirty:.4e}, RMS clean={rms_clean:.4e}. "
            f"Le moteur C n'a pas exécuté la déconvolution."
        )

    # ------------------------------------------------------------------
    # 7.3  Test formel : comparaison pixel à pixel contre Difmap CLI
    # ------------------------------------------------------------------

    def test_make_clean_map_vs_difmap_cli(self, fichier_valide, tmp_path):
        """
        Preuve formelle d'exactitude : compare la Clean Map du wrapper
        contre la vérité terrain produite par le vrai binaire Difmap.

        Protocole :
          1. Génère une Clean Map de référence via le CLI Difmap (wmap).
          2. Génère la même Clean Map via make_clean_map().
          3. Recadre le wrapper sur la zone centrale 256×256 (zone nettoyée).
          4. Appelle standardizer.compare_images() pour calculer les résidus.
          5. Vérifie que err_max < 1e-4 Jy/beam (seuil identical dirty-map tests).

        La différence résiduelle (< 1e-4 Jy/beam) est due à la différence
        de gestion du modèle interne (keep_fn dans wmap vs double mapres
        dans native_restore). Elle reste dans la précision flottante float32.
        """
        fits_ref = str(tmp_path / "clean_ref.fits")

        try:
            _generer_ref_clean_cli(fichier_valide, fits_ref)
        except (RuntimeError, FileNotFoundError, subprocess.TimeoutExpired) as exc:
            pytest.skip(f"Difmap CLI indisponible ou a échoué : {exc}")

        with fits.open(fits_ref) as hdul:
            img_cli = hdul[0].data.squeeze().astype(np.float32)

        with DifmapSession() as session:
            session.observe(fichier_valide)
            session.imager.make_clean_map(512, 0.1, niter=100, gain=0.05, pol="RR")
            # get_map() retourne la grille complète (512×512) ;
            # on recadre sur la zone centrale que wmap exporte (256×256).
            img_wrapper = session.imager.get_cropped_map(target_shape=img_cli.shape)
            assert img_wrapper.shape == img_cli.shape, (
                f"Échec du recadrage : attendu {img_cli.shape}, obtenu {img_wrapper.shape}"
            )

        metrics = standardizer.compare_images(img_cli, img_wrapper)

        print(
            f"\n{'='*60}\n"
            f" VALIDATION CLEAN MAP : CLI vs Wrapper\n"
            f"{'='*60}\n"
            f" err_max : {metrics['err_max']:.2e} Jy/beam\n"
            f" rmse    : {metrics['rmse']:.2e} Jy/beam\n"
            f" std_err : {metrics['std_err']:.2e} Jy/beam\n"
            f" NaN     : {np.isnan(img_wrapper).sum()}\n"
            f"{'='*60}"
        )

        assert not np.any(np.isnan(img_wrapper)), "NaN détectés dans le wrapper"
        assert metrics['err_max'] < 1e-4, (
            f"Divergence trop grande vs CLI Difmap : "
            f"err_max={metrics['err_max']:.2e} Jy/beam (seuil : 1e-4)"
        )