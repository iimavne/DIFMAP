# difmap_wrapper/gui/utils.py
"""Utilitaires GUI : styles matplotlib, handler de log, routeur de signaux."""

import logging
from PyQt6.QtCore import QObject, pyqtSignal


# ── MatplotlibStyler ─────────────────────────────────────────────────────────

class MatplotlibStyler:
    """Applique un style cohérent à tous les axes Matplotlib de l'application."""

    COLORS = {
        'title':      '#2C3E50',
        'axis_label': '#5A7080',
        'tick':       '#5A7080',
        'grid':       '#E8EDF2',
        'spine':      '#C8D4E0',
        'background': 'white',
    }

    SIZES = {
        'title':            10,
        'label':            9,
        'tick':             8,
        'grid_width':       0.5,
        'line_width_spine': 0.8,
    }

    @staticmethod
    def setup_axes(ax, title_text="", xlabel="", ylabel=""):
        ax.clear()
        ax.set_facecolor(MatplotlibStyler.COLORS['background'])
        ax.get_figure().set_facecolor(MatplotlibStyler.COLORS['background'])
        ax.set_title(title_text, fontsize=MatplotlibStyler.SIZES['title'],
                     color=MatplotlibStyler.COLORS['title'], pad=6)
        ax.set_xlabel(xlabel, fontsize=MatplotlibStyler.SIZES['label'],
                      color=MatplotlibStyler.COLORS['axis_label'])
        ax.set_ylabel(ylabel, fontsize=MatplotlibStyler.SIZES['label'],
                      color=MatplotlibStyler.COLORS['axis_label'])
        ax.grid(color=MatplotlibStyler.COLORS['grid'], linestyle='-',
                linewidth=MatplotlibStyler.SIZES['grid_width'], alpha=0.8)
        ax.tick_params(axis='both', which='major',
                       labelsize=MatplotlibStyler.SIZES['tick'],
                       colors=MatplotlibStyler.COLORS['tick'])
        for spine in ax.spines.values():
            spine.set_color(MatplotlibStyler.COLORS['spine'])
            spine.set_linewidth(MatplotlibStyler.SIZES['line_width_spine'])

    @staticmethod
    def customize_colors(d):
        MatplotlibStyler.COLORS.update(d)

    @staticmethod
    def customize_sizes(d):
        MatplotlibStyler.SIZES.update(d)


# ── DifmapLogHandler ─────────────────────────────────────────────────────────

class _LogSignalEmitter(QObject):
    log_emitted = pyqtSignal(str, str)


class DifmapLogHandler(logging.Handler):
    """
    Intercepte les logs du namespace 'difmap' et les route vers ImprovedLogConsole.

    Niveaux personnalisés via extra dict :
        logger.info(msg, extra={'difmap_level': 'success'})
    """

    _LEVEL_MAP = {
        logging.DEBUG:    'debug',
        logging.INFO:     'info',
        logging.WARNING:  'warning',
        logging.ERROR:    'error',
        logging.CRITICAL: 'error',
    }

    def __init__(self):
        super().__init__()
        self._emitter = _LogSignalEmitter()
        self.log_emitted = self._emitter.log_emitted
        self.setFormatter(logging.Formatter('%(message)s'))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = getattr(record, 'difmap_level', None)
            if level is None:
                level = self._LEVEL_MAP.get(record.levelno, 'info')
            msg = self.format(record)
            self._emitter.log_emitted.emit(level, msg)
        except Exception:
            self.handleError(record)


# ── SignalRouter ─────────────────────────────────────────────────────────────

class SignalRouter:
    """Connecte les signaux PyQt aux actions des éditeurs de plots."""

    def __init__(self, main_window):
        self.window = main_window
        self.toolbar = main_window.toolbar
        self.control_panel = main_window.control_panel

    def _get_active_editor(self):
        return self.window._get_active_editor()

    def route_toolbar_action(self, action_attr, method_name, args=None):
        if not hasattr(self.toolbar, action_attr):
            return
        action = getattr(self.toolbar, action_attr)
        args = args or []

        def callback():
            editor = self._get_active_editor()
            if editor and hasattr(editor, method_name):
                getattr(editor, method_name)(*args)
                if hasattr(editor, 'fig') and hasattr(editor.fig, 'canvas'):
                    editor.fig.canvas.setFocus()

        action.triggered.connect(callback)

    def route_button_both(self, button_attr, method_name, args=None):
        if not hasattr(self.control_panel, button_attr):
            logging.getLogger(__name__).warning(f"ControlPanel has no attribute {button_attr}")
            return
        button = getattr(self.control_panel, button_attr)
        args = args or []

        def callback():
            for widget in [self.window.plot_widget, self.window.radplot_widget]:
                if widget and hasattr(widget, 'editor') and widget.editor:
                    editor = widget.editor
                    if hasattr(editor, method_name):
                        getattr(editor, method_name)(*args)
            active_editor = self._get_active_editor()
            if active_editor and hasattr(active_editor, 'fig') and hasattr(active_editor.fig, 'canvas'):
                active_editor.fig.canvas.setFocus()

        button.clicked.connect(callback)

    def route_checkbox_both(self, checkbox_attr, method_name):
        if not hasattr(self.control_panel, checkbox_attr):
            logging.getLogger(__name__).warning(f"ControlPanel has no attribute {checkbox_attr}")
            return
        checkbox = getattr(self.control_panel, checkbox_attr)

        def callback(checked):
            for widget in [self.window.plot_widget, self.window.radplot_widget]:
                if widget and hasattr(widget, 'editor') and widget.editor:
                    editor = widget.editor
                    if hasattr(editor, method_name):
                        getattr(editor, method_name)(checked)
            active_editor = self._get_active_editor()
            if active_editor and hasattr(active_editor, 'fig') and hasattr(active_editor.fig, 'canvas'):
                active_editor.fig.canvas.setFocus()

        checkbox.toggled.connect(callback)

    def route_slider_both(self, slider_attr, method_name):
        if not hasattr(self.control_panel, slider_attr):
            logging.getLogger(__name__).warning(f"ControlPanel has no attribute {slider_attr}")
            return
        slider = getattr(self.control_panel, slider_attr)

        def callback(value):
            for widget in [self.window.plot_widget, self.window.radplot_widget]:
                if widget and hasattr(widget, 'editor') and widget.editor:
                    editor = widget.editor
                    if hasattr(editor, method_name):
                        getattr(editor, method_name)(float(value))
            active_editor = self._get_active_editor()
            if active_editor and hasattr(active_editor, 'fig') and hasattr(active_editor.fig, 'canvas'):
                active_editor.fig.canvas.setFocus()

        slider.valueChanged.connect(callback)
