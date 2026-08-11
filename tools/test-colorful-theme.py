#!/usr/bin/env python3
"""Regression tests for tools/make-colorful-theme.py.

The generator is intentionally conservative: it may only replace a symbolic
icon with fixed-color artwork that already exists in Papirus. It must never
synthesize colors. Full Papirus and Papirus-Dark builds verify that every changed
icon is a byte-for-byte copy of an existing source-theme file and every symbolic
icon without a fixed-color counterpart stays byte-for-byte unchanged.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATOR_PATH = REPO_ROOT / "tools" / "make-colorful-theme.py"

spec = importlib.util.spec_from_file_location("make_colorful_theme", GENERATOR_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Could not load {GENERATOR_PATH}")

generator = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = generator
spec.loader.exec_module(generator)


class ColorfulThemeTests(unittest.TestCase):
    def test_relative_papirus_symlinks_are_followed_and_existing_art_is_copied(self) -> None:
        """Papirus-Dark links are dereferenced and copied artwork stays exact."""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "repo"
            papirus = root / "Papirus" / "22x22"
            dark = root / "Papirus-Dark"

            (papirus / "status").mkdir(parents=True)
            (papirus / "symbolic" / "status").mkdir(parents=True)
            (dark / "22x22").mkdir(parents=True)

            colorful = papirus / "status" / "network-wireless.svg"
            symbolic = papirus / "symbolic" / "status" / "network-wireless-symbolic.svg"
            colorful_bytes = (
                '<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22">'
                '<path fill="#123456" d="M1 1h20v20H1z"/>'
                '</svg>\n'
            ).encode()
            symbolic_bytes = (
                '<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22">'
                '<path style="fill:currentColor" d="M1 1h20v20H1z"/>'
                '</svg>\n'
            ).encode()
            colorful.write_bytes(colorful_bytes)
            symbolic.write_bytes(symbolic_bytes)

            (dark / "index.theme").write_text(
                "[Icon Theme]\n"
                "Name=Papirus-Dark\n"
                "Comment=fixture\n"
                "Inherits=breeze-dark,hicolor\n",
                encoding="utf-8",
            )

            os.symlink("../../Papirus/22x22/status", dark / "22x22" / "status")
            os.symlink("../../Papirus/22x22/symbolic", dark / "22x22" / "symbolic")

            destination = Path(temp_dir) / "out" / "Papirus-Dark-Colorful"
            stats = generator.build_theme(dark, destination, "Papirus-Dark Colorful")
            generated = destination / "22x22" / "symbolic" / "status" / symbolic.name

            self.assertEqual(stats.symbolic_files, 1)
            self.assertEqual(stats.symbolic_dynamic_before, 1)
            self.assertEqual(stats.reused_existing_color, 1)
            self.assertEqual(stats.left_unchanged, 0)
            self.assertEqual(stats.symbolic_dynamic_remaining, 0)
            self.assertEqual(generated.read_bytes(), colorful_bytes)
            self.assertEqual(
                stats.replacements,
                (
                    generator.Replacement(
                        target="22x22/symbolic/status/network-wireless-symbolic.svg",
                        source="22x22/status/network-wireless.svg",
                    ),
                ),
            )

    def test_symbolic_only_icon_is_left_byte_for_byte_unchanged(self) -> None:
        """No existing color counterpart means no replacement and no recolor."""
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "Papirus"
            symbolic_dir = source / "22x22" / "symbolic" / "status"
            symbolic_dir.mkdir(parents=True)
            (source / "index.theme").write_text(
                "[Icon Theme]\nName=Papirus\nComment=fixture\nInherits=breeze,hicolor\n",
                encoding="utf-8",
            )

            icon = symbolic_dir / "made-up-symbolic-only-symbolic.svg"
            original = (
                '<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22">'
                '<path class="ColorScheme-NegativeText" '
                'style="fill:currentColor" d="M1 1h20v20H1z"/>'
                '</svg>\n'
            ).encode()
            icon.write_bytes(original)

            destination = Path(temp_dir) / "out" / "Papirus-Colorful"
            stats = generator.build_theme(source, destination, "Papirus Colorful")
            generated = destination / "22x22" / "symbolic" / "status" / icon.name

            self.assertEqual(stats.reused_existing_color, 0)
            self.assertEqual(stats.left_unchanged, 1)
            self.assertEqual(stats.symbolic_dynamic_remaining, 1)
            self.assertEqual(stats.replacements, ())
            self.assertEqual(generated.read_bytes(), original)
            self.assertTrue(generator.uses_dynamic_theme_color(generated))

    def assert_real_theme_uses_only_existing_artwork(self, theme_name: str) -> None:
        """Prove every modified real-theme icon came from an existing source file."""
        source = REPO_ROOT / theme_name
        self.assertTrue((source / "index.theme").is_file())

        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            baseline = temp / f"{theme_name}-baseline"
            destination = temp / f"{theme_name}-Colorful"

            # Use the same dereferenced snapshot layout as the generator, but do
            # not rewrite or replace anything in this baseline.
            shutil.copytree(source, baseline, symlinks=False)
            stats = generator.build_theme(
                source,
                destination,
                f"{theme_name} Colorful Test",
            )

            print(
                f"REAL {theme_name} result: "
                f"symbolic={stats.symbolic_files}, "
                f"dynamic-symbolic-before={stats.symbolic_dynamic_before}, "
                f"reused-existing-color={stats.reused_existing_color}, "
                f"left-unchanged={stats.left_unchanged}, "
                f"dynamic-symbolic-remaining={stats.symbolic_dynamic_remaining}, "
                "synthesized=0",
                flush=True,
            )

            self.assertGreater(stats.symbolic_files, 0)
            self.assertGreater(stats.symbolic_dynamic_before, 0)
            self.assertGreater(stats.reused_existing_color, 0)
            self.assertGreater(
                stats.left_unchanged,
                0,
                f"{theme_name} unexpectedly had a color counterpart for every symbolic icon",
            )
            self.assertEqual(
                stats.symbolic_dynamic_remaining,
                stats.left_unchanged,
                "only unresolved original symbolic icons may remain dynamic",
            )

            replacement_by_target = {item.target: item.source for item in stats.replacements}
            self.assertEqual(len(replacement_by_target), stats.reused_existing_color)

            # Every replacement must be exactly the bytes of a pre-existing,
            # fixed-color file in the untouched Papirus snapshot.
            for target_rel, source_rel in replacement_by_target.items():
                baseline_target = baseline / target_rel
                baseline_source = baseline / source_rel
                generated_target = destination / target_rel

                self.assertTrue(baseline_target.is_file())
                self.assertTrue(baseline_source.is_file())
                self.assertTrue(generated_target.is_file())
                self.assertTrue(generator.uses_dynamic_theme_color(baseline_target))
                self.assertFalse(generator.uses_dynamic_theme_color(baseline_source))
                self.assertEqual(generated_target.read_bytes(), baseline_source.read_bytes())

            # Conversely, every original dynamic symbolic icon that did not get
            # a real counterpart must remain completely untouched.
            baseline_symbolic_dynamic = [
                path
                for path in baseline.rglob("*")
                if path.is_file()
                and path.suffix.lower() in generator.IMAGE_SUFFIXES
                and generator.is_symbolic_path(path, baseline)
                and generator.uses_dynamic_theme_color(path)
            ]
            unchanged_count = 0
            for baseline_icon in baseline_symbolic_dynamic:
                rel = str(baseline_icon.relative_to(baseline))
                if rel in replacement_by_target:
                    continue
                generated_icon = destination / rel
                self.assertEqual(
                    generated_icon.read_bytes(),
                    baseline_icon.read_bytes(),
                    f"symbolic-only icon was altered instead of left alone: {rel}",
                )
                unchanged_count += 1

            self.assertEqual(unchanged_count, stats.left_unchanged)

            # The generated theme may have a new display name/comment, but keep
            # the source theme's inheritance instead of changing fallback art.
            baseline_index = (baseline / "index.theme").read_text(encoding="utf-8")
            generated_index = (destination / "index.theme").read_text(encoding="utf-8")
            baseline_inherits = next(
                (line for line in baseline_index.splitlines() if line.startswith("Inherits=")),
                None,
            )
            if baseline_inherits is not None:
                self.assertIn(baseline_inherits, generated_index)

    def test_real_papirus_uses_only_existing_color_artwork(self) -> None:
        self.assert_real_theme_uses_only_existing_artwork("Papirus")

    def test_real_papirus_dark_uses_only_existing_color_artwork(self) -> None:
        self.assert_real_theme_uses_only_existing_artwork("Papirus-Dark")


if __name__ == "__main__":
    unittest.main(verbosity=2)
