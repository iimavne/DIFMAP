# difmap_wrapper/gui/components/styled_buttons.py
"""
Boutons préstylisés utilisant le Design System
À importer et utiliser directement dans les composants
"""

from PyQt6.QtWidgets import QPushButton
from PyQt6.QtCore import Qt
from difmap_wrapper.gui.styles import DesignSystem
import qtawesome as qta


class PrimaryButton(QPushButton):
    """Bouton d'action principale (fond bleu astral)."""

    def __init__(self, text="", icon=None, parent=None):
        """
        Parameters
        ----------
        text : str, optional
            Texte affiché sur le bouton.
        icon : str, optional
            Nom d'icône qtawesome (ex. ``'fa5s.folder-open'``).
        parent : QWidget, optional
            Widget parent Qt.
        """
        super().__init__(text, parent)
        self.setStyleSheet(DesignSystem.get_button_primary())
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if icon:
            self.setIcon(qta.icon(icon))


class SecondaryButton(QPushButton):
    """Bouton secondaire pour actions normales (fond gris clair)."""

    def __init__(self, text="", icon=None, parent=None):
        """
        Parameters
        ----------
        text : str, optional
            Texte affiché sur le bouton.
        icon : str, optional
            Nom d'icône qtawesome (ex. ``'fa5s.search'``).
        parent : QWidget, optional
            Widget parent Qt.
        """
        super().__init__(text, parent)
        self.setStyleSheet(DesignSystem.get_button_secondary())
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if icon:
            self.setIcon(qta.icon(icon))


class DangerButton(QPushButton):
    """Bouton danger pour actions destructrices (fond rouge pâle)."""

    def __init__(self, text="", icon=None, parent=None):
        """
        Parameters
        ----------
        text : str, optional
            Texte affiché sur le bouton.
        icon : str, optional
            Nom d'icône qtawesome (ex. ``'fa5s.trash'``).
        parent : QWidget, optional
            Widget parent Qt.
        """
        super().__init__(text, parent)
        self.setStyleSheet(DesignSystem.get_button_danger())
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if icon:
            self.setIcon(qta.icon(icon))


class SuccessButton(QPushButton):
    """Bouton succès pour actions positives (fond vert pâle)."""

    def __init__(self, text="", icon=None, parent=None):
        """
        Parameters
        ----------
        text : str, optional
            Texte affiché sur le bouton.
        icon : str, optional
            Nom d'icône qtawesome (ex. ``'fa5s.check'``).
        parent : QWidget, optional
            Widget parent Qt.
        """
        super().__init__(text, parent)
        self.setStyleSheet(DesignSystem.get_button_success())
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if icon:
            self.setIcon(qta.icon(icon))


# ============================================================
# Utilisation :
# ============================================================
# 
# from .styled_buttons import (
#     PrimaryButton, SecondaryButton, DangerButton, SuccessButton
# )
# 
# # Dans votre layout :
# btn_load = PrimaryButton("📂 Load", icon='fa5s.folder-open')
# btn_cancel = SecondaryButton("Cancel")
# btn_delete = DangerButton("🗑 Delete", icon='fa5s.trash')
# btn_save = SuccessButton("✓ Save", icon='fa5s.check')
#
