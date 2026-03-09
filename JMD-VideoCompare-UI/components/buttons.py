"""
Button primitives. Use setProperty("variant", ...) for QSS styling.
No subclasses; standard QPushButton with variant property.
"""
from PyQt6.QtWidgets import QPushButton
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QSize


def primary_button(text: str = "", parent=None) -> QPushButton:
    """Primary action button (blue fill)."""
    btn = QPushButton(text, parent)
    btn.setProperty("variant", "primary")
    return btn


def secondary_button(text: str = "", parent=None) -> QPushButton:
    """Secondary button (muted fill)."""
    btn = QPushButton(text, parent)
    btn.setProperty("variant", "secondary")
    return btn


def outline_button(text: str = "", parent=None) -> QPushButton:
    """Outline button (border, transparent fill)."""
    btn = QPushButton(text, parent)
    btn.setProperty("variant", "outline")
    return btn


def ghost_button(text: str = "", parent=None) -> QPushButton:
    """Ghost button (transparent, for logo/icon actions)."""
    btn = QPushButton(text, parent)
    btn.setProperty("variant", "ghost")
    return btn
