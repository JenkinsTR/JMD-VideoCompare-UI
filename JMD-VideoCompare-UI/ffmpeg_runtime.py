"""
FFmpeg runtime discovery/download helpers.
Pure stdlib module so CLI mode can run headless without importing Qt.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable

FFMPEG_DOWNLOAD_URLS = [
    "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
    "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip",
]

UpdateCallback = Callable[[str], None]


def default_cache_root() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if base:
        root = Path(base) / "JMDigital" / "JMD-VideoCompare-UI" / "ffmpeg-runtime"
    else:
        root = Path.home() / ".jmd-video-compare-ui" / "ffmpeg-runtime"
    root.mkdir(parents=True, exist_ok=True)
    return root


def validate_exe(exe_path: Path) -> bool:
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


def validate_ffmpeg_pair(ffmpeg_path: Path, ffprobe_path: Path) -> bool:
    return validate_exe(ffmpeg_path) and validate_exe(ffprobe_path)


def find_ffmpeg_pair_in_tree(root: Path) -> tuple[Path | None, Path | None]:
    if not root.exists():
        return None, None
    for ffmpeg_path in root.rglob("ffmpeg.exe"):
        ffprobe_path = ffmpeg_path.with_name("ffprobe.exe")
        if ffprobe_path.exists() and validate_ffmpeg_pair(ffmpeg_path, ffprobe_path):
            return ffmpeg_path, ffprobe_path
    return None, None


def resolve_system_ffmpeg_pair() -> tuple[Path | None, Path | None]:
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
    if validate_ffmpeg_pair(ffmpeg, ffprobe):
        return ffmpeg, ffprobe
    return None, None


def _download_archive(target_path: Path, update_cb: UpdateCallback) -> None:
    last_error: Exception | None = None
    for url in FFMPEG_DOWNLOAD_URLS:
        host = urllib.parse.urlparse(url).netloc
        try:
            update_cb(f"Downloading FFmpeg from {host}...")
            req = urllib.request.Request(url, headers={"User-Agent": "JMD-VideoCompare-UI"})
            with urllib.request.urlopen(req, timeout=45) as response, open(target_path, "wb") as out_file:
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
        except Exception as exc:
            last_error = exc
            update_cb(f"Download failed from {host}, trying fallback...")
    raise RuntimeError(f"Failed to download FFmpeg: {last_error}")


def _safe_extract_zip(zip_path: Path, output_dir: Path) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir, ignore_errors=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zf:
        out_root = output_dir.resolve()
        for member in zf.infolist():
            target = (output_dir / member.filename).resolve()
            if not str(target).startswith(str(out_root)):
                raise RuntimeError("Unsafe archive path detected while extracting FFmpeg.")
        zf.extractall(output_dir)


def _noop(_: str) -> None:
    pass


def ensure_ffmpeg_runtime(
    base_dir: Path,
    update_cb: UpdateCallback | None = None,
    *,
    force_download: bool = False,
    cache_root: Path | None = None,
) -> tuple[str, str, str]:
    """
    Resolve ffmpeg/ffprobe paths and source:
    - "system": from PATH
    - "bundled": from base_dir/bin
    - "cached": from previous download cache
    - "downloaded": freshly downloaded
    """
    cb = update_cb or _noop
    root = cache_root or default_cache_root()

    if not force_download:
        cb("Checking system FFmpeg installation...")
        system_ffmpeg, system_ffprobe = resolve_system_ffmpeg_pair()
        if system_ffmpeg and system_ffprobe:
            return str(system_ffmpeg), str(system_ffprobe), "system"

        cb("Checking bundled FFmpeg runtime...")
        bundled_ffmpeg = base_dir / "bin" / "ffmpeg.exe"
        bundled_ffprobe = base_dir / "bin" / "ffprobe.exe"
        if validate_ffmpeg_pair(bundled_ffmpeg, bundled_ffprobe):
            return str(bundled_ffmpeg), str(bundled_ffprobe), "bundled"

        cb("Checking cached FFmpeg runtime...")
        cached_root = root / "current"
        cached_ffmpeg, cached_ffprobe = find_ffmpeg_pair_in_tree(cached_root)
        if cached_ffmpeg and cached_ffprobe:
            return str(cached_ffmpeg), str(cached_ffprobe), "cached"

    cb("FFmpeg not found. Starting first-run download...")
    archive_path = root / "ffmpeg-runtime.zip"
    extract_tmp = root / "extract-tmp"
    install_root = root / "current"

    _download_archive(archive_path, cb)
    cb("Extracting FFmpeg...")
    _safe_extract_zip(archive_path, extract_tmp)

    extracted_ffmpeg, extracted_ffprobe = find_ffmpeg_pair_in_tree(extract_tmp)
    if not extracted_ffmpeg or not extracted_ffprobe:
        raise RuntimeError("Downloaded archive does not contain ffmpeg.exe and ffprobe.exe.")

    if install_root.exists():
        shutil.rmtree(install_root, ignore_errors=True)
    install_root.mkdir(parents=True, exist_ok=True)

    source_dir = extracted_ffmpeg.parent
    target_dir = install_root / "bin"
    shutil.copytree(source_dir, target_dir, dirs_exist_ok=True)

    final_ffmpeg = target_dir / "ffmpeg.exe"
    final_ffprobe = target_dir / "ffprobe.exe"
    if not validate_ffmpeg_pair(final_ffmpeg, final_ffprobe):
        raise RuntimeError("FFmpeg validation failed after extraction.")

    shutil.rmtree(extract_tmp, ignore_errors=True)
    try:
        archive_path.unlink(missing_ok=True)
    except Exception:
        pass

    cb("FFmpeg setup complete.")
    return str(final_ffmpeg), str(final_ffprobe), "downloaded"
