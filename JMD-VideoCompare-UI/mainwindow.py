# This Python file uses the following encoding: utf-8
import sys
import subprocess
import re
import os
from pathlib import Path
import shutil
import zipfile
import urllib.request
import urllib.parse
try:
    import winreg
except ImportError:  # non-Windows
    winreg = None

# Base path: PyInstaller extracts to _MEIPASS when frozen
_BASE_DIR = Path(getattr(sys, "_MEIPASS", ".")) if getattr(sys, "frozen", False) else Path(__file__).resolve().parent

# Ensure theme and components are importable when running mainwindow.py directly
sys.path.insert(0, str(_BASE_DIR))

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QMessageBox, QSplashScreen,
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QCheckBox, QSpinBox,
    QFrame, QPlainTextEdit, QDockWidget, QProgressBar
)
from PyQt6.QtGui import (
    QTextCursor,
    QDesktopServices,
    QPixmap,
    QIcon,
    QCursor,
    QFont,
    QColor,
    QLinearGradient,
    QRadialGradient,
    QPainter,
    QPen,
    QPainterPath,
    QFontMetrics,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl, QSize, QTimer, QSettings
import logging

from theme import apply_theme
from theme import stylesheet as theme_stylesheet
from theme.tokens import Tokens
from app_info import APP_NAME, SPLASH_SUBTITLE, version_label, window_title
from ffmpeg_runtime import default_cache_root
from components import (
    primary_button,
    secondary_button,
    ghost_button,
    SectionCard,
    SectionHeader,
    AnimatedComboBox,
    AnimatedFontComboBox,
)

# Setup logging
logging.basicConfig(filename='app.log', filemode='w', format='%(name)s - %(levelname)s - %(message)s')


_FONT_STYLE_WORDS = (
    "regular",
    "bold",
    "italic",
    "oblique",
    "semibold",
    "demibold",
    "extrabold",
    "ultrabold",
    "black",
    "heavy",
    "light",
    "extralight",
    "ultralight",
    "medium",
    "thin",
    "condensed",
    "narrow",
)

_FFMPEG_DOWNLOAD_URLS = [
    "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
    "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip",
]


def _strip_style_words(font_name: str) -> str:
    """Remove trailing style words from a registry font display name."""
    words = font_name.strip().split()
    while words and words[-1].lower() in _FONT_STYLE_WORDS:
        words.pop()
    return " ".join(words) if words else font_name.strip()


class FontScanner(QThread):
    update_signal = pyqtSignal(str)

    def __init__(self, font_dir: str):
        super().__init__()
        self.font_dir = font_dir
        self.font_cache = {}

    def _add_cache_entry(self, family: str, font_path: str) -> None:
        family = family.strip()
        if family and family not in self.font_cache:
            self.font_cache[family] = font_path

    def _scan_windows_font_registry(self):
        if winreg is None:
            return

        key_path = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"
        fonts_dir = Path(self.font_dir)
        total = 0

        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as fonts_key:
            while True:
                try:
                    display_name, font_value, _ = winreg.EnumValue(fonts_key, total)
                    total += 1
                except OSError:
                    break

                if not isinstance(font_value, str):
                    continue

                lower_value = font_value.lower()
                if not lower_value.endswith((".ttf", ".otf", ".ttc", ".otc")):
                    continue

                font_path = Path(font_value)
                if not font_path.is_absolute():
                    font_path = fonts_dir / font_path
                if not font_path.exists():
                    continue

                clean_name = re.sub(r"\s*\(.*\)\s*$", "", display_name).strip()
                if not clean_name:
                    continue

                self._add_cache_entry(clean_name, str(font_path))
                self._add_cache_entry(_strip_style_words(clean_name), str(font_path))

                if total % 50 == 0:
                    self.update_signal.emit(f"Scanning fonts: {total} entries")

    def run(self):
        # Use registry lookup to avoid loading every system font into Qt,
        # which can trigger thousands of DirectWrite warnings.
        self.update_signal.emit("Scanning font registry...")
        try:
            self._scan_windows_font_registry()
        except Exception as e:
            logging.warning(f"Font cache scan failed: {e}")

        self.update_signal.emit("Font scanning complete.")

    def get_font_cache(self):
        return self.font_cache


def _parse_time_to_seconds(time_str: str) -> float:
    """Parse HH:MM:SS or HH:MM:SS.ms to seconds."""
    m = re.match(r"(\d+):(\d+):(\d+)(?:\.(\d+))?", time_str.strip())
    if not m:
        return 0.0
    h, mm, s = int(m.group(1)), int(m.group(2)), int(m.group(3))
    ms = int(m.group(4)) if m.group(4) else 0
    return h * 3600 + mm * 60 + s + ms / 100.0


def _ffmpeg_cache_root() -> Path:
    return default_cache_root()


def _validate_exe(exe_path: Path) -> bool:
    if not exe_path.exists() or not exe_path.is_file():
        return False
    try:
        result = subprocess.run(
            [str(exe_path), "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=8,
        )
        return result.returncode == 0
    except Exception:
        return False


def _validate_ffmpeg_pair(ffmpeg_path: Path, ffprobe_path: Path) -> bool:
    return _validate_exe(ffmpeg_path) and _validate_exe(ffprobe_path)


def _find_ffmpeg_pair_in_tree(root: Path) -> tuple[Path | None, Path | None]:
    if not root.exists():
        return None, None
    for ffmpeg_path in root.rglob("ffmpeg.exe"):
        ffprobe_path = ffmpeg_path.with_name("ffprobe.exe")
        if ffprobe_path.exists() and _validate_ffmpeg_pair(ffmpeg_path, ffprobe_path):
            return ffmpeg_path, ffprobe_path
    return None, None


def _resolve_system_ffmpeg_pair() -> tuple[Path | None, Path | None]:
    ffmpeg_path = shutil.which("ffmpeg")
    ffprobe_path = shutil.which("ffprobe")
    if ffmpeg_path and not ffprobe_path:
        sibling = Path(ffmpeg_path).with_name("ffprobe.exe")
        if sibling.exists():
            ffprobe_path = str(sibling)
    if not ffmpeg_path or not ffprobe_path:
        return None, None
    ffmpeg = Path(ffmpeg_path)
    ffprobe = Path(ffprobe_path)
    if _validate_ffmpeg_pair(ffmpeg, ffprobe):
        return ffmpeg, ffprobe
    return None, None


def _download_ffmpeg_archive(target_path: Path, update_cb) -> None:
    last_error = None
    for url in _FFMPEG_DOWNLOAD_URLS:
        try:
            host = urllib.parse.urlparse(url).netloc
            update_cb(f"Downloading FFmpeg from {host}...")
            request = urllib.request.Request(url, headers={"User-Agent": "JMD-VideoCompare-UI"})
            with urllib.request.urlopen(request, timeout=45) as response, open(target_path, "wb") as out_file:
                total_str = response.headers.get("Content-Length")
                total = int(total_str) if total_str and total_str.isdigit() else 0
                downloaded = 0
                next_percent = 5
                while True:
                    chunk = response.read(1024 * 256)
                    if not chunk:
                        break
                    out_file.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        percent = int((downloaded * 100) / total)
                        if percent >= next_percent:
                            update_cb(f"Downloading FFmpeg... {min(percent, 100)}%")
                            next_percent += 5
            update_cb("Download complete.")
            return
        except Exception as e:
            last_error = e
            update_cb(f"Download failed from {host}, trying fallback...")
            continue
    raise RuntimeError(f"Failed to download FFmpeg: {last_error}")


def _safe_extract_zip(zip_path: Path, output_dir: Path) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir, ignore_errors=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.infolist():
            member_target = (output_dir / member.filename).resolve()
            if not str(member_target).startswith(str(output_dir.resolve())):
                raise RuntimeError("Unsafe archive path detected while extracting FFmpeg.")
        zf.extractall(output_dir)


def _ensure_ffmpeg_runtime(base_dir: Path, update_cb) -> tuple[str, str, str]:
    # Prefer user/system install to avoid unnecessary downloads.
    update_cb("Checking system FFmpeg installation...")
    system_ffmpeg, system_ffprobe = _resolve_system_ffmpeg_pair()
    if system_ffmpeg and system_ffprobe:
        return str(system_ffmpeg), str(system_ffprobe), "system"

    # Bundled binaries (if present in dev/build environment).
    update_cb("Checking bundled FFmpeg runtime...")
    bundled_ffmpeg = base_dir / "bin" / "ffmpeg.exe"
    bundled_ffprobe = base_dir / "bin" / "ffprobe.exe"
    if _validate_ffmpeg_pair(bundled_ffmpeg, bundled_ffprobe):
        return str(bundled_ffmpeg), str(bundled_ffprobe), "bundled"

    # Cached runtime from previous downloads.
    update_cb("Checking cached FFmpeg runtime...")
    cache_root = _ffmpeg_cache_root()
    cached_root = cache_root / "current"
    cached_ffmpeg, cached_ffprobe = _find_ffmpeg_pair_in_tree(cached_root)
    if cached_ffmpeg and cached_ffprobe:
        return str(cached_ffmpeg), str(cached_ffprobe), "cached"

    # Download + extract runtime.
    update_cb("FFmpeg not found. Starting first-run download...")
    archive_path = cache_root / "ffmpeg-runtime.zip"
    extract_tmp = cache_root / "extract-tmp"
    install_root = cache_root / "current"

    _download_ffmpeg_archive(archive_path, update_cb)
    update_cb("Extracting FFmpeg...")
    _safe_extract_zip(archive_path, extract_tmp)

    extracted_ffmpeg, extracted_ffprobe = _find_ffmpeg_pair_in_tree(extract_tmp)
    if not extracted_ffmpeg or not extracted_ffprobe:
        raise RuntimeError("Downloaded FFmpeg archive does not contain ffmpeg.exe and ffprobe.exe.")

    if install_root.exists():
        shutil.rmtree(install_root, ignore_errors=True)
    install_root.mkdir(parents=True, exist_ok=True)

    source_dir = extracted_ffmpeg.parent
    target_dir = install_root / "bin"
    shutil.copytree(source_dir, target_dir, dirs_exist_ok=True)

    final_ffmpeg = target_dir / "ffmpeg.exe"
    final_ffprobe = target_dir / "ffprobe.exe"
    if not _validate_ffmpeg_pair(final_ffmpeg, final_ffprobe):
        raise RuntimeError("Downloaded FFmpeg runtime failed validation after extraction.")

    shutil.rmtree(extract_tmp, ignore_errors=True)
    try:
        archive_path.unlink(missing_ok=True)
    except Exception:
        pass

    update_cb("FFmpeg setup complete.")
    return str(final_ffmpeg), str(final_ffprobe), "downloaded"


def _detect_system_theme_mode(app: QApplication) -> str:
    """
    Detect OS color scheme preference.
    Falls back to light mode when unavailable/unknown.
    """
    try:
        scheme = app.styleHints().colorScheme()
        if scheme == Qt.ColorScheme.Dark:
            return theme_stylesheet.THEME_DARK
    except Exception:
        pass
    return theme_stylesheet.THEME_LIGHT


def _build_splash_pixmap(base_dir: Path) -> QPixmap:
    """Build splash pixmap with centered title/subtitle and status-safe footer."""
    splash_path = base_dir / "images" / "splash.png"
    pixmap = QPixmap(str(splash_path))
    if pixmap.isNull():
        pixmap = QPixmap(600, 250)
        pixmap.fill(QColor("#0E1E3D"))

    width = pixmap.width()
    height = pixmap.height()
    status_zone_height = max(34, min(42, int(height * 0.16)))
    content_top = 16
    content_bottom = height - status_zone_height - 12
    content_height = max(64, content_bottom - content_top)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

    # Subtle contrast layer over the base splash image.
    overlay = QLinearGradient(0, 0, width, height)
    overlay.setColorAt(0.0, QColor(5, 10, 18, 46))
    overlay.setColorAt(1.0, QColor(5, 10, 18, 10))
    painter.fillRect(0, 0, width, height, overlay)

    # Top-right logo card.
    logo_card_width = min(188, int(width * 0.32))
    logo_card_height = min(58, int(height * 0.24))
    logo_card_x = width - logo_card_width - 20
    logo_card_y = 16

    card_path = QPainterPath()
    card_path.addRoundedRect(float(logo_card_x), float(logo_card_y), float(logo_card_width), float(logo_card_height), 10.0, 10.0)
    painter.fillPath(card_path, QColor(255, 255, 255, 34))
    painter.setPen(QPen(QColor(255, 255, 255, 68), 1))
    painter.drawPath(card_path)

    logo_path = base_dir / "images" / "JMDigital.png"
    logo = QPixmap(str(logo_path))
    if not logo.isNull():
        padded_width = max(1, logo_card_width - 24)
        padded_height = max(1, logo_card_height - 20)
        scaled_logo = logo.scaled(
            padded_width,
            padded_height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        logo_x = logo_card_x + int((logo_card_width - scaled_logo.width()) / 2)
        logo_y = logo_card_y + int((logo_card_height - scaled_logo.height()) / 2)
        painter.drawPixmap(logo_x, logo_y, scaled_logo)

    # Centered content block in usable vertical area.
    title_text = APP_NAME.upper()
    subtitle_text = SPLASH_SUBTITLE
    text_left = 30
    text_right = logo_card_x - 14
    text_width = max(200, text_right - text_left)

    title_font = QFont(theme_stylesheet.TITLE_FONT_FAMILY or "Segoe UI")
    title_font.setBold(True)
    title_font.setPixelSize(max(26, min(52, int(height * 0.22))))
    title_metrics = QFontMetrics(title_font)
    while title_metrics.horizontalAdvance(title_text) > text_width and title_font.pixelSize() > 22:
        title_font.setPixelSize(title_font.pixelSize() - 1)
        title_metrics = QFontMetrics(title_font)

    subtitle_font = QFont("Segoe UI")
    subtitle_font.setPixelSize(max(11, min(16, int(height * 0.06))))
    subtitle_metrics = QFontMetrics(subtitle_font)

    block_gap = 8
    block_height = title_metrics.height() + block_gap + subtitle_metrics.height()
    block_top = content_top + max(0, int((content_height - block_height) / 2))

    painter.setPen(QColor("#F8FBFF"))
    painter.setFont(title_font)
    painter.drawText(text_left, block_top + title_metrics.ascent(), title_text)

    painter.setPen(QColor(220, 232, 248, 238))
    painter.setFont(subtitle_font)
    subtitle_y = block_top + title_metrics.height() + block_gap + subtitle_metrics.ascent()
    painter.drawText(text_left, subtitle_y, subtitle_text)

    # Version above status-safe zone, bottom-left.
    version_font = QFont("Segoe UI")
    version_font.setPixelSize(10)
    painter.setFont(version_font)
    painter.setPen(QColor(214, 226, 244, 220))
    version_y = height - status_zone_height - 8
    painter.drawText(20, version_y, version_label())

    # Footer zone used by live splash status text.
    status_top = height - status_zone_height
    painter.fillRect(0, status_top, width, status_zone_height, QColor(6, 12, 24, 188))
    line_gradient = QLinearGradient(0, status_top, width, status_top)
    line_gradient.setColorAt(0.0, QColor("#68A8FF"))
    line_gradient.setColorAt(1.0, QColor("#9BC8FF"))
    painter.setPen(QPen(line_gradient, 1))
    painter.drawLine(0, status_top, width, status_top)

    painter.end()
    return pixmap


class StartupThread(QThread):
    update_signal = pyqtSignal(str)
    ready_signal = pyqtSignal(str, str, str)  # ffmpeg, ffprobe, source
    error_signal = pyqtSignal(str)

    def __init__(self, base_dir: Path):
        super().__init__()
        self.base_dir = base_dir

    def _emit_update(self, message: str) -> None:
        self.update_signal.emit(message)

    def run(self):
        try:
            ffmpeg_path, ffprobe_path, source = _ensure_ffmpeg_runtime(self.base_dir, self._emit_update)
            self.ready_signal.emit(ffmpeg_path, ffprobe_path, source)
        except Exception as e:
            self.error_signal.emit(str(e))


class FFmpegThread(QThread):
    update_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, str)  # percent 0-100, status text

    def __init__(self, command, duration_seconds: float = 0):
        super().__init__()
        self.command = command
        self.duration_seconds = duration_seconds
        self._time_re = re.compile(r"time=(\d+):(\d+):(\d+)\.?(\d*)")

    def run(self):
        try:
            process = subprocess.Popen(
                self.command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            stdout = process.stdout
            if stdout:
                for line in stdout:
                    standardized_line = line.replace("\r\n", "\n").replace("\r", "\n").strip()
                    self.update_signal.emit(standardized_line)
                    # Parse progress: time=HH:MM:SS.ms
                    if self.duration_seconds > 0:
                        match = self._time_re.search(standardized_line)
                        if match:
                            h, mm, s = int(match.group(1)), int(match.group(2)), int(match.group(3))
                            ms_str = match.group(4) or "0"
                            ms = int(ms_str) / (10 ** len(ms_str)) if ms_str else 0
                            current_sec = h * 3600 + mm * 60 + s + ms
                            percent = min(100, int(100 * current_sec / self.duration_seconds))
                            status = f"{percent}% - {match.group(0).replace('time=', '')}"
                            self.progress_signal.emit(percent, status)
            process.wait()
            self.update_signal.emit("Processing completed successfully.")
            self.progress_signal.emit(100, "Complete")
        except Exception as e:
            self.update_signal.emit(f"FFmpeg subprocess error: {e}")
            self.progress_signal.emit(0, str(e))


class MainWindow(QMainWindow):
    def __init__(self, parent=None, initial_theme_mode: str | None = None):
        super().__init__(parent)
        self.theme_mode = theme_stylesheet._normalize_mode(initial_theme_mode)
        self._is_loading_settings = False
        self.settings = QSettings("JMDigital", "JMD-VideoCompare-UI")
        self.ffmpeg_exe_path = str(_BASE_DIR / "bin" / "ffmpeg.exe")
        self.ffprobe_exe_path = str(_BASE_DIR / "bin" / "ffprobe.exe")
        self.font_cache = {}
        self._build_ui()
        self._connect_signals()
        self.populate_codec_comboboxes()
        self.populate_color_comboboxes()
        self._load_settings()
        self._apply_tooltips()
        self._update_theme_toggle_button()
        self._connect_persistence_signals()

    def _build_ui(self):
        self.setWindowTitle(window_title())
        self.resize(1000, 800)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(Tokens.SPACE_4)
        main_layout.setContentsMargins(Tokens.SPACE_6, Tokens.SPACE_6, Tokens.SPACE_6, Tokens.SPACE_6)

        # Header: title + logo
        header_layout = QHBoxLayout()
        self.labelTitle = SectionHeader("JMD Video Compare UI", level="h1")
        header_layout.addWidget(self.labelTitle)
        header_layout.addStretch()
        self.logoButton = ghost_button(parent=self)
        self.logoButton.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.logoButton.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        icon = QIcon()
        icon.addFile(str(_BASE_DIR / "images" / "JMDigital.png"), QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.logoButton.setIcon(icon)
        self.logoButton.setIconSize(QSize(160, 35))
        header_layout.addWidget(self.logoButton)
        self.themeToggleButton = ghost_button(parent=self)
        self.themeToggleButton.setProperty("role", "theme-toggle")
        self.themeToggleButton.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.themeToggleButton.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        header_layout.addWidget(self.themeToggleButton)
        main_layout.addLayout(header_layout)

        main_layout.addWidget(self._make_hline())

        # Video 1 | Video 2 two-column layout
        video_layout = QHBoxLayout()
        video_layout.setSpacing(Tokens.SPACE_6)
        video_layout.addLayout(self._build_video_section("Video 1 (left side)", is_video1=True))
        video_layout.addWidget(self._make_vline())
        video_layout.addLayout(self._build_video_section("Video 2 (right side)", is_video1=False))
        main_layout.addLayout(video_layout)

        main_layout.addWidget(self._make_hline())

        # Output options - compact layout
        output_group = SectionCard("Output Video Options")
        output_layout = QGridLayout()
        output_layout.setSpacing(Tokens.SPACE_2)
        output_layout.setContentsMargins(Tokens.SPACE_3, Tokens.SPACE_4, Tokens.SPACE_3, Tokens.SPACE_3)

        row = 0
        output_layout.addWidget(QLabel("Duration:"), row, 0)
        self.lineEditDuration = QLineEdit("00:01:30")
        self.lineEditDuration.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTrailing | Qt.AlignmentFlag.AlignVCenter)
        self.lineEditDuration.setMaximumWidth(90)
        output_layout.addWidget(self.lineEditDuration, row, 1)

        output_layout.addWidget(QLabel("Video Codec:"), row, 2)
        self.comboBoxVideoCodec = AnimatedComboBox()
        self.comboBoxVideoCodec.setMinimumWidth(100)
        output_layout.addWidget(self.comboBoxVideoCodec, row, 3)

        output_layout.addWidget(QLabel("Audio Codec:"), row, 4)
        self.comboBoxAudioCodec = AnimatedComboBox()
        self.comboBoxAudioCodec.setMinimumWidth(100)
        output_layout.addWidget(self.comboBoxAudioCodec, row, 5)

        output_layout.addWidget(QLabel("Bitrate:"), row, 6)
        self.lineEditBirate = QLineEdit("4000")
        self.lineEditBirate.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTrailing | Qt.AlignmentFlag.AlignVCenter)
        self.lineEditBirate.setMaximumWidth(70)
        output_layout.addWidget(self.lineEditBirate, row, 7)

        row += 1
        self.checkBoxOutputVideoDivider = QCheckBox("Vertical divider")
        self.checkBoxOutputVideoDivider.setChecked(True)
        output_layout.addWidget(self.checkBoxOutputVideoDivider, row, 0)

        output_layout.addWidget(QLabel("Width:"), row, 1)
        self.lineEditOutputVideoDividerWidth = QLineEdit("4")
        self.lineEditOutputVideoDividerWidth.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTrailing | Qt.AlignmentFlag.AlignVCenter)
        self.lineEditOutputVideoDividerWidth.setMaximumWidth(50)
        output_layout.addWidget(self.lineEditOutputVideoDividerWidth, row, 2)

        output_layout.addWidget(QLabel("Color:"), row, 3)
        self.comboBoxVideoDividerColor = AnimatedComboBox()
        self.comboBoxVideoDividerColor.setMinimumWidth(80)
        output_layout.addWidget(self.comboBoxVideoDividerColor, row, 4)

        self.checkBoxOutputAudioVideo1 = QCheckBox("Audio from Video 1")
        self.checkBoxOutputAudioVideo1.setChecked(True)
        output_layout.addWidget(self.checkBoxOutputAudioVideo1, row, 5)

        self.checkBoxOutputAudioVideo2 = QCheckBox("Audio from Video 2")
        output_layout.addWidget(self.checkBoxOutputAudioVideo2, row, 6)

        output_group.setLayout(output_layout)
        main_layout.addWidget(output_group)

        # Process button (primary CTA)
        self.pushButton = primary_button("Process", parent=self)
        self.pushButton.setMinimumHeight(44)
        main_layout.addWidget(self.pushButton)

        main_layout.addWidget(self._make_hline())

        # Output file
        file_layout = QHBoxLayout()
        file_layout.setSpacing(Tokens.SPACE_2)
        file_layout.addWidget(QLabel("Output Video File:"))
        self.lineEditOutputVideoFile = QLineEdit()
        self.lineEditOutputVideoFile.setMinimumHeight(28)
        file_layout.addWidget(self.lineEditOutputVideoFile)
        self.pushButtonOutputVideoBrowse = secondary_button("Browse", parent=self)
        file_layout.addWidget(self.pushButtonOutputVideoBrowse)
        file_layout.addWidget(QLabel("Video Type:"))
        self.comboBoxOutputVideoType = AnimatedComboBox()
        self.comboBoxOutputVideoType.addItems(["mkv", "mp4", "avi", "mov", "flv", "wmv", "webm"])
        file_layout.addWidget(self.comboBoxOutputVideoType)
        main_layout.addLayout(file_layout)

        # Log toggle button (opens/closes log dock)
        self.logToggleButton = secondary_button("Show Log", parent=self)
        self.logToggleButton.setCheckable(True)
        self.logToggleButton.setChecked(False)
        main_layout.addWidget(self.logToggleButton)

        self.setMenuBar(None)  # No menu bar
        self.statusbar = self.statusBar()

        # Progress bar in status bar
        self.progressBar = QProgressBar()
        self.progressBar.setMaximumWidth(200)
        self.progressBar.setVisible(False)
        self.statusbar.addPermanentWidget(self.progressBar)

        # Log dock (toggleable, separate window)
        self.logDock = QDockWidget("Log", self)
        self.logDock.setObjectName("LogDock")
        self.plainTextEditOutput = QPlainTextEdit()
        self.plainTextEditOutput.setMinimumHeight(150)
        self.logDock.setWidget(self.plainTextEditOutput)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.logDock)
        self.logDock.hide()
        self.logDock.visibilityChanged.connect(self._on_log_dock_visibility_changed)

    def _build_video_section(self, title: str, is_video1: bool):
        layout = QVBoxLayout()
        layout.setSpacing(Tokens.SPACE_2)
        layout.setContentsMargins(0, 0, 0, 0)

        header = SectionHeader(title, level="h2")
        layout.addWidget(header)

        path_layout = QHBoxLayout()
        path_layout.setSpacing(Tokens.SPACE_2)
        if is_video1:
            self.lineEditVideo1 = QLineEdit()
            path_layout.addWidget(self.lineEditVideo1)
            self.pushButtonVideo1Browse = secondary_button("Browse", parent=self)
            path_layout.addWidget(self.pushButtonVideo1Browse)
        else:
            self.lineEditVideo2 = QLineEdit()
            path_layout.addWidget(self.lineEditVideo2)
            self.pushButtonVideo2Browse = secondary_button("Browse", parent=self)
            path_layout.addWidget(self.pushButtonVideo2Browse)
        layout.addLayout(path_layout)

        if is_video1:
            self.checkBoxVideo1AddText = QCheckBox("Add Overlay Text")
            self.checkBoxVideo1AddText.setChecked(True)
            layout.addWidget(self.checkBoxVideo1AddText)
            font_row = QHBoxLayout()
            font_row.addWidget(QLabel("Font:"))
            self.fontComboBoxVideo1 = AnimatedFontComboBox()
            font_row.addWidget(self.fontComboBoxVideo1)
            font_row.addWidget(QLabel("Size:"))
            self.spinBoxVideo1FontSize = QSpinBox()
            self.spinBoxVideo1FontSize.setRange(8, 200)
            self.spinBoxVideo1FontSize.setValue(48)
            self.spinBoxVideo1FontSize.setMinimumWidth(70)
            font_row.addWidget(self.spinBoxVideo1FontSize)
            layout.addLayout(font_row)
            self.lineEditVideo1Text = QLineEdit("Original")
            layout.addWidget(self.lineEditVideo1Text)
            pos_row = QHBoxLayout()
            pos_row.addWidget(QLabel("Text position:"))
            self.checkBoxVideo1AddTextBottom = QCheckBox("Bottom")
            self.checkBoxVideo1AddTextBottom.setChecked(True)
            pos_row.addWidget(self.checkBoxVideo1AddTextBottom)
            self.checkBoxVideo1AddTextTop = QCheckBox("Top")
            pos_row.addWidget(self.checkBoxVideo1AddTextTop)
            self.checkBoxVideo1AddTextMiddle = QCheckBox("Middle")
            pos_row.addWidget(self.checkBoxVideo1AddTextMiddle)
            pos_row.addWidget(QLabel("Color:"))
            self.comboBoxVideo1AddTextColor = AnimatedComboBox()
            pos_row.addWidget(self.comboBoxVideo1AddTextColor)
            layout.addLayout(pos_row)
            layout.addWidget(QLabel("Start Time (HH:MM:SS)"))
            self.lineEditStartTimeVideo1 = QLineEdit("00:00:00")
            self.lineEditStartTimeVideo1.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTrailing | Qt.AlignmentFlag.AlignVCenter)
            layout.addWidget(self.lineEditStartTimeVideo1)
        else:
            self.checkBoxVideo2AddText = QCheckBox("Add Overlay Text")
            self.checkBoxVideo2AddText.setChecked(True)
            layout.addWidget(self.checkBoxVideo2AddText)
            font_row = QHBoxLayout()
            font_row.addWidget(QLabel("Font:"))
            self.fontComboBoxVideo2 = AnimatedFontComboBox()
            font_row.addWidget(self.fontComboBoxVideo2)
            font_row.addWidget(QLabel("Size:"))
            self.spinBoxVideo2FontSize = QSpinBox()
            self.spinBoxVideo2FontSize.setRange(8, 200)
            self.spinBoxVideo2FontSize.setValue(48)
            self.spinBoxVideo2FontSize.setMinimumWidth(70)
            font_row.addWidget(self.spinBoxVideo2FontSize)
            layout.addLayout(font_row)
            self.lineEditVideo2Text = QLineEdit("New")
            layout.addWidget(self.lineEditVideo2Text)
            pos_row = QHBoxLayout()
            pos_row.addWidget(QLabel("Text position:"))
            self.checkBoxVideo2AddTextBottom = QCheckBox("Bottom")
            self.checkBoxVideo2AddTextBottom.setChecked(True)
            pos_row.addWidget(self.checkBoxVideo2AddTextBottom)
            self.checkBoxVideo2AddTextTop = QCheckBox("Top")
            pos_row.addWidget(self.checkBoxVideo2AddTextTop)
            self.checkBoxVideo2AddTextMiddle = QCheckBox("Middle")
            pos_row.addWidget(self.checkBoxVideo2AddTextMiddle)
            pos_row.addWidget(QLabel("Color:"))
            self.comboBoxVideo2AddTextColor = AnimatedComboBox()
            pos_row.addWidget(self.comboBoxVideo2AddTextColor)
            layout.addLayout(pos_row)
            layout.addWidget(QLabel("Start Time (HH:MM:SS)"))
            self.lineEditStartTimeVideo2 = QLineEdit("00:00:00")
            self.lineEditStartTimeVideo2.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTrailing | Qt.AlignmentFlag.AlignVCenter)
            layout.addWidget(self.lineEditStartTimeVideo2)

        return layout

    def _make_hline(self):
        line = QFrame()
        line.setProperty("role", "divider-h")
        line.setFrameShape(QFrame.Shape.NoFrame)
        line.setFixedHeight(3)
        return line

    def _make_vline(self):
        line = QFrame()
        line.setProperty("role", "divider-v")
        line.setFrameShape(QFrame.Shape.NoFrame)
        line.setFixedWidth(3)
        return line

    def _toggle_log_visibility(self, checked):
        if checked:
            self.logDock.show()
            self.logToggleButton.setChecked(True)
            self.logToggleButton.setText("Hide Log")
        else:
            self.logDock.hide()
            self.logToggleButton.setChecked(False)
            self.logToggleButton.setText("Show Log")

    def _on_log_dock_visibility_changed(self, visible):
        self.logToggleButton.blockSignals(True)
        self.logToggleButton.setChecked(visible)
        self.logToggleButton.setText("Hide Log" if visible else "Show Log")
        self.logToggleButton.blockSignals(False)

    def _connect_signals(self):
        self.logoButton.clicked.connect(self.open_url)
        self.themeToggleButton.clicked.connect(self.toggle_theme_mode)
        self.logToggleButton.toggled.connect(lambda c: self._toggle_log_visibility(c))
        self.pushButton.clicked.connect(self.process_videos)
        self.pushButtonVideo1Browse.clicked.connect(self.browse_video1)
        self.pushButtonVideo2Browse.clicked.connect(self.browse_video2)
        self.pushButtonOutputVideoBrowse.clicked.connect(self.browse_output_video)
        self.checkBoxOutputAudioVideo1.clicked.connect(self.update_audio_source)
        self.checkBoxOutputAudioVideo2.clicked.connect(self.update_audio_source)
        self.checkBoxVideo1AddTextBottom.clicked.connect(self.update_text_position_video1)
        self.checkBoxVideo1AddTextTop.clicked.connect(self.update_text_position_video1)
        self.checkBoxVideo1AddTextMiddle.clicked.connect(self.update_text_position_video1)
        self.checkBoxVideo2AddTextBottom.clicked.connect(self.update_text_position_video2)
        self.checkBoxVideo2AddTextTop.clicked.connect(self.update_text_position_video2)
        self.checkBoxVideo2AddTextMiddle.clicked.connect(self.update_text_position_video2)

    def _connect_persistence_signals(self) -> None:
        self.lineEditVideo1.textChanged.connect(self._save_settings)
        self.lineEditVideo2.textChanged.connect(self._save_settings)
        self.lineEditOutputVideoFile.textChanged.connect(self._save_settings)
        self.lineEditVideo1Text.textChanged.connect(self._save_settings)
        self.lineEditVideo2Text.textChanged.connect(self._save_settings)
        self.lineEditStartTimeVideo1.textChanged.connect(self._save_settings)
        self.lineEditStartTimeVideo2.textChanged.connect(self._save_settings)
        self.lineEditDuration.textChanged.connect(self._save_settings)
        self.lineEditBirate.textChanged.connect(self._save_settings)
        self.lineEditOutputVideoDividerWidth.textChanged.connect(self._save_settings)

        self.comboBoxVideoCodec.currentTextChanged.connect(self._save_settings)
        self.comboBoxAudioCodec.currentTextChanged.connect(self._save_settings)
        self.comboBoxVideoDividerColor.currentTextChanged.connect(self._save_settings)
        self.comboBoxOutputVideoType.currentTextChanged.connect(self._save_settings)
        self.comboBoxVideo1AddTextColor.currentTextChanged.connect(self._save_settings)
        self.comboBoxVideo2AddTextColor.currentTextChanged.connect(self._save_settings)
        self.fontComboBoxVideo1.currentFontChanged.connect(lambda _: self._save_settings())
        self.fontComboBoxVideo2.currentFontChanged.connect(lambda _: self._save_settings())
        self.spinBoxVideo1FontSize.valueChanged.connect(self._save_settings)
        self.spinBoxVideo2FontSize.valueChanged.connect(self._save_settings)

        self.checkBoxVideo1AddText.toggled.connect(self._save_settings)
        self.checkBoxVideo2AddText.toggled.connect(self._save_settings)
        self.checkBoxVideo1AddTextTop.toggled.connect(self._save_settings)
        self.checkBoxVideo1AddTextMiddle.toggled.connect(self._save_settings)
        self.checkBoxVideo1AddTextBottom.toggled.connect(self._save_settings)
        self.checkBoxVideo2AddTextTop.toggled.connect(self._save_settings)
        self.checkBoxVideo2AddTextMiddle.toggled.connect(self._save_settings)
        self.checkBoxVideo2AddTextBottom.toggled.connect(self._save_settings)
        self.checkBoxOutputVideoDivider.toggled.connect(self._save_settings)
        self.checkBoxOutputAudioVideo1.toggled.connect(self._save_settings)
        self.checkBoxOutputAudioVideo2.toggled.connect(self._save_settings)
        self.logDock.visibilityChanged.connect(lambda _: self._save_settings())

    def _text_position_value_video1(self) -> str:
        if self.checkBoxVideo1AddTextTop.isChecked():
            return "top"
        if self.checkBoxVideo1AddTextMiddle.isChecked():
            return "middle"
        return "bottom"

    def _text_position_value_video2(self) -> str:
        if self.checkBoxVideo2AddTextTop.isChecked():
            return "top"
        if self.checkBoxVideo2AddTextMiddle.isChecked():
            return "middle"
        return "bottom"

    def _set_text_position_video1(self, value: str) -> None:
        value = (value or "bottom").lower()
        self.checkBoxVideo1AddTextTop.setChecked(value == "top")
        self.checkBoxVideo1AddTextMiddle.setChecked(value == "middle")
        self.checkBoxVideo1AddTextBottom.setChecked(value not in ("top", "middle"))

    def _set_text_position_video2(self, value: str) -> None:
        value = (value or "bottom").lower()
        self.checkBoxVideo2AddTextTop.setChecked(value == "top")
        self.checkBoxVideo2AddTextMiddle.setChecked(value == "middle")
        self.checkBoxVideo2AddTextBottom.setChecked(value not in ("top", "middle"))

    def _update_browse_dir_from_path(self, path_str: str, setting_key: str) -> None:
        path_str = (path_str or "").strip().strip('"')
        if not path_str:
            return
        path = Path(path_str)
        folder = path if path.is_dir() else path.parent
        if folder.exists():
            self.settings.setValue(setting_key, str(folder))

    def _save_settings(self) -> None:
        if self._is_loading_settings:
            return

        s = self.settings
        s.setValue("video1/path", self.lineEditVideo1.text())
        s.setValue("video2/path", self.lineEditVideo2.text())
        s.setValue("video1/add_text", self.checkBoxVideo1AddText.isChecked())
        s.setValue("video2/add_text", self.checkBoxVideo2AddText.isChecked())
        s.setValue("video1/font_family", self.fontComboBoxVideo1.currentFont().family())
        s.setValue("video2/font_family", self.fontComboBoxVideo2.currentFont().family())
        s.setValue("video1/font_size", self.spinBoxVideo1FontSize.value())
        s.setValue("video2/font_size", self.spinBoxVideo2FontSize.value())
        s.setValue("video1/text", self.lineEditVideo1Text.text())
        s.setValue("video2/text", self.lineEditVideo2Text.text())
        s.setValue("video1/text_color", self.comboBoxVideo1AddTextColor.currentText())
        s.setValue("video2/text_color", self.comboBoxVideo2AddTextColor.currentText())
        s.setValue("video1/start_time", self.lineEditStartTimeVideo1.text())
        s.setValue("video2/start_time", self.lineEditStartTimeVideo2.text())
        s.setValue("video1/text_position", self._text_position_value_video1())
        s.setValue("video2/text_position", self._text_position_value_video2())

        s.setValue("output/duration", self.lineEditDuration.text())
        s.setValue("output/video_codec", self.comboBoxVideoCodec.currentText())
        s.setValue("output/audio_codec", self.comboBoxAudioCodec.currentText())
        s.setValue("output/bitrate", self.lineEditBirate.text())
        s.setValue("output/divider_enabled", self.checkBoxOutputVideoDivider.isChecked())
        s.setValue("output/divider_width", self.lineEditOutputVideoDividerWidth.text())
        s.setValue("output/divider_color", self.comboBoxVideoDividerColor.currentText())
        s.setValue("output/container", self.comboBoxOutputVideoType.currentText())
        s.setValue("output/file", self.lineEditOutputVideoFile.text())
        s.setValue("output/audio_video1", self.checkBoxOutputAudioVideo1.isChecked())
        s.setValue("output/audio_video2", self.checkBoxOutputAudioVideo2.isChecked())

        s.setValue("ui/log_visible", self.logDock.isVisible())

        self._update_browse_dir_from_path(self.lineEditVideo1.text(), "browse/video1_dir")
        self._update_browse_dir_from_path(self.lineEditVideo2.text(), "browse/video2_dir")
        self._update_browse_dir_from_path(self.lineEditOutputVideoFile.text(), "browse/output_dir")

    def _load_settings(self) -> None:
        s = self.settings
        self._is_loading_settings = True
        try:
            self.lineEditVideo1.setText(s.value("video1/path", self.lineEditVideo1.text(), type=str))
            self.lineEditVideo2.setText(s.value("video2/path", self.lineEditVideo2.text(), type=str))
            self.checkBoxVideo1AddText.setChecked(s.value("video1/add_text", self.checkBoxVideo1AddText.isChecked(), type=bool))
            self.checkBoxVideo2AddText.setChecked(s.value("video2/add_text", self.checkBoxVideo2AddText.isChecked(), type=bool))

            self.fontComboBoxVideo1.setCurrentFont(QFont(s.value("video1/font_family", self.fontComboBoxVideo1.currentFont().family(), type=str)))
            self.fontComboBoxVideo2.setCurrentFont(QFont(s.value("video2/font_family", self.fontComboBoxVideo2.currentFont().family(), type=str)))
            self.spinBoxVideo1FontSize.setValue(s.value("video1/font_size", self.spinBoxVideo1FontSize.value(), type=int))
            self.spinBoxVideo2FontSize.setValue(s.value("video2/font_size", self.spinBoxVideo2FontSize.value(), type=int))

            self.lineEditVideo1Text.setText(s.value("video1/text", self.lineEditVideo1Text.text(), type=str))
            self.lineEditVideo2Text.setText(s.value("video2/text", self.lineEditVideo2Text.text(), type=str))
            self.lineEditStartTimeVideo1.setText(s.value("video1/start_time", self.lineEditStartTimeVideo1.text(), type=str))
            self.lineEditStartTimeVideo2.setText(s.value("video2/start_time", self.lineEditStartTimeVideo2.text(), type=str))
            self._set_text_position_video1(s.value("video1/text_position", self._text_position_value_video1(), type=str))
            self._set_text_position_video2(s.value("video2/text_position", self._text_position_value_video2(), type=str))

            self.lineEditDuration.setText(s.value("output/duration", self.lineEditDuration.text(), type=str))
            self.lineEditBirate.setText(s.value("output/bitrate", self.lineEditBirate.text(), type=str))
            self.lineEditOutputVideoDividerWidth.setText(s.value("output/divider_width", self.lineEditOutputVideoDividerWidth.text(), type=str))
            self.checkBoxOutputVideoDivider.setChecked(s.value("output/divider_enabled", self.checkBoxOutputVideoDivider.isChecked(), type=bool))
            self.checkBoxOutputAudioVideo1.setChecked(s.value("output/audio_video1", self.checkBoxOutputAudioVideo1.isChecked(), type=bool))
            self.checkBoxOutputAudioVideo2.setChecked(s.value("output/audio_video2", self.checkBoxOutputAudioVideo2.isChecked(), type=bool))
            self.lineEditOutputVideoFile.setText(s.value("output/file", self.lineEditOutputVideoFile.text(), type=str))

            self.comboBoxVideoCodec.setCurrentText(s.value("output/video_codec", self.comboBoxVideoCodec.currentText(), type=str))
            self.comboBoxAudioCodec.setCurrentText(s.value("output/audio_codec", self.comboBoxAudioCodec.currentText(), type=str))
            self.comboBoxVideoDividerColor.setCurrentText(s.value("output/divider_color", self.comboBoxVideoDividerColor.currentText(), type=str))
            self.comboBoxVideo1AddTextColor.setCurrentText(s.value("video1/text_color", self.comboBoxVideo1AddTextColor.currentText(), type=str))
            self.comboBoxVideo2AddTextColor.setCurrentText(s.value("video2/text_color", self.comboBoxVideo2AddTextColor.currentText(), type=str))
            self.comboBoxOutputVideoType.setCurrentText(s.value("output/container", self.comboBoxOutputVideoType.currentText(), type=str))

            log_visible = s.value("ui/log_visible", False, type=bool)
            self._toggle_log_visibility(log_visible)
        finally:
            self._is_loading_settings = False

        self._save_settings()

    def _dialog_start_path(self, current_value: str, browse_key: str) -> str:
        current_value = (current_value or "").strip().strip('"')
        if current_value:
            path = Path(current_value)
            if path.exists():
                return str(path)
            if path.parent.exists():
                return str(path)

        last_dir = self.settings.value(browse_key, "", type=str)
        if last_dir and Path(last_dir).exists():
            return last_dir
        return str(Path.home())

    def _set_tooltip(self, widget, text: str) -> None:
        widget.setToolTip(text)
        widget.setStatusTip(text)

    def _apply_tooltips(self) -> None:
        # Header/actions
        self._set_tooltip(self.logoButton, "Open the JMD website.")
        self._set_tooltip(self.themeToggleButton, "Switch between light and dark mode.")
        self._set_tooltip(self.pushButton, "Start building the side-by-side comparison video.")
        self._set_tooltip(self.logToggleButton, "Show or hide the processing log panel.")

        # Video 1 inputs
        self._set_tooltip(self.lineEditVideo1, "Path to the first source video.")
        self._set_tooltip(self.pushButtonVideo1Browse, "Browse for the first source video.")
        self._set_tooltip(self.checkBoxVideo1AddText, "Enable a text label on Video 1.")
        self._set_tooltip(self.fontComboBoxVideo1, "Choose the font for the Video 1 label.")
        self._set_tooltip(self.spinBoxVideo1FontSize, "Font size for the Video 1 label.")
        self._set_tooltip(self.lineEditVideo1Text, "Text shown on top of Video 1.")
        self._set_tooltip(self.checkBoxVideo1AddTextTop, "Place Video 1 label near the top.")
        self._set_tooltip(self.checkBoxVideo1AddTextMiddle, "Place Video 1 label in the middle.")
        self._set_tooltip(self.checkBoxVideo1AddTextBottom, "Place Video 1 label near the bottom.")
        self._set_tooltip(self.comboBoxVideo1AddTextColor, "Color of the Video 1 label text.")
        self._set_tooltip(self.lineEditStartTimeVideo1, "Start time in Video 1 (HH:MM:SS).")

        # Video 2 inputs
        self._set_tooltip(self.lineEditVideo2, "Path to the second source video.")
        self._set_tooltip(self.pushButtonVideo2Browse, "Browse for the second source video.")
        self._set_tooltip(self.checkBoxVideo2AddText, "Enable a text label on Video 2.")
        self._set_tooltip(self.fontComboBoxVideo2, "Choose the font for the Video 2 label.")
        self._set_tooltip(self.spinBoxVideo2FontSize, "Font size for the Video 2 label.")
        self._set_tooltip(self.lineEditVideo2Text, "Text shown on top of Video 2.")
        self._set_tooltip(self.checkBoxVideo2AddTextTop, "Place Video 2 label near the top.")
        self._set_tooltip(self.checkBoxVideo2AddTextMiddle, "Place Video 2 label in the middle.")
        self._set_tooltip(self.checkBoxVideo2AddTextBottom, "Place Video 2 label near the bottom.")
        self._set_tooltip(self.comboBoxVideo2AddTextColor, "Color of the Video 2 label text.")
        self._set_tooltip(self.lineEditStartTimeVideo2, "Start time in Video 2 (HH:MM:SS).")

        # Output options
        self._set_tooltip(self.lineEditDuration, "Output duration (HH:MM:SS).")
        self._set_tooltip(self.comboBoxVideoCodec, "Video codec used for encoding.")
        self._set_tooltip(self.comboBoxAudioCodec, "Audio codec used for encoding.")
        self._set_tooltip(self.lineEditBirate, "Target video bitrate in kbps.")
        self._set_tooltip(self.checkBoxOutputVideoDivider, "Add a vertical divider between videos.")
        self._set_tooltip(self.lineEditOutputVideoDividerWidth, "Divider width in pixels.")
        self._set_tooltip(self.comboBoxVideoDividerColor, "Divider color.")
        self._set_tooltip(self.checkBoxOutputAudioVideo1, "Use audio track from Video 1.")
        self._set_tooltip(self.checkBoxOutputAudioVideo2, "Use audio track from Video 2.")

        # Output file and log
        self._set_tooltip(self.lineEditOutputVideoFile, "Output file path and base name.")
        self._set_tooltip(self.pushButtonOutputVideoBrowse, "Choose where to save the output video.")
        self._set_tooltip(self.comboBoxOutputVideoType, "Container format for the output file.")
        self._set_tooltip(self.logDock, "Processing output and FFmpeg command log.")
        self._set_tooltip(self.plainTextEditOutput, "Live processing output from FFmpeg.")
        self._set_tooltip(self.progressBar, "Current encode progress.")

    def _update_theme_toggle_button(self) -> None:
        is_dark = self.theme_mode == theme_stylesheet.THEME_DARK
        glyph = "\uf185" if is_dark else "\uf186"  # sun / moon
        action = "Switch to light mode." if is_dark else "Switch to dark mode."

        font = QFont(theme_stylesheet.FONT_AWESOME_SOLID_FAMILY or "Font Awesome 6 Pro Solid")
        font.setPixelSize(16)
        self.themeToggleButton.setFont(font)
        self.themeToggleButton.setText(glyph)
        self.themeToggleButton.setToolTip(action)
        self.themeToggleButton.setStatusTip(action)

    def _apply_current_theme(self) -> None:
        app = QApplication.instance()
        if app is None:
            return
        self.theme_mode = apply_theme(app, _BASE_DIR, self.theme_mode)
        self._update_theme_toggle_button()

    def _clear_initial_focus(self) -> None:
        focused = self.focusWidget()
        if focused:
            focused.clearFocus()
        central = self.centralWidget()
        if central:
            central.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            central.setFocus(Qt.FocusReason.OtherFocusReason)

    def toggle_theme_mode(self) -> None:
        if self.theme_mode == theme_stylesheet.THEME_DARK:
            self.theme_mode = theme_stylesheet.THEME_LIGHT
        else:
            self.theme_mode = theme_stylesheet.THEME_DARK
        self._apply_current_theme()

    def _set_ffmpeg_runtime(self, ffmpeg_path: str, ffprobe_path: str) -> None:
        self.ffmpeg_exe_path = ffmpeg_path
        self.ffprobe_exe_path = ffprobe_path

    def _show_splash_message(self, message: str) -> None:
        self.splash.showMessage(
            message,
            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter,
            QColor("#DCE9FF"),
        )

    def _start_font_scan(self) -> None:
        fonts_dir = os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts')
        self.font_scanner = FontScanner(fonts_dir)
        self.font_scanner.update_signal.connect(self._show_splash_message)
        self.font_scanner.finished.connect(self.on_font_scanning_finished)
        self.font_scanner.start()

    def _on_startup_ready(self, ffmpeg_path: str, ffprobe_path: str, source: str) -> None:
        self._set_ffmpeg_runtime(ffmpeg_path, ffprobe_path)
        self._show_splash_message(f"FFmpeg ready ({source}).")
        self._start_font_scan()

    def _on_startup_error(self, error_text: str) -> None:
        logging.error(f"FFmpeg startup setup failed: {error_text}")
        self._show_splash_message("FFmpeg setup failed, continuing startup...")
        self._start_font_scan()

    def start_font_scanning(self, splash):
        self.splash = splash
        self.startup_thread = StartupThread(_BASE_DIR)
        self.startup_thread.update_signal.connect(self._show_splash_message)
        self.startup_thread.ready_signal.connect(self._on_startup_ready)
        self.startup_thread.error_signal.connect(self._on_startup_error)
        self.startup_thread.start()

    def on_font_scanning_finished(self):
        self.font_cache = self.font_scanner.get_font_cache()
        self.splash.finish(self)
        self.show()
        QTimer.singleShot(0, self._clear_initial_focus)

    def open_url(self):
        QDesktopServices.openUrl(QUrl("https://jmd.vc"))

    def populate_codec_comboboxes(self):
        self.comboBoxVideoCodec.addItems(['libx264', 'libx265', 'mpeg4', 'vp9', 'av1'])
        self.comboBoxAudioCodec.addItems(['aac', 'libmp3lame', 'opus', 'vorbis', 'flac'])

    def populate_color_comboboxes(self):
        colors = ['white', 'black', 'red', 'green', 'blue', 'yellow', 'purple', 'cyan', 'grey']
        self.comboBoxVideoDividerColor.addItems(colors)
        self.comboBoxVideo1AddTextColor.addItems(colors)
        self.comboBoxVideo2AddTextColor.addItems(colors)

    def update_audio_source(self):
        sender = self.sender()
        if sender == self.checkBoxOutputAudioVideo1 and sender.isChecked():
            self.checkBoxOutputAudioVideo2.setChecked(False)
        elif sender == self.checkBoxOutputAudioVideo2 and sender.isChecked():
            self.checkBoxOutputAudioVideo1.setChecked(False)

    def update_text_position_video1(self):
        sender = self.sender()
        if sender.isChecked():
            self.checkBoxVideo1AddTextBottom.setChecked(sender == self.checkBoxVideo1AddTextBottom)
            self.checkBoxVideo1AddTextTop.setChecked(sender == self.checkBoxVideo1AddTextTop)
            self.checkBoxVideo1AddTextMiddle.setChecked(sender == self.checkBoxVideo1AddTextMiddle)

    def update_text_position_video2(self):
        sender = self.sender()
        if sender.isChecked():
            self.checkBoxVideo2AddTextBottom.setChecked(sender == self.checkBoxVideo2AddTextBottom)
            self.checkBoxVideo2AddTextTop.setChecked(sender == self.checkBoxVideo2AddTextTop)
            self.checkBoxVideo2AddTextMiddle.setChecked(sender == self.checkBoxVideo2AddTextMiddle)

    def browse_video1(self):
        start_path = self._dialog_start_path(self.lineEditVideo1.text(), "browse/video1_dir")
        file_name, _ = QFileDialog.getOpenFileName(self, "Select Video 1", start_path)
        if file_name:
            self.lineEditVideo1.setText(file_name)
            self._update_browse_dir_from_path(file_name, "browse/video1_dir")

    def browse_video2(self):
        start_path = self._dialog_start_path(self.lineEditVideo2.text(), "browse/video2_dir")
        file_name, _ = QFileDialog.getOpenFileName(self, "Select Video 2", start_path)
        if file_name:
            self.lineEditVideo2.setText(file_name)
            self._update_browse_dir_from_path(file_name, "browse/video2_dir")

    def browse_output_video(self):
        start_path = self._dialog_start_path(self.lineEditOutputVideoFile.text(), "browse/output_dir")
        file_name, _ = QFileDialog.getSaveFileName(self, "Select Output Video File", start_path)
        if file_name:
            self.lineEditOutputVideoFile.setText(file_name)
            self._update_browse_dir_from_path(file_name, "browse/output_dir")

    def validate_time_format(self, time_str):
        return re.match(r"\d{2}:\d{2}:\d{2}", time_str) is not None

    def get_resolution(self, video_path):
        cmd = [self.ffprobe_exe_path, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=s=x:p=0", video_path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logging.error(f"ffprobe error: {result.stderr}")
            return (0, 0)
        match = re.match(r'(\d+)x(\d+)', result.stdout)
        return match.groups() if match else (0, 0)

    def get_font_path(self, font_family):
        if not font_family:
            return ""

        # Exact lookup.
        if font_family in self.font_cache:
            return self.font_cache[font_family]

        # Common cleanup for style suffixes.
        stripped = _strip_style_words(font_family)
        if stripped in self.font_cache:
            return self.font_cache[stripped]

        # Case-insensitive fallbacks.
        target = font_family.lower()
        for family, path in self.font_cache.items():
            if family.lower() == target:
                return path
        for family, path in self.font_cache.items():
            if family.lower().startswith(target):
                return path

        # Stable fallback for Windows.
        fallback = Path(os.environ.get("WINDIR", "C:\\Windows")) / "Fonts" / "arial.ttf"
        if fallback.exists():
            return str(fallback)
        return ""

    def convert_font_path(self, font_path):
        return font_path.replace('\\', '/').replace(':', '\\:')

    def get_frame_rate(self, video_path, override_framerate=None):
        if override_framerate:
            try:
                return str(float(override_framerate))
            except ValueError:
                pass
        cmd = [self.ffprobe_exe_path, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate", "-of", "default=noprint_wrappers=1:nokey=1", video_path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logging.error(f"ffprobe error: {result.stderr}")
            return "25"
        try:
            num, den = result.stdout.strip().split('/')
            return str(int(num) / int(den))
        except Exception as e:
            logging.error(f"Error calculating frame rate: {e}")
            return "25"

    def process_videos(self):
        if not _validate_ffmpeg_pair(Path(self.ffmpeg_exe_path), Path(self.ffprobe_exe_path)):
            QMessageBox.critical(
                self,
                "FFmpeg Missing",
                "FFmpeg/FFprobe are not available. Restart the app with an internet connection or install FFmpeg on your system PATH.",
            )
            return

        video1_path = self.lineEditVideo1.text()
        video2_path = self.lineEditVideo2.text()
        start_time_video1 = self.lineEditStartTimeVideo1.text()
        start_time_video2 = self.lineEditStartTimeVideo2.text()
        duration = self.lineEditDuration.text()
        video_codec = self.comboBoxVideoCodec.currentText()
        audio_codec = self.comboBoxAudioCodec.currentText()
        bitrate = self.lineEditBirate.text()
        divider_width = self.lineEditOutputVideoDividerWidth.text()
        divider_color = self.comboBoxVideoDividerColor.currentText()
        output_file = self.lineEditOutputVideoFile.text()
        output_file_extension = self.comboBoxOutputVideoType.currentText()
        use_audio_from_video1 = self.checkBoxOutputAudioVideo1.isChecked()
        use_audio_from_video2 = self.checkBoxOutputAudioVideo2.isChecked()

        res1 = self.get_resolution(video1_path)
        res2 = self.get_resolution(video2_path)

        if res1 == (0, 0) or res2 == (0, 0):
            QMessageBox.critical(self, "Error", "Failed to obtain video resolutions. Check input file paths.")
            return

        half_width1 = int(res1[0]) // 2
        half_width2 = int(res2[0]) // 2
        if half_width1 % 2 != 0:
            half_width1 -= 1
        if half_width2 % 2 != 0:
            half_width2 -= 1

        font_video1 = self.fontComboBoxVideo1.currentFont().family()
        font_path_video1_raw = self.get_font_path(font_video1)
        font_path_video1 = self.convert_font_path(font_path_video1_raw)

        font_video2 = self.fontComboBoxVideo2.currentFont().family()
        font_path_video2_raw = self.get_font_path(font_video2)
        font_path_video2 = self.convert_font_path(font_path_video2_raw)

        text_video1 = self.lineEditVideo1Text.text()
        text_video2 = self.lineEditVideo2Text.text()
        font_size_video1 = self.spinBoxVideo1FontSize.value()
        font_size_video2 = self.spinBoxVideo2FontSize.value()
        color_video1 = self.comboBoxVideo1AddTextColor.currentText()
        color_video2 = self.comboBoxVideo2AddTextColor.currentText()

        text_position_video1 = "(h-text_h)/2"
        if self.checkBoxVideo1AddTextTop.isChecked():
            text_position_video1 = "10"
        elif self.checkBoxVideo1AddTextBottom.isChecked():
            text_position_video1 = "h-text_h-10"

        text_position_video2 = "(h-text_h)/2"
        if self.checkBoxVideo2AddTextTop.isChecked():
            text_position_video2 = "10"
        elif self.checkBoxVideo2AddTextBottom.isChecked():
            text_position_video2 = "h-text_h-10"

        crop_scale_left = f"crop=iw/2:ih:0:0,scale=-2:{int(res2[1])}"
        crop_right = f"crop={int(res2[0])/2}:{int(res2[1])}:{int(res2[0])/2}:0"
        filter_complex = f"[0:v]{crop_scale_left}[left];[1:v]{crop_right}[right];"

        if self.checkBoxVideo1AddText.isChecked():
            filter_complex += f"[left]drawtext=text='{text_video1}':fontfile='{font_path_video1}':fontsize={font_size_video1}:fontcolor={color_video1}:x=(w-text_w)/2:y={text_position_video1}[left];"
        if self.checkBoxVideo2AddText.isChecked():
            filter_complex += f"[right]drawtext=text='{text_video2}':fontfile='{font_path_video2}':fontsize={font_size_video2}:fontcolor={color_video2}:x=(w-text_w)/2:y={text_position_video2}[right];"

        if self.checkBoxOutputVideoDivider.isChecked():
            divider_layout = f"|w0+{divider_width}_0"
        else:
            divider_layout = "|w0_0"
        filter_complex += f"[left][right]xstack=inputs=2:layout=0_0{divider_layout}:fill={divider_color}[v]"

        if not output_file.endswith(f".{output_file_extension}"):
            output_file = f"{output_file}.{output_file_extension}"

        cmd = [
            self.ffmpeg_exe_path,
            "-ss", str(start_time_video1),
            "-i", str(video1_path),
            "-ss", str(start_time_video2),
            "-i", str(video2_path),
            "-filter_complex", filter_complex,
            "-map", "[v]",
            "-t", str(duration),
            "-c:v", str(video_codec),
            "-b:v", str(bitrate) + "k",
            str(output_file)
        ]
        if use_audio_from_video1:
            cmd.extend(["-map", "0:a", "-c:a", audio_codec])
        elif use_audio_from_video2:
            cmd.extend(["-map", "1:a", "-c:a", audio_codec])

        self.append_to_output("FFmpeg command:\n" + " ".join(cmd))

        # Parse duration for progress (HH:MM:SS -> seconds)
        duration_seconds = _parse_time_to_seconds(duration)

        try:
            self.ffmpeg_thread = FFmpegThread(cmd, duration_seconds)
            self.ffmpeg_thread.update_signal.connect(self.append_to_output)
            self.ffmpeg_thread.progress_signal.connect(self._on_ffmpeg_progress)
            self.ffmpeg_thread.finished.connect(self._on_ffmpeg_finished)
            self.progressBar.setVisible(True)
            self.progressBar.setValue(0)
            self.statusbar.showMessage("Processing...")
            self.ffmpeg_thread.start()
        except Exception as e:
            logging.error(f"Error in process_videos: {e}")
            QMessageBox.critical(self, "Error", f"An unexpected error occurred: {e}")

    def _on_ffmpeg_progress(self, percent: int, status: str):
        self.progressBar.setValue(percent)
        self.statusbar.showMessage(status)

    def _on_ffmpeg_finished(self):
        self.progressBar.setValue(100)
        self.statusbar.showMessage("Processing complete.")
        # Keep progress bar visible briefly, then hide
        def _hide_progress():
            self.progressBar.setVisible(False)
            self.statusbar.showMessage("Ready")
        QTimer.singleShot(2000, _hide_progress)

    def append_to_output(self, text):
        QApplication.processEvents()
        self.plainTextEditOutput.appendPlainText(text)
        self.plainTextEditOutput.moveCursor(QTextCursor.MoveOperation.End)
        self.plainTextEditOutput.ensureCursorVisible()


def run_gui(argv: list[str] | None = None) -> int:
    app = QApplication(argv if argv is not None else sys.argv)
    initial_theme_mode = _detect_system_theme_mode(app)
    apply_theme(app, _BASE_DIR, initial_theme_mode)

    splash_pix = _build_splash_pixmap(_BASE_DIR)
    splash = QSplashScreen(splash_pix)
    splash.show()
    app.processEvents()

    main_window = MainWindow(initial_theme_mode=initial_theme_mode)
    main_window.start_font_scanning(splash)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run_gui())
