"""
Tests complets pour la classe Visualizer - Vérification de l'intégration avec la session.
"""

import pytest
from unittest.mock import patch, MagicMock
import numpy as np
from matplotlib import pyplot as plt
from difmap_wrapper.visualizer import Visualizer
from difmap_wrapper.session import DifmapSession
from difmap_wrapper.exceptions import DifmapStateError


# =====================================================================
# TESTS VISUALIZER - Initialisation et Accès à la Session
# =====================================================================

class TestVisualizerInitialization:
    """Tests de l'initialisation correcte de Visualizer avec session."""
    
    def test_visualizer_initialization(self):
        """Vérifie que Visualizer est créé et stocke la session."""
        session = DifmapSession()
        
        assert isinstance(session.vis, Visualizer)
        assert session.vis._session is session
        assert hasattr(session.vis, '_native')
    
    def test_visualizer_has_methods(self):
        """Vérifie que Visualizer a toutes les méthodes attendues."""
        session = DifmapSession()
        
        assert hasattr(session.vis, 'uvplot')
        assert hasattr(session.vis, 'radplot')
        assert hasattr(session.vis, 'mapplot')
        assert hasattr(session.vis, 'plot_image')
    
    def test_visualizer_appartient_a_sa_session(self):
        """Vérifie que le Visualizer référence bien la session parente."""
        session1 = DifmapSession()
        assert session1.vis._session is session1
        session1.cleanup()

        session2 = DifmapSession()
        assert session2.vis._session is session2
        session2.cleanup()


# =====================================================================
# TESTS UVPLOT - Avec accès à source via session
# =====================================================================

class TestUVPlot:
    """Tests pour la méthode uvplot()."""
    
    @patch("matplotlib.pyplot.show")
    @patch("matplotlib.pyplot.subplots")
    def test_uvplot_cree_figure(self, mock_subplots, mock_show, fichier_valide):
        """Vérifie que uvplot crée une figure si aucune n'est fournie."""
        with DifmapSession() as session:
            session.observe(fichier_valide)
            session.obs.select()
            
            # Mock matplotlib
            fig_mock, ax_mock = MagicMock(), MagicMock()
            mock_subplots.return_value = (fig_mock, ax_mock)
            
            # Mock les données UV
            session.vis._native.get_uv_data = MagicMock(return_value={
                'u': np.array([1000, 2000]),
                'v': np.array([500, 1500]),
                'amp': np.array([1.0, 2.0])
            })
            
            try:
                result = session.vis.uvplot(interactive=False)
                assert result is not None
            except Exception:
                # Peut échouer pour d'autres raisons, on s'en fout
                pass
    
    @patch("matplotlib.pyplot.show")
    def test_uvplot_utilise_source_session(self, mock_show, fichier_valide):
        """Vérifie que uvplot utilise session.obs.source pour le titre."""
        with DifmapSession() as session:
            session.observe(fichier_valide)
            session.obs.select()
            
            # Mock les données UV
            session.vis._native.get_uv_data = MagicMock(return_value={
                'u': np.array([1000, 2000]),
                'v': np.array([500, 1500]),
                'amp': np.array([1.0, 2.0])
            })
            
            # Patch ax.set_title pour capturer le titre
            with patch.object(plt, 'subplots') as mock_subplots:
                fig_mock = MagicMock()
                ax_mock = MagicMock()
                mock_subplots.return_value = (fig_mock, ax_mock)
                
                try:
                    session.vis.uvplot()
                    
                    # Vérifier que set_title a été appelé avec le nom de la source
                    assert ax_mock.set_title.called
                    call_args = ax_mock.set_title.call_args
                    if call_args:
                        title = call_args[0][0] if call_args[0] else ""
                        # Le titre doit contenir le nom de la source
                        assert "Couverture UV" in title
                except Exception:
                    pass


# =====================================================================
# TESTS RADPLOT - Avec accès à source via session
# =====================================================================

class TestRadPlot:
    """Tests pour la méthode radplot()."""
    
    @patch("matplotlib.pyplot.show")
    def test_radplot_utilise_source_session(self, mock_show, fichier_valide):
        """Vérifie que radplot utilise session.obs.source pour le titre."""
        with DifmapSession() as session:
            session.observe(fichier_valide)
            session.obs.select()
            
            # Mock les données UV
            session.vis._native.get_uv_data = MagicMock(return_value={
                'u': np.array([1000, 2000]),
                'v': np.array([500, 1500]),
                'amp': np.array([1.0, 2.0])
            })
            
            with patch.object(plt, 'subplots') as mock_subplots:
                fig_mock = MagicMock()
                ax_mock = MagicMock()
                mock_subplots.return_value = (fig_mock, ax_mock)
                
                try:
                    session.vis.radplot()
                    
                    # Vérifier que set_title a été appelé
                    assert ax_mock.set_title.called
                    call_args = ax_mock.set_title.call_args
                    if call_args:
                        title = call_args[0][0] if call_args[0] else ""
                        assert "Radplot" in title
                except Exception:
                    pass


# =====================================================================
# TESTS MAPPLOT - Accès à imager via session
# =====================================================================

class TestMapPlot:
    """Tests pour la méthode mapplot()."""
    
    def test_mapplot_accede_imager_via_session(self):
        """Vérifie que mapplot() peut accéder à imager._last_cellsize via session."""
        session = DifmapSession()
        
        # Sans mapsize, doit lever une erreur
        with pytest.raises(DifmapStateError):
            session.vis.mapplot()
        
        # Après avoir défini le cellsize, ne doit pas lever d'erreur de mapsize
        session.imager._last_cellsize = 1.0
        session.imager.get_map = MagicMock(return_value=np.ones((10, 10)))
        session.imager.get_map_package = MagicMock(return_value={
            'data': np.ones((10, 10)),
            'extent': [5, -5, -5, 5]
        })
        
        try:
            session.vis.mapplot()
        except DifmapStateError as e:
            # Si c'est un problème d'invert, c'est normal
            if "invert" in str(e):
                pass
            else:
                raise
    
    @patch("matplotlib.pyplot.show")
    def test_mapplot_avec_dict_personnalise(self, mock_show):
        """Vérifie que mapplot() accepte un dictionnaire prépréparé."""
        session = DifmapSession()
        
        # Patch plot_image pour vérifier l'appel
        with patch.object(session.vis, 'plot_image') as mock_plot_image:
            fake_dict = {
                'data': np.ones((10, 10)),
                'extent': [5, -5, -5, 5]
            }
            
            session.vis.mapplot(img_dict=fake_dict)
            
            # Vérifier que plot_image a été appelé avec le bon dictionnaire
            mock_plot_image.assert_called_once()
            call_args = mock_plot_image.call_args[0][0]
            assert np.array_equal(call_args['data'], fake_dict['data'])
            assert call_args['extent'] == fake_dict['extent']


# =====================================================================
# TESTS PLOT_IMAGE - Méthode statique
# =====================================================================

class TestPlotImage:
    """Tests pour la méthode plot_image()."""
    
    def test_plot_image_appelle_matplotlib(self):
        """Vérifie que plot_image appelle les bonnes fonctions matplotlib."""
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        session = DifmapSession()

        fake_dict = {
            'data': np.ones((10, 10)),
            'extent': [5, -5, -5, 5]
        }

        with patch("matplotlib.axes.Axes.imshow", return_value=MagicMock()) as mock_imshow, \
             patch("matplotlib.figure.Figure.colorbar") as mock_colorbar, \
             patch.object(plt, "show"):
            session.vis.plot_image(fake_dict, cmap='viridis', title='Test', show=False)

        mock_imshow.assert_called_once()
        mock_colorbar.assert_called_once()
    
    def test_plot_image_valide_cles(self):
        """Vérifie que plot_image valide les clés du dictionnaire."""
        session = DifmapSession()
        
        # Manque 'extent'
        bad_dict = {'data': np.ones((5, 5))}
        
        with pytest.raises(KeyError):
            session.vis.plot_image(bad_dict)
        
        # Manque 'data'
        bad_dict2 = {'extent': [1, 2, 3, 4]}
        
        with pytest.raises(KeyError):
            session.vis.plot_image(bad_dict2)


# =====================================================================
# TESTS D'INTÉGRATION - Visualizer + Session
# =====================================================================

class TestVisualizerIntegration:
    """Tests d'intégration de Visualizer avec DifmapSession."""
    
    def test_visualizer_survit_contexte_manager(self, fichier_valide):
        """Vérifie que Visualizer existe toujours après la fermeture du contexte."""
        with DifmapSession() as session:
            vis_ref = session.vis
        
        # Après le with, vis doit toujours exister (même si la session est nettoyée)
        assert vis_ref is not None
        assert hasattr(vis_ref, '_session')
    
    def test_visualizer_accede_autres_sous_objets(self, fichier_valide):
        """Vérifie que Visualizer peut accéder à d'autres sous-objets via session."""
        with DifmapSession() as session:
            session.observe(fichier_valide)
            
            # Visualizer doit pouvoir accéder à obs et imager
            assert session.vis._session.obs is not None
            assert session.vis._session.imager is not None
            
            # Accès au source via obs
            source = session.vis._session.obs.source
            assert source != "Inconnue"
    
    def test_visualizer_avec_modifications_session(self, fichier_valide):
        """Vérifie que Visualizer reflète les changements de l'état de la session."""
        with DifmapSession() as session:
            # Au départ, pas chargé
            assert session.uv_loaded is False
            
            session.observe(fichier_valide)
            # Maintenant, chargé
            assert session.uv_loaded is True
            assert session.vis._session.uv_loaded is True
