# difmap_wrapper/gui/styles.py
"""Styles unifiés : palette de couleurs DesignSystem et thèmes clair/sombre."""


class DesignSystem:
    """
    Palette "bleu astral" + centre blanc + terminal sombre.
    Panneau gauche  →  bleu astral profond
    Zone centrale   →  blanc / gris très clair
    Terminal droit  →  quasi-noir
    """

    ASTRAL_DEEPEST = "#0A1628"
    ASTRAL_DEEP    = "#0E1F35"
    ASTRAL_BG      = "#162D4A"
    ASTRAL_SURFACE = "#1C3A5E"
    ASTRAL_HOVER   = "#254F7A"
    ASTRAL_BORDER  = "#2A4D72"
    ASTRAL_TEXT    = "#D8E7F7"
    ASTRAL_DIM     = "#A8BCD2"
    ASTRAL_MUTED   = "#2D4862"
    ASTRAL_ACCENT  = "#4A98D4"

    BACKGROUND   = "#F4F7FA"
    SURFACE      = "#FFFFFF"
    SURFACE_ALT  = "#E8ECF2"
    BORDER       = "#C8D4E0"
    BORDER_LIGHT = "#DDE4EC"

    TEXT           = "#1C2B3A"
    TEXT_SECONDARY = "#40566F"
    TEXT_MUTED     = "#6F849B"

    TERMINAL_BG     = "#0D1117"
    TERMINAL_TEXT   = "#C1D1E2"
    TERMINAL_BORDER = "#1C2535"

    PRIMARY        = ASTRAL_ACCENT
    PRIMARY_HOVER  = "#5BAAE0"
    PRIMARY_ACTIVE = "#3A88C4"

    SUCCESS = "#2E7D32"
    WARNING = "#E65100"
    DANGER  = "#C62828"
    INFO    = "#00838F"

    PLOT_DATA           = "#1565C0"
    PLOT_FOCUS          = "#C62828"
    PLOT_TITLE_INACTIVE = "#7090B0"
    PLOT_MODEL          = "#E65100"
    PLOT_ERROR          = "#00695C"

    FONT_FAMILY = "'Segoe UI', 'Roboto', 'Helvetica Neue', Arial, sans-serif"
    FONT_MONO   = "'Source Code Pro', 'Menlo', 'Monaco', monospace"
    FONT_SIZE_XS   = "11px"
    FONT_SIZE_SM   = "12px"
    FONT_SIZE_BASE = "13px"
    FONT_SIZE_LG   = "15px"
    FONT_SIZE_XL   = "17px"
    FONT_WEIGHT_MEDIUM   = "500"
    FONT_WEIGHT_SEMIBOLD = "600"
    FONT_WEIGHT_BOLD     = "700"

    SPACING_XS = "4px"; SPACING_SM = "8px"; SPACING_MD = "12px"
    SPACING_LG = "16px"; SPACING_XL = "24px"
    RADIUS_SM = "4px"; RADIUS_MD = "6px"; RADIUS_LG = "8px"

    @staticmethod
    def get_button_primary():
        D = DesignSystem
        return f"""
            QPushButton {{
                background-color: {D.ASTRAL_ACCENT};
                color: #FFFFFF;
                border: none;
                border-radius: {D.RADIUS_MD};
                padding: 7px 14px;
                font-family: {D.FONT_FAMILY};
                font-size: {D.FONT_SIZE_BASE};
                font-weight: {D.FONT_WEIGHT_SEMIBOLD};
            }}
            QPushButton:hover  {{ background-color: {D.PRIMARY_HOVER}; }}
            QPushButton:pressed {{ background-color: {D.PRIMARY_ACTIVE}; }}
            QPushButton:disabled {{
                background-color: #C8D4E0;
                color: {D.TEXT_MUTED};
            }}
        """

    @staticmethod
    def get_button_secondary():
        D = DesignSystem
        return f"""
            QPushButton {{
                background-color: {D.SURFACE_ALT};
                color: {D.TEXT};
                border: 1px solid {D.BORDER};
                border-radius: {D.RADIUS_MD};
                padding: 7px 12px;
                font-family: {D.FONT_FAMILY};
                font-size: {D.FONT_SIZE_BASE};
            }}
            QPushButton:hover  {{ background-color: {D.BORDER}; border-color: {D.PRIMARY}; }}
            QPushButton:pressed {{ background-color: #C8D8E8; }}
            QPushButton:disabled {{
                background-color: {D.SURFACE};
                color: {D.TEXT_MUTED};
                border-color: {D.BORDER_LIGHT};
            }}
        """

    @staticmethod
    def get_button_danger():
        return """
            QPushButton {
                background-color: #FDECEA; color: #A51E1E;
                border: 1px solid #F0B7B7; border-radius: 6px; padding: 7px 14px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #F5C6C6; }
        """

    @staticmethod
    def get_button_success():
        return """
            QPushButton {
                background-color: #E8F5E9; color: #236628;
                border: 1px solid #B8DDBA; border-radius: 6px; padding: 7px 14px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #C8E6C9; }
        """

    @staticmethod
    def get_tab_style():
        D = DesignSystem
        return f"""
            QTabBar::tab {{
                background-color: {D.SURFACE_ALT};
                color: {D.TEXT_SECONDARY};
                padding: 8px 20px;
                border: 1px solid {D.BORDER_LIGHT};
                border-bottom: none;
                margin-right: 2px;
                font-weight: {D.FONT_WEIGHT_MEDIUM};
                font-size: {D.FONT_SIZE_BASE};
            }}
            QTabBar::tab:selected {{
                background-color: {D.SURFACE};
                color: {D.ASTRAL_BG};
                font-weight: {D.FONT_WEIGHT_BOLD};
                border-color: {D.BORDER};
                border-bottom: 3px solid {D.ASTRAL_ACCENT};
            }}
            QTabBar::tab:hover:!selected {{
                background-color: {D.BORDER_LIGHT};
            }}
            QTabWidget::pane {{
                border: 1px solid {D.BORDER};
                background-color: {D.SURFACE};
            }}
        """

    @staticmethod
    def get_outer_tab_style():
        """Super-onglets style navigation bar : fond clair, underline accent sur l'actif."""
        D = DesignSystem
        return f"""
            QTabWidget {{
                background-color: {D.SURFACE_ALT};
            }}
            QTabBar {{
                background-color: {D.SURFACE_ALT};
            }}
            QTabBar::tab {{
                background-color: {D.SURFACE_ALT};
                color: {D.TEXT_SECONDARY};
                padding: 10px 18px;
                border: 1px solid {D.BORDER_LIGHT};
                border-bottom: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                margin-right: 6px;
                margin-top: 4px;
                margin-bottom: -1px;
                font-family: {D.FONT_FAMILY};
                font-weight: {D.FONT_WEIGHT_MEDIUM};
                font-size: {D.FONT_SIZE_LG};
                min-width: 90px;
            }}
            QTabBar::tab:selected {{
                background-color: {D.SURFACE};
                color: {D.ASTRAL_BG};
                font-weight: {D.FONT_WEIGHT_BOLD};
                border: 2px solid {D.ASTRAL_ACCENT};
                border-bottom: none;
                margin-top: 0px;
                margin-bottom: -1px;
            }}
            QTabBar::tab:hover:!selected {{
                background-color: {D.SURFACE};
                color: {D.TEXT};
                border-color: {D.BORDER};
            }}
            QTabWidget::pane {{
                border: 1px solid {D.BORDER};
                background-color: {D.SURFACE};
            }}
        """

    @staticmethod
    def get_inner_tab_style():
        """Sous-onglets style pills/chips : petits boutons arrondis compacts."""
        D = DesignSystem
        return f"""
            QTabWidget {{
                background-color: {D.SURFACE_ALT};
            }}
            QTabBar {{
                background-color: {D.SURFACE_ALT};
            }}
            QTabBar::tab {{
                background-color: {D.SURFACE_ALT};
                color: {D.TEXT_SECONDARY};
                padding: 7px 16px;
                border: 1px solid {D.BORDER_LIGHT};
                border-radius: 8px;
                margin-right: 6px;
                margin-top: 6px;
                margin-bottom: 6px;
                font-family: {D.FONT_FAMILY};
                font-weight: {D.FONT_WEIGHT_MEDIUM};
                font-size: {D.FONT_SIZE_BASE};
            }}
            QTabBar::tab:selected {{
                background-color: rgba(74, 152, 212, 0.12);
                color: {D.ASTRAL_BG};
                border: 1px solid {D.ASTRAL_ACCENT};
                font-weight: {D.FONT_WEIGHT_SEMIBOLD};
            }}
            QTabBar::tab:hover:!selected {{
                background-color: {D.SURFACE};
                border-color: {D.ASTRAL_ACCENT};
                color: {D.TEXT};
            }}
            QTabWidget::pane {{
                border: none;
                background-color: {D.SURFACE};
            }}
        """

    @staticmethod
    def get_unified_toolbar_style():
        """Barre unique fusionnée : Load · Save · | · Help · Exit · → Terminal."""
        D = DesignSystem
        return f"""
            QToolBar {{
                background-color: {D.ASTRAL_DEEPEST};
                border: none;
                border-bottom: 1px solid {D.ASTRAL_BORDER};
                padding: 2px 8px;
                spacing: 2px;
                min-height: 34px;
            }}
            QToolBar::separator {{
                background-color: {D.ASTRAL_BORDER};
                width: 1px;
                margin: 6px 8px;
            }}
            QToolBar QWidget {{
                background-color: {D.ASTRAL_DEEPEST};
            }}
            QToolButton {{
                padding: 6px 14px;
                border-radius: {D.RADIUS_MD};
                color: #FFFFFF;
                font-family: {D.FONT_FAMILY};
                font-size: {D.FONT_SIZE_BASE};
                font-weight: {D.FONT_WEIGHT_SEMIBOLD};
                border: 1px solid transparent;
                min-height: 28px;
                background-color: {D.ASTRAL_DEEPEST};
            }}
            QToolButton:hover {{
                background-color: {D.ASTRAL_SURFACE};
                color: #FFFFFF;
                border: 1px solid {D.ASTRAL_BORDER};
            }}
            QToolButton:pressed {{
                background-color: {D.ASTRAL_HOVER};
                color: #FFFFFF;
                border: 1px solid {D.ASTRAL_ACCENT};
            }}
            QToolButton:disabled {{
                color: {D.ASTRAL_MUTED};
                background-color: {D.ASTRAL_DEEPEST};
            }}
        """

    @staticmethod
    def get_toolbar_style():
        D = DesignSystem
        return f"""
            QToolBar {{
                background-color: {D.SURFACE};
                border-bottom: 1px solid {D.BORDER};
                padding: 3px 6px;
                spacing: 2px;
            }}
            QToolBar::separator {{
                background-color: {D.BORDER};
                width: 1px;
                margin: 4px 4px;
            }}
            QToolButton {{
                padding: 6px 10px;
                border-radius: {D.RADIUS_SM};
                color: {D.TEXT};
                font-size: {D.FONT_SIZE_BASE};
                border: 1px solid transparent;
                min-height: 28px;
            }}
            QToolButton:hover {{
                background-color: {D.SURFACE_ALT};
                border: 1px solid {D.BORDER};
                color: {D.ASTRAL_BG};
            }}
            QToolButton:checked {{
                background-color: {D.ASTRAL_BG};
                color: #FFFFFF;
                border: 1px solid {D.ASTRAL_ACCENT};
            }}
            QToolButton:checked:hover {{
                background-color: {D.ASTRAL_HOVER};
            }}
            QToolButton:pressed {{
                background-color: {D.ASTRAL_BG};
                color: #FFFFFF;
            }}
            QToolButton:disabled {{
                color: {D.TEXT_MUTED};
            }}
            QLabel {{
                color: {D.TEXT_SECONDARY};
                font-size: {D.FONT_SIZE_SM};
            }}
        """

    @staticmethod
    def get_panel_qss():
        D = DesignSystem
        return f"""
            QWidget {{
                background-color: {D.ASTRAL_BG};
                color: {D.ASTRAL_TEXT};
                font-family: {D.FONT_FAMILY};
                font-size: {D.FONT_SIZE_BASE};
            }}
            QDockWidget::title {{
                background-color: {D.ASTRAL_DEEPEST};
                color: {D.ASTRAL_TEXT};
                padding: 7px 10px;
                font-weight: {D.FONT_WEIGHT_BOLD};
                font-size: {D.FONT_SIZE_SM};
                text-transform: uppercase;
            }}
            QLabel {{
                color: {D.ASTRAL_DIM};
                font-size: {D.FONT_SIZE_SM};
                qproperty-wordWrap: 1;
            }}
            QLabel:disabled {{ color: {D.ASTRAL_MUTED}; }}
            QCheckBox {{
                color: {D.ASTRAL_TEXT};
                spacing: 8px;
                padding: 3px 0;
                min-height: 22px;
            }}
            QCheckBox:disabled {{ color: {D.ASTRAL_MUTED}; }}
            QCheckBox::indicator {{
                width: 16px; height: 16px;
                border-radius: 4px;
                border: 1px solid {D.ASTRAL_BORDER};
                background-color: {D.ASTRAL_DEEP};
            }}
            QCheckBox::indicator:checked {{
                background-color: {D.ASTRAL_ACCENT};
                border-color: {D.PRIMARY_HOVER};
            }}
            QComboBox, QLineEdit, QSpinBox {{
                background-color: {D.ASTRAL_SURFACE};
                border: 1px solid {D.ASTRAL_BORDER};
                border-radius: {D.RADIUS_MD};
                padding: 6px 8px;
                color: {D.ASTRAL_TEXT};
                font-size: {D.FONT_SIZE_BASE};
                min-height: 26px;
                selection-background-color: {D.ASTRAL_ACCENT};
            }}
            QComboBox:hover, QLineEdit:hover, QSpinBox:hover {{
                border-color: {D.ASTRAL_ACCENT};
            }}
            QComboBox:focus, QLineEdit:focus, QSpinBox:focus {{
                border: 1px solid {D.PRIMARY_HOVER};
            }}
            QLineEdit:disabled, QSpinBox:disabled {{
                background-color: {D.ASTRAL_DEEP};
                color: {D.ASTRAL_MUTED};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 22px;
            }}
            QSpinBox::up-button, QSpinBox::down-button {{
                width: 16px;
                background-color: {D.ASTRAL_DEEP};
                border: none;
            }}
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
                background-color: {D.ASTRAL_HOVER};
            }}
            QSlider::groove:horizontal {{
                border: 1px solid {D.ASTRAL_BORDER};
                height: 5px;
                background: {D.ASTRAL_SURFACE};
                border-radius: 3px;
                margin: 0 5px;
            }}
            QSlider::handle:horizontal {{
                background: {D.ASTRAL_ACCENT};
                border: 1px solid {D.PRIMARY_HOVER};
                width: 14px; height: 14px;
                border-radius: 7px;
                margin: -6px 0;
            }}
            QSlider::handle:horizontal:hover {{ background: {D.PRIMARY_HOVER}; }}
            QScrollArea {{ border: none; background-color: {D.ASTRAL_BG}; }}
        """

    @staticmethod
    def get_panel_toggle_button_qss():
        D = DesignSystem
        return f"""
            QPushButton {{
                background-color: {D.ASTRAL_MUTED};
                color: {D.ASTRAL_DEEPEST};
                border: none;
                border-radius: 10px;
                padding: 3px 9px;
                font-size: {D.FONT_SIZE_XS};
                font-weight: {D.FONT_WEIGHT_BOLD};
                min-width: 42px;
                max-width: 42px;
                min-height: 21px;
            }}
            QPushButton:checked {{
                background-color: {D.ASTRAL_ACCENT};
                color: #FFFFFF;
            }}
        """

    @staticmethod
    def get_panel_field_qss():
        D = DesignSystem
        return f"""
            QLineEdit {{
                background-color: {D.ASTRAL_SURFACE};
                border: 1px solid {D.ASTRAL_BORDER};
                border-radius: {D.RADIUS_MD};
                padding: 5px 7px;
                color: {D.ASTRAL_TEXT};
                font-size: {D.FONT_SIZE_BASE};
                min-height: 24px;
            }}
            QLineEdit:focus {{ border: 1px solid {D.ASTRAL_ACCENT}; }}
            QLineEdit:disabled {{
                background-color: {D.ASTRAL_DEEP};
                color: {D.ASTRAL_MUTED};
            }}
        """

    @staticmethod
    def get_panel_action_button_qss(kind="primary"):
        D = DesignSystem
        colors = {
            "primary": (D.ASTRAL_ACCENT, D.PRIMARY_HOVER, D.PRIMARY_ACTIVE, "#FFFFFF"),
            "success": ("#2F7D4A", "#3E9360", "#286A3F", "#FFFFFF"),
            "warning": ("#9A5A28", "#B36B32", "#7D4820", "#FFFFFF"),
            "quiet": (D.ASTRAL_SURFACE, D.ASTRAL_HOVER, D.ASTRAL_DEEP, D.ASTRAL_TEXT),
        }
        bg, hover, pressed, fg = colors.get(kind, colors["primary"])
        border = bg if kind != "quiet" else D.ASTRAL_BORDER
        return f"""
            QPushButton {{
                background-color: {bg};
                color: {fg};
                border: 1px solid {border};
                border-radius: {D.RADIUS_MD};
                padding: 7px 11px;
                font-size: {D.FONT_SIZE_BASE};
                font-weight: {D.FONT_WEIGHT_SEMIBOLD};
                min-height: 28px;
            }}
            QPushButton:hover {{ background-color: {hover}; color: #FFFFFF; }}
            QPushButton:pressed {{ background-color: {pressed}; }}
            QPushButton:disabled {{
                background-color: {D.ASTRAL_DEEP};
                color: {D.ASTRAL_MUTED};
                border-color: {D.ASTRAL_BORDER};
            }}
        """

    @staticmethod
    def get_plot_toolbar_qss(name="PlotToolbar", with_menu=False):
        D = DesignSystem
        menu = ""
        if with_menu:
            menu = f"""
            QMenu {{
                background-color: {D.SURFACE};
                border: 1px solid {D.BORDER};
                border-radius: {D.RADIUS_LG};
                padding: 5px;
                font-family: {D.FONT_FAMILY};
                font-size: {D.FONT_SIZE_BASE};
            }}
            QMenu::item {{
                padding: 7px 16px 7px 12px;
                border-radius: {D.RADIUS_MD};
                color: {D.TEXT};
                min-width: 170px;
            }}
            QMenu::item:selected {{
                background-color: {D.ASTRAL_BG};
                color: #FFFFFF;
            }}
            QMenu::item:checked {{
                color: {D.ASTRAL_ACCENT};
                font-weight: {D.FONT_WEIGHT_SEMIBOLD};
            }}
            """
        return f"""
            QWidget#{name} {{
                background-color: {D.BACKGROUND};
                border-bottom: 1px solid {D.BORDER};
                padding: 2px 6px;
            }}
            QLabel {{
                color: {D.TEXT_MUTED};
                font-size: {D.FONT_SIZE_SM};
                font-weight: {D.FONT_WEIGHT_SEMIBOLD};
                background: transparent;
            }}
            QPushButton, QToolButton {{
                background-color: {D.SURFACE};
                color: {D.TEXT_SECONDARY};
                border: 1px solid {D.BORDER};
                border-radius: {D.RADIUS_LG};
                padding: 3px 8px;
                font-size: {D.FONT_SIZE_SM};
                font-family: {D.FONT_FAMILY};
                font-weight: {D.FONT_WEIGHT_MEDIUM};
                min-height: 22px;
                min-width: 64px;
            }}
            QPushButton:hover, QToolButton:hover {{
                background-color: {D.SURFACE_ALT};
                border-color: {D.ASTRAL_ACCENT};
                color: {D.TEXT};
            }}
            QPushButton:checked, QToolButton:checked {{
                background-color: {D.ASTRAL_BG};
                color: #FFFFFF;
                border-color: {D.ASTRAL_BG};
                font-weight: {D.FONT_WEIGHT_SEMIBOLD};
            }}
            QPushButton:pressed, QToolButton:pressed {{
                background-color: {D.ASTRAL_HOVER};
                color: #FFFFFF;
            }}
            QToolButton::menu-indicator {{ image: none; width: 0; }}
            QComboBox {{
                background-color: {D.SURFACE};
                color: {D.TEXT};
                border: 1px solid {D.BORDER};
                border-radius: {D.RADIUS_MD};
                padding: 3px 8px;
                font-size: {D.FONT_SIZE_SM};
                min-width: 145px;
                min-height: 22px;
            }}
            QComboBox:hover {{ border-color: {D.PRIMARY}; }}
            QComboBox::drop-down {{ border: none; width: 22px; }}
            {menu}
        """

    @staticmethod
    def get_scrollbar_style():
        D = DesignSystem
        return f"""
            QScrollBar:vertical {{
                background: {D.ASTRAL_BG};
                width: 7px; border-radius: 3px;
            }}
            QScrollBar::handle:vertical {{
                background: {D.ASTRAL_BORDER};
                border-radius: 3px; min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{ background: {D.ASTRAL_ACCENT}; }}
            QScrollBar::sub-line:vertical, QScrollBar::add-line:vertical {{
                border: none; background: none;
            }}
        """

    @staticmethod
    def get_full_app_style():
        D = DesignSystem
        return f"""
            QMainWindow, QWidget {{
                background-color: {D.BACKGROUND};
                color: {D.TEXT};
                font-family: {D.FONT_FAMILY};
                font-size: {D.FONT_SIZE_BASE};
            }}
            QDockWidget {{
                background-color: {D.ASTRAL_DEEP};
                color: {D.ASTRAL_TEXT};
            }}
            QDockWidget::title {{
                background-color: {D.ASTRAL_DEEPEST};
                color: {D.ASTRAL_TEXT};
                padding: 7px 10px;
                font-weight: bold;
                font-size: {D.FONT_SIZE_BASE};
                text-transform: uppercase;
            }}
            QMenuBar {{
                background-color: {D.ASTRAL_DEEPEST};
                color: {D.ASTRAL_TEXT};
                border-bottom: 1px solid {D.ASTRAL_BORDER};
                padding: 2px 4px;
            }}
            QMenuBar::item:selected {{
                background-color: {D.ASTRAL_SURFACE};
                border-radius: 3px;
            }}
            QMenu {{
                background-color: {D.ASTRAL_BG};
                color: {D.ASTRAL_TEXT};
                border: 1px solid {D.ASTRAL_BORDER};
            }}
            QMenu::item:selected {{
                background-color: {D.ASTRAL_HOVER};
                color: #FFFFFF;
            }}
            QWidget:disabled, QLabel:disabled, QCheckBox:disabled,
            QGroupBox:disabled, QGroupBox::title:disabled {{
                color: {D.TEXT_MUTED};
            }}
            {D.get_tab_style()}
            {D.get_toolbar_style()}
            {D.get_scrollbar_style()}
        """


# ── Thèmes clair / sombre ────────────────────────────────────────────────────

LIGHT_THEME = {
    'name': 'Light',
    'primary': '#3f8adc',
    'primary_hover': '#3074c1',
    'primary_active': '#2563aa',
    'secondary': '#6c757d',
    'success': '#28a745',
    'warning': '#ffc107',
    'danger': '#dc3545',
    'info': '#17a2b8',
    'background': '#ffffff',
    'surface': '#f8f9fa',
    'surface_alt': '#e9ecef',
    'text': '#212529',
    'text_secondary': '#6c757d',
    'text_muted': '#adb5bd',
    'text_light': '#e9ecef',
    'border': '#dee2e6',
    'border_light': '#e9ecef',
    'divider': '#dee2e6',
}

DARK_THEME = {
    'name': 'Dark',
    'primary': '#5eb3ff',
    'primary_hover': '#4da3f0',
    'primary_active': '#3d93e0',
    'secondary': '#a0aec0',
    'success': '#48bb78',
    'warning': '#ed8936',
    'danger': '#f56565',
    'info': '#38b2e6',
    'background': '#0f0f1e',
    'surface': '#1e1e2e',
    'surface_alt': '#2d2d3d',
    'text': '#e8e8f0',
    'text_secondary': '#a0aec0',
    'text_muted': '#6d7a96',
    'text_light': '#212529',
    'border': '#434358',
    'border_light': '#2d2d3d',
    'divider': '#434358',
}

THEMES = {'light': LIGHT_THEME, 'dark': DARK_THEME}


def get_theme(name='light'):
    return THEMES.get(name, LIGHT_THEME)


def generate_qss_from_theme(theme):
    return f"""
        QWidget {{ background-color: {theme['background']}; color: {theme['text']}; }}
        QLabel {{ color: {theme['text']}; }}
        QPushButton {{
            background-color: {theme['surface_alt']}; color: {theme['text']};
            border: 1px solid {theme['border']};
        }}
        QPushButton:hover {{ background-color: {theme['primary']}; color: white; }}
        QLineEdit {{
            background-color: {theme['surface']}; color: {theme['text']};
            border: 1px solid {theme['border']};
        }}
        QGroupBox {{ color: {theme['text_secondary']}; border: 1px solid {theme['border']}; }}
    """
