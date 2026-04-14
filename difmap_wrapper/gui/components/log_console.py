# difmap_wrapper/gui/components/log_console.py
from PyQt6.QtWidgets import QDockWidget, QTextEdit
from PyQt6.QtCore import Qt
from datetime import datetime

class LogConsole(QDockWidget):
    def __init__(self, title="SYSTEM & INSPECTION LOG", parent=None):
        super().__init__(title, parent)
        self.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)
        self.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        
        # Style QSS pour correspondre à la maquette (Fond sombre, texte vert)
        self.text_edit.setStyleSheet("""
            QTextEdit {
                background-color: #1a1a1a;
                color: #2ecc71;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 11px;
                border: none;
                padding: 10px;
            }
        """)
        
        self.setWidget(self.text_edit)

    def log(self, message):
        """Ajoute un message horodaté à la console."""
        time_str = datetime.now().strftime("%H:%M:%S")
        self.text_edit.append(f"[{time_str}] {message}")
        
        # Auto-scroll vers le bas
        scrollbar = self.text_edit.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())