"""
Unified entrypoint for GUI + CLI modes.
CLI paths stay headless and do not import PyQt modules.
"""

from __future__ import annotations

import sys
from pathlib import Path

_BASE_DIR = (
    Path(getattr(sys, "_MEIPASS", "."))
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parent
)
sys.path.insert(0, str(_BASE_DIR))

_CLI_COMMANDS = {"process", "ffmpeg-test", "--version", "-V", "--help", "-h"}


def _ensure_console_for_cli() -> None:
    """Attach to parent console (or allocate one) when running CLI under windowed EXE."""
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        attached = kernel32.AttachConsole(ctypes.c_uint(-1))
        if attached == 0:
            kernel32.AllocConsole()
        sys.stdout = open("CONOUT$", "w", encoding="utf-8", buffering=1)
        sys.stderr = open("CONOUT$", "w", encoding="utf-8", buffering=1)
        try:
            sys.stdin = open("CONIN$", "r", encoding="utf-8")
        except Exception:
            pass
    except Exception:
        pass


def main(argv: list[str] | None = None) -> int:
    args = list(argv) if argv is not None else sys.argv[1:]

    if args and args[0] in _CLI_COMMANDS:
        _ensure_console_for_cli()
        from app_cli import run_from_argv

        return run_from_argv(args, base_dir=_BASE_DIR)

    from mainwindow import run_gui

    return run_gui([sys.argv[0], *args])


if __name__ == "__main__":
    raise SystemExit(main())
