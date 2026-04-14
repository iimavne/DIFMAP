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
    """Bouton principal pour actions importantes"""
    
    def __init__(self, text="", icon=None, parent=None):
        super().__init__(text, parent)
        self.setStyleSheet(DesignSystem.get_button_primary())
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if icon:
            self.setIcon(qta.icon(icon))


class SecondaryButton(QPushButton):
    """Bouton secondaire pour actions normales"""
    
    def __init__(self, text="", icon=None, parent=None):
        super().__init__(text, parent)
        self.setStyleSheet(DesignSystem.get_button_secondary())
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if icon:
            self.setIcon(qta.icon(icon))


class DangerButton(QPushButton):
    """Bouton danger pour actions destructrices"""
    
    def __init__(self, text="", icon=None, parent=None):
        super().__init__(text, parent)
        self.setStyleSheet(DesignSystem.get_button_danger())
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if icon:
            self.setIcon(qta.icon(icon))


class SuccessButton(QPushButton):
    """Bouton succès pour actions positives"""
    
    def __init__(self, text="", icon=None, parent=None):
        super().__init__(text, parent)
        self.setStyleSheet(DesignSystem.get_button_success())
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if icon:
            self.setIcon(qta.icon(icon))


# ============================================================
# Utilisation :
# ============================================================
# 
# from difmap_wrapper.gui.components.styled_buttons import (
#     PrimaryButton, SecondaryButton, DangerButton, SuccessButton
# )
# 
# # Dans votre layout :
# btn_load = PrimaryButton("📂 Load", icon='fa5s.folder-open')
# btn_cancel = SecondaryButton("Cancel")
# btn_delete = DangerButton("🗑 Delete", icon='fa5s.trash')
# btn_save = SuccessButton("✓ Save", icon='fa5s.check')
#
