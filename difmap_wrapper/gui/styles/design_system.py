# difmap_wrapper/gui/styles/design_system.py
"""
Design System centralisé - Define toutes les constantes visuelles
"""

class DesignSystem:
    """
    Centralise tous les éléments de design de DIFMAP Modern.
    Assure la cohérence visuelle dans toute l'application.
    """

    # ============================================================
    # COULEURS - Palette Primaire
    # ============================================================
    PRIMARY = "#3f8adc"           # Bleu professionnel
    PRIMARY_HOVER = "#3074c1"     # Hover state
    PRIMARY_ACTIVE = "#2563aa"    # Active state

    SECONDARY = "#6c757d"         # Gris neutre
    SUCCESS = "#28a745"           # Vert validation
    WARNING = "#ffc107"           # Orange alerte
    DANGER = "#dc3545"            # Rouge erreur
    INFO = "#17a2b8"              # Cyan information

    # ============================================================
    # COULEURS - Surfaces
    # ============================================================
    BACKGROUND = "#ffffff"        # Fond blanc pur
    SURFACE = "#f8f9fa"           # Surface gris très clair
    SURFACE_ALT = "#e9ecef"       # Surface alternative
    
    # ============================================================
    # COULEURS - Texte
    # ============================================================
    TEXT = "#212529"              # Texte principal (noir)
    TEXT_SECONDARY = "#6c757d"    # Texte secondaire (gris)
    TEXT_MUTED = "#adb5bd"        # Texte désactivé
    TEXT_LIGHT = "#e9ecef"        # Texte sur fond sombre
    
    # ============================================================
    # COULEURS - Plots (Scatter, Matplotlib)
    # ============================================================
    PLOT_DATA = "#1a5276"         # Couleur des points de données (bleu foncé)
    PLOT_FOCUS = "#dc3545"        # Couleur des points focalisés (rouge)
    PLOT_TITLE_INACTIVE = "#4b5563" # Couleur titre plot sans focus (gris)
    
    # ============================================================
    # COULEURS - Bordures et Séparations
    # ============================================================
    BORDER = "#dee2e6"            # Bordures standard
    BORDER_LIGHT = "#e9ecef"      # Bordures légères
    DIVIDER = "#dee2e6"           # Dividers

    # ============================================================
    # TYPOGRAPHIE
    # ============================================================
    FONT_FAMILY = "'Segoe UI', 'Roboto', 'Helvetica Neue', Arial, sans-serif"
    FONT_MONO = "'Source Code Pro', 'Menlo', 'Monaco', monospace"
    
    FONT_SIZE_XS = "9px"
    FONT_SIZE_SM = "10px"
    FONT_SIZE_BASE = "11px"
    FONT_SIZE_LG = "12px"
    FONT_SIZE_XL = "14px"
    FONT_SIZE_XXL = "16px"
    
    FONT_WEIGHT_NORMAL = "400"
    FONT_WEIGHT_MEDIUM = "500"
    FONT_WEIGHT_SEMIBOLD = "600"
    FONT_WEIGHT_BOLD = "700"

    # ============================================================
    # ESPACEMENT (Système 4px)
    # ============================================================
    SPACING_XS = "4px"
    SPACING_SM = "8px"
    SPACING_MD = "12px"
    SPACING_LG = "16px"
    SPACING_XL = "24px"
    SPACING_XXL = "32px"

    # ============================================================
    # BORDER RADIUS
    # ============================================================
    RADIUS_NONE = "0px"
    RADIUS_SM = "4px"
    RADIUS_MD = "6px"
    RADIUS_LG = "8px"
    RADIUS_XL = "12px"
    RADIUS_FULL = "999px"

    # ============================================================
    # OMBRES
    # ============================================================
    SHADOW_NONE = "none"
    SHADOW_SM = "0 1px 2px rgba(0, 0, 0, 0.05)"
    SHADOW_MD = "0 2px 8px rgba(0, 0, 0, 0.1)"
    SHADOW_LG = "0 4px 16px rgba(0, 0, 0, 0.15)"
    SHADOW_XL = "0 8px 24px rgba(0, 0, 0, 0.2)"
    
    # Ombres colorées
    SHADOW_PRIMARY = "0 2px 8px rgba(63, 138, 220, 0.3)"
    SHADOW_SUCCESS = "0 2px 8px rgba(40, 167, 69, 0.3)"
    SHADOW_DANGER = "0 2px 8px rgba(220, 53, 69, 0.3)"

    # ============================================================
    # TRANSITIONS
    # ============================================================
    TRANSITION_FAST = "100ms"
    TRANSITION_BASE = "200ms"
    TRANSITION_SLOW = "300ms"
    EASING = "ease-in-out"

    # ============================================================
    # COMPOSÉS - QSS Styles Prêts à l'Emploi
    # ============================================================

    @staticmethod
    def get_button_primary():
        """Style principal pour les boutons CTA"""
        return f"""
            QPushButton {{
                background-color: {DesignSystem.PRIMARY};
                color: white;
                border: none;
                border-radius: {DesignSystem.RADIUS_MD};
                padding: {DesignSystem.SPACING_SM} {DesignSystem.SPACING_LG};
                font-family: {DesignSystem.FONT_FAMILY};
                font-size: {DesignSystem.FONT_SIZE_BASE};
                font-weight: {DesignSystem.FONT_WEIGHT_SEMIBOLD};
            }}
            QPushButton:hover {{
                background-color: {DesignSystem.PRIMARY_HOVER};
            }}
            QPushButton:pressed {{
                background-color: {DesignSystem.PRIMARY_ACTIVE};
            }}
            QPushButton:disabled {{
                background-color: {DesignSystem.BORDER_LIGHT};
                color: {DesignSystem.TEXT_MUTED};
            }}
        """

    @staticmethod
    def get_button_secondary():
        """Style secondaire pour les boutons normaux"""
        return f"""
            QPushButton {{
                background-color: {DesignSystem.SURFACE_ALT};
                color: {DesignSystem.TEXT};
                border: 1px solid {DesignSystem.BORDER};
                border-radius: {DesignSystem.RADIUS_MD};
                padding: {DesignSystem.SPACING_SM} {DesignSystem.SPACING_LG};
                font-family: {DesignSystem.FONT_FAMILY};
                font-size: {DesignSystem.FONT_SIZE_BASE};
                font-weight: {DesignSystem.FONT_WEIGHT_MEDIUM};
            }}
            QPushButton:hover {{
                background-color: {DesignSystem.BORDER_LIGHT};
                border-color: {DesignSystem.BORDER};
            }}
            QPushButton:pressed {{
                background-color: {DesignSystem.BORDER};
            }}
            QPushButton:disabled {{
                background-color: {DesignSystem.SURFACE};
                color: {DesignSystem.TEXT_MUTED};
            }}
        """

    @staticmethod
    def get_button_danger():
        """Style danger pour actions destructrices"""
        return f"""
            QPushButton {{
                background-color: #f8d7da;
                color: #721c24;
                border: 1px solid #f5c6cb;
                border-radius: {DesignSystem.RADIUS_MD};
                padding: {DesignSystem.SPACING_SM} {DesignSystem.SPACING_LG};
                font-weight: {DesignSystem.FONT_WEIGHT_SEMIBOLD};
            }}
            QPushButton:hover {{
                background-color: #f5c6cb;
                border-color: #ed969e;
            }}
            QPushButton:pressed {{
                background-color: #ed969e;
            }}
        """

    @staticmethod
    def get_button_success():
        """Style succès pour actions positives"""
        return f"""
            QPushButton {{
                background-color: #d4edda;
                color: #155724;
                border: 1px solid #c3e6cb;
                border-radius: {DesignSystem.RADIUS_MD};
                padding: {DesignSystem.SPACING_SM} {DesignSystem.SPACING_LG};
                font-weight: {DesignSystem.FONT_WEIGHT_SEMIBOLD};
            }}
            QPushButton:hover {{
                background-color: #c3e6cb;
                border-color: #b1dfbb;
            }}
        """

    @staticmethod
    def get_input_style():
        """Style pour inputs (QLineEdit, QComboBox, etc.)"""
        return f"""
            QLineEdit, QComboBox, QSpinBox {{
                background-color: {DesignSystem.BACKGROUND};
                color: {DesignSystem.TEXT};
                border: 1px solid {DesignSystem.BORDER};
                border-radius: {DesignSystem.RADIUS_SM};
                padding: {DesignSystem.SPACING_XS} {DesignSystem.SPACING_SM};
                font-family: {DesignSystem.FONT_FAMILY};
                font-size: {DesignSystem.FONT_SIZE_BASE};
            }}
            QLineEdit:hover, QComboBox:hover, QSpinBox:hover {{
                border: 1px solid {DesignSystem.PRIMARY};
            }}
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
                border: 2px solid {DesignSystem.PRIMARY};
                background-color: {DesignSystem.BACKGROUND};
            }}
            QLineEdit::placeholder {{
                color: {DesignSystem.TEXT_MUTED};
            }}
            
            QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled {{
                background-color: {DesignSystem.SURFACE};
                color: {DesignSystem.TEXT_MUTED};
                border: 1px solid {DesignSystem.BORDER_LIGHT};
            }}
        """

    @staticmethod
    def get_groupbox_style():
        """Style pour groupes"""
        return f"""
            QGroupBox {{
                border: 1px solid {DesignSystem.BORDER};
                border-radius: {DesignSystem.RADIUS_MD};
                margin-top: {DesignSystem.SPACING_LG};
                padding-top: {DesignSystem.SPACING_MD};
                color: {DesignSystem.TEXT};
                font-weight: {DesignSystem.FONT_WEIGHT_SEMIBOLD};
                font-size: {DesignSystem.FONT_SIZE_BASE};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: {DesignSystem.SPACING_SM};
                padding: 0 {DesignSystem.SPACING_XS};
            }}
        """

    @staticmethod
    def get_label_style():
        """Style pour labels"""
        return f"""
            QLabel {{
                color: {DesignSystem.TEXT};
                font-family: {DesignSystem.FONT_FAMILY};
                font-size: {DesignSystem.FONT_SIZE_BASE};
            }}
        """

    @staticmethod
    def get_console_style():
        """Style pour console de logs moderne"""
        return f"""
            QTextEdit {{
                background-color: {DesignSystem.BACKGROUND};
                color: {DesignSystem.TEXT};
                border: 1px solid {DesignSystem.BORDER};
                border-radius: {DesignSystem.RADIUS_MD};
                font-family: {DesignSystem.FONT_MONO};
                font-size: {DesignSystem.FONT_SIZE_SM};
                padding: {DesignSystem.SPACING_MD};
            }}
        """

    @staticmethod
    def get_tab_style():
        """Style pour onglets modernes"""
        return f"""
            QTabBar::tab {{
                background-color: {DesignSystem.SURFACE};
                color: {DesignSystem.TEXT_SECONDARY};
                padding: {DesignSystem.SPACING_SM} {DesignSystem.SPACING_LG};
                border: none;
                margin-right: 2px;
                font-weight: {DesignSystem.FONT_WEIGHT_MEDIUM};
                font-size: {DesignSystem.FONT_SIZE_BASE};
                border-bottom: 3px solid transparent;
            }}
            QTabBar::tab:selected {{
                background-color: {DesignSystem.BACKGROUND};
                color: {DesignSystem.PRIMARY};
                font-weight: {DesignSystem.FONT_WEIGHT_BOLD};
                border-bottom: 3px solid {DesignSystem.PRIMARY};
            }}
            QTabBar::tab:hover {{
                background-color: {DesignSystem.SURFACE_ALT};
            }}
            QTabWidget::pane {{
                border: 1px solid {DesignSystem.BORDER};
                background-color: {DesignSystem.BACKGROUND};
                border-radius: {DesignSystem.RADIUS_MD};
            }}
        """

    @staticmethod
    def get_toolbar_style():
        """Style pour barre d'outils"""
        return f"""
            QToolBar {{
                background-color: {DesignSystem.SURFACE};
                border-bottom: 1px solid {DesignSystem.BORDER};
                padding: {DesignSystem.SPACING_XS};
                spacing: {DesignSystem.SPACING_SM};
            }}
            QToolButton {{
                padding: {DesignSystem.SPACING_XS} {DesignSystem.SPACING_SM};
                border-radius: {DesignSystem.RADIUS_SM};
                color: {DesignSystem.TEXT};
                font-weight: {DesignSystem.FONT_WEIGHT_MEDIUM};
                font-size: {DesignSystem.FONT_SIZE_BASE};
            }}
            QToolButton:hover {{
                background-color: {DesignSystem.BACKGROUND};
            }}
            QToolButton:pressed {{
                background-color: {DesignSystem.BORDER};
            }}
        """

    @staticmethod
    def get_scrollbar_style():
        """Style pour scrollbars"""
        return f"""
            QScrollBar:vertical {{
                background: {DesignSystem.SURFACE};
                width: 8px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {DesignSystem.BORDER};
                border-radius: 4px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {DesignSystem.TEXT_SECONDARY};
            }}
            QScrollBar::sub-line:vertical, QScrollBar::add-line:vertical {{
                border: none;
                background: none;
            }}
        """

    @staticmethod
    def get_full_app_style():
        """Style complet pour l'application en cascade"""
        return f"""
            QMainWindow, QWidget {{
                background-color: {DesignSystem.BACKGROUND};
                color: {DesignSystem.TEXT};
                font-family: {DesignSystem.FONT_FAMILY};
            }}
            
            /* --- FORCE le texte gris clair pour TOUS les éléments désactivés --- */
            QWidget:disabled, QLabel:disabled, QCheckBox:disabled, QGroupBox:disabled, QGroupBox::title:disabled {{
                color: {DesignSystem.TEXT_MUTED};
            }}
            
            {DesignSystem.get_tab_style()}
            {DesignSystem.get_toolbar_style()}
            {DesignSystem.get_scrollbar_style()}
            {DesignSystem.get_groupbox_style()}
            {DesignSystem.get_input_style()}
            {DesignSystem.get_label_style()}
        """
        
if __name__ == "__main__":
    # Test d'affichage
    print("Design System - DIFMAP Modern")
    print(f"Primary Color: {DesignSystem.PRIMARY}")
    print(f"Font Family: {DesignSystem.FONT_FAMILY}")
    print(f"\nButton Primary Style:\n{DesignSystem.get_button_primary()}")
