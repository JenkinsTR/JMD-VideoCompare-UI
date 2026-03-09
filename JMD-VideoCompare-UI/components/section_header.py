"""
Section header: typography-driven heading for content blocks.
"""
from PyQt6.QtWidgets import QLabel
from PyQt6.QtGui import QFont

from theme.tokens import Tokens
from theme import stylesheet as theme_stylesheet


def SectionHeader(text: str, level: str = "h2", parent=None) -> QLabel:
    """
    Section header with typography hierarchy.
    level: "h1" | "h2" | "h3"
    """
    lbl = QLabel(text, parent)
    lbl.setProperty("role", "section-header")
    lbl.setProperty("heading-level", level)
    if level == "h1":
        font = QFont()
        if theme_stylesheet.TITLE_FONT_FAMILY:
            font.setFamily(theme_stylesheet.TITLE_FONT_FAMILY)
        font.setPointSize(Tokens.FONT_SIZE_3XL)
        font.setWeight(700)
        lbl.setFont(font)
    elif level == "h2":
        font = QFont()
        font.setPointSize(Tokens.FONT_SIZE_LG)
        font.setWeight(600)
        lbl.setFont(font)
    else:  # h3
        font = QFont()
        font.setPointSize(Tokens.FONT_SIZE_MD)
        font.setWeight(600)
        lbl.setFont(font)
    return lbl
