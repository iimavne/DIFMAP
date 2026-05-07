# difmap_wrapper/gui/widgets/plot_toolbars.py
"""
Toolbars spécifiques pour chaque type de plot.

Architecture :
- BasePlotToolbar : Fonctionnalités communes (zoom, refresh, crosshair, help)
- UVPlotToolbar   : UV plot (flag, cut, conjugate, telescope nav)
- RadPlotToolbar  : Radplot (mode 1/2/3, model, errors, residuals, stats)
- MapToolbar      : Maps (color/grey, log/linear, contours, model)
"""

from PyQt6.QtWidgets import (
    QToolBar, QWidget, QSizePolicy, QLabel, 
    QButtonGroup, QToolButton, QSeparator
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QAction, QKeySequence

try:
    import qtawesome as qta
    _HAS_QTA = True
except ImportError:
    _HAS_QTA = False

from difmap_wrapper.gui.styles import DesignSystem

D = DesignSystem


def _icon(name: str, color: str = None) -> object:
    """
    Crée une icône QtAwesome si disponible.
    
    Parameters
    ----------
    name : str
        Nom de l'icône FontAwesome (ex. 'fa5s.search').
    color : str, optional
        Couleur hexadécimale. Si None, utilise la couleur d'accent.
    
    Returns
    -------
    QIcon or None
    """
    if not _HAS_QTA:
        return None
    try:
        return qta.icon(name, color=color or D.ASTRAL_ACCENT)
    except Exception:
        return None


class ToolButton(QToolButton):
    """Bouton de toolbar stylisé pour DIFMAP Modern."""
    
    def __init__(self, text: str, shortcut: str = None, tooltip: str = None,
                 icon_name: str = None, checkable: bool = False, parent=None):
        """
        Parameters
        ----------
        text : str
            Texte affiché (court, 1-2 caractères si possible).
        shortcut : str, optional
            Raccourci clavier (ex. 'Z' pour 'Z').
        tooltip : str, optional
            Infobulle détaillée.
        icon_name : str, optional
            Nom de l'icône FontAwesome.
        checkable : bool
            Si True, le bouton est toggleable.
        """
        super().__init__(parent)
        self.setText(text)
        self.setCheckable(checkable)
        
        if icon_name:
            icon = _icon(icon_name)
            if icon:
                self.setIcon(icon)
        
        # Tooltip avec raccourci
        tip = tooltip or text
        if shortcut:
            tip = f"{tip} [{shortcut}]"
            # Note: les raccourcis clavier sont gérés par le parent
        self.setToolTip(tip)
        
        self._shortcut = shortcut


class BasePlotToolbar(QToolBar):
    """
    Toolbar de base pour tous les plots.
    
    Fonctionnalités communes :
    - Zoom (Z)
    - Reset / Refresh (L)
    - Crosshair (+)
    - Help (H)
    
    Signaux émis :
    - zoom_requested : Demande de zoom
    - reset_requested : Reset de la vue
    - crosshair_toggled : Toggle crosshair
    - help_requested : Afficher l'aide
    """
    
    zoom_requested = pyqtSignal()
    reset_requested = pyqtSignal()
    crosshair_toggled = pyqtSignal(bool)
    help_requested = pyqtSignal()
    
    # Raccourcis communs (correspondent à difmap_src)
    KEY_ZOOM = 'Z'
    KEY_RESET = 'L'
    KEY_CROSSHAIR = '+'
    KEY_HELP = 'H'
    
    def __init__(self, title: str = "Plot Toolbar", parent=None):
        super().__init__(title, parent)
        self.setMovable(False)
        self.setIconSize(QSize(20, 20))
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        
        self._buttons = {}
        self._build_common_actions()
    
    def _build_common_actions(self):
        """Construit les actions communes à tous les plots."""
        # Groupe Navigation
        self._add_separator()
        
        # Zoom
        self.action_zoom = QAction(_icon("fa5s.search-plus"), "Zoom", self)
        self.action_zoom.setToolTip(f"Zoom area [{self.KEY_ZOOM}]")
        self.action_zoom.setShortcut(QKeySequence(self.KEY_ZOOM))
        self.action_zoom.triggered.connect(self.zoom_requested.emit)
        self.addAction(self.action_zoom)
        self._buttons['zoom'] = self.action_zoom
        
        # Reset / Refresh
        self.action_reset = QAction(_icon("fa5s.sync-alt"), "Reset", self)
        self.action_reset.setToolTip(f"Reset view [{self.KEY_RESET}]")
        self.action_reset.setShortcut(QKeySequence(self.KEY_RESET))
        self.action_reset.triggered.connect(self.reset_requested.emit)
        self.addAction(self.action_reset)
        self._buttons['reset'] = self.action_reset
        
        # Groupe Affichage
        self._add_separator()
        
        # Crosshair
        self.action_crosshair = QAction(_icon("fa5s.crosshairs"), "Crosshair", self)
        self.action_crosshair.setToolTip(f"Toggle crosshair [{self.KEY_CROSSHAIR}]")
        self.action_crosshair.setCheckable(True)
        self.action_crosshair.setShortcut(QKeySequence(self.KEY_CROSSHAIR))
        self.action_crosshair.triggered.connect(self._on_crosshair)
        self.addAction(self.action_crosshair)
        self._buttons['crosshair'] = self.action_crosshair
        
        # Spacer extensible
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.addWidget(spacer)
        
        # Help (à droite)
        self.action_help = QAction(_icon("fa5s.question-circle"), "Help", self)
        self.action_help.setToolTip(f"Keyboard shortcuts [{self.KEY_HELP}]")
        self.action_help.setShortcut(QKeySequence(self.KEY_HELP))
        self.action_help.triggered.connect(self.help_requested.emit)
        self.addAction(self.action_help)
        self._buttons['help'] = self.action_help
    
    def _add_separator(self):
        """Ajoute un séparateur visuel."""
        self.addSeparator()
    
    def _on_crosshair(self, checked: bool):
        """Gère le toggle crosshair."""
        self.crosshair_toggled.emit(checked)
    
    def set_crosshair_state(self, enabled: bool):
        """Met à jour l'état du bouton crosshair."""
        self.action_crosshair.setChecked(enabled)


class UVPlotToolbar(BasePlotToolbar):
    """
    Toolbar pour UV Plot.
    
    Actions spécifiques (en plus des communes) :
    - Flag point (A)
    - Cut area (C)
    - Cancel (D)
    - Conjugate (%)
    - Telescope navigation (N/P)
    - Show info (S)
    - Marker size (.)
    - Channel mode (W)
    
    Correspondance difmap_src/uvplot.c
    """
    
    # Signaux spécifiques UV
    flag_requested = pyqtSignal()
    cut_area_requested = pyqtSignal()
    cancel_requested = pyqtSignal()
    conjugate_toggled = pyqtSignal(bool)
    next_telescope = pyqtSignal()
    prev_telescope = pyqtSignal()
    show_info_requested = pyqtSignal()
    marker_size_toggled = pyqtSignal()
    channel_mode_toggled = pyqtSignal(bool)
    
    # Raccourcis UV Plot
    KEY_FLAG = 'A'
    KEY_CUT = 'C'
    KEY_CANCEL = 'D'
    KEY_CONJUGATE = '%'
    KEY_NEXT_TEL = 'N'
    KEY_PREV_TEL = 'P'
    KEY_SHOW = 'S'
    KEY_MARKER = '.'
    KEY_CHANNEL = 'W'
    
    def __init__(self, parent=None):
        super().__init__("UV Plot Toolbar", parent)
        self._build_uv_actions()
    
    def _build_uv_actions(self):
        """Ajoute les actions spécifiques UV au début de la toolbar."""
        # Insérer avant les actions communes
        self.clear()
        
        # Groupe Édition
        self._add_separator()
        
        # Flag point
        self.action_flag = QAction(_icon("fa5s.flag"), "Flag", self)
        self.action_flag.setToolTip(f"Flag nearest point [{self.KEY_FLAG}]")
        self.action_flag.setShortcut(QKeySequence(self.KEY_FLAG))
        self.action_flag.triggered.connect(self.flag_requested.emit)
        self.addAction(self.action_flag)
        
        # Cut area
        self.action_cut = QAction(_icon("fa5s.cut"), "Cut Area", self)
        self.action_cut.setToolTip(f"Select area to flag [{self.KEY_CUT}]")
        self.action_cut.setShortcut(QKeySequence(self.KEY_CUT))
        self.action_cut.triggered.connect(self.cut_area_requested.emit)
        self.addAction(self.action_cut)
        
        # Cancel
        self.action_cancel = QAction(_icon("fa5s.times"), "Cancel", self)
        self.action_cancel.setToolTip(f"Cancel selection [{self.KEY_CANCEL}]")
        self.action_cancel.setShortcut(QKeySequence(self.KEY_CANCEL))
        self.action_cancel.triggered.connect(self.cancel_requested.emit)
        self.addAction(self.action_cancel)
        
        # Groupe Affichage UV
        self._add_separator()
        
        # Conjugate
        self.action_conjugate = QAction(_icon("fa5s.exchange-alt"), "Conjugate", self)
        self.action_conjugate.setToolTip(f"Toggle conjugate vis [{self.KEY_CONJUGATE}]")
        self.action_conjugate.setCheckable(True)
        self.action_conjugate.setShortcut(QKeySequence(self.KEY_CONJUGATE))
        self.action_conjugate.triggered.connect(self._on_conjugate)
        self.addAction(self.action_conjugate)
        
        # Marker size
        self.action_marker = QAction(_icon("fa5s.circle"), "Size", self)
        self.action_marker.setToolTip(f"Toggle marker size [{self.KEY_MARKER}]")
        self.action_marker.setShortcut(QKeySequence(self.KEY_MARKER))
        self.action_marker.triggered.connect(self.marker_size_toggled.emit)
        self.addAction(self.action_marker)
        
        # Groupe Télescope
        self._add_separator()
        
        # Prev telescope
        self.action_prev_tel = QAction(_icon("fa5s.arrow-left"), "Prev", self)
        self.action_prev_tel.setToolTip(f"Previous telescope [{self.KEY_PREV_TEL}]")
        self.action_prev_tel.setShortcut(QKeySequence(self.KEY_PREV_TEL))
        self.action_prev_tel.triggered.connect(self.prev_telescope.emit)
        self.addAction(self.action_prev_tel)
        
        # Next telescope
        self.action_next_tel = QAction(_icon("fa5s.arrow-right"), "Next", self)
        self.action_next_tel.setToolTip(f"Next telescope [{self.KEY_NEXT_TEL}]")
        self.action_next_tel.setShortcut(QKeySequence(self.KEY_NEXT_TEL))
        self.action_next_tel.triggered.connect(self.next_telescope.emit)
        self.addAction(self.action_next_tel)
        
        # Groupe Info
        self._add_separator()
        
        # Show info
        self.action_info = QAction(_icon("fa5s.info-circle"), "Info", self)
        self.action_info.setToolTip(f"Show nearest point info [{self.KEY_SHOW}]")
        self.action_info.setShortcut(QKeySequence(self.KEY_SHOW))
        self.action_info.triggered.connect(self.show_info_requested.emit)
        self.addAction(self.action_info)
        
        # Channel mode
        self.action_channel = QAction(_icon("fa5s.bars"), "Channel", self)
        self.action_channel.setToolTip(f"Toggle channel mode [{self.KEY_CHANNEL}]")
        self.action_channel.setCheckable(True)
        self.action_channel.setShortcut(QKeySequence(self.KEY_CHANNEL))
        self.action_channel.triggered.connect(self._on_channel_mode)
        self.addAction(self.action_channel)
        
        # Ajouter les actions communes
        self._build_common_actions()
    
    def _on_conjugate(self, checked: bool):
        self.conjugate_toggled.emit(checked)
    
    def _on_channel_mode(self, checked: bool):
        self.channel_mode_toggled.emit(checked)
    
    def set_conjugate_state(self, enabled: bool):
        self.action_conjugate.setChecked(enabled)


class RadPlotToolbar(BasePlotToolbar):
    """
    Toolbar pour Radplot.
    
    Actions spécifiques :
    - Mode 1/2/3 (Amplitude/Phase/Both)
    - Model (M)
    - Residuals (-)
    - Errors (E)
    - Stats (S)
    - Vector stats (V)
    - UV Range (U)
    - Telescope nav (N/P)
    - Marker size (.)
    
    Correspondance difmap_src/uvradplt.c
    """
    
    # Signaux spécifiques Radplot
    mode_changed = pyqtSignal(int)  # 1=amp, 2=phase, 3=both
    model_toggled = pyqtSignal(bool)
    residuals_toggled = pyqtSignal(bool)
    errors_toggled = pyqtSignal(bool)
    stats_requested = pyqtSignal()
    vector_stats_requested = pyqtSignal()
    uv_range_requested = pyqtSignal()
    next_telescope = pyqtSignal()
    prev_telescope = pyqtSignal()
    marker_size_toggled = pyqtSignal()
    
    # Raccourcis Radplot
    KEY_AMP = '1'
    KEY_PHASE = '2'
    KEY_BOTH = '3'
    KEY_MODEL = 'M'
    KEY_RESIDUALS = '-'
    KEY_ERRORS = 'E'
    KEY_STATS = 'S'
    KEY_VEC_STATS = 'V'
    KEY_UV_RANGE = 'U'
    KEY_NEXT_TEL = 'N'
    KEY_PREV_TEL = 'P'
    KEY_MARKER = '.'
    
    def __init__(self, parent=None):
        super().__init__("Radplot Toolbar", parent)
        self._current_mode = 3  # Both par défaut
    
    def _build_common_actions(self):
        """Surcharge pour construire les actions Radplot."""
        self.clear()
        
        # Groupe Mode
        self._add_separator()
        
        # Mode buttons (mutuellement exclusifs)
        self._mode_group = QButtonGroup(self)
        self._mode_group.setExclusive(True)
        
        self.action_amp = QAction(_icon("fa5s.chart-line"), "Amp", self)
        self.action_amp.setToolTip(f"Amplitude only [{self.KEY_AMP}]")
        self.action_amp.setCheckable(True)
        self.action_amp.setShortcut(QKeySequence(self.KEY_AMP))
        self.action_amp.triggered.connect(lambda: self._set_mode(1))
        self.addAction(self.action_amp)
        
        self.action_phase = QAction(_icon("fa5s.chart-area"), "Phase", self)
        self.action_phase.setToolTip(f"Phase only [{self.KEY_PHASE}]")
        self.action_phase.setCheckable(True)
        self.action_phase.setShortcut(QKeySequence(self.KEY_PHASE))
        self.action_phase.triggered.connect(lambda: self._set_mode(2))
        self.addAction(self.action_phase)
        
        self.action_both = QAction(_icon("fa5s.columns"), "Both", self)
        self.action_both.setToolTip(f"Amplitude & Phase [{self.KEY_BOTH}]")
        self.action_both.setCheckable(True)
        self.action_both.setChecked(True)  # Défaut
        self.action_both.setShortcut(QKeySequence(self.KEY_BOTH))
        self.action_both.triggered.connect(lambda: self._set_mode(3))
        self.addAction(self.action_both)
        
        # Groupe Affichage
        self._add_separator()
        
        # Model
        self.action_model = QAction(_icon("fa5s.project-diagram"), "Model", self)
        self.action_model.setToolTip(f"Toggle model display [{self.KEY_MODEL}]")
        self.action_model.setCheckable(True)
        self.action_model.setShortcut(QKeySequence(self.KEY_MODEL))
        self.action_model.triggered.connect(self._on_model)
        self.addAction(self.action_model)
        
        # Residuals
        self.action_residuals = QAction(_icon("fa5s.minus"), "Residuals", self)
        self.action_residuals.setToolTip(f"Show residuals (Data-Model) [{self.KEY_RESIDUALS}]")
        self.action_residuals.setCheckable(True)
        self.action_residuals.setShortcut(QKeySequence(self.KEY_RESIDUALS))
        self.action_residuals.triggered.connect(self._on_residuals)
        self.addAction(self.action_residuals)
        
        # Errors
        self.action_errors = QAction(_icon("fa5s.ruler-vertical"), "Errors", self)
        self.action_errors.setToolTip(f"Toggle error plot [{self.KEY_ERRORS}]")
        self.action_errors.setCheckable(True)
        self.action_errors.setShortcut(QKeySequence(self.KEY_ERRORS))
        self.action_errors.triggered.connect(self._on_errors)
        self.addAction(self.action_errors)
        
        # Groupe Stats
        self._add_separator()
        
        # Stats
        self.action_stats = QAction(_icon("fa5s.chart-bar"), "Stats", self)
        self.action_stats.setToolTip(f"Scalar statistics [{self.KEY_STATS}]")
        self.action_stats.setShortcut(QKeySequence(self.KEY_STATS))
        self.action_stats.triggered.connect(self.stats_requested.emit)
        self.addAction(self.action_stats)
        
        # Vector stats
        self.action_vec_stats = QAction(_icon("fa5s.vector-square"), "Vec", self)
        self.action_vec_stats.setToolTip(f"Vector statistics [{self.KEY_VEC_STATS}]")
        self.action_vec_stats.setShortcut(QKeySequence(self.KEY_VEC_STATS))
        self.action_vec_stats.triggered.connect(self.vector_stats_requested.emit)
        self.addAction(self.action_vec_stats)
        
        # UV Range
        self.action_uv_range = QAction(_icon("fa5s.arrows-alt-h"), "UV Range", self)
        self.action_uv_range.setToolTip(f"Select UV range [{self.KEY_UV_RANGE}]")
        self.action_uv_range.setShortcut(QKeySequence(self.KEY_UV_RANGE))
        self.action_uv_range.triggered.connect(self.uv_range_requested.emit)
        self.addAction(self.action_uv_range)
        
        # Groupe Télescope
        self._add_separator()
        
        # Prev/Next telescope
        self.action_prev_tel = QAction(_icon("fa5s.arrow-left"), "Prev", self)
        self.action_prev_tel.setToolTip(f"Previous telescope [{self.KEY_PREV_TEL}]")
        self.action_prev_tel.setShortcut(QKeySequence(self.KEY_PREV_TEL))
        self.action_prev_tel.triggered.connect(self.prev_telescope.emit)
        self.addAction(self.action_prev_tel)
        
        self.action_next_tel = QAction(_icon("fa5s.arrow-right"), "Next", self)
        self.action_next_tel.setToolTip(f"Next telescope [{self.KEY_NEXT_TEL}]")
        self.action_next_tel.setShortcut(QKeySequence(self.KEY_NEXT_TEL))
        self.action_next_tel.triggered.connect(self.next_telescope.emit)
        self.addAction(self.action_next_tel)
        
        # Marker size
        self.action_marker = QAction(_icon("fa5s.circle"), "Size", self)
        self.action_marker.setToolTip(f"Toggle marker size [{self.KEY_MARKER}]")
        self.action_marker.setShortcut(QKeySequence(self.KEY_MARKER))
        self.action_marker.triggered.connect(self.marker_size_toggled.emit)
        self.addAction(self.action_marker)
        
        # Actions communes (zoom, reset, crosshair, help)
        super()._build_common_actions()
    
    def _set_mode(self, mode: int):
        """Change le mode d'affichage (1=amp, 2=phase, 3=both)."""
        self._current_mode = mode
        self.mode_changed.emit(mode)
    
    def _on_model(self, checked: bool):
        self.model_toggled.emit(checked)
    
    def _on_residuals(self, checked: bool):
        self.residuals_toggled.emit(checked)
    
    def _on_errors(self, checked: bool):
        self.errors_toggled.emit(checked)
    
    def set_mode(self, mode: int):
        """Met à jour le mode depuis l'extérieur."""
        self._current_mode = mode
        self.action_amp.setChecked(mode == 1)
        self.action_phase.setChecked(mode == 2)
        self.action_both.setChecked(mode == 3)
    
    def set_model_state(self, enabled: bool):
        self.action_model.setChecked(enabled)
    
    def set_residuals_state(self, enabled: bool):
        self.action_residuals.setChecked(enabled)
    
    def set_errors_state(self, enabled: bool):
        self.action_errors.setChecked(enabled)


class MapToolbar(BasePlotToolbar):
    """
    Toolbar pour Dirty/Clean/Residual Maps.
    
    Actions spécifiques :
    - Color/Grey (C/G)
    - Log/Linear scale (T)
    - Contours
    - Model display (M)
    - Pixel value (V)
    - Stats (S)
    - Clean window (A)
    - Delete window (D)
    
    Correspondance difmap_src/maplot.c
    """
    
    # Signaux spécifiques Map
    color_mode_changed = pyqtSignal(bool)  # True=color, False=grey
    scale_changed = pyqtSignal(str)  # 'linear' or 'log'
    contours_toggled = pyqtSignal(bool)
    model_toggled = pyqtSignal(bool)
    pixel_value_requested = pyqtSignal()
    stats_requested = pyqtSignal()
    window_add_requested = pyqtSignal()
    window_delete_requested = pyqtSignal()
    fiddle_requested = pyqtSignal()
    
    # Raccourcis Map
    KEY_COLOR = 'C'
    KEY_GREY = 'G'
    KEY_SCALE = 'T'
    KEY_MODEL = 'M'
    KEY_PIXEL = 'V'
    KEY_STATS = 'S'
    KEY_WINDOW = 'A'
    KEY_DELETE = 'D'
    KEY_FIDDLE = 'F'
    
    def __init__(self, parent=None):
        super().__init__("Map Toolbar", parent)
        self._is_color = True
        self._is_log = False
    
    def _build_common_actions(self):
        """Surcharge pour construire les actions Map."""
        self.clear()
        
        # Groupe Affichage
        self._add_separator()
        
        # Color
        self.action_color = QAction(_icon("fa5s.palette"), "Color", self)
        self.action_color.setToolTip(f"Pseudo-color [{self.KEY_COLOR}]")
        self.action_color.setCheckable(True)
        self.action_color.setChecked(True)
        self.action_color.setShortcut(QKeySequence(self.KEY_COLOR))
        self.action_color.triggered.connect(lambda: self._set_color_mode(True))
        self.addAction(self.action_color)
        
        # Grey
        self.action_grey = QAction(_icon("fa5s.adjust"), "Grey", self)
        self.action_grey.setToolTip(f"Grey-scale [{self.KEY_GREY}]")
        self.action_grey.setCheckable(True)
        self.action_grey.setShortcut(QKeySequence(self.KEY_GREY))
        self.action_grey.triggered.connect(lambda: self._set_color_mode(False))
        self.addAction(self.action_grey)
        
        # Log/Linear
        self.action_scale = QAction(_icon("fa5s.chart-line"), "Log", self)
        self.action_scale.setToolTip(f"Toggle log/linear [{self.KEY_SCALE}]")
        self.action_scale.setCheckable(True)
        self.action_scale.setShortcut(QKeySequence(self.KEY_SCALE))
        self.action_scale.triggered.connect(self._on_scale)
        self.addAction(self.action_scale)
        
        # Groupe Contours
        self._add_separator()
        
        # Contours toggle
        self.action_contours = QAction(_icon("fa5s.border-all"), "Contours", self)
        self.action_contours.setToolTip("Toggle contour lines")
        self.action_contours.setCheckable(True)
        self.action_contours.setChecked(True)
        self.action_contours.triggered.connect(self._on_contours)
        self.addAction(self.action_contours)
        
        # Model
        self.action_model = QAction(_icon("fa5s.project-diagram"), "Model", self)
        self.action_model.setToolTip(f"Toggle model components [{self.KEY_MODEL}]")
        self.action_model.setCheckable(True)
        self.action_model.setShortcut(QKeySequence(self.KEY_MODEL))
        self.action_model.triggered.connect(self._on_model)
        self.addAction(self.action_model)
        
        # Groupe Info
        self._add_separator()
        
        # Pixel value
        self.action_pixel = QAction(_icon("fa5s.crosshairs"), "Value", self)
        self.action_pixel.setToolTip(f"Show pixel value [{self.KEY_PIXEL}]")
        self.action_pixel.setShortcut(QKeySequence(self.KEY_PIXEL))
        self.action_pixel.triggered.connect(self.pixel_value_requested.emit)
        self.addAction(self.action_pixel)
        
        # Stats
        self.action_stats = QAction(_icon("fa5s.chart-bar"), "Stats", self)
        self.action_stats.setToolTip(f"Window statistics [{self.KEY_STATS}]")
        self.action_stats.setShortcut(QKeySequence(self.KEY_STATS))
        self.action_stats.triggered.connect(self.stats_requested.emit)
        self.addAction(self.action_stats)
        
        # Groupe Windows
        self._add_separator()
        
        # Add window
        self.action_window = QAction(_icon("fa5s.plus-square"), "Window", self)
        self.action_window.setToolTip(f"Add clean window [{self.KEY_WINDOW}]")
        self.action_window.setShortcut(QKeySequence(self.KEY_WINDOW))
        self.action_window.triggered.connect(self.window_add_requested.emit)
        self.addAction(self.action_window)
        
        # Delete window
        self.action_delete = QAction(_icon("fa5s.minus-square"), "Delete", self)
        self.action_delete.setToolTip(f"Delete window [{self.KEY_DELETE}]")
        self.action_delete.setShortcut(QKeySequence(self.KEY_DELETE))
        self.action_delete.triggered.connect(self.window_delete_requested.emit)
        self.addAction(self.action_delete)
        
        # Fiddle
        self.action_fiddle = QAction(_icon("fa5s.sliders-h"), "Fiddle", self)
        self.action_fiddle.setToolTip(f"Adjust color table [{self.KEY_FIDDLE}]")
        self.action_fiddle.setShortcut(QKeySequence(self.KEY_FIDDLE))
        self.action_fiddle.triggered.connect(self.fiddle_requested.emit)
        self.addAction(self.action_fiddle)
        
        # Actions communes (zoom, reset, crosshair, help)
        super()._build_common_actions()
    
    def _set_color_mode(self, is_color: bool):
        """Change le mode couleur/gris."""
        self._is_color = is_color
        self.action_color.setChecked(is_color)
        self.action_grey.setChecked(not is_color)
        self.color_mode_changed.emit(is_color)
    
    def _on_scale(self, checked: bool):
        """Toggle log/linear."""
        self._is_log = checked
        self.action_scale.setText("Log" if checked else "Linear")
        self.scale_changed.emit('log' if checked else 'linear')
    
    def _on_contours(self, checked: bool):
        self.contours_toggled.emit(checked)
    
    def _on_model(self, checked: bool):
        self.model_toggled.emit(checked)
    
    def set_color_mode(self, is_color: bool):
        self._is_color = is_color
        self.action_color.setChecked(is_color)
        self.action_grey.setChecked(not is_color)
    
    def set_scale(self, scale: str):
        self._is_log = (scale == 'log')
        self.action_scale.setChecked(self._is_log)
        self.action_scale.setText("Log" if self._is_log else "Linear")
    
    def set_model_state(self, enabled: bool):
        self.action_model.setChecked(enabled)
    
    def set_contours_state(self, enabled: bool):
        self.action_contours.setChecked(enabled)


# Mapping des toolbars par type de plot
TOOLBAR_CLASSES = {
    'uv': UVPlotToolbar,
    'radplot': RadPlotToolbar,
    'dirty_map': MapToolbar,
    'clean_map': MapToolbar,
    'residual_map': MapToolbar,
}
