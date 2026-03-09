"""
Input primitives. QLineEdit/QComboBox styled via app QSS.
LabeledInput groups a label + input for form layout.
"""
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QFontComboBox,
    QPushButton,
    QStyle,
    QStyleOptionComboBox,
)
from PyQt6.QtCore import Qt, QEasingCurve, QVariantAnimation
from PyQt6.QtGui import QColor, QFont, QPainter

from theme.tokens import Tokens
from theme import stylesheet as theme_stylesheet


class _AnimatedArrowMixin:
    """Shared behavior for Font Awesome arrow rendering + open/close animation."""

    _arrow_glyph = "\uf078"  # Font Awesome chevron-down

    def _init_animated_arrow(self) -> None:
        self.setProperty("faAnimated", True)
        self._arrow_rotation = 0.0
        self._arrow_animation = QVariantAnimation(self)
        self._arrow_animation.setDuration(160)
        self._arrow_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._arrow_animation.valueChanged.connect(self._on_arrow_value_changed)

    def _on_arrow_value_changed(self, value) -> None:
        self._arrow_rotation = float(value)
        self.update()

    def _animate_arrow(self, target_degrees: float) -> None:
        self._arrow_animation.stop()
        self._arrow_animation.setStartValue(self._arrow_rotation)
        self._arrow_animation.setEndValue(float(target_degrees))
        self._arrow_animation.start()

    def _arrow_rect(self):
        option = QStyleOptionComboBox()
        self.initStyleOption(option)
        return self.style().subControlRect(
            QStyle.ComplexControl.CC_ComboBox,
            option,
            QStyle.SubControl.SC_ComboBoxArrow,
            self,
        )

    def _arrow_color(self) -> QColor:
        if self.isEnabled():
            color = self.palette().color(self.foregroundRole())
            if color.isValid():
                return color
        return QColor(Tokens.FOREGROUND)

    def _arrow_font(self) -> QFont:
        family = theme_stylesheet.FONT_AWESOME_SOLID_FAMILY or "Font Awesome 6 Pro Solid"
        font = QFont(family)
        rect = self._arrow_rect()
        size_px = max(10, min(14, rect.height() - 8))
        font.setPixelSize(size_px)
        return font

    def _paint_animated_arrow(self) -> None:
        rect = self._arrow_rect()
        if not rect.isValid() or rect.isNull():
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setPen(self._arrow_color())
        painter.setFont(self._arrow_font())

        center = rect.center()
        painter.translate(center)
        painter.rotate(self._arrow_rotation)
        painter.translate(-center)
        painter.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), self._arrow_glyph)
        painter.end()


class AnimatedComboBox(QComboBox, _AnimatedArrowMixin):
    """QComboBox with Font Awesome animated chevron."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_animated_arrow()

    def showPopup(self) -> None:
        self._animate_arrow(180.0)
        super().showPopup()

    def hidePopup(self) -> None:
        super().hidePopup()
        self._animate_arrow(0.0)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        self._paint_animated_arrow()


class AnimatedFontComboBox(QFontComboBox, _AnimatedArrowMixin):
    """QFontComboBox with Font Awesome animated chevron."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_animated_arrow()

    def showPopup(self) -> None:
        self._animate_arrow(180.0)
        super().showPopup()

    def hidePopup(self) -> None:
        super().hidePopup()
        self._animate_arrow(0.0)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        self._paint_animated_arrow()


def LabeledInput(
    label: str,
    widget: QWidget,
    parent=None,
) -> QWidget:
    """Wrap a label above an input widget."""
    container = QWidget(parent)
    layout = QVBoxLayout(container)
    layout.setSpacing(Tokens.SPACE_1)
    layout.setContentsMargins(0, 0, 0, 0)
    lbl = QLabel(label)
    lbl.setStyleSheet(f"font-weight: 500; font-size: {Tokens.FONT_SIZE_SM}px;")
    layout.addWidget(lbl)
    layout.addWidget(widget)
    return container


def labeled_row(label: str, *widgets: QWidget, parent=None) -> QWidget:
    """Horizontal row: label on left, widgets on right."""
    container = QWidget(parent)
    layout = QHBoxLayout(container)
    layout.setSpacing(Tokens.SPACE_2)
    layout.setContentsMargins(0, 0, 0, 0)
    lbl = QLabel(label)
    lbl.setMinimumWidth(120)
    layout.addWidget(lbl)
    for w in widgets:
        layout.addWidget(w)
    return container
