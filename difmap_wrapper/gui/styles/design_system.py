# difmap_wrapper/gui/styles/design_system.py

class DesignSystem:
    """
    Palette "bleu astral" + centre blanc + terminal sombre.
    Panneau gauche  →  bleu astral profond
    Zone centrale   →  blanc / gris très clair
    Terminal droit  →  quasi-noir
    """

    # ============================================================
    # BLEU ASTRAL — panneau gauche, dock titres, menu bar
    # ============================================================
    ASTRAL_DEEPEST = "#0A1628"   # titres de dock, menu bar
    ASTRAL_DEEP    = "#0E1F35"   # fond du dock widget
    ASTRAL_BG      = "#162D4A"   # fond principal panneau gauche
    ASTRAL_SURFACE = "#1C3A5E"   # group boxes
    ASTRAL_HOVER   = "#254F7A"   # survol
    ASTRAL_BORDER  = "#2A4D72"   # bordures
    ASTRAL_TEXT    = "#B8CFE8"   # texte principal
    ASTRAL_DIM     = "#6080A0"   # texte secondaire / labels
    ASTRAL_MUTED   = "#2D4862"   # texte désactivé
    ASTRAL_ACCENT  = "#4A98D4"   # highlight actif

    # ============================================================
    # CENTRE BLANC — zone de plots / onglets
    # ============================================================
    BACKGROUND   = "#F0F2F5"    # fond fenêtre principale
    SURFACE      = "#FFFFFF"    # panneaux blancs, zone plot
    SURFACE_ALT  = "#E8ECF2"    # alt surface, onglets inactifs
    BORDER       = "#C8D4E0"    # bordures légères
    BORDER_LIGHT = "#DDE4EC"

    TEXT         = "#1C2B3A"    # texte principal (zone centrale)
    TEXT_SECONDARY = "#4A607A"
    TEXT_MUTED   = "#90A8C0"

    # ============================================================
    # TERMINAL SOMBRE — dock droit
    # ============================================================
    TERMINAL_BG     = "#0D1117"
    TERMINAL_TEXT   = "#A0B4C8"
    TERMINAL_BORDER = "#1C2535"

    # ============================================================
    # ACCENTS SÉMANTIQUES
    # ============================================================
    PRIMARY        = ASTRAL_ACCENT    # "#4A98D4"
    PRIMARY_HOVER  = "#5BAAE0"
    PRIMARY_ACTIVE = "#3A88C4"

    SUCCESS = "#2E7D32"
    WARNING = "#E65100"
    DANGER  = "#C62828"
    INFO    = "#00838F"

    # ============================================================
    # COULEURS PLOTS MATPLOTLIB (fond blanc)
    # ============================================================
    PLOT_DATA           = "#1565C0"   # bleu profond, données
    PLOT_FOCUS          = "#C62828"   # rouge, points flaggés
    PLOT_TITLE_INACTIVE = "#7090B0"
    PLOT_MODEL          = "#E65100"   # orange, modèle
    PLOT_ERROR          = "#00695C"   # teal, erreurs

    # ============================================================
    # TYPOGRAPHIE
    # ============================================================
    FONT_FAMILY = "'Segoe UI', 'Roboto', 'Helvetica Neue', Arial, sans-serif"
    FONT_MONO   = "'Source Code Pro', 'Menlo', 'Monaco', monospace"
    FONT_SIZE_XS   = "9px"
    FONT_SIZE_SM   = "10px"
    FONT_SIZE_BASE = "11px"
    FONT_SIZE_LG   = "13px"
    FONT_WEIGHT_MEDIUM   = "500"
    FONT_WEIGHT_SEMIBOLD = "600"
    FONT_WEIGHT_BOLD     = "700"

    SPACING_XS = "4px"; SPACING_SM = "8px"; SPACING_MD = "12px"
    SPACING_LG = "16px"; SPACING_XL = "24px"
    RADIUS_SM = "3px"; RADIUS_MD = "5px"; RADIUS_LG = "8px"

    # ============================================================
    # STYLES QSS COMPOSÉS
    # ============================================================

    @staticmethod
    def get_button_primary():
        """
        Feuille QSS pour les boutons d'action principale.

        Returns
        -------
        str
            Style QSS (fond bleu astral, états hover / pressed / disabled).
        """
        D = DesignSystem
        return f"""
            QPushButton {{
                background-color: {D.ASTRAL_ACCENT};
                color: #FFFFFF;
                border: none;
                border-radius: {D.RADIUS_MD};
                padding: 6px 14px;
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
        """
        Feuille QSS pour les boutons secondaires.

        Returns
        -------
        str
            Style QSS (fond gris clair, bordure subtile, hover avec accent primaire).
        """
        D = DesignSystem
        return f"""
            QPushButton {{
                background-color: {D.SURFACE_ALT};
                color: {D.TEXT};
                border: 1px solid {D.BORDER};
                border-radius: {D.RADIUS_MD};
                padding: 5px 10px;
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
        """
        Feuille QSS pour les boutons d'action destructrice.

        Returns
        -------
        str
            Style QSS (fond rouge pâle, texte rouge vif).
        """
        return """
            QPushButton {
                background-color: #FDECEA; color: #C62828;
                border: 1px solid #F5C6C6; border-radius: 5px; padding: 6px 14px;
            }
            QPushButton:hover { background-color: #F5C6C6; }
        """

    @staticmethod
    def get_button_success():
        """
        Feuille QSS pour les boutons d'action positive (confirmation, sauvegarde).

        Returns
        -------
        str
            Style QSS (fond vert pâle, texte vert).
        """
        return """
            QPushButton {
                background-color: #E8F5E9; color: #2E7D32;
                border: 1px solid #C8E6C9; border-radius: 5px; padding: 6px 14px;
            }
            QPushButton:hover { background-color: #C8E6C9; }
        """

    @staticmethod
    def get_tab_style():
        """
        Feuille QSS pour les onglets (``QTabBar`` et ``QTabWidget``).

        Returns
        -------
        str
            Style QSS avec onglet actif souligné en bleu astral et fond blanc.
        """
        D = DesignSystem
        return f"""
            QTabBar::tab {{
                background-color: {D.SURFACE_ALT};
                color: {D.TEXT_SECONDARY};
                padding: 7px 20px;
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
    def get_toolbar_style():
        """
        Feuille QSS pour la barre d'outils (``QToolBar`` et ``QToolButton``).

        Returns
        -------
        str
            Style QSS (fond blanc, hover gris clair, état actif fond bleu astral).
        """
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
                padding: 4px 10px;
                border-radius: {D.RADIUS_SM};
                color: {D.TEXT};
                font-size: {D.FONT_SIZE_BASE};
                border: 1px solid transparent;
                min-height: 24px;
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
    def get_scrollbar_style():
        """
        Feuille QSS pour la scrollbar verticale.

        Returns
        -------
        str
            Style QSS (barre fine bleu astral, handle avec hover en accent).
        """
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
        """
        Feuille QSS globale de l'application.

        Agrège les styles onglets, toolbar, scrollbar, menus et dock widgets
        en une seule chaîne applicable directement à ``QMainWindow``.

        Returns
        -------
        str
            Feuille de style QSS complète pour l'ensemble de l'application.
        """
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
                padding: 5px 10px;
                font-weight: bold;
                font-size: {D.FONT_SIZE_SM};
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
