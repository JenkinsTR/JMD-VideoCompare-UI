"""
Card and block primitives. Flat poster blocks, no shadows.
"""
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QGroupBox, QWidget
from PyQt6.QtCore import Qt

from theme.tokens import Tokens


class Card(QFrame):
    """
    Flat content block. Use for grouping widgets.
    No border, no shadow. Background from QSS or tokens.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("role", "card")
        self._layout = QVBoxLayout(self)
        self._layout.setSpacing(Tokens.SPACE_2)
        self._layout.setContentsMargins(Tokens.SPACE_4, Tokens.SPACE_4, Tokens.SPACE_4, Tokens.SPACE_4)

    def layout(self) -> QVBoxLayout:
        return self._layout


class SectionCard(QGroupBox):
    """
    QGroupBox styled as a section card. Title at top.
    Uses app QSS for QGroupBox styling.
    """

    def __init__(self, title: str = "", parent=None):
        super().__init__(title, parent)
