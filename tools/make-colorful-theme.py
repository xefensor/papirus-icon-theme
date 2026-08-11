#!/usr/bin/env python3
"""Build Papirus variants without theme-driven monochrome artwork.

The generator follows two rules, in this order:

1. If the selected Papirus variant already contains fixed-color artwork with the
   same semantic icon name, copy that artwork exactly. Because Papirus,
   Papirus-Dark and Papirus-Light are generated separately, a light/dark-specific
   colored variant is automatically preferred for its matching theme.
2. If no fixed-color counterpart exists, keep the original SVG geometry and bake
   Papirus' own semantic color palette into the dynamic ``currentColor`` /
   ``context-fill`` / ``context-stroke`` artwork. Existing ColorScheme semantic
   classes (positive, negative, warning, highlight) are respected. Plain
   ColorScheme-Text UI icons are assigned a semantic color from their icon name.

This applies to every dynamic SVG, not only files named ``*-symbolic``. That is
important for KDE action/menu icons such as system-suspend, system-reboot and
window-pin, which are normal icon names but still use currentColor.

Papirus-Dark and Papirus-Light contain relative symlinks into sibling themes.
The output dereferences those links so each generated user theme is standalone.
"""

from __future__ import annotations

import argparse
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
PALETTE_KEYS = ("Text", "Highlight", "NeutralText", "PositiveText", "NegativeText")

# Match Papirus' embedded KDE color-scheme fallback declarations, e.g.
# .ColorScheme-NegativeText { color:#f44336; }
PALETTE_RE = re.compile(
    r"\.ColorScheme-(Text|Highlight|NeutralText|PositiveText|NegativeText)\s*"
    r"\{[^}]*?color\s*:\s*(#[0-9a-fA-F]{6,8})",
    re.IGNORECASE | re.DOTALL,
)

START_TAG_RE = re.compile(
    r"<(?![!?/])(?P<tag>[A-Za-z_][\w:.-]*)(?P<attrs>[^<>]*)>",
    re.DOTALL,
)
CLASS_ATTR_RE = re.compile(r"\bclass\s*=\s*([\"'])(?P<value>.*?)\1", re.DOTALL)


@dataclass(frozen=True)
class Replacement:
    """One generated target replaced with existing fixed-color Papirus artwork."""

    target: str
    source: str


@dataclass(frozen=True)
class BuildStats:
    theme: str
    symbolic_files: int
    dynamic_before: int
    reused_existing_color: int
    recolored_semantic: int
    dynamic_remaining: int
    replacements: tuple[Replacement, ...]
    recolored: tuple[str, ...]
    palette: tuple[tuple[str, str], ...]


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
    """Return True if an SVG asks the desktop theme to provide visible color."""
    if path.suffix.lower() != ".svg":
        return False

    try:
        lowered = path.read_text(encoding="utf-8", errors="ignore").lower()
    except OSError:
        return True

    return any(marker in lowered for marker in DYNAMIC_COLOR_MARKERS)


def normalized_stem(path: Path) -> str:
    """Normalize the symbolic suffix while preserving the semantic icon name."""
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
    """Prefer the closest fixed-color artwork from the selected theme variant."""
    score = 0

    target_size, target_scale = size_key(target, root)
    candidate_size, candidate_scale = size_key(candidate, root)
    target_context = context_key(target, root)
    candidate_context = context_key(candidate, root)

    if target_context and target_context == candidate_context:
        score += 10_000
    elif {target_context, candidate_context} <= {"panel", "status"}:
        score += 8_000

    if target_size and candidate_size:
        if target_size == candidate_size:
            score += 5_000
        else:
            score -= abs(target_size - candidate_size) * 20

    if target_scale == candidate_scale:
        score += 500

    # Prefer matching symbolic/non-symbolic style when both options exist.
    if is_symbolic_path(target, root) == is_symbolic_path(candidate, root):
        score += 400

    if candidate.suffix.lower() == ".svg":
        score += 300

    if not any("@" in part for part in candidate.relative_to(root).parts):
        score += 20

    return score


def extract_palette(text: str) -> dict[str, str]:
    """Extract the fixed fallback colors already embedded in Papirus SVGs."""
    palette: dict[str, str] = {}
    for key, color in PALETTE_RE.findall(text):
        canonical = next((item for item in PALETTE_KEYS if item.lower() == key.lower()), key)
        palette.setdefault(canonical, color.lower())
    return palette


def discover_theme_palette(root: Path) -> dict[str, str]:
    """Discover the selected variant's own KDE fallback palette from its SVGs."""
    palette: dict[str, str] = {}

    for path in root.rglob("*.svg"):
        if not path.is_file():
            continue
        try:
            found = extract_palette(path.read_text(encoding="utf-8", errors="ignore"))
        except OSError:
            continue
        for key, color in found.items():
            palette.setdefault(key, color)
        if all(key in palette for key in PALETTE_KEYS):
            break

    missing = [key for key in PALETTE_KEYS if key not in palette]
    if missing:
        raise ValueError(
            f"Could not discover complete Papirus palette in {root}; missing: {', '.join(missing)}"
        )

    return palette


def semantic_palette_key(path: Path) -> str:
    """Choose a Papirus semantic color for otherwise plain ColorScheme-Text art."""
    name = normalized_stem(path)

    # Destructive / failure actions.
    negative = (
        "delete",
        "remove",
        "trash",
        "close",
        "cancel",
        "shutdown",
        "power-off",
        "poweroff",
        "log-out",
        "logout",
        "uninstall",
        "disconnect",
        "disconnected",
        "reject",
        "forbid",
        "denied",
        "error",
        "failed",
        "failure",
        "broken",
        "erase",
    )

    # Constructive / success actions.
    positive = (
        "add",
        "create",
        "insert",
        "apply",
        "accept",
        "confirm",
        "save",
        "log-in",
        "login",
        "install",
        "connect",
        "connected",
        "enable",
        "start",
        "resume",
        "unlock",
    )

    # Paused/attention/favorite state: Papirus' NeutralText orange.
    neutral = (
        "suspend",
        "hibernate",
        "sleep",
        "pause",
        "warning",
        "caution",
        "attention",
        "favorite",
        "bookmark",
        "starred",
        "pin",
        "locked",
    )

    if any(token in name for token in negative):
        return "NegativeText"
    if any(token in name for token in positive):
        return "PositiveText"
    if any(token in name for token in neutral):
        return "NeutralText"

    # Navigation, editing, settings, restart, information and generic UI actions
    # use Papirus' Highlight blue rather than falling back to monochrome Text.
    return "Highlight"


def class_palette_key(tag_text: str) -> str | None:
    """Read an element's explicit ColorScheme semantic class, if it has one."""
    class_match = CLASS_ATTR_RE.search(tag_text)
    if not class_match:
        return None

    classes = class_match.group("value").split()
    for key in ("NegativeText", "PositiveText", "NeutralText", "Highlight", "Text"):
        wanted = f"ColorScheme-{key}".lower()
        if any(item.lower() == wanted for item in classes):
            return key
    return None


def replace_dynamic_markers(text: str, path: Path, palette: dict[str, str]) -> str:
    """Bake Papirus semantic colors into one SVG without changing its geometry."""
    default_key = semantic_palette_key(path)
    default_color = palette[default_key]

    def replace_tag(match: re.Match[str]) -> str:
        tag_text = match.group(0)
        lowered = tag_text.lower()
        if not any(marker in lowered for marker in DYNAMIC_COLOR_MARKERS):
            return tag_text

        explicit_key = class_palette_key(tag_text)
        # Plain ColorScheme-Text means "normal foreground" upstream. For the
        # colorful variant, use the icon-name semantic color instead. Explicit
        # warning/success/error/highlight classes keep their Papirus meaning.
        key = explicit_key if explicit_key and explicit_key != "Text" else default_key
        color = palette[key]

        result = re.sub(r"currentColor", color, tag_text, flags=re.IGNORECASE)
        result = re.sub(r"context-fill", color, result, flags=re.IGNORECASE)
        result = re.sub(r"context-stroke", color, result, flags=re.IGNORECASE)
        return result

    result = START_TAG_RE.sub(replace_tag, text)

    # Catch unusual CSS/text forms not located directly in an element start tag.
    # They receive the icon's default semantic color so no dynamic marker can
    # survive into the generated theme.
    result = re.sub(r"currentColor", default_color, result, flags=re.IGNORECASE)
    result = re.sub(r"context-fill", default_color, result, flags=re.IGNORECASE)
    result = re.sub(r"context-stroke", default_color, result, flags=re.IGNORECASE)
    return result


def recolor_dynamic_svg(path: Path, palette: dict[str, str]) -> None:
    """Bake fixed semantic colors into a dynamic SVG in place."""
    original = path.read_text(encoding="utf-8", errors="strict")
    changed = replace_dynamic_markers(original, path, palette)
    path.write_text(changed, encoding="utf-8")

    if uses_dynamic_theme_color(path):
        raise ValueError(f"Dynamic color marker survived recoloring: {path}")


def rewrite_index_theme(index_path: Path, display_name: str) -> None:
    """Rename the generated theme while preserving its original inheritance."""
    text = index_path.read_text(encoding="utf-8", errors="replace")
    text = re.sub(r"(?m)^Name=.*$", f"Name={display_name}", text, count=1)
    text = re.sub(
        r"(?m)^Comment=.*$",
        "Comment=Papirus with fixed colorful UI, action, status and symbolic artwork",
        text,
        count=1,
    )
    index_path.write_text(text, encoding="utf-8")


def build_theme(source: Path, destination: Path, display_name: str) -> BuildStats:
    if not (source / "index.theme").is_file():
        raise FileNotFoundError(f"Not an icon theme: {source}")

    if source.resolve() == destination.resolve():
        raise ValueError("Source and destination must be different")

    if destination.exists():
        shutil.rmtree(destination)

    destination.parent.mkdir(parents=True, exist_ok=True)

    # Dereference Papirus-Dark/Papirus-Light links so each generated theme keeps
    # the exact source variant overrides and becomes self-contained.
    shutil.copytree(source, destination, symlinks=False)
    rewrite_index_theme(destination / "index.theme", display_name)

    image_files = [
        path
        for path in destination.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    ]
    symbolic_files = [path for path in image_files if is_symbolic_path(path, destination)]
    dynamic_files = [path for path in image_files if uses_dynamic_theme_color(path)]

    palette = discover_theme_palette(destination)

    # Snapshot every pre-existing fixed-color icon before changing any targets.
    # This guarantees candidate selection cannot accidentally reuse a colorized
    # file produced earlier in the same build.
    fixed_color_by_stem: dict[str, list[Path]] = defaultdict(list)
    for path in image_files:
        if not uses_dynamic_theme_color(path):
            fixed_color_by_stem[normalized_stem(path)].append(path)

    replacements: list[Replacement] = []
    recolored: list[str] = []

    for target in dynamic_files:
        candidates = fixed_color_by_stem.get(normalized_stem(target), [])

        if candidates:
            source_icon = max(
                candidates,
                key=lambda candidate: candidate_score(target, candidate, destination),
            )
            target_rel = str(target.relative_to(destination))
            source_rel = str(source_icon.relative_to(destination))
            source_bytes = source_icon.read_bytes()

            target.unlink()
            target.write_bytes(source_bytes)
            shutil.copystat(source_icon, target)
            replacements.append(Replacement(target=target_rel, source=source_rel))
            continue

        # No real colored counterpart exists in this Papirus variant. Preserve
        # the exact SVG paths/shapes and only replace its theme-supplied colors.
        recolor_dynamic_svg(target, palette)
        recolored.append(str(target.relative_to(destination)))

    remaining = [
        path
        for path in destination.rglob("*.svg")
        if path.is_file() and uses_dynamic_theme_color(path)
    ]

    return BuildStats(
        theme=source.name,
        symbolic_files=len(symbolic_files),
        dynamic_before=len(dynamic_files),
        reused_existing_color=len(replacements),
        recolored_semantic=len(recolored),
        dynamic_remaining=len(remaining),
        replacements=tuple(replacements),
        recolored=tuple(recolored),
        palette=tuple((key, palette[key]) for key in PALETTE_KEYS),
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

    print(f"Created:                   {destination}")
    print(f"Source variant:            {stats.theme}")
    print(f"Symbolic files:            {stats.symbolic_files}")
    print(f"Dynamic SVGs before:       {stats.dynamic_before}")
    print(f"Existing color art reused: {stats.reused_existing_color}")
    print(f"Semantic recolors:         {stats.recolored_semantic}")
    print(f"Dynamic SVGs remaining:    {stats.dynamic_remaining}")
    print("Palette:                   " + ", ".join(f"{key}={value}" for key, value in stats.palette))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
