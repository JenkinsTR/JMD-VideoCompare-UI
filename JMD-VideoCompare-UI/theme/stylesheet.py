"""
Load and apply app-wide QSS stylesheet.
Applied once at QApplication level. Uses design tokens.
"""
import os
from pathlib import Path
from typing import Literal

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont, QFontDatabase

from .tokens import Tokens

ThemeMode = Literal["light", "dark"]
THEME_LIGHT: ThemeMode = "light"
THEME_DARK: ThemeMode = "dark"

# Title font family (set after loading from theme/fonts)
TITLE_FONT_FAMILY = None
FONT_AWESOME_SOLID_FAMILY = None
SYSTEM_UI_FONT_FAMILY = None


def _load_font(font_path: Path) -> list[str]:
    """Load a font file and return discovered families."""
    if not font_path.exists():
        return []
    font_id = QFontDatabase.addApplicationFont(str(font_path))
    if font_id == -1:
        return []
    return [f for f in QFontDatabase.applicationFontFamilies(font_id) if f]


def _load_system_ui_font_family() -> str | None:
    """Best-effort load of Windows UI font so body text stays system-native."""
    global SYSTEM_UI_FONT_FAMILY
    if SYSTEM_UI_FONT_FAMILY:
        return SYSTEM_UI_FONT_FAMILY

    if os.name != "nt":
        return None

    fonts_dir = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    for name in ("segoeui.ttf", "segoeuib.ttf", "segoeuil.ttf"):
        families = _load_font(fonts_dir / name)
        for family in families:
            if "Segoe UI" in family:
                SYSTEM_UI_FONT_FAMILY = family
                return SYSTEM_UI_FONT_FAMILY
        if families:
            SYSTEM_UI_FONT_FAMILY = families[0]
            return SYSTEM_UI_FONT_FAMILY
    return None


def _normalize_mode(mode: str | None) -> ThemeMode:
    if isinstance(mode, str) and mode.lower() == THEME_DARK:
        return THEME_DARK
    return THEME_LIGHT


def _palette(mode: ThemeMode) -> dict[str, str]:
    if mode == THEME_DARK:
        return {
            "BACKGROUND": "#0B1220",
            "FOREGROUND": "#E5E7EB",
            "PRIMARY": "#60A5FA",
            "PRIMARY_HOVER": "#3B82F6",
            "PRIMARY_PRESSED": "#2563EB",
            "MUTED": "#111827",
            "MUTED_HOVER": "#1F2937",
            "BORDER": "#334155",
            "BORDER_FOCUS": "#60A5FA",
            "CODE_BG": "#0F172A",
        }
    return {
        "BACKGROUND": "#FFFFFF",
        "FOREGROUND": "#111827",
        "PRIMARY": "#3B82F6",
        "PRIMARY_HOVER": "#2563EB",
        "PRIMARY_PRESSED": "#1D4ED8",
        "MUTED": "#F3F4F6",
        "MUTED_HOVER": "#E5E7EB",
        "BORDER": "#E5E7EB",
        "BORDER_FOCUS": "#3B82F6",
        "CODE_BG": "#F8FAFC",
    }


def _build_stylesheet(base_dir: Path | None = None, mode: ThemeMode = THEME_LIGHT) -> str:
    """Build QSS from tokens. Single source, no duplication."""
    t = Tokens
    p = _palette(mode)
    animated_arrow_rule = """
QComboBox[faAnimated="true"]::down-arrow,
QFontComboBox[faAnimated="true"]::down-arrow {
    image: none;
    width: 0px;
    height: 0px;
}"""
    theme_toggle_font_rule = ""
    if FONT_AWESOME_SOLID_FAMILY:
        escaped_fa = FONT_AWESOME_SOLID_FAMILY.replace('"', '\\"')
        theme_toggle_font_rule = f"""
    font-family: "{escaped_fa}";
    font-size: 16px;
    font-weight: 600;"""
    title_rule = ""
    if TITLE_FONT_FAMILY:
        escaped = TITLE_FONT_FAMILY.replace('"', '\\"')
        title_rule = f"""
QLabel[role="section-header"][heading-level="h1"] {{
    font-family: "{escaped}";
    font-size: {t.FONT_SIZE_3XL}px;
    font-weight: 700;
}}"""
    return f"""
/* === Base === */
QWidget {{
    background-color: {p["BACKGROUND"]};
    color: {p["FOREGROUND"]};
    font-size: {t.FONT_SIZE_MD}px;
}}

QMainWindow {{
    background-color: {p["BACKGROUND"]};
}}

/* === Buttons: Primary (variant=primary) === */
QPushButton[variant="primary"] {{
    background-color: {p["PRIMARY"]};
    color: white;
    border: none;
    border-radius: {t.RADIUS_MD}px;
    padding: {t.SPACE_2}px {t.SPACE_6}px;
    font-weight: 600;
    min-height: 20px;
}}
QPushButton[variant="primary"]:hover {{
    background-color: {p["PRIMARY_HOVER"]};
}}
QPushButton[variant="primary"]:pressed {{
    background-color: {p["PRIMARY_PRESSED"]};
}}
QPushButton[variant="primary"]:focus {{
    outline: {t.BORDER_WIDTH}px solid {p["BORDER_FOCUS"]};
    outline-offset: 2px;
}}

/* === Buttons: Secondary (variant=secondary) === */
QPushButton[variant="secondary"] {{
    background-color: {p["MUTED"]};
    color: {p["FOREGROUND"]};
    border: none;
    border-radius: {t.RADIUS_MD}px;
    padding: {t.SPACE_2}px {t.SPACE_4}px;
    font-weight: 500;
}}
QPushButton[variant="secondary"]:hover {{
    background-color: {p["MUTED_HOVER"]};
}}
QPushButton[variant="secondary"]:focus {{
    outline: {t.BORDER_WIDTH}px solid {p["BORDER_FOCUS"]};
    outline-offset: 2px;
}}

/* === Buttons: Outline (variant=outline) === */
QPushButton[variant="outline"] {{
    background-color: transparent;
    color: {p["PRIMARY"]};
    border: {t.BORDER_WIDTH_OUTLINE}px solid {p["PRIMARY"]};
    border-radius: {t.RADIUS_MD}px;
    padding: {t.SPACE_2}px {t.SPACE_4}px;
    font-weight: 500;
}}
QPushButton[variant="outline"]:hover {{
    background-color: {p["PRIMARY"]};
    color: white;
}}
QPushButton[variant="outline"]:focus {{
    outline: {t.BORDER_WIDTH}px solid {p["BORDER_FOCUS"]};
    outline-offset: 2px;
}}

/* === Buttons: Ghost/Flat (variant=ghost) - for logo etc === */
QPushButton[variant="ghost"] {{
    background-color: transparent;
    color: {p["FOREGROUND"]};
    border: none;
}}
QPushButton[variant="ghost"]:hover {{
    background-color: {p["MUTED"]};
}}
QPushButton[variant="ghost"]:focus {{
    outline: {t.BORDER_WIDTH}px solid {p["BORDER_FOCUS"]};
    outline-offset: 2px;
}}

/* === Default button (no variant) === */
QPushButton {{
    background-color: {p["MUTED"]};
    color: {p["FOREGROUND"]};
    border: none;
    border-radius: {t.RADIUS_MD}px;
    padding: {t.SPACE_2}px {t.SPACE_4}px;
    font-weight: 500;
}}
QPushButton:hover {{
    background-color: {p["MUTED_HOVER"]};
}}
QPushButton:focus {{
    outline: {t.BORDER_WIDTH}px solid {p["BORDER_FOCUS"]};
    outline-offset: 2px;
}}

/* === Text inputs (QLineEdit, QPlainTextEdit) === */
QLineEdit, QPlainTextEdit {{
    background-color: {p["MUTED"]};
    color: {p["FOREGROUND"]};
    border: none;
    border-radius: {t.RADIUS_MD}px;
    padding: {t.SPACE_2}px {t.SPACE_3}px;
    min-height: 20px;
    selection-background-color: {p["PRIMARY"]};
    selection-color: white;
}}
QLineEdit:focus, QPlainTextEdit:focus {{
    background-color: {p["BACKGROUND"]};
    border: {t.BORDER_WIDTH}px solid {p["PRIMARY"]};
}}

/* === Dropdowns (QComboBox, QFontComboBox) - visually distinct === */
QComboBox, QFontComboBox {{
    background-color: {p["MUTED"]};
    color: {p["FOREGROUND"]};
    border: 1px solid {p["BORDER"]};
    border-radius: {t.RADIUS_MD}px;
    padding: {t.SPACE_2}px {t.SPACE_3}px;
    padding-right: 28px;
    min-height: 20px;
    selection-background-color: {p["PRIMARY"]};
    selection-color: white;
}}
QComboBox:focus, QFontComboBox:focus {{
    background-color: {p["BACKGROUND"]};
    border: {t.BORDER_WIDTH}px solid {p["PRIMARY"]};
}}
QComboBox::drop-down, QFontComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border-left: 1px solid {p["BORDER"]};
    border-top-right-radius: {t.RADIUS_MD}px;
    border-bottom-right-radius: {t.RADIUS_MD}px;
    background-color: {p["MUTED_HOVER"]};
}}
QComboBox::drop-down:hover, QFontComboBox::drop-down:hover {{
    background-color: {p["BORDER"]};
}}
{animated_arrow_rule}
QComboBox QAbstractItemView, QFontComboBox QAbstractItemView {{
    background-color: {p["BACKGROUND"]};
    selection-background-color: {p["MUTED_HOVER"]};
}}

/* === Checkboxes === */
QCheckBox {{
    spacing: {t.SPACE_2}px;
}}
QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border-radius: 4px;
    background-color: {p["MUTED"]};
    border: 2px solid {p["BORDER"]};
}}
QCheckBox::indicator:checked {{
    background-color: {p["PRIMARY"]};
    border-color: {p["PRIMARY"]};
}}
QCheckBox::indicator:hover {{
    background-color: {p["MUTED_HOVER"]};
}}
QCheckBox:focus {{
    outline: {t.BORDER_WIDTH}px solid {p["BORDER_FOCUS"]};
    outline-offset: 2px;
}}

/* === Cards / GroupBox - consistent with main UI, white bg === */
QGroupBox {{
    background-color: {p["BACKGROUND"]};
    color: {p["FOREGROUND"]};
    border: 1px solid {p["BORDER"]};
    border-radius: {t.RADIUS_LG}px;
    padding: {t.SPACE_3}px;
    padding-top: {t.SPACE_5}px;
    margin-top: {t.SPACE_2}px;
    font-weight: 600;
    font-size: {t.FONT_SIZE_SM}px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: {t.SPACE_4}px;
    padding: 0 {t.SPACE_2}px;
}}

/* === Section header (QFrame with role) === */
QFrame[role="section-header"] {{
    background-color: transparent;
    border: none;
}}
{title_rule}

/* === Theme toggle button === */
QPushButton[role="theme-toggle"] {{
    background-color: {p["MUTED"]};
    color: {p["FOREGROUND"]};
    border: 1px solid {p["BORDER"]};
    border-radius: {t.RADIUS_MD}px;
    min-width: 34px;
    max-width: 34px;
    min-height: 30px;
    max-height: 30px;
    padding: 0px;
    {theme_toggle_font_rule}
}}
QPushButton[role="theme-toggle"]:hover {{
    background-color: {p["MUTED_HOVER"]};
}}
QPushButton[role="theme-toggle"]:pressed {{
    background-color: {p["BORDER"]};
}}
QPushButton[role="theme-toggle"]:focus {{
    outline: {t.BORDER_WIDTH}px solid {p["BORDER_FOCUS"]};
    outline-offset: 2px;
}}

/* === Labels === */
QLabel {{
    color: {p["FOREGROUND"]};
}}

/* === Dividers === */
QFrame[role="divider-h"], QFrame[role="divider-v"] {{
    background-color: {p["BORDER"]};
    border: none;
}}

/* === PlainTextEdit (output log) === */
QPlainTextEdit {{
    font-family: "Consolas", "Monaco", "Courier New", monospace;
    font-size: {t.FONT_SIZE_SM}px;
    background-color: {p["CODE_BG"]};
    border: 1px solid {p["BORDER"]};
}}

/* === Progress bar === */
QProgressBar {{
    border: none;
    border-radius: {t.RADIUS_MD}px;
    background-color: {p["MUTED"]};
    text-align: center;
}}
QProgressBar::chunk {{
    background-color: {p["PRIMARY"]};
    border-radius: {t.RADIUS_MD}px;
}}

/* === Dock widget === */
QDockWidget {{
    font-weight: 500;
}}
QDockWidget::title {{
    background-color: {p["MUTED"]};
    padding: {t.SPACE_2}px {t.SPACE_4}px;
}}

/* === Status bar === */
QStatusBar {{
    background-color: {p["MUTED"]};
    border-top: 1px solid {p["BORDER"]};
}}
"""


def load_stylesheet(base_dir: Path | None = None, mode: str | None = None) -> str:
    """Return the app stylesheet string (built from tokens)."""
    return _build_stylesheet(base_dir, _normalize_mode(mode))


def _load_theme_fonts(base_dir: Path) -> str | None:
    """Load fonts from theme/fonts. Returns title font family (Bebas Neue or Eurostile)."""
    global TITLE_FONT_FAMILY, FONT_AWESOME_SOLID_FAMILY
    fonts_dir = base_dir / "theme" / "fonts"
    if not fonts_dir.exists():
        return None

    # Preferred title fonts in fallback order.
    title_families: list[str] = []
    for name in ["BebasNeue-Regular.ttf", "Eurostile-Bold.ttf", "Eurostile-Regular.ttf"]:
        title_families.extend(_load_font(fonts_dir / name))

    # Explicitly load Font Awesome Pro 6 Solid for animated dropdown arrows.
    fa_families = _load_font(fonts_dir / "fa-solid-900.ttf")
    FONT_AWESOME_SOLID_FAMILY = None
    for family in fa_families:
        if "Font Awesome 6" in family and "Solid" in family:
            FONT_AWESOME_SOLID_FAMILY = family
            break
    if FONT_AWESOME_SOLID_FAMILY is None and fa_families:
        FONT_AWESOME_SOLID_FAMILY = fa_families[0]

    TITLE_FONT_FAMILY = title_families[0] if title_families else None
    return TITLE_FONT_FAMILY


def apply_theme(
    app: QApplication,
    base_dir: Path | None = None,
    mode: str | None = None,
) -> ThemeMode:
    """
    Apply Fusion style + app-wide QSS. Call once at startup.
    Loads fonts from theme/fonts if base_dir provided.
    """
    theme_mode = _normalize_mode(mode)
    if base_dir:
        _load_theme_fonts(base_dir)
    app.setStyle("Fusion")
    # Lock body/control typography to the system UI font.
    ui_family = _load_system_ui_font_family() or "Segoe UI"
    app_font = QFont(ui_family, Tokens.FONT_SIZE_MD)
    app.setFont(app_font)
    app.setStyleSheet(load_stylesheet(base_dir, theme_mode))
    return theme_mode
