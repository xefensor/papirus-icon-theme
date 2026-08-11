#!/usr/bin/env python3
"""Build a Papirus variant that prefers existing colorful Papirus artwork.

KDE Plasma may explicitly request ``*-symbolic`` icons. This generator keeps
those symbolic filenames so Plasma can still find them, but when Papirus already
contains a fixed-color icon with the same semantic name, the symbolic file is
replaced by a byte-for-byte copy of that existing Papirus artwork.

No colors are invented, synthesized, or baked into symbolic artwork. If Papirus
has no fixed-color counterpart for a symbolic icon, that icon is left exactly as
it was in the source theme.

Papirus-Dark contains relative symlinks into the sibling Papirus theme. The
output dereferences those links so the generated user theme is self-contained.
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


@dataclass(frozen=True)
class Replacement:
    """One generated file and the existing Papirus file copied into it."""

    target: str
    source: str


@dataclass(frozen=True)
class BuildStats:
    symbolic_files: int
    symbolic_dynamic_before: int
    reused_existing_color: int
    left_unchanged: int
    symbolic_dynamic_remaining: int
    replacements: tuple[Replacement, ...]


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
    """Return True if an SVG asks the desktop theme to provide its color."""
    if path.suffix.lower() != ".svg":
        return False

    try:
        lowered = path.read_text(encoding="utf-8", errors="ignore").lower()
    except OSError:
        return True

    return any(marker in lowered for marker in DYNAMIC_COLOR_MARKERS)


def normalized_stem(path: Path) -> str:
    """Normalize symbolic naming without guessing unrelated icon aliases."""
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
    """Prefer the closest existing Papirus counterpart; never alter artwork."""
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

    if candidate.suffix.lower() == ".svg":
        score += 300

    if not any("@" in part for part in candidate.relative_to(root).parts):
        score += 20

    return score


def rewrite_index_theme(index_path: Path, display_name: str) -> None:
    """Rename the generated theme while preserving Papirus inheritance."""
    text = index_path.read_text(encoding="utf-8", errors="replace")
    text = re.sub(r"(?m)^Name=.*$", f"Name={display_name}", text, count=1)
    text = re.sub(
        r"(?m)^Comment=.*$",
        "Comment=Papirus symbolic names backed by existing colorful Papirus artwork where available",
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

    # Papirus-Dark contains relative symlinks into the sibling Papirus theme.
    # Dereferencing them also gives us a complete snapshot from which existing
    # fixed-color counterparts can be selected.
    shutil.copytree(source, destination, symlinks=False)
    rewrite_index_theme(destination / "index.theme", display_name)

    image_files = [
        path
        for path in destination.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    ]
    symbolic_files = [path for path in image_files if is_symbolic_path(path, destination)]
    symbolic_dynamic = [path for path in symbolic_files if uses_dynamic_theme_color(path)]

    # Snapshot all existing fixed-color artwork before replacing anything.
    # A candidate is valid only when it already exists in Papirus and does not
    # depend on currentColor/context-fill/context-stroke.
    fixed_color_by_stem: dict[str, list[Path]] = defaultdict(list)
    for path in image_files:
        if not uses_dynamic_theme_color(path):
            fixed_color_by_stem[normalized_stem(path)].append(path)

    replacements: list[Replacement] = []

    for target in symbolic_dynamic:
        candidates = fixed_color_by_stem.get(normalized_stem(target), [])
        if not candidates:
            # This is intentional: keep the original symbolic icon unchanged.
            continue

        source_icon = max(
            candidates,
            key=lambda candidate: candidate_score(target, candidate, destination),
        )

        target_rel = str(target.relative_to(destination))
        source_rel = str(source_icon.relative_to(destination))
        source_bytes = source_icon.read_bytes()

        # Copy the existing file exactly. No SVG parsing or recoloring happens.
        target.unlink()
        target.write_bytes(source_bytes)
        shutil.copystat(source_icon, target)
        replacements.append(Replacement(target=target_rel, source=source_rel))

    remaining = [path for path in symbolic_files if uses_dynamic_theme_color(path)]

    return BuildStats(
        symbolic_files=len(symbolic_files),
        symbolic_dynamic_before=len(symbolic_dynamic),
        reused_existing_color=len(replacements),
        left_unchanged=len(symbolic_dynamic) - len(replacements),
        symbolic_dynamic_remaining=len(remaining),
        replacements=tuple(replacements),
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

    print(f"Created:                       {destination}")
    print(f"Symbolic files:                {stats.symbolic_files}")
    print(f"Dynamic symbolic before:       {stats.symbolic_dynamic_before}")
    print(f"Reused existing color artwork: {stats.reused_existing_color}")
    print(f"Left unchanged (no color art): {stats.left_unchanged}")
    print(f"Dynamic symbolic remaining:    {stats.symbolic_dynamic_remaining}")
    print("Synthesized/recolored:          0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
