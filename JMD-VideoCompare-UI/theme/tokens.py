"""
Design tokens: single source of truth for colors, spacing, typography, radii.
All values are multiples of 4px base unit. No shadows, no depth.
"""


class Tokens:
    """Flat design tokens (light mode)."""

    # Colors
    BACKGROUND = "#FFFFFF"
    FOREGROUND = "#111827"
    PRIMARY = "#3B82F6"
    PRIMARY_HOVER = "#2563EB"
    PRIMARY_PRESSED = "#1D4ED8"
    SECONDARY = "#10B981"
    ACCENT = "#F59E0B"
    MUTED = "#F3F4F6"
    MUTED_HOVER = "#E5E7EB"
    BORDER = "#E5E7EB"
    BORDER_FOCUS = "#3B82F6"

    # Spacing (4px base unit)
    SPACE_1 = 4
    SPACE_2 = 8
    SPACE_3 = 12
    SPACE_4 = 16
    SPACE_5 = 20
    SPACE_6 = 24
    SPACE_8 = 32

    # Radii
    RADIUS_MD = 6
    RADIUS_LG = 8

    # Typography
    # Keep body/control typography system-native. Custom fonts are reserved for
    # the title header and Font Awesome icon glyphs.
    FONT_FAMILY = '"Segoe UI"'
    FONT_SIZE_SM = 12
    FONT_SIZE_MD = 14
    FONT_SIZE_LG = 16
    FONT_SIZE_XL = 20
    FONT_SIZE_2XL = 24
    FONT_SIZE_3XL = 28  # Main app title

    # Borders
    BORDER_WIDTH = 2
    BORDER_WIDTH_OUTLINE = 4
