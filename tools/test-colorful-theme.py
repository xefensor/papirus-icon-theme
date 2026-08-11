#!/usr/bin/env python3
"""Regression tests for the DESIGN.md-compliant colorful Papirus generator."""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATOR_PATH = REPO_ROOT / "tools" / "make-colorful-theme.py"
DESIGN_PATH = REPO_ROOT / "tools" / "work" / "DESIGN.md"
EXAMPLE_PATH = REPO_ROOT / "tools" / "work" / "examples-papirus.svg"

spec = importlib.util.spec_from_file_location("make_colorful_theme", GENERATOR_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Could not load {GENERATOR_PATH}")

generator = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = generator
spec.loader.exec_module(generator)


def dynamic_svg(body: str, size: int = 22) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}">'
        '<defs><style id="current-color-scheme" type="text/css">'
        '.ColorScheme-Text { color:#444444; } '
        '.ColorScheme-Highlight { color:#4285f4; } '
        '.ColorScheme-NeutralText { color:#ff9800; } '
        '.ColorScheme-PositiveText { color:#4caf50; } '
        '.ColorScheme-NegativeText { color:#f44336; }'
        '</style></defs>'
        f"{body}</svg>\n"
    )


class ColorfulThemeTests(unittest.TestCase):
    def test_design_sources_exist_and_palette_matches_example(self) -> None:
        self.assertTrue(DESIGN_PATH.is_file())
        self.assertTrue(EXAMPLE_PATH.is_file())
        example = EXAMPLE_PATH.read_text(encoding="utf-8", errors="ignore").lower()
        for color in generator.DESIGN_COLORS.values():
            self.assertIn(color, example)

    def test_relative_papirus_symlinks_are_followed_and_fixed_art_wins(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "repo"
            papirus = root / "Papirus" / "22x22"
            dark = root / "Papirus-Dark"
            (papirus / "status").mkdir(parents=True)
            (papirus / "symbolic" / "status").mkdir(parents=True)
            (dark / "22x22").mkdir(parents=True)

            fixed = papirus / "status" / "network-wireless.svg"
            fixed_bytes = (
                '<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22">'
                '<path fill="#123456" d="M1 1h20v20H1z"/></svg>\n'
            ).encode()
            fixed.write_bytes(fixed_bytes)
            (papirus / "symbolic" / "status" / "network-wireless-symbolic.svg").write_text(
                dynamic_svg(
                    '<path class="ColorScheme-Text" style="fill:currentColor" '
                    'd="M1 1h20v20H1z"/>'
                ),
                encoding="utf-8",
            )

            (dark / "index.theme").write_text(
                "[Icon Theme]\nName=Papirus-Dark\nComment=fixture\nInherits=breeze-dark,hicolor\n",
                encoding="utf-8",
            )
            os.symlink("../../Papirus/22x22/status", dark / "22x22" / "status")
            os.symlink("../../Papirus/22x22/symbolic", dark / "22x22" / "symbolic")

            destination = Path(temp_dir) / "out" / "Papirus-Dark-Colorful"
            stats = generator.build_theme(dark, destination, "Papirus-Dark Colorful")
            generated = destination / "22x22/symbolic/status/network-wireless-symbolic.svg"

            self.assertEqual(stats.reused_existing_color, 1)
            self.assertEqual(stats.designed_fallbacks, 0)
            self.assertEqual(stats.dynamic_remaining, 0)
            self.assertEqual(generated.read_bytes(), fixed_bytes)

    def test_existing_light_and_dark_fixed_color_variants_are_respected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "repo"
            outputs: dict[str, bytes] = {}

            for theme_name, fixed_color in (
                ("Papirus-Light", "#102030"),
                ("Papirus-Dark", "#d0e0f0"),
            ):
                source = root / theme_name
                symbolic_dir = source / "22x22/symbolic/status"
                fixed_dir = source / "22x22/status"
                symbolic_dir.mkdir(parents=True)
                fixed_dir.mkdir(parents=True)
                (source / "index.theme").write_text(
                    f"[Icon Theme]\nName={theme_name}\nComment=fixture\nInherits=hicolor\n",
                    encoding="utf-8",
                )
                (symbolic_dir / "example-symbolic.svg").write_text(
                    dynamic_svg(
                        '<path class="ColorScheme-Text" style="fill:currentColor" '
                        'd="M1 1h20v20H1z"/>'
                    ),
                    encoding="utf-8",
                )
                fixed_bytes = (
                    '<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22">'
                    f'<path fill="{fixed_color}" d="M1 1h20v20H1z"/></svg>\n'
                ).encode()
                (fixed_dir / "example.svg").write_bytes(fixed_bytes)

                destination = Path(temp_dir) / "out" / f"{theme_name}-Colorful"
                stats = generator.build_theme(source, destination, f"{theme_name} Colorful")
                generated = destination / "22x22/symbolic/status/example-symbolic.svg"
                self.assertEqual(stats.reused_existing_color, 1)
                self.assertEqual(stats.designed_fallbacks, 0)
                outputs[theme_name] = generated.read_bytes()
                self.assertEqual(outputs[theme_name], fixed_bytes)

            self.assertNotEqual(outputs["Papirus-Light"], outputs["Papirus-Dark"])

    def test_22px_fallback_uses_design_color_shadow_and_highlight(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "Papirus"
            actions = source / "22x22/actions"
            actions.mkdir(parents=True)
            (source / "index.theme").write_text(
                "[Icon Theme]\nName=Papirus\nComment=fixture\nInherits=hicolor\n",
                encoding="utf-8",
            )
            (actions / "system-suspend.svg").write_text(
                dynamic_svg(
                    '<path class="ColorScheme-Text" style="fill:currentColor" '
                    'd="M2 2h18v18H2z"/>'
                ),
                encoding="utf-8",
            )

            destination = Path(temp_dir) / "out" / "Papirus-Colorful"
            stats = generator.build_theme(source, destination, "Papirus Colorful")
            generated = destination / "22x22/actions/system-suspend.svg"
            text = generated.read_text(encoding="utf-8").lower()

            self.assertEqual(stats.designed_fallbacks, 1)
            self.assertEqual(stats.dynamic_remaining, 0)
            self.assertIn(generator.DESIGN_COLORS["orange"], text)
            self.assertIn('flood-color="#000000"', text)
            self.assertIn('flood-opacity="0.2"', text)
            self.assertIn('flood-color="#ffffff"', text)
            self.assertIn('dy="0.5"', text)
            self.assertNotIn("currentcolor", text)
            self.assertNotIn("<lineargradient", text)
            self.assertNotIn("<radialgradient", text)

    def test_16px_fallback_has_no_generated_shadow_or_highlight(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "Papirus"
            actions = source / "16x16/actions"
            actions.mkdir(parents=True)
            (source / "index.theme").write_text(
                "[Icon Theme]\nName=Papirus\nComment=fixture\nInherits=hicolor\n",
                encoding="utf-8",
            )
            (actions / "edit-delete.svg").write_text(
                dynamic_svg(
                    '<path class="ColorScheme-Text" style="fill:currentColor" '
                    'd="M1 1h14v14H1z"/>',
                    size=16,
                ),
                encoding="utf-8",
            )

            destination = Path(temp_dir) / "out" / "Papirus-Colorful"
            generator.build_theme(source, destination, "Papirus Colorful")
            text = (destination / "16x16/actions/edit-delete.svg").read_text(
                encoding="utf-8"
            ).lower()

            self.assertIn(generator.DESIGN_COLORS["red"], text)
            self.assertNotIn("papirus-colorful-layering", text)
            self.assertNotIn("currentcolor", text)

    def test_kde_action_semantics_use_only_design_example_colors(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "Papirus"
            actions = source / "22x22/actions"
            actions.mkdir(parents=True)
            (source / "index.theme").write_text(
                "[Icon Theme]\nName=Papirus\nComment=fixture\nInherits=hicolor\n",
                encoding="utf-8",
            )

            expected = {
                "system-suspend.svg": generator.DESIGN_COLORS["orange"],
                "system-suspend-hibernate.svg": generator.DESIGN_COLORS["orange"],
                "system-reboot.svg": generator.DESIGN_COLORS["blue"],
                "system-shutdown.svg": generator.DESIGN_COLORS["red"],
                "window-pin.svg": generator.DESIGN_COLORS["purple"],
                "list-add.svg": generator.DESIGN_COLORS["green"],
                "edit-delete.svg": generator.DESIGN_COLORS["red"],
            }

            for name in expected:
                (actions / name).write_text(
                    dynamic_svg(
                        '<path class="ColorScheme-Text" style="fill:currentColor" '
                        'd="M1 1h20v20H1z"/>'
                    ),
                    encoding="utf-8",
                )

            destination = Path(temp_dir) / "out" / "Papirus-Colorful"
            stats = generator.build_theme(source, destination, "Papirus Colorful")
            self.assertEqual(stats.designed_fallbacks, len(expected))
            self.assertEqual(stats.dynamic_remaining, 0)

            for name, color in expected.items():
                text = (destination / "22x22/actions" / name).read_text(
                    encoding="utf-8"
                ).lower()
                self.assertIn(color, text, name)

    def assert_real_theme_is_design_colored(self, theme_name: str) -> None:
        source = REPO_ROOT / theme_name
        self.assertTrue((source / "index.theme").is_file())

        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / f"{theme_name}-Colorful"
            stats = generator.build_theme(source, destination, f"{theme_name} Colorful Test")

            print(
                f"REAL {theme_name} result: "
                f"symbolic={stats.symbolic_files}, "
                f"dynamic-before={stats.dynamic_before}, "
                f"reused-existing-color={stats.reused_existing_color}, "
                f"design-fallbacks={stats.designed_fallbacks}, "
                f"dynamic-remaining={stats.dynamic_remaining}",
                flush=True,
            )

            self.assertGreater(stats.symbolic_files, 0)
            self.assertGreater(stats.dynamic_before, 0)
            self.assertGreater(stats.reused_existing_color, 0)
            self.assertGreater(stats.designed_fallbacks, 0)
            self.assertEqual(stats.dynamic_remaining, 0)

            remaining = [
                path
                for path in destination.rglob("*.svg")
                if path.is_file() and generator.uses_dynamic_theme_color(path)
            ]
            self.assertEqual(remaining, [])

            representatives = (
                "22x22/actions/system-suspend.svg",
                "22x22/actions/system-suspend-hibernate.svg",
                "22x22/actions/system-reboot.svg",
                "22x22/actions/system-shutdown.svg",
                "22x22/actions/window-pin.svg",
            )
            replacement_targets = {item.target for item in stats.replacements}
            designed_targets = set(stats.designed)

            for rel in representatives:
                icon = destination / rel
                self.assertTrue(icon.is_file(), f"missing {theme_name}/{rel}")
                self.assertFalse(generator.uses_dynamic_theme_color(icon), rel)
                self.assertTrue(
                    rel in replacement_targets or rel in designed_targets,
                    f"representative icon was neither reused nor designed: {rel}",
                )

            index_text = (destination / "index.theme").read_text(encoding="utf-8")
            self.assertIn(f"Name={theme_name} Colorful Test", index_text)

    def test_real_papirus(self) -> None:
        self.assert_real_theme_is_design_colored("Papirus")

    def test_real_papirus_dark(self) -> None:
        self.assert_real_theme_is_design_colored("Papirus-Dark")

    def test_real_papirus_light(self) -> None:
        self.assert_real_theme_is_design_colored("Papirus-Light")


if __name__ == "__main__":
    unittest.main(verbosity=2)
