# difmap_wrapper/gui/styles/themes.py
"""
Thèmes prédéfinis pour DIFMAP Modern
Supporte Light et Dark modes
"""

# ============================================================
# THÈME CLAIR (Défaut)
# ============================================================
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

# ============================================================
# THÈME SOMBRE
# ============================================================
DARK_THEME = {
    'name': 'Dark',
    'primary': '#5eb3ff',           # Bleu lumineux
    'primary_hover': '#4da3f0',
    'primary_active': '#3d93e0',
    'secondary': '#a0aec0',
    'success': '#48bb78',           # Vert lumineux
    'warning': '#ed8936',           # Orange vif
    'danger': '#f56565',            # Rouge lumineux
    'info': '#38b2e6',              # Cyan clair
    
    'background': '#0f0f1e',        # Noir pur
    'surface': '#1e1e2e',           # Gris très foncé
    'surface_alt': '#2d2d3d',       # Gris foncé alt
    
    'text': '#e8e8f0',              # Blanc cassé
    'text_secondary': '#a0aec0',    # Gris texte
    'text_muted': '#6d7a96',        # Gris désactivé
    'text_light': '#212529',        # Pour texte sur fond clair
    
    'border': '#434358',
    'border_light': '#2d2d3d',
    'divider': '#434358',
}

# ============================================================
# EXPORTATION
# ============================================================
THEMES = {
    'light': LIGHT_THEME,
    'dark': DARK_THEME,
}

def get_theme(name='light'):
    """
    Retourne un dictionnaire de thème par son nom.

    Parameters
    ----------
    name : str, optional
        Nom du thème : ``'light'`` ou ``'dark'``. Défaut : ``'light'``.

    Returns
    -------
    dict
        Dictionnaire de couleurs du thème demandé (``LIGHT_THEME`` par défaut).
    """
    return THEMES.get(name, LIGHT_THEME)

def generate_qss_from_theme(theme):
    """
    Génère une feuille de style QSS minimale à partir d'un dictionnaire de thème.

    Parameters
    ----------
    theme : dict
        Dictionnaire de couleurs (ex. ``LIGHT_THEME`` ou ``DARK_THEME``).

    Returns
    -------
    str
        Feuille QSS couvrant ``QWidget``, ``QLabel``, ``QPushButton``,
        ``QLineEdit`` et ``QGroupBox``.
    """
    return f"""
        QWidget {{
            background-color: {theme['background']};
            color: {theme['text']};
        }}
        QLabel {{
            color: {theme['text']};
        }}
        QPushButton {{
            background-color: {theme['surface_alt']};
            color: {theme['text']};
            border: 1px solid {theme['border']};
        }}
        QPushButton:hover {{
            background-color: {theme['primary']};
            color: white;
        }}
        QLineEdit {{
            background-color: {theme['surface']};
            color: {theme['text']};
            border: 1px solid {theme['border']};
        }}
        QGroupBox {{
            color: {theme['text_secondary']};
            border: 1px solid {theme['border']};
        }}
    """
