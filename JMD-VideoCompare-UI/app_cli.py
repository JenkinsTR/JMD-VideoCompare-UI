"""
Headless CLI mode for JMD Video Compare UI.
No Qt imports in this module.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from app_info import APP_CLI_NAME, APP_NAME, cli_banner, version_label
from ffmpeg_runtime import ensure_ffmpeg_runtime, validate_ffmpeg_pair

_COLOR_CHOICES = ["white", "black", "red", "green", "blue", "yellow", "purple", "cyan", "grey"]
_VIDEO_CODEC_CHOICES = ["libx264", "libx265", "mpeg4", "vp9", "av1"]
_AUDIO_CODEC_CHOICES = ["aac", "libmp3lame", "opus", "vorbis", "flac"]
_OUTPUT_TYPE_CHOICES = ["mkv", "mp4", "avi", "mov", "flv", "wmv", "webm"]
_POSITION_CHOICES = ["top", "middle", "bottom"]

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


def _strip_style_words(font_name: str) -> str:
    words = font_name.strip().split()
    while words and words[-1].lower() in _FONT_STYLE_WORDS:
        words.pop()
    return " ".join(words) if words else font_name.strip()


def _parse_time_to_seconds(time_str: str) -> float:
    m = re.match(r"(\d+):(\d+):(\d+)(?:\.(\d+))?", time_str.strip())
    if not m:
        return 0.0
    h, mm, s = int(m.group(1)), int(m.group(2)), int(m.group(3))
    ms = int(m.group(4)) if m.group(4) else 0
    return h * 3600 + mm * 60 + s + ms / 100.0


def _print_update(message: str) -> None:
    print(message)


def _probe_resolution(ffprobe_path: str, video_path: str) -> tuple[int, int]:
    cmd = [
        ffprobe_path,
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height",
        "-of",
        "csv=s=x:p=0",
        video_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed for {video_path}: {result.stderr.strip()}")
    match = re.match(r"(\d+)x(\d+)", result.stdout.strip())
    if not match:
        raise RuntimeError(f"Unable to parse resolution for {video_path}: {result.stdout.strip()}")
    return int(match.group(1)), int(match.group(2))


def _escape_drawtext_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("'", "\\'")


def _convert_font_path_for_ffmpeg(font_path: str) -> str:
    return font_path.replace("\\", "/").replace(":", "\\:")


def _scan_windows_fonts_registry() -> dict[str, str]:
    if os.name != "nt":
        return {}
    try:
        import winreg  # type: ignore
    except Exception:
        return {}

    fonts: dict[str, str] = {}
    key_path = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"
    fonts_dir = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"

    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
        idx = 0
        while True:
            try:
                display_name, font_value, _ = winreg.EnumValue(key, idx)
                idx += 1
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

            fonts.setdefault(clean_name, str(font_path))
            fonts.setdefault(_strip_style_words(clean_name), str(font_path))

    return fonts


def _resolve_font_path(explicit_path: str | None, family: str, font_cache: dict[str, str]) -> str:
    if explicit_path:
        path = Path(explicit_path)
        if path.exists():
            return str(path)
        raise RuntimeError(f"Font file not found: {explicit_path}")

    family = (family or "").strip()
    if family in font_cache:
        return font_cache[family]

    stripped = _strip_style_words(family)
    if stripped in font_cache:
        return font_cache[stripped]

    target = family.lower()
    for cached_family, cached_path in font_cache.items():
        if cached_family.lower() == target:
            return cached_path
    for cached_family, cached_path in font_cache.items():
        if cached_family.lower().startswith(target):
            return cached_path

    fallback = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "arial.ttf"
    if fallback.exists():
        return str(fallback)
    raise RuntimeError(f"Unable to resolve font family '{family}'.")


@dataclass
class CliProcessOptions:
    video1: str
    video2: str
    output: str
    output_type: str
    start1: str
    start2: str
    duration: str
    video_codec: str
    audio_codec: str
    bitrate_k: int
    divider: bool
    divider_width: int
    divider_color: str
    audio_source: str
    text1_enable: bool
    text2_enable: bool
    text1: str
    text2: str
    text1_font_family: str
    text2_font_family: str
    text1_font_file: str | None
    text2_font_file: str | None
    text1_font_size: int
    text2_font_size: int
    text1_color: str
    text2_color: str
    text1_position: str
    text2_position: str
    dry_run: bool
    ffmpeg_path: str | None
    ffprobe_path: str | None
    force_download_ffmpeg: bool


def _position_expr(position: str) -> str:
    if position == "top":
        return "10"
    if position == "bottom":
        return "h-text_h-10"
    return "(h-text_h)/2"


def _build_ffmpeg_command(
    opts: CliProcessOptions,
    ffmpeg_path: str,
    ffprobe_path: str,
    font_cache: dict[str, str],
) -> list[str]:
    if not Path(opts.video1).exists():
        raise RuntimeError(f"Video 1 not found: {opts.video1}")
    if not Path(opts.video2).exists():
        raise RuntimeError(f"Video 2 not found: {opts.video2}")

    res1_w, res1_h = _probe_resolution(ffprobe_path, opts.video1)
    res2_w, res2_h = _probe_resolution(ffprobe_path, opts.video2)
    if res1_w <= 0 or res2_w <= 0:
        raise RuntimeError("Failed to obtain valid input video resolutions.")

    half_width2 = res2_w // 2
    if half_width2 % 2 != 0:
        half_width2 -= 1

    font1 = _resolve_font_path(opts.text1_font_file, opts.text1_font_family, font_cache)
    font2 = _resolve_font_path(opts.text2_font_file, opts.text2_font_family, font_cache)
    font1 = _convert_font_path_for_ffmpeg(font1)
    font2 = _convert_font_path_for_ffmpeg(font2)

    crop_scale_left = f"crop=iw/2:ih:0:0,scale=-2:{res2_h}"
    crop_right = f"crop={half_width2}:{res2_h}:{half_width2}:0"
    filter_complex = f"[0:v]{crop_scale_left}[left];[1:v]{crop_right}[right];"

    if opts.text1_enable:
        text1 = _escape_drawtext_text(opts.text1)
        filter_complex += (
            f"[left]drawtext=text='{text1}':fontfile='{font1}':fontsize={opts.text1_font_size}:"
            f"fontcolor={opts.text1_color}:x=(w-text_w)/2:y={_position_expr(opts.text1_position)}[left];"
        )
    if opts.text2_enable:
        text2 = _escape_drawtext_text(opts.text2)
        filter_complex += (
            f"[right]drawtext=text='{text2}':fontfile='{font2}':fontsize={opts.text2_font_size}:"
            f"fontcolor={opts.text2_color}:x=(w-text_w)/2:y={_position_expr(opts.text2_position)}[right];"
        )

    divider_layout = f"|w0+{opts.divider_width}_0" if opts.divider else "|w0_0"
    filter_complex += f"[left][right]xstack=inputs=2:layout=0_0{divider_layout}:fill={opts.divider_color}[v]"

    output_file = opts.output
    if not output_file.lower().endswith(f".{opts.output_type.lower()}"):
        output_file = f"{output_file}.{opts.output_type}"

    cmd = [
        ffmpeg_path,
        "-ss",
        opts.start1,
        "-i",
        opts.video1,
        "-ss",
        opts.start2,
        "-i",
        opts.video2,
        "-filter_complex",
        filter_complex,
        "-map",
        "[v]",
        "-t",
        opts.duration,
        "-c:v",
        opts.video_codec,
        "-b:v",
        f"{opts.bitrate_k}k",
    ]

    if opts.audio_source == "video1":
        cmd.extend(["-map", "0:a", "-c:a", opts.audio_codec])
    elif opts.audio_source == "video2":
        cmd.extend(["-map", "1:a", "-c:a", opts.audio_codec])

    cmd.append(output_file)
    return cmd


def _run_ffmpeg_command(cmd: list[str], duration: str) -> int:
    duration_seconds = _parse_time_to_seconds(duration)
    time_re = re.compile(r"time=(\d+):(\d+):(\d+)\.?(\d*)")

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert process.stdout is not None

    for line in process.stdout:
        standardized = line.replace("\r\n", "\n").replace("\r", "\n").rstrip()
        if standardized:
            print(standardized)
        if duration_seconds > 0:
            m = time_re.search(standardized)
            if m:
                h, mm, s = int(m.group(1)), int(m.group(2)), int(m.group(3))
                ms_str = m.group(4) or "0"
                ms = int(ms_str) / (10 ** len(ms_str)) if ms_str else 0
                current = h * 3600 + mm * 60 + s + ms
                percent = min(100, int(100 * current / duration_seconds))
                print(f"[progress] {percent}%")

    process.wait()
    return int(process.returncode or 0)


def _run_process_command(args: argparse.Namespace, base_dir: Path) -> int:
    opts = CliProcessOptions(
        video1=args.video1,
        video2=args.video2,
        output=args.output,
        output_type=args.output_type,
        start1=args.start1,
        start2=args.start2,
        duration=args.duration,
        video_codec=args.video_codec,
        audio_codec=args.audio_codec,
        bitrate_k=int(args.bitrate),
        divider=bool(args.divider),
        divider_width=int(args.divider_width),
        divider_color=args.divider_color,
        audio_source=args.audio_source,
        text1_enable=bool(args.text1_enable),
        text2_enable=bool(args.text2_enable),
        text1=args.text1,
        text2=args.text2,
        text1_font_family=args.text1_font_family,
        text2_font_family=args.text2_font_family,
        text1_font_file=args.text1_font_file,
        text2_font_file=args.text2_font_file,
        text1_font_size=int(args.text1_font_size),
        text2_font_size=int(args.text2_font_size),
        text1_color=args.text1_color,
        text2_color=args.text2_color,
        text1_position=args.text1_position,
        text2_position=args.text2_position,
        dry_run=bool(args.dry_run),
        ffmpeg_path=args.ffmpeg_path,
        ffprobe_path=args.ffprobe_path,
        force_download_ffmpeg=bool(args.force_download_ffmpeg),
    )

    if opts.ffmpeg_path and not opts.ffprobe_path:
        sibling = Path(opts.ffmpeg_path).with_name("ffprobe.exe")
        if sibling.exists():
            opts.ffprobe_path = str(sibling)
    if opts.ffprobe_path and not opts.ffmpeg_path:
        sibling = Path(opts.ffprobe_path).with_name("ffmpeg.exe")
        if sibling.exists():
            opts.ffmpeg_path = str(sibling)

    if opts.ffmpeg_path and opts.ffprobe_path:
        ffmpeg_path, ffprobe_path, source = opts.ffmpeg_path, opts.ffprobe_path, "manual"
    else:
        ffmpeg_path, ffprobe_path, source = ensure_ffmpeg_runtime(
            base_dir,
            _print_update,
            force_download=opts.force_download_ffmpeg,
        )

    if not validate_ffmpeg_pair(Path(ffmpeg_path), Path(ffprobe_path)):
        raise RuntimeError("Resolved FFmpeg/FFprobe runtime failed validation.")

    print(f"Using FFmpeg source: {source}")
    print(f"ffmpeg:  {ffmpeg_path}")
    print(f"ffprobe: {ffprobe_path}")

    font_cache = _scan_windows_fonts_registry()
    cmd = _build_ffmpeg_command(opts, ffmpeg_path, ffprobe_path, font_cache)
    print("FFmpeg command:")
    print(" ".join(cmd))
    if opts.dry_run:
        return 0

    return _run_ffmpeg_command(cmd, opts.duration)


def _run_ffmpeg_test_command(args: argparse.Namespace, base_dir: Path) -> int:
    ffmpeg_path, ffprobe_path, source = ensure_ffmpeg_runtime(
        base_dir,
        _print_update,
        force_download=bool(args.force_download),
    )
    print(f"Resolved source: {source}")
    print(f"ffmpeg:  {ffmpeg_path}")
    print(f"ffprobe: {ffprobe_path}")
    if not validate_ffmpeg_pair(Path(ffmpeg_path), Path(ffprobe_path)):
        print("Validation failed.", file=sys.stderr)
        return 2
    print("FFmpeg runtime validation successful.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=APP_CLI_NAME,
        description=f"Headless CLI for {APP_NAME}. {version_label()}",
    )
    parser.add_argument("-V", "--version", action="version", version=cli_banner())
    sub = parser.add_subparsers(dest="command", required=True)

    p_test = sub.add_parser("ffmpeg-test", help="Test FFmpeg detection/download.")
    p_test.add_argument(
        "--force-download",
        action="store_true",
        help="Force a fresh FFmpeg download even if system/cached runtime exists.",
    )

    p_proc = sub.add_parser("process", help="Run video compare processing headless.")
    p_proc.add_argument("--video1", required=True, help="Path to Video 1 input file.")
    p_proc.add_argument("--video2", required=True, help="Path to Video 2 input file.")
    p_proc.add_argument("--output", required=True, help="Output file path without extension or with extension.")
    p_proc.add_argument("--output-type", default="mkv", choices=_OUTPUT_TYPE_CHOICES)
    p_proc.add_argument("--start1", default="00:00:00", help="Video 1 start time HH:MM:SS.")
    p_proc.add_argument("--start2", default="00:00:00", help="Video 2 start time HH:MM:SS.")
    p_proc.add_argument("--duration", default="00:01:30", help="Output duration HH:MM:SS.")
    p_proc.add_argument("--video-codec", default="libx264", choices=_VIDEO_CODEC_CHOICES)
    p_proc.add_argument("--audio-codec", default="aac", choices=_AUDIO_CODEC_CHOICES)
    p_proc.add_argument("--bitrate", type=int, default=4000, help="Video bitrate in kbps.")
    p_proc.add_argument("--divider", action=argparse.BooleanOptionalAction, default=True, help="Enable vertical divider.")
    p_proc.add_argument("--divider-width", type=int, default=4)
    p_proc.add_argument("--divider-color", default="white", choices=_COLOR_CHOICES)
    p_proc.add_argument(
        "--audio-source",
        default="video1",
        choices=["video1", "video2", "none"],
        help="Audio source mapping in output.",
    )

    p_proc.add_argument("--text1-enable", action=argparse.BooleanOptionalAction, default=True)
    p_proc.add_argument("--text2-enable", action=argparse.BooleanOptionalAction, default=True)
    p_proc.add_argument("--text1", default="Original")
    p_proc.add_argument("--text2", default="New")
    p_proc.add_argument("--text1-font-family", default="Arial")
    p_proc.add_argument("--text2-font-family", default="Arial")
    p_proc.add_argument("--text1-font-file", default=None, help="Optional explicit font file for Video 1 label.")
    p_proc.add_argument("--text2-font-file", default=None, help="Optional explicit font file for Video 2 label.")
    p_proc.add_argument("--text1-font-size", type=int, default=48)
    p_proc.add_argument("--text2-font-size", type=int, default=48)
    p_proc.add_argument("--text1-color", default="white", choices=_COLOR_CHOICES)
    p_proc.add_argument("--text2-color", default="white", choices=_COLOR_CHOICES)
    p_proc.add_argument("--text1-position", default="bottom", choices=_POSITION_CHOICES)
    p_proc.add_argument("--text2-position", default="bottom", choices=_POSITION_CHOICES)

    p_proc.add_argument("--ffmpeg-path", default=None, help="Optional explicit ffmpeg.exe path.")
    p_proc.add_argument("--ffprobe-path", default=None, help="Optional explicit ffprobe.exe path.")
    p_proc.add_argument(
        "--force-download-ffmpeg",
        action="store_true",
        help="Force FFmpeg download before processing.",
    )
    p_proc.add_argument("--dry-run", action="store_true", help="Print command and exit.")
    return parser


def run_from_argv(argv: list[str], *, base_dir: Path) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    print(cli_banner())

    try:
        if args.command == "ffmpeg-test":
            return _run_ffmpeg_test_command(args, base_dir)
        if args.command == "process":
            return _run_process_command(args, base_dir)
        parser.error(f"Unknown command: {args.command}")
        return 2
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
