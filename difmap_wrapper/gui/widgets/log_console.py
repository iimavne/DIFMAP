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
        'info':    '#6890B8',   # bleu-gris (fond sombre)
        'success': '#4CAF50',   # vert
        'warning': '#E6A817',   # ambre
        'error':   '#EF5350',   # rouge vif
        'debug':   '#607080',   # gris
        'inspect': '#26C6DA',   # teal
        'stats':   '#AB8FE0',   # violet doux
    }
    def __init__(self, title="SYSTEM LOG", parent=None):
        """
        Parameters
        ----------
        title : str, optional
            Titre affiché dans la barre du dock widget.
        parent : QWidget, optional
            Widget parent Qt.
        """
        super().__init__(title, parent)
        self.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)
        self.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        
        # Widget texte en lecture seule
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        
        self.text_edit.setStyleSheet(f"""
            QTextEdit {{
                background-color: {DesignSystem.TERMINAL_BG};
                color: {DesignSystem.TERMINAL_TEXT};
                font-family: {DesignSystem.FONT_MONO};
                font-size: 12px;
                border: none;
                padding: 8px;
            }}
        """)
        
        self.setWidget(self.text_edit)

    def log_info(self, message):
        """
        Affiche un message d'information (couleur bleu-gris).

        Parameters
        ----------
        message : str
            Texte à afficher dans la console.
        """
        self._append_styled(message, 'info')

    def log_success(self, message):
        """
        Affiche un message de succès (couleur verte).

        Parameters
        ----------
        message : str
            Texte à afficher dans la console.
        """
        self._append_styled(message, 'success')

    def log_warning(self, message):
        """
        Affiche un avertissement (couleur ambre).

        Parameters
        ----------
        message : str
            Texte à afficher dans la console.
        """
        self._append_styled(message, 'warning')

    def log_error(self, message):
        """
        Affiche un message d'erreur (couleur rouge vif).

        Parameters
        ----------
        message : str
            Texte à afficher dans la console.
        """
        self._append_styled(message, 'error')

    def log_debug(self, message):
        """
        Affiche un message de débogage (couleur gris sombre).

        Parameters
        ----------
        message : str
            Texte à afficher dans la console.
        """
        self._append_styled(message, 'debug')

    def log_inspect(self, message):
        """
        Affiche un message d'inspection de point (couleur teal).

        Parameters
        ----------
        message : str
            Texte à afficher dans la console.
        """
        self._append_styled(message, 'inspect')

    def log(self, message):
        """
        Log générique — équivalent à :meth:`log_info`.

        Parameters
        ----------
        message : str
            Texte à afficher dans la console.
        """
        self.log_info(message)

    def log_stats(self, message):
        """
        Affiche un message de statistiques (couleur violet doux).

        Parameters
        ----------
        message : str
            Texte à afficher dans la console.
        """
        self._append_styled(message, 'stats')
        
    def _append_styled(self, message, level='info'):
        """
        Ajoute un message formaté avec horodatage, icône et couleur.

        Gère automatiquement l'alignement des messages multi-lignes (``\\n``).

        Parameters
        ----------
        message : str
            Texte à afficher (peut contenir des sauts de ligne).
        level : str, optional
            Niveau de log : ``'info'``, ``'success'``, ``'warning'``, ``'error'``,
            ``'debug'``, ``'inspect'`` ou ``'stats'``. Défaut : ``'info'``.
        """
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

    # =========================================================
    # Connexion au système de logging Python
    # =========================================================

    def connect_handler(self, handler) -> None:
        """
        Abonne cette console aux logs émis par DifmapLogHandler.

        Paramètre
        ---------
        handler : DifmapLogHandler
            Le handler dont le signal log_emitted sera connecté à _dispatch().

        Exemple
        -------
        >>> from difmap_wrapper.gui.log_handler import DifmapLogHandler
        >>> handler = DifmapLogHandler()
        >>> logging.getLogger('difmap').addHandler(handler)
        >>> console.connect_handler(handler)
        """
        handler.log_emitted.connect(self._dispatch)

    def _dispatch(self, level: str, message: str) -> None:
        """Slot Qt : reçoit (level, message) depuis DifmapLogHandler et affiche."""
        self._append_styled(message, level)

    # =========================================================
    # Utilitaires
    # =========================================================

    def clear_log(self):
        """Efface tout le contenu de la console."""
        self.text_edit.clear()

    def copy_all(self):
        """Copie tout le contenu de la console dans le presse-papiers."""
        self.text_edit.selectAll()
        self.text_edit.copy()

    def set_theme(self, theme_dict):
        """
        Change le thème de la console (non implémenté, réservé à un usage futur).

        Parameters
        ----------
        theme_dict : dict
            Dictionnaire de couleurs du nouveau thème.
        """
        pass