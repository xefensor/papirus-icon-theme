#!/usr/bin/env python3
"""Create a Papirus variant whose symbolic icon names resolve to colorful artwork.

KDE Plasma may explicitly request icons ending in ``-symbolic``. Removing the
symbolic directories is not enough because icon-theme inheritance can then fall
back to another monochrome theme. This tool keeps the symbolic filenames KDE
asks for, but replaces their contents with the closest normal Papirus icon when
one exists.

The source theme is copied with symlinks dereferenced, so Papirus-Dark's links
back into Papirus become a self-contained generated theme.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from collections import defaultdict
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


def is_symbolic_part(part: str) -> bool:
    return part == "symbolic" or part.startswith("symbolic-")


def is_symbolic_path(path: Path, root: Path) -> bool:
    rel = path.relative_to(root)
    return (
        "-symbolic" in path.stem
        or ".symbolic" in path.name
        or any(is_symbolic_part(part) for part in rel.parts[:-1])
    )


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


def candidate_score(symbolic: Path, candidate: Path, root: Path) -> int:
    score = 0

    sym_size, sym_scale = size_key(symbolic, root)
    cand_size, cand_scale = size_key(candidate, root)
    sym_context = context_key(symbolic, root)
    cand_context = context_key(candidate, root)

    if sym_context and sym_context == cand_context:
        score += 10_000
    elif {sym_context, cand_context} <= {"panel", "status"}:
        # KDE/Papirus often place equivalent tray artwork in either directory.
        score += 8_000

    if sym_size and cand_size:
        if sym_size == cand_size:
            score += 5_000
        else:
            score -= abs(sym_size - cand_size) * 20

    if sym_scale == cand_scale:
        score += 500

    if candidate.suffix.lower() == ".svg":
        score += 300

    # Prefer regular fixed-size directories over unusual aliases when tied.
    if not any("@" in part for part in candidate.relative_to(root).parts):
        score += 20

    return score


def rewrite_index_theme(index_path: Path, display_name: str) -> None:
    text = index_path.read_text(encoding="utf-8", errors="replace")
    text = re.sub(r"(?m)^Name=.*$", f"Name={display_name}", text, count=1)
    text = re.sub(
        r"(?m)^Comment=.*$",
        "Comment=Papirus with colorful artwork for symbolic icon requests",
        text,
        count=1,
    )

    # The generated theme is self-contained. Keeping only hicolor as inheritance
    # avoids falling straight back into Breeze's symbolic artwork for missing
    # names while retaining the standard freedesktop fallback.
    if re.search(r"(?m)^Inherits=", text):
        text = re.sub(r"(?m)^Inherits=.*$", "Inherits=hicolor", text, count=1)
    else:
        text = text.replace("[Icon Theme]\n", "[Icon Theme]\nInherits=hicolor\n", 1)

    index_path.write_text(text, encoding="utf-8")


def build_theme(source: Path, destination: Path, display_name: str) -> tuple[int, int, list[Path]]:
    if not (source / "index.theme").is_file():
        raise FileNotFoundError(f"Not an icon theme: {source}")

    if source.resolve() == destination.resolve():
        raise ValueError("Source and destination must be different")

    if destination.exists():
        shutil.rmtree(destination)

    destination.parent.mkdir(parents=True, exist_ok=True)

    # Important for Papirus-Dark: many directories are relative symlinks into
    # the sibling Papirus directory. Dereference them so the generated theme is
    # self-contained. Do NOT use ignore_dangling_symlinks=True here: Python's
    # copytree checks relative link targets in a way that causes valid Papirus
    # links such as ../../Papirus/22x22/symbolic to be skipped entirely.
    shutil.copytree(
        source,
        destination,
        symlinks=False,
    )

    rewrite_index_theme(destination / "index.theme", display_name)

    normal_by_stem: dict[str, list[Path]] = defaultdict(list)
    symbolic_files: list[Path] = []

    for path in destination.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        if is_symbolic_path(path, destination):
            symbolic_files.append(path)
        else:
            normal_by_stem[normalized_stem(path)].append(path)

    replaced = 0
    unmatched: list[Path] = []

    for symbolic in symbolic_files:
        candidates = normal_by_stem.get(normalized_stem(symbolic), [])
        if not candidates:
            unmatched.append(symbolic)
            continue

        source_icon = max(
            candidates,
            key=lambda candidate: candidate_score(symbolic, candidate, destination),
        )

        # Replace the symbolic artwork while intentionally keeping the original
        # symbolic filename. Plasma still gets the name it requested, but the
        # pixels/vector paths are the normal colorful Papirus artwork.
        symbolic.unlink()
        shutil.copy2(source_icon, symbolic)
        replaced += 1

    return len(symbolic_files), replaced, unmatched


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
        total, replaced, unmatched = build_theme(source, destination, display_name)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    report = destination / "unmatched-symbolic-icons.txt"
    if unmatched:
        report.write_text(
            "\n".join(str(path.relative_to(destination)) for path in unmatched) + "\n",
            encoding="utf-8",
        )
    elif report.exists():
        report.unlink()

    print(f"Created:   {destination}")
    print(f"Symbolic:  {total}")
    print(f"Replaced:  {replaced}")
    print(f"Unmatched: {len(unmatched)}")
    if unmatched:
        print(f"Report:    {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
