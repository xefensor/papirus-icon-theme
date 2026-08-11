#!/usr/bin/env python3
"""Build a Papirus variant that does not rely on symbolic/theme colors.

KDE Plasma can explicitly prefer ``*-symbolic`` icons. Merely deleting those
files is not sufficient because icon-theme inheritance can fall back to another
symbolic icon. Instead, this generator keeps every icon name Plasma may request
but makes the resulting artwork independent of the desktop color scheme.

For every SVG that uses ``currentColor``, ``context-fill`` or ``context-stroke``:

1. Reuse a same-named fixed-color Papirus icon when one exists.
2. Otherwise preserve the original symbolic shape and bake in a deterministic
   Papirus-style color. Semantic ColorScheme classes such as NegativeText,
   PositiveText and NeutralText keep useful red/green/orange meanings.

The generated theme is self-contained and inherits only hicolor, so it cannot
silently fall back to Breeze symbolic artwork for missing names.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


KNOWN_CONTEXTS = {
    "actions",
    "animations",
    "apps",
    "categories",
    "devices",
    "emblems",
    "emotes",
    "mimetypes",
    "panel",
    "places",
    "status",
}

IMAGE_SUFFIXES = {".svg", ".png", ".xpm"}
DYNAMIC_COLOR_MARKERS = ("currentcolor", "context-fill", "context-stroke")

# Colors already common in Papirus and Material-style Linux icon themes. The
# fallback choice is deterministic per icon name, so an icon keeps the same
# color across sizes and regenerated builds.
PALETTE = (
    "#3999e6",  # blue
    "#00bcd4",  # cyan
    "#4caf50",  # green
    "#ff9800",  # orange
    "#9c27b0",  # purple
    "#009688",  # teal
    "#e91e63",  # pink
    "#3f51b5",  # indigo
    "#8bc34a",  # light green
    "#ffc107",  # amber
)

SEMANTIC_COLORS = {
    "negative": "#f44336",
    "positive": "#4caf50",
    "neutral": "#ff9800",
    "highlight": "#3999e6",
}


@dataclass(frozen=True)
class BuildStats:
    symbolic_files: int
    dynamic_before: int
    reused_fixed: int
    synthesized: int
    dynamic_remaining: int


def is_symbolic_part(part: str) -> bool:
    return part == "symbolic" or part.startswith("symbolic-")


def is_symbolic_path(path: Path, root: Path) -> bool:
    rel = path.relative_to(root)
    return (
        "-symbolic" in path.stem
        or ".symbolic" in path.name
        or any(is_symbolic_part(part) for part in rel.parts[:-1])
    )


def uses_dynamic_theme_color(path: Path) -> bool:
    """Return True if an SVG still asks the renderer for a theme color."""
    if path.suffix.lower() != ".svg":
        return False

    try:
        lowered = path.read_text(encoding="utf-8", errors="ignore").lower()
    except OSError:
        return True

    return any(marker in lowered for marker in DYNAMIC_COLOR_MARKERS)


def normalized_stem(path: Path) -> str:
    stem = path.stem
    stem = stem.replace(".symbolic", "")
    stem = re.sub(r"-symbolic$", "", stem)
    return stem.lower()


def size_key(path: Path, root: Path) -> tuple[int, int]:
    """Return logical size and scale, e.g. 22x22 -> (22, 1)."""
    for part in path.relative_to(root).parts:
        match = re.fullmatch(r"(\d+)x(\d+)(?:@(\d+)x)?", part)
        if match and match.group(1) == match.group(2):
            return int(match.group(1)), int(match.group(3) or 1)
    return 0, 1


def context_key(path: Path, root: Path) -> str | None:
    for part in reversed(path.relative_to(root).parts[:-1]):
        if part in KNOWN_CONTEXTS:
            return part
    return None


def candidate_score(target: Path, candidate: Path, root: Path) -> int:
    score = 0

    target_size, target_scale = size_key(target, root)
    candidate_size, candidate_scale = size_key(candidate, root)
    target_context = context_key(target, root)
    candidate_context = context_key(candidate, root)

    if target_context and target_context == candidate_context:
        score += 10_000
    elif {target_context, candidate_context} <= {"panel", "status"}:
        # KDE/Papirus often place equivalent tray artwork in either directory.
        score += 8_000

    if target_size and candidate_size:
        if target_size == candidate_size:
            score += 5_000
        else:
            score -= abs(target_size - candidate_size) * 20

    if target_scale == candidate_scale:
        score += 500

    if candidate.suffix.lower() == ".svg":
        score += 300

    if not any("@" in part for part in candidate.relative_to(root).parts):
        score += 20

    return score


def base_color_for_stem(stem: str) -> str:
    """Choose a stable, meaningful color for symbolic-only artwork."""
    lowered = stem.lower()

    battery = re.search(r"battery-level-(\d+)", lowered)
    if battery:
        level = int(battery.group(1))
        if level <= 20:
            return "#f44336"
        if level <= 50:
            return "#ff9800"
        return "#4caf50"

    hints: tuple[tuple[tuple[str, ...], str], ...] = (
        (("error", "fail", "critical", "denied", "broken"), "#f44336"),
        (("warning", "caution"), "#ff9800"),
        (("battery", "charging", "power"), "#4caf50"),
        (("network", "wireless", "wifi", "bluetooth"), "#3999e6"),
        (("audio", "volume", "headphone", "microphone", "speaker"), "#00bcd4"),
        (("brightness", "sun", "daytime"), "#ffc107"),
        (("camera", "video", "photo", "image"), "#9c27b0"),
        (("keyboard", "caps", "num-lock", "scroll-lock"), "#9c27b0"),
        (("drive", "disk", "storage", "usb", "removable"), "#009688"),
        (("lock", "auth", "security", "shield", "key"), "#ff9800"),
        (("clock", "alarm", "time", "timer"), "#ff9800"),
        (("success", "positive", "connected", "uptodate"), "#4caf50"),
    )
    for words, color in hints:
        if any(word in lowered for word in words):
            return color

    digest = hashlib.sha256(lowered.encode("utf-8")).digest()
    return PALETTE[digest[0] % len(PALETTE)]


def color_for_tag(tag: str, fallback: str) -> str:
    """Preserve KDE semantic color classes while fixing ordinary Text colors."""
    class_match = re.search(r"\bclass\s*=\s*([\"'])(.*?)\1", tag, flags=re.I | re.S)
    if not class_match:
        return fallback

    classes = class_match.group(2).lower()
    if "negative" in classes:
        return SEMANTIC_COLORS["negative"]
    if "positive" in classes:
        return SEMANTIC_COLORS["positive"]
    if "neutral" in classes:
        return SEMANTIC_COLORS["neutral"]
    if "highlight" in classes:
        return SEMANTIC_COLORS["highlight"]
    return fallback


def synthesize_fixed_color_svg(path: Path) -> None:
    """Bake fixed colors into a dynamic SVG without changing its geometry."""
    text = path.read_text(encoding="utf-8", errors="replace")
    fallback = base_color_for_stem(normalized_stem(path))

    # First replace dynamic colors tag-by-tag so ColorScheme semantic classes
    # can retain red/green/orange/blue meaning where Papirus supplied it.
    def replace_tag(match: re.Match[str]) -> str:
        tag = match.group(0)
        lowered = tag.lower()
        if not any(marker in lowered for marker in DYNAMIC_COLOR_MARKERS):
            return tag
        color = color_for_tag(tag, fallback)
        tag = re.sub(r"currentColor", color, tag, flags=re.I)
        tag = re.sub(r"context-fill", color, tag, flags=re.I)
        tag = re.sub(r"context-stroke", color, tag, flags=re.I)
        return tag

    text = re.sub(r"<[^>]+>", replace_tag, text, flags=re.S)

    # Catch dynamic references inside CSS text rather than element attributes.
    # These cannot be reliably associated with one semantic class without a CSS
    # parser, so use the icon's stable fallback color.
    text = re.sub(r"currentColor", fallback, text, flags=re.I)
    text = re.sub(r"context-fill", fallback, text, flags=re.I)
    text = re.sub(r"context-stroke", fallback, text, flags=re.I)

    path.write_text(text, encoding="utf-8")


def rewrite_index_theme(index_path: Path, display_name: str) -> None:
    text = index_path.read_text(encoding="utf-8", errors="replace")
    text = re.sub(r"(?m)^Name=.*$", f"Name={display_name}", text, count=1)
    text = re.sub(
        r"(?m)^Comment=.*$",
        "Comment=Papirus with fixed colorful artwork instead of symbolic theme colors",
        text,
        count=1,
    )

    if re.search(r"(?m)^Inherits=", text):
        text = re.sub(r"(?m)^Inherits=.*$", "Inherits=hicolor", text, count=1)
    else:
        text = text.replace("[Icon Theme]\n", "[Icon Theme]\nInherits=hicolor\n", 1)

    index_path.write_text(text, encoding="utf-8")


def build_theme(source: Path, destination: Path, display_name: str) -> BuildStats:
    if not (source / "index.theme").is_file():
        raise FileNotFoundError(f"Not an icon theme: {source}")

    if source.resolve() == destination.resolve():
        raise ValueError("Source and destination must be different")

    if destination.exists():
        shutil.rmtree(destination)

    destination.parent.mkdir(parents=True, exist_ok=True)

    # Papirus-Dark contains relative symlinks into the sibling Papirus theme.
    # Dereference them to make the generated theme fully self-contained.
    shutil.copytree(source, destination, symlinks=False)
    rewrite_index_theme(destination / "index.theme", display_name)

    image_files = [
        path
        for path in destination.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    ]
    symbolic_files = [path for path in image_files if is_symbolic_path(path, destination)]
    dynamic_files = [path for path in image_files if uses_dynamic_theme_color(path)]

    # Snapshot fixed-color candidates before changing anything. Fixed symbolic
    # artwork is allowed as a source too: what matters is that its pixels/vector
    # fills are already independent of the desktop color scheme.
    fixed_color_by_stem: dict[str, list[Path]] = defaultdict(list)
    for path in image_files:
        if not uses_dynamic_theme_color(path):
            fixed_color_by_stem[normalized_stem(path)].append(path)

    reused_fixed = 0
    synthesized = 0

    for target in dynamic_files:
        candidates = fixed_color_by_stem.get(normalized_stem(target), [])
        if candidates:
            source_icon = max(
                candidates,
                key=lambda candidate: candidate_score(target, candidate, destination),
            )
            target.unlink()
            shutil.copy2(source_icon, target)
            reused_fixed += 1
        else:
            synthesize_fixed_color_svg(target)
            synthesized += 1

    remaining = [
        path
        for path in destination.rglob("*.svg")
        if path.is_file() and uses_dynamic_theme_color(path)
    ]
    if remaining:
        report = destination / "dynamic-color-icons.txt"
        report.write_text(
            "\n".join(str(path.relative_to(destination)) for path in remaining) + "\n",
            encoding="utf-8",
        )
        raise RuntimeError(
            f"generated theme still contains {len(remaining)} dynamic-color SVGs; "
            f"see {report}"
        )

    return BuildStats(
        symbolic_files=len(symbolic_files),
        dynamic_before=len(dynamic_files),
        reused_fixed=reused_fixed,
        synthesized=synthesized,
        dynamic_remaining=0,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        default="Papirus-Dark",
        help="source theme directory (default: Papirus-Dark)",
    )
    parser.add_argument(
        "--output-root",
        default=str(Path.home() / ".local/share/icons"),
        help="directory in which to create the generated theme",
    )
    parser.add_argument(
        "--name",
        help="generated directory name (default: <source>-Colorful)",
    )
    parser.add_argument(
        "--display-name",
        help="name shown by desktop settings (default: <source> Colorful)",
    )
    args = parser.parse_args()

    source = Path(args.source).expanduser().resolve()
    output_root = Path(args.output_root).expanduser().resolve()
    theme_name = args.name or f"{source.name}-Colorful"
    display_name = args.display_name or f"{source.name} Colorful"
    destination = output_root / theme_name

    try:
        stats = build_theme(source, destination, display_name)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"Created:           {destination}")
    print(f"Symbolic files:    {stats.symbolic_files}")
    print(f"Dynamic before:    {stats.dynamic_before}")
    print(f"Reused fixed art:  {stats.reused_fixed}")
    print(f"Colorized fallback:{stats.synthesized:>5}")
    print(f"Dynamic remaining: {stats.dynamic_remaining}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
