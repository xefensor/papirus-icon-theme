#!/usr/bin/env python3
"""Build colorful Papirus variants that follow tools/work/DESIGN.md.

The generator treats upstream Papirus artwork and generated fallbacks differently.

Rules:
1. Existing fixed-color artwork from the selected variant wins unchanged. This
   preserves real Papirus/Papirus-Dark/Papirus-Light differences.
2. Only icons with no fixed-color counterpart are generated.
3. Generated icons keep their original geometry, use a small unified semantic
   color system derived from tools/work/examples-papirus.svg, and are deliberately
   less saturated than the example anchors so they do not overpower real Papirus
   artwork.
4. Function and category decide the generated family consistently:
   blue = neutral/system/device, green = positive, amber = attention/paused,
   red = destructive/error.
5. DESIGN.md shadow/highlight and size rules are applied without gradients.

Papirus-Dark and Papirus-Light contain relative symlinks into sibling themes.
The output dereferences those links so each generated user theme is standalone.
"""

from __future__ import annotations

import argparse
import colorsys
import re
import shutil
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path


SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)

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

# Exact example colors from tools/work/examples-papirus.svg.
# DESIGN.md explicitly points to that file as a source of good Papirus colors.
DESIGN_COLORS = {
    "blue": "#248afd",
    "green": "#4bae4f",
    "red": "#c2352a",
    "pink": "#f9548f",
    "orange": "#e97e10",
    "purple": "#7767c0",
    "light-grey": "#cccccc",
    "dark-grey": "#5d5d5d",
}
DESIGN_EFFECT_COLORS = {"shadow": "#000000", "highlight": "#ffffff"}

# Generated UI fallbacks must be quieter than full Papirus artwork.
# Keep the source hue/lightness, cap only HLS saturation. This means the palette
# remains derived from Papirus' example colors rather than introducing unrelated
# hues. Green is already below the cap and therefore remains unchanged.
GENERATED_SATURATION_CAP = 0.45


def _muted_example_color(color: str) -> str:
    value = color.lstrip("#")
    r, g, b = (int(value[i : i + 2], 16) / 255 for i in (0, 2, 4))
    hue, lightness, saturation = colorsys.rgb_to_hls(r, g, b)
    r2, g2, b2 = colorsys.hls_to_rgb(
        hue,
        lightness,
        min(saturation, GENERATED_SATURATION_CAP),
    )
    return f"#{round(r2 * 255):02x}{round(g2 * 255):02x}{round(b2 * 255):02x}"


# Deliberately only four generated semantic families. Existing Papirus artwork
# may of course use the full upstream palette; it is copied unchanged.
GENERATED_COLORS = {
    "blue": _muted_example_color(DESIGN_COLORS["blue"]),
    "green": _muted_example_color(DESIGN_COLORS["green"]),
    "amber": _muted_example_color(DESIGN_COLORS["orange"]),
    "red": _muted_example_color(DESIGN_COLORS["red"]),
}

# Hard brightness-limit examples stated in DESIGN.md.
DESIGN_BRIGHT_LIMIT = "#e4e4e4"
DESIGN_DARK_LIMIT = "#4f4f4f"

START_TAG_RE = re.compile(
    r"<(?![!?/])(?P<tag>[A-Za-z_][\w:.-]*)(?P<attrs>[^<>]*)>",
    re.DOTALL,
)
CLASS_ATTR_RE = re.compile(r"\bclass\s*=\s*([\"'])(?P<value>.*?)\1", re.DOTALL)
HEX_RE = re.compile(r"#[0-9a-fA-F]{6,8}")
BATTERY_LEVEL_RE = re.compile(r"(?:battery|power).*?(?:level[-_]?)(\d{1,3})")


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
    designed_fallbacks: int
    dynamic_remaining: int
    replacements: tuple[Replacement, ...]
    designed: tuple[str, ...]
    family_counts: tuple[tuple[str, int], ...]


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

    if is_symbolic_path(target, root) == is_symbolic_path(candidate, root):
        score += 400

    if candidate.suffix.lower() == ".svg":
        score += 300

    if not any("@" in part for part in candidate.relative_to(root).parts):
        score += 20

    return score


def _contains_any(name: str, tokens: tuple[str, ...]) -> bool:
    return any(token in name for token in tokens)


def generated_color_family(path: Path) -> str:
    """Return the unified semantic family for a generated-only fallback.

    This is intentionally based on both function and icon category. Related
    controls therefore keep the same family instead of receiving one-off colors.
    """
    name = normalized_stem(path)
    parts = {part.lower() for part in path.parts}
    context = next((part for part in KNOWN_CONTEXTS if part in parts), "")

    # Battery is stateful enough to deserve explicit thresholds.
    if "battery" in name:
        if _contains_any(name, ("charging", "charged", "full", "good")):
            return "green"
        if _contains_any(name, ("critical", "empty", "missing", "error", "failed")):
            return "red"
        level = BATTERY_LEVEL_RE.search(name)
        if level:
            value = max(0, min(100, int(level.group(1))))
            if value <= 15:
                return "red"
            if value <= 40:
                return "amber"
            return "green"

    # Strong state/failure semantics always win over category identity.
    if _contains_any(
        name,
        (
            "delete",
            "remove",
            "trash",
            "uninstall",
            "shutdown",
            "power-off",
            "poweroff",
            "disconnect",
            "disconnected",
            "disable",
            "disabled",
            "offline",
            "muted",
            "mute",
            "cancel",
            "close",
            "stop",
            "log-out",
            "logout",
            "reject",
            "forbid",
            "denied",
            "error",
            "failed",
            "failure",
            "broken",
            "critical",
            "erase",
        ),
    ):
        return "red"

    # Restart/session are neutral system actions. Check them before positive
    # tokens so "restart" cannot accidentally match "start".
    if _contains_any(
        name,
        (
            "reboot",
            "restart",
            "session",
            "switch-user",
            "user-switch",
        ),
    ):
        return "blue"

    # Marking/holding actions keep one amber family even when names also contain
    # generic constructive words such as "new" (e.g. bookmark-new).
    if _contains_any(
        name,
        (
            "pin",
            "pinned",
            "favorite",
            "favourite",
            "bookmark",
            "starred",
        ),
    ):
        return "amber"

    # Constructive actions are green. Keep this before the remaining lock-state
    # amber tokens so "unlock" does not accidentally match "lock".
    if _contains_any(
        name,
        (
            "list-add",
            "add",
            "create",
            "new",
            "insert",
            "apply",
            "accept",
            "confirm",
            "save",
            "install",
            "enable",
            "start",
            "resume",
            "unlock",
            "success",
            "okay",
            "dialog-ok",
        ),
    ):
        return "green"

    # Sleep/hold/attention states form the rest of the amber family.
    if _contains_any(
        name,
        (
            "suspend",
            "hibernate",
            "sleep",
            "pause",
            "warning",
            "caution",
            "attention",
            "limited",
            "degraded",
            "locked",
            "lock",
            "busy",
        ),
    ):
        return "amber"

    # Connection actions are green, but connected *status identities* stay blue
    # with their network/audio/Bluetooth family.
    if name.startswith(("network-connect", "bluetooth-connect", "device-connect")):
        return "green"

    # Explicit neutral/system/device identity family.
    if _contains_any(
        name,
        (
            "edit",
            "configure",
            "configuration",
            "settings",
            "preferences",
            "properties",
            "info",
            "information",
            "open",
            "tools",
            "reboot",
            "restart",
            "session",
            "switch-user",
            "user-switch",
            "speaker",
            "audio",
            "volume",
            "microphone",
            "headphone",
            "display",
            "monitor",
            "screen",
            "network",
            "wireless",
            "wifi",
            "ethernet",
            "bluetooth",
            "vpn",
            "device",
            "sync",
            "refresh",
            "reload",
            "search",
            "find",
            "zoom",
            "navigate",
            "go-",
        ),
    ):
        return "blue"

    # Category defaults keep related generated-only icons coherent.
    if context in {
        "actions",
        "panel",
        "status",
        "devices",
        "categories",
        "places",
        "apps",
        "emblems",
        "emotes",
        "mimetypes",
        "animations",
    }:
        return "blue"

    return "blue"


def generated_design_color(path: Path) -> str:
    return GENERATED_COLORS[generated_color_family(path)]


def class_generated_family(tag_text: str) -> str | None:
    """Map explicit KDE semantic classes onto unified generated families."""
    match = CLASS_ATTR_RE.search(tag_text)
    if not match:
        return None

    classes = {item.lower() for item in match.group("value").split()}
    if "colorscheme-negativetext" in classes:
        return "red"
    if "colorscheme-positivetext" in classes:
        return "green"
    if "colorscheme-neutraltext" in classes:
        return "amber"
    if "colorscheme-highlight" in classes:
        return "blue"
    return None


def replace_dynamic_markers(text: str, path: Path) -> tuple[str, str, str]:
    """Replace dynamic markers with the generated family color."""
    default_family = generated_color_family(path)
    default_color = GENERATED_COLORS[default_family]

    def replace_tag(match: re.Match[str]) -> str:
        tag_text = match.group(0)
        lowered = tag_text.lower()
        if not any(marker in lowered for marker in DYNAMIC_COLOR_MARKERS):
            return tag_text

        explicit_family = class_generated_family(tag_text)
        family = explicit_family or default_family
        color = GENERATED_COLORS[family]
        result = re.sub(r"currentColor", color, tag_text, flags=re.IGNORECASE)
        result = re.sub(r"context-fill", color, result, flags=re.IGNORECASE)
        result = re.sub(r"context-stroke", color, result, flags=re.IGNORECASE)
        return result

    result = START_TAG_RE.sub(replace_tag, text)
    result = re.sub(r"currentColor", default_color, result, flags=re.IGNORECASE)
    result = re.sub(r"context-fill", default_color, result, flags=re.IGNORECASE)
    result = re.sub(r"context-stroke", default_color, result, flags=re.IGNORECASE)
    return result, default_color, default_family


def _svg_tag(local_name: str) -> str:
    return f"{{{SVG_NS}}}{local_name}"


def shadow_highlight_offset(size: int) -> float:
    """Return the shadow/highlight offset from DESIGN.md."""
    if size <= 16:
        return 0.0
    if size <= 24:
        return 0.5
    return 1.0


def add_design_layer_effect(path: Path, logical_size: int, base_color: str) -> None:
    """Add Papirus shadow/highlight layers without changing SVG geometry.

    The filter is a vector equivalent of the DESIGN.md construction:
    - black 20% copy offset downward;
    - white top rim made from SourceAlpha minus the downward-offset alpha.
    No blur or gradient is used.
    """
    offset = shadow_highlight_offset(logical_size)
    if offset == 0:
        return

    tree = ET.parse(path)
    root = tree.getroot()

    defs = root.find(_svg_tag("defs"))
    if defs is None:
        defs = ET.Element(_svg_tag("defs"))
        root.insert(0, defs)

    filter_id = "papirus-colorful-layering"
    existing_ids = {element.get("id") for element in root.iter() if element.get("id")}
    suffix = 1
    while filter_id in existing_ids:
        suffix += 1
        filter_id = f"papirus-colorful-layering-{suffix}"

    filter_node = ET.SubElement(
        defs,
        _svg_tag("filter"),
        {
            "id": filter_id,
            "x": "-20%",
            "y": "-20%",
            "width": "140%",
            "height": "150%",
            "color-interpolation-filters": "sRGB",
        },
    )

    ET.SubElement(
        filter_node,
        _svg_tag("feFlood"),
        {
            "flood-color": DESIGN_EFFECT_COLORS["shadow"],
            "flood-opacity": "0.2",
            "result": "papirusShadowColor",
        },
    )
    ET.SubElement(
        filter_node,
        _svg_tag("feComposite"),
        {
            "in": "papirusShadowColor",
            "in2": "SourceAlpha",
            "operator": "in",
            "result": "papirusShadowShape",
        },
    )
    ET.SubElement(
        filter_node,
        _svg_tag("feOffset"),
        {
            "in": "papirusShadowShape",
            "dy": f"{offset:g}",
            "result": "papirusShadow",
        },
    )
    ET.SubElement(
        filter_node,
        _svg_tag("feOffset"),
        {
            "in": "SourceAlpha",
            "dy": f"{offset:g}",
            "result": "papirusOffsetAlpha",
        },
    )
    ET.SubElement(
        filter_node,
        _svg_tag("feComposite"),
        {
            "in": "SourceAlpha",
            "in2": "papirusOffsetAlpha",
            "operator": "out",
            "result": "papirusHighlightMask",
        },
    )

    # Generated semantic colors are mid-value colors, so DESIGN.md's normal 20%
    # highlight applies. Real fixed-color art is never rewritten here.
    ET.SubElement(
        filter_node,
        _svg_tag("feFlood"),
        {
            "flood-color": DESIGN_EFFECT_COLORS["highlight"],
            "flood-opacity": "0.2",
            "result": "papirusHighlightColor",
        },
    )
    ET.SubElement(
        filter_node,
        _svg_tag("feComposite"),
        {
            "in": "papirusHighlightColor",
            "in2": "papirusHighlightMask",
            "operator": "in",
            "result": "papirusHighlight",
        },
    )
    merge = ET.SubElement(filter_node, _svg_tag("feMerge"))
    ET.SubElement(merge, _svg_tag("feMergeNode"), {"in": "papirusShadow"})
    ET.SubElement(merge, _svg_tag("feMergeNode"), {"in": "SourceGraphic"})
    ET.SubElement(merge, _svg_tag("feMergeNode"), {"in": "papirusHighlight"})

    non_drawable = {
        _svg_tag("defs"),
        _svg_tag("title"),
        _svg_tag("desc"),
        _svg_tag("metadata"),
    }
    drawable = [child for child in list(root) if child.tag not in non_drawable]
    if not drawable:
        return

    group = ET.Element(_svg_tag("g"), {"filter": f"url(#{filter_id})"})
    insert_at = len(root)
    for child in drawable:
        root.remove(child)
        group.append(child)
    root.insert(insert_at, group)

    ET.indent(tree, space=" ")
    tree.write(path, encoding="unicode", xml_declaration=False)


def design_fallback_svg(path: Path, logical_size: int) -> str:
    """Turn one dynamic SVG into a unified Papirus-style generated fallback.

    Returns the semantic family used for audit/reporting.
    """
    original = path.read_text(encoding="utf-8", errors="strict")
    old_colors = {color.lower() for color in HEX_RE.findall(original)}

    changed, base_color, family = replace_dynamic_markers(original, path)
    path.write_text(changed, encoding="utf-8")

    if uses_dynamic_theme_color(path):
        raise ValueError(f"Dynamic color marker survived design recoloring: {path}")

    add_design_layer_effect(path, logical_size, base_color)

    # Safety rail: generated fallbacks may introduce only the four muted semantic
    # colors derived from examples-papirus.svg plus DESIGN.md effect colors.
    after = path.read_text(encoding="utf-8", errors="strict")
    new_colors = {color.lower() for color in HEX_RE.findall(after)} - old_colors
    allowed = {value.lower() for value in GENERATED_COLORS.values()}
    allowed.update(value.lower() for value in DESIGN_EFFECT_COLORS.values())
    unexpected = sorted(new_colors - allowed)
    if unexpected:
        raise ValueError(
            f"Generated colors outside the unified fallback palette in {path}: "
            + ", ".join(unexpected)
        )

    if "<linearGradient" in after or "<radialGradient" in after:
        if "<linearGradient" not in original and "<radialGradient" not in original:
            raise ValueError(f"Generator introduced a gradient, forbidden by DESIGN.md: {path}")

    return family


def rewrite_index_theme(index_path: Path, display_name: str) -> None:
    """Rename the generated theme while preserving its original inheritance."""
    text = index_path.read_text(encoding="utf-8", errors="replace")
    text = re.sub(r"(?m)^Name=.*$", f"Name={display_name}", text, count=1)
    text = re.sub(
        r"(?m)^Comment=.*$",
        "Comment=Papirus colorful UI variant with unified muted generated fallbacks",
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
    # its variant-specific artwork and becomes self-contained.
    shutil.copytree(source, destination, symlinks=False)
    rewrite_index_theme(destination / "index.theme", display_name)

    image_files = [
        path
        for path in destination.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    ]
    symbolic_files = [path for path in image_files if is_symbolic_path(path, destination)]
    dynamic_files = [path for path in image_files if uses_dynamic_theme_color(path)]

    # Snapshot pre-existing fixed-color art before generating fallbacks.
    fixed_color_by_stem: dict[str, list[Path]] = defaultdict(list)
    for path in image_files:
        if not uses_dynamic_theme_color(path):
            fixed_color_by_stem[normalized_stem(path)].append(path)

    replacements: list[Replacement] = []
    designed: list[str] = []
    family_counts: Counter[str] = Counter()

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

        logical_size, _scale = size_key(target, destination)
        family = design_fallback_svg(target, logical_size)
        family_counts[family] += 1
        designed.append(str(target.relative_to(destination)))

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
        designed_fallbacks=len(designed),
        dynamic_remaining=len(remaining),
        replacements=tuple(replacements),
        designed=tuple(designed),
        family_counts=tuple(sorted(family_counts.items())),
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
    print(f"Generated fallbacks:       {stats.designed_fallbacks}")
    print(f"Dynamic SVGs remaining:    {stats.dynamic_remaining}")
    print(
        "Generated families:        "
        + ", ".join(f"{name}={count}" for name, count in stats.family_counts)
    )
    print(
        "Generated palette:         "
        + ", ".join(f"{name}={color}" for name, color in GENERATED_COLORS.items())
    )
    print("Design source:             tools/work/DESIGN.md + examples-papirus.svg")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
