#!/usr/bin/env python3
"""Regression tests for tools/make-colorful-theme.py.

The full Papirus-Dark build is intentional. A tiny fixture alone previously let
a broken generator report ``Symbolic: 0`` while looking correct in isolation.
These tests now require the generated real theme to contain zero dynamic theme
color references.
"""

from __future__ import annotations

import importlib.util
import os
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
    def test_relative_papirus_symlinks_are_followed_and_replaced(self) -> None:
        """Papirus-Dark's ../../Papirus/... symlinks must be dereferenced."""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "repo"
            papirus = root / "Papirus" / "22x22"
            dark = root / "Papirus-Dark"

            (papirus / "status").mkdir(parents=True)
            (papirus / "symbolic" / "status").mkdir(parents=True)
            (dark / "22x22").mkdir(parents=True)

            colorful = papirus / "status" / "network-wireless.svg"
            symbolic = papirus / "symbolic" / "status" / "network-wireless-symbolic.svg"
            colorful.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22">'
                '<path fill="#3999e6" d="M1 1h20v20H1z"/>'
                '</svg>\n',
                encoding="utf-8",
            )
            symbolic.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22">'
                '<path style="fill:currentColor" d="M1 1h20v20H1z"/>'
                '</svg>\n',
                encoding="utf-8",
            )

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

            generated = destination / "22x22" / "symbolic" / "status" / "network-wireless-symbolic.svg"
            generated_text = generated.read_text(encoding="utf-8")

            self.assertEqual(stats.symbolic_files, 1)
            self.assertEqual(stats.dynamic_before, 1)
            self.assertEqual(stats.reused_fixed, 1)
            self.assertEqual(stats.synthesized, 0)
            self.assertEqual(stats.dynamic_remaining, 0)
            self.assertFalse(generator.uses_dynamic_theme_color(generated))
            self.assertIn("#3999e6", generated_text)
            self.assertNotIn("currentColor", generated_text)

    def test_symbolic_only_icon_gets_fixed_color_fallback(self) -> None:
        """An icon with no colorful counterpart must not remain monochrome."""
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "Papirus-Dark"
            symbolic_dir = source / "22x22" / "symbolic" / "status"
            symbolic_dir.mkdir(parents=True)
            (source / "index.theme").write_text(
                "[Icon Theme]\nName=Papirus-Dark\nComment=fixture\nInherits=breeze-dark,hicolor\n",
                encoding="utf-8",
            )

            battery = symbolic_dir / "battery-level-0-symbolic.svg"
            battery.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22">'
                '<path class="ColorScheme-NegativeText error" '
                'style="fill:currentColor" d="M1 1h20v20H1z"/>'
                '</svg>\n',
                encoding="utf-8",
            )

            destination = Path(temp_dir) / "out" / "Papirus-Dark-Colorful"
            stats = generator.build_theme(source, destination, "Papirus-Dark Colorful")
            generated = destination / "22x22" / "symbolic" / "status" / battery.name
            text = generated.read_text(encoding="utf-8").lower()

            self.assertEqual(stats.reused_fixed, 0)
            self.assertEqual(stats.synthesized, 1)
            self.assertEqual(stats.dynamic_remaining, 0)
            self.assertFalse(generator.uses_dynamic_theme_color(generated))
            self.assertIn("#f44336", text)
            self.assertNotIn("currentcolor", text)

    def test_real_papirus_dark_has_zero_dynamic_color_svgs(self) -> None:
        """Build the real fork and prove no theme-driven monochrome SVG remains."""
        source = REPO_ROOT / "Papirus-Dark"
        self.assertTrue((source / "index.theme").is_file())

        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / "Papirus-Dark-Colorful"
            stats = generator.build_theme(
                source,
                destination,
                "Papirus-Dark Colorful Test",
            )

            print(
                "REAL Papirus-Dark result: "
                f"symbolic={stats.symbolic_files}, "
                f"dynamic-before={stats.dynamic_before}, "
                f"reused-fixed={stats.reused_fixed}, "
                f"synthesized={stats.synthesized}, "
                f"dynamic-remaining={stats.dynamic_remaining}",
                flush=True,
            )

            self.assertGreater(stats.symbolic_files, 0)
            self.assertGreater(stats.dynamic_before, 0)
            self.assertGreater(stats.reused_fixed, 0)
            self.assertGreater(
                stats.synthesized,
                0,
                "real theme unexpectedly exercised no symbolic-only fallback",
            )
            self.assertEqual(stats.dynamic_remaining, 0)

            remaining = [
                path
                for path in destination.rglob("*.svg")
                if path.is_file() and generator.uses_dynamic_theme_color(path)
            ]
            self.assertEqual(remaining, [], "generated theme still contains dynamic-color SVGs")

            # Representative Plasma tray/status icons. Audio should normally be
            # replaced from existing fixed Papirus artwork; battery-level-0 was
            # previously one of the unmatched symbolic-only names and therefore
            # exercises the fallback path on the real repository.
            audio = destination / "22x22" / "symbolic" / "status" / "audio-volume-high-symbolic.svg"
            battery = destination / "22x22" / "symbolic" / "status" / "battery-level-0-symbolic.svg"
            bluetooth = destination / "22x22" / "symbolic" / "status" / "bluetooth-disconnected-symbolic.svg"

            for icon in (audio, battery, bluetooth):
                self.assertTrue(icon.is_file(), f"missing representative icon: {icon}")
                self.assertFalse(
                    generator.uses_dynamic_theme_color(icon),
                    f"representative icon is still dynamic: {icon}",
                )

            battery_text = battery.read_text(encoding="utf-8", errors="ignore").lower()
            self.assertIn("#f44336", battery_text)
            self.assertNotIn("currentcolor", battery_text)

            index_text = (destination / "index.theme").read_text(encoding="utf-8")
            self.assertIn("Name=Papirus-Dark Colorful Test", index_text)
            self.assertIn("Inherits=hicolor", index_text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
