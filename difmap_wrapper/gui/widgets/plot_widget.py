# difmap_wrapper/gui/plot_widget.py
import numpy as np
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import QLabel, QComboBox, QPushButton
try:
    import qtawesome as qta
    _HAS_QTA = True
except ImportError:
    _HAS_QTA = False

from .base_plot_widget import BasePlotWidget
from difmap_wrapper.gui.editors.uv_editor import UVPlotEditor
from difmap_wrapper.gui.utils import MatplotlibStyler
from difmap_wrapper.gui.styles import DesignSystem

_TOOLBAR_QSS = f"""
QWidget#PlotToolbar {{
    background-color: {DesignSystem.SURFACE_ALT};
    border-bottom: 1px solid {DesignSystem.BORDER};
    padding: 4px 0;
    height: 32px;
}}
QPushButton {{
    background-color: {DesignSystem.SURFACE};
    color: {DesignSystem.TEXT};
    border: 1px solid {DesignSystem.BORDER};
    border-radius: 5px;
    padding: 4px 10px;
    font-size: 10px;
    min-height: 26px;
    min-width: 70px;
}}
QPushButton:hover  {{
    background-color: {DesignSystem.SURFACE_ALT};
    border-color: {DesignSystem.PRIMARY};
    color: {DesignSystem.TEXT};
}}
QPushButton:pressed {{
    background-color: {DesignSystem.BORDER_LIGHT};
    border-color: {DesignSystem.PRIMARY_ACTIVE};
    color: {DesignSystem.TEXT};
}}
QLabel {{
    color: {DesignSystem.TEXT_MUTED};
    font-size: 10px;
    font-weight: bold;
    background: transparent;
    padding-left: 4px;
}}
QComboBox {{
    background-color: {DesignSystem.SURFACE};
    color: {DesignSystem.TEXT};
    border: 1px solid {DesignSystem.BORDER};
    border-radius: 5px;
    padding: 3px 8px;
    font-size: 10px;
    min-width: 180px;
    min-height: 26px;
}}
QComboBox:hover {{ border-color: {DesignSystem.PRIMARY}; }}
QComboBox::drop-down {{ border: none; width: 18px; }}
QComboBox::down-arrow {{ width: 10px; height: 10px; }}
"""


def _icon(name: str, color: str = "#C8DCF0"):
    """Return a qtawesome icon or None if unavailable."""
    if not _HAS_QTA:
        return None
    try:
        return qta.icon(name, color=color)
    except Exception:
        return None


def _make_button(text: str, icon_name: str = None) -> QPushButton:
    btn = QPushButton(text)
    if icon_name:
        ico = _icon(icon_name)
        if ico:
            btn.setIcon(ico)
            btn.setIconSize(QSize(14, 14))
    return btn


class UVPlotWidget(BasePlotWidget):
    """
    Widget PyQt6 encapsulant un graphique Matplotlib interactif pour le plan UV.

    M3 — reload_data() permet de réutiliser le widget sans détruire l'onglet.
         Les callbacks sont stockés à l'init pour être réutilisés lors du reload.
    """

    def __init__(self, observation, data, parent=None,
                 save_callback=None, sync_callback=None):
        """
        Parameters
        ----------
        observation : Observation
            Objet contenant les métadonnées et le masque de flagging.
        data : dict
            Données UV brutes (clés ``'u'``, ``'v'``, ``'amp'``, ``'phase'``, ``'weight'``...).
        parent : QWidget, optional
            Widget parent Qt.
        save_callback : callable, optional
            Fonction appelée lors de la sauvegarde (ouvre un dialogue fichier).
        sync_callback : callable, optional
            Fonction appelée pour synchroniser l'état éditeur → MainWindow.
        """
        super().__init__(parent=parent, figsize=(8, 8), layout_type='constrained')

        # Stocker les callbacks pour les réutiliser dans reload_data()
        self._save_callback = save_callback
        self._sync_callback = sync_callback

        self.observation = observation
        self.data        = data

        self._build_local_toolbar()
        self._draw_and_create_editor()

    # =========================================================
    # TOOLBAR LOCALE
    # =========================================================

    _UV_TOOLS = [
        ("Inspect  [s]",           "INSPECT"),
        ("Pan  [M]",               "PAN"),
        ("Zoom Box  [Z]",          "ZOOM"),
        ("Flag Box  [C]",          "CUT"),
        
    ]

    def _build_local_toolbar(self) -> None:
        """Crée la mini-toolbar au-dessus du canvas UV."""
        row = self.plot_toolbar_row
        row.setObjectName("PlotToolbar")
        row.setStyleSheet(_TOOLBAR_QSS)
        row.setFixedHeight(32)
        row.setVisible(True)
        lay = self.plot_toolbar_layout

        lay.addWidget(QLabel("  Tools:"))
        self._tool_combo = QComboBox()
        self._tool_combo.setToolTip("Tool active (Keyboard shortcut)")
        for label, data in self._UV_TOOLS:
            self._tool_combo.addItem(label, data)
        lay.addWidget(self._tool_combo)

        lay.addSpacing(10)

        self._btn_undo    = _make_button("Undo Flag [U]",    "fa5s.undo")
        self._btn_reset   = _make_button("Reset [R]",   "fa5s.expand-arrows-alt")
        self._btn_dezoom  = _make_button("Dézoom [O]",  "fa5s.search-minus")
        self._btn_refresh = _make_button("Refresh [L]", "fa5s.sync-alt")
        for btn, tip in [
            (self._btn_undo,    "Annuler le dernier flagging"),
            (self._btn_reset,   "Réinitialiser la vue (tous les graphiques)"),
            (self._btn_dezoom,  "Dézoomer de 50 %"),
            (self._btn_refresh, "Rafraîchir l'affichage"),
        ]:
            btn.setToolTip(tip)
            lay.addWidget(btn)

        lay.addStretch()

        # Connexions — les lambdas capturent self.editor à l'appel, pas à la connexion
        self._tool_combo.currentIndexChanged.connect(self._on_tool_changed)
        self._btn_undo.clicked.connect(
            lambda: self._on_button_click(self.editor.action_undo, None) if self.editor else None)
        self._btn_reset.clicked.connect(
            lambda: self._on_button_click(self.editor.action_home, None) if self.editor else None)
        self._btn_dezoom.clicked.connect(
            lambda: self._on_button_click(self.editor.action_dezoom, None) if self.editor else None)
        self._btn_refresh.clicked.connect(
            lambda: self._on_button_click(self.editor.action_redisplay, None) if self.editor else None)

    def _on_tool_changed(self, index: int) -> None:
        """Applique le mode sélectionné dans le combo à l'éditeur actif."""
        if index < 0 or not self.editor:
            return
        mode = self._tool_combo.itemData(index)
        if mode == "INSPECT":
            self.editor.inspect_active = True
            self.editor._set_mode(None)
        else:
            self.editor.inspect_active = False
            self.editor._set_mode(mode)
        self.canvas.setFocus()

    def _on_button_click(self, func, arg=None):
        """Exécute l'action du bouton et remet le focus sur le canvas pour les raccourcis clavier."""
        if func:
            func(arg)
        self.canvas.setFocus()

    def sync_inspect_state(self, active: bool) -> None:
        """Synchronise le combo quand l'état inspect change via raccourci clavier."""
        if not hasattr(self, '_tool_combo'):
            return
        if active:
            self._tool_combo.blockSignals(True)
            self._tool_combo.setCurrentIndex(0)   # "Inspect"
            self._tool_combo.blockSignals(False)

    def sync_tool_state(self, tool: str) -> None:
        """Synchronise le combo de la toolbar locale avec le mode actif de l'éditeur."""
        if not hasattr(self, '_tool_combo') or tool is None:
            return
        if tool == "INSPECT":
            target_index = 0
        else:
            target_index = next((i for i in range(self._tool_combo.count())
                                 if self._tool_combo.itemData(i) == tool), -1)
        if target_index < 0:
            return
        self._tool_combo.blockSignals(True)
        self._tool_combo.setCurrentIndex(target_index)
        self._tool_combo.blockSignals(False)

    def _draw_and_create_editor(self) -> None:
        """Trace les scatter plots et instancie l'éditeur."""
        self.ax.clear()
        self._setup_axes()
        
        u = self.data['u'] / 1e6
        v = self.data['v'] / 1e6

        self.editor = UVPlotEditor(
            observation=self.observation,
            fig=self.fig,
            ax=self.ax,
            data=self.data,
            base_color=DesignSystem.PLOT_DATA,
            save_callback=self._save_callback,
            sync_callback=self._sync_callback,
        )
        self.editor.update_marker_size(self.editor.marker_size_pct)
        # Appliquer le mode courant du combo au nouvel éditeur
        if hasattr(self, '_tool_combo'):
            self._on_tool_changed(self._tool_combo.currentIndex())

    def reload_data(self, data, observation=None) -> None:
        """
        M3 — Met à jour les données sans détruire/recréer le widget ni l'onglet.

        Déconnecte les écouteurs de l'ancien éditeur (cleanup()), puis recrée
        l'éditeur proprement.
        
        Restore l'état du crosshair du nouvel éditeur.

        Parameters
        ----------
        data : dict
            Nouvelles données UV depuis Observation.get_data().
        observation : Observation, optional
            Nouvelle observation (ex : après changement de polarisation).
        """
        if observation is not None:
            self.observation = observation
        self.data = data

        # : Sauvegarder l'état du crosshair AVANT cleanup
        crosshair_was_active = False
        if self.editor and hasattr(self.editor, 'cursor_active'):
            crosshair_was_active = self.editor.cursor_active

        # Déconnexion propre des anciens écouteurs Matplotlib
        if self.editor:
            self.editor.cleanup()

        # Recréation de l'éditeur (nouvelles connexions événements, nouveau masque)
        self._draw_and_create_editor()
        
        # Restaurer l'état du crosshair sur le nouvel éditeur
        if crosshair_was_active and self.editor and hasattr(self.editor, 'cursor_active'):
            if not self.editor.cursor_active:
                # Force l'activation du crosshair sur le nouvel éditeur
                self.editor.action_toggle_crosshair(None)
        
        self.fig.canvas.draw()

    def _setup_axes(self):
        """Configure les axes spécifiques au plan UV."""
        MatplotlibStyler.setup_axes(
            self.ax,
            title_text="UV Coverage",
            xlabel=r"U ($M\lambda$)",
            ylabel=r"V ($M\lambda$)"
        )
        self.ax.invert_xaxis()
        self.ax.set_aspect('equal', adjustable='box')
