# difmap_wrapper/gui/header_widget.py
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QTextEdit, QLabel,
                             QFileDialog, QApplication)
from PyQt6.QtGui import QFont, QTextCharFormat, QColor, QSyntaxHighlighter
from PyQt6.QtCore import Qt, QRegularExpression
from difmap_wrapper.gui.styles import DesignSystem

D = DesignSystem


class _HeaderHighlighter(QSyntaxHighlighter):
    """Coloration syntaxique légère pour le texte de header difmap."""

    def __init__(self, document):
        super().__init__(document)
        self._rules = []

        def _rule(pattern, color, bold=False):
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            if bold:
                fmt.setFontWeight(700)
            self._rules.append((QRegularExpression(pattern), fmt))

        # Titres de section (lignes sans indentation, pas de "=")
        _rule(r"^[A-Z][A-Za-z ]+:$", D.ASTRAL_ACCENT, bold=True)
        # Clés FITS (OBSERVER =, DATE-OBS =, etc.)
        _rule(r"\b[A-Z\-]{3,10}\s*=", "#e8c97d", bold=True)
        # Valeurs entre guillemets
        _rule(r'"[^"]*"', "#82c891")
        # Nombres (entier ou flottant, y compris notation scientifique)
        _rule(r"\b[-+]?\d+\.?\d*([eE][-+]?\d+)?\b", "#79b8e0")
        # Séparateurs de tableaux
        _rule(r"^[-= ]+$", D.ASTRAL_MUTED)
        # Labels de champs indentés
        _rule(r"^\s{2,4}\w[\w. ]+\s*:", "#c0b0ff")
        # RA/DEC
        _rule(r"\d{2}[h:]\d{2}[m:]\d{2}\.?\d*[s]?", "#ffb347")

    def highlightBlock(self, text: str):
        for pattern, fmt in self._rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), fmt)


class HeaderWidget(QWidget):
    """
    Onglet d'affichage du header d'observation UVFITS.

    Équivalent graphique de la commande ``header`` de difmap.
    Peut aussi être utilisé via ``session.obs.header()`` en script.
    """

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.session = session
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        # ── Barre d'outils ──────────────────────────────────────────
        bar = QHBoxLayout()
        bar.setSpacing(6)

        lbl = QLabel("Observation Header")
        lbl.setStyleSheet(
            f"color: {D.ASTRAL_TEXT}; font-size: {D.FONT_SIZE_LG}; font-weight: bold;"
        )
        bar.addWidget(lbl)
        bar.addStretch()

        btn_style = f"""
            QPushButton {{
                background-color: {D.ASTRAL_SURFACE};
                border: 1px solid {D.ASTRAL_BORDER};
                border-radius: {D.RADIUS_MD};
                color: {D.ASTRAL_TEXT};
                font-size: {D.FONT_SIZE_BASE};
                padding: 6px 12px;
                min-height: 28px;
            }}
            QPushButton:hover {{ background-color: {D.ASTRAL_HOVER}; }}
            QPushButton:disabled {{ color: {D.ASTRAL_MUTED}; }}
        """

        self.btn_refresh = QPushButton("⟳  Refresh")
        self.btn_copy    = QPushButton("⎘  Copy")
        self.btn_save    = QPushButton("⬇  Save…")
        for btn in (self.btn_refresh, self.btn_copy, self.btn_save):
            btn.setStyleSheet(btn_style)
            btn.setMinimumHeight(30)
            bar.addWidget(btn)

        root.addLayout(bar)

        # ── Zone de texte monospace ──────────────────────────────────
        self.text_area = QTextEdit()
        self.text_area.setReadOnly(True)
        font = QFont("Monospace", 12)
        font.setStyleHint(QFont.StyleHint.TypeWriter)
        self.text_area.setFont(font)
        self.text_area.setStyleSheet(f"""
            QTextEdit {{
                background-color: {D.ASTRAL_DEEPEST};
                color: {D.ASTRAL_TEXT};
                border: 1px solid {D.ASTRAL_BORDER};
                border-radius: {D.RADIUS_MD};
                padding: 10px;
                selection-background-color: {D.ASTRAL_ACCENT};
            }}
            QScrollBar:vertical {{
                width: 8px; background: {D.ASTRAL_DEEP};
            }}
            QScrollBar::handle:vertical {{
                background: {D.ASTRAL_BORDER}; border-radius: 4px;
            }}
        """)
        self._highlighter = _HeaderHighlighter(self.text_area.document())
        root.addWidget(self.text_area)

        # ── Status bar ───────────────────────────────────────────────
        self.lbl_status = QLabel("No observation loaded.")
        self.lbl_status.setStyleSheet(
            f"color: {D.ASTRAL_DIM}; font-size: {D.FONT_SIZE_XS}; font-style: italic;"
        )
        root.addWidget(self.lbl_status)

        # ── Connexions ───────────────────────────────────────────────
        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_copy   .clicked.connect(self._copy_to_clipboard)
        self.btn_save   .clicked.connect(self._save_to_file)

    # ── API publique ─────────────────────────────────────────────────

    def refresh(self):
        """Relit le header depuis le moteur C et rafraîchit l'affichage."""
        try:
            if not self.session.uv_loaded:
                self.text_area.setPlainText("(no observation loaded)")
                self.lbl_status.setText("No observation loaded.")
                return
            text = self.session.obs.header()
            self.text_area.setPlainText(text)
            src = self.session.obs.source
            self.lbl_status.setText(f"Source: {src}  —  header read OK")
        except Exception as e:
            self.text_area.setPlainText(f"Error reading header:\n{e}")
            self.lbl_status.setText(f"Error: {e}")

    def _copy_to_clipboard(self):
        text = self.text_area.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
            self.lbl_status.setText("Header copied to clipboard.")

    def _save_to_file(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save header", "header.txt", "Text files (*.txt);;All files (*)"
        )
        if path:
            try:
                with open(path, "w") as f:
                    f.write(self.text_area.toPlainText())
                self.lbl_status.setText(f"Saved to {path}")
            except Exception as e:
                self.lbl_status.setText(f"Save error: {e}")
