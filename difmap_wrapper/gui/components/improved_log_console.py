# difmap_wrapper/gui/components/improved_log_console.py
"""
Console de logs améliorée avec support des niveaux et couleurs
À utiliser à la place de log_console.py pour une meilleure esthétique
"""

from PyQt6.QtWidgets import QDockWidget, QTextEdit
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QTextCursor, QTextCharFormat, QColor
from datetime import datetime
from difmap_wrapper.gui.styles import DesignSystem


class ImprovedLogConsole(QDockWidget):
    """Console de logs modernes avec codes de couleur et icônes"""
    
    # Icônes/symboles pour chaque niveau
    ICONS = {
        'info': '',
        'success': '',
        'warning': '',
        'error': '',
        'debug': '',
        'inspect': '', # Pas d'icône pour l'inspection pour rester sobre
    }
    
    COLORS = {
        'info': '#0056b3',
        'success': '#155724',
        'warning': '#d97706',   # Orange
        'error': '#dc3545',     # Rouge
        'debug': '#495057',
        'inspect': '#0284c7', 
        'stats': '#8b5cf6',
    }
    def __init__(self, title="SYSTEM LOG", parent=None):
        super().__init__(title, parent)
        self.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)
        self.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        
        # Widget texte en lecture seule
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        
        # Style moderne et ULTRA LISIBLE
        self.text_edit.setStyleSheet(f"""
            QTextEdit {{
                background-color: {DesignSystem.SURFACE}; /* Fond légèrement gris pour le contraste */
                color: {DesignSystem.TEXT};
                font-family: {DesignSystem.FONT_MONO};
                font-size: 13px; /* <-- TAILLE AUGMENTÉE POUR UNE LECTURE CONFORTABLE */
                border: 1px solid {DesignSystem.BORDER};
                border-radius: {DesignSystem.RADIUS_MD};
                padding: {DesignSystem.SPACING_MD};
            }}
            QTextEdit:focus {{
                border: 2px solid {DesignSystem.PRIMARY};
            }}
        """)
        
        self.setWidget(self.text_edit)

    def log_info(self, message):
        """Log d'information (bleu)"""
        self._append_styled(message, 'info')

    def log_success(self, message):
        """Log de succès (vert)"""
        self._append_styled(message, 'success')

    def log_warning(self, message):
        """Log d'alerte (orange foncé)"""
        self._append_styled(message, 'warning')

    def log_error(self, message):
        """Log d'erreur (rouge)"""
        self._append_styled(message, 'error')

    def log_debug(self, message):
        """Log de debug (gris)"""
        self._append_styled(message, 'debug')
    
    def log_inspect(self, message):
        """Log d'inspection (bleu clair)"""
        self._append_styled(message, 'inspect')

    def log(self, message):
        """Log générique (équivalent à info)"""
        self.log_info(message)

    def log_stats(self, message):
        """Log des statistiques mathématiques (violet)"""
        self._append_styled(message, 'stats')
        
    def _append_styled(self, message, level='info'):
        """Ajoute un message avec formatage spécifique au niveau et alignement multi-lignes"""
        icon = self.ICONS.get(level, '')
        color = self.COLORS.get(level, DesignSystem.TEXT)
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # 1. On calcule le préfixe de la première ligne
        prefix = f"{icon}[{timestamp}]  "
        
        # 2. On calcule l'espace vide exact pour aligner les lignes suivantes
        indent = " " * len(prefix)
        
        # 3. On découpe le message s'il a plusieurs lignes (\n)
        lines = str(message).split('\n')
        
        # 4. On assemble : préfixe pour la ligne 1, espaces pour les autres
        formatted_msg = f"{prefix}{lines[0]}"
        if len(lines) > 1:
            for line in lines[1:]:
                formatted_msg += f"\n{indent}{line}"
        
        # Écriture dans l'éditeur (inchangé)
        cursor = self.text_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        fmt.setFontWeight(600)
        
        cursor.setCharFormat(fmt)
        cursor.insertText(formatted_msg + "\n")
        self.text_edit.setTextCursor(cursor)
        
        scrollbar = self.text_edit.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def clear_log(self):
        """Efface la console"""
        self.text_edit.clear()

    def copy_all(self):
        """Copie tout le contenu"""
        self.text_edit.selectAll()
        self.text_edit.copy()

    def set_theme(self, theme_dict):
        """Change le thème (optionnel)"""
        pass