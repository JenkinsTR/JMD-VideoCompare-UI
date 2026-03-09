"""
Application metadata shared by GUI, CLI, and splash rendering.
"""

from __future__ import annotations

import os

APP_NAME = "JMD Video Compare UI"
APP_CLI_NAME = "JMD-VideoCompare-UI"
APP_VERSION = "1.0.0"

# Override via environment at build/release time if needed.
DEFAULT_BUILD_DATE = "2026-02-27"
BUILD_DATE = os.environ.get("JMDVC_BUILD_DATE", DEFAULT_BUILD_DATE)

SPLASH_SUBTITLE = "Create side-by-side video comparisons quickly and consistently."


def version_label() -> str:
    return f"v{APP_VERSION} ({BUILD_DATE})"


def cli_banner() -> str:
    return f"{APP_CLI_NAME} {version_label()}"


def window_title() -> str:
    return f"{APP_NAME} {version_label()}"
