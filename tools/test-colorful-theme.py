#!/usr/bin/env python3
"""Regression tests for tools/make-colorful-theme.py.

The important regression cases are KDE's ordinary currentColor action icons, not
just ``*-symbolic`` names. Full builds of Papirus, Papirus-Dark and Papirus-Light
must leave no dynamic color markers. Fixtures also prove that an existing
variant-specific colored icon wins over semantic recoloring.
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


PALETTE_LIGHT = (
    ".ColorScheme-Text { color:#444444; } "
    ".ColorScheme-Highlight { color:#4285f4; } "
    ".ColorScheme-NeutralText { color:#ff9800; } "
    ".ColorScheme-PositiveText { color:#4caf50; } "
    ".ColorScheme-NegativeText { color:#f44336; }"
)
PALETTE_DARK = PALETTE_LIGHT.replace("#444444", "#dfdfdf")


def dynamic_svg(body: str, *, palette: str = PALETTE_LIGHT) -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22">'
        f'<defs><style>{palette}</style></defs>{body}</svg>\n'
    )


class ColorfulThemeTests(unittest.TestCase):
    def test_relative_papirus_symlinks_are_followed(self) -> None:
        """Papirus-Dark's ../../Papirus/... links must still be dereferenced."""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "repo"
            papirus = root / "Papirus" / "22x22"
            dark = root / "Papirus-Dark"

            (papirus / "status").mkdir(parents=True)
            (papirus / "symbolic" / "status").mkdir(parents=True)
            (dark / "22x22").mkdir(parents=True)

            fixed = papirus / "status" / "network-wireless.svg"
            symbolic = papirus / "symbolic" / "status" / "network-wireless-symbolic.svg"
            fixed_bytes = (
                '<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22">'
                '<path fill="#123456" d="M1 1h20v20H1z"/></svg>\n'
            ).encode()
            fixed.write_bytes(fixed_bytes)
            symbolic.write_text(
                dynamic_svg('<path class="ColorScheme-Text" style="fill:currentColor" d="M1 1h20v20H1z"/>', palette=PALETTE_DARK),
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
            self.assertEqual(stats.dynamic_remaining, 0)
            self.assertEqual(generated.read_bytes(), fixed_bytes)

    def test_existing_light_and_dark_color_variants_are_respected(self) -> None:
        """Same semantic icon may have different fixed art in light and dark themes."""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "repo"

            outputs: dict[str, bytes] = {}
            for theme_name, palette, fixed_color in (
                ("Papirus-Light", PALETTE_LIGHT, "#102030"),
                ("Papirus-Dark", PALETTE_DARK, "#d0e0f0"),
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
                    dynamic_svg('<path class="ColorScheme-Text" style="fill:currentColor" d="M1 1h20v20H1z"/>', palette=palette),
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
                self.assertEqual(stats.recolored_semantic, 0)
                self.assertEqual(stats.dynamic_remaining, 0)
                outputs[theme_name] = generated.read_bytes()
                self.assertEqual(outputs[theme_name], fixed_bytes)

            self.assertNotEqual(outputs["Papirus-Light"], outputs["Papirus-Dark"])

    def test_plain_action_icons_get_semantic_papirus_colors(self) -> None:
        """Power/context-menu style currentColor actions must become colored."""
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "Papirus"
            actions = source / "22x22/actions"
            actions.mkdir(parents=True)
            (source / "index.theme").write_text(
                "[Icon Theme]\nName=Papirus\nComment=fixture\nInherits=hicolor\n",
                encoding="utf-8",
            )

            for name in (
                "system-suspend.svg",
                "system-suspend-hibernate.svg",
                "system-reboot.svg",
                "system-shutdown.svg",
                "window-pin.svg",
                "list-add.svg",
                "edit-delete.svg",
            ):
                (actions / name).write_text(
                    dynamic_svg('<path class="ColorScheme-Text" style="fill:currentColor" d="M1 1h20v20H1z"/>'),
                    encoding="utf-8",
                )

            destination = Path(temp_dir) / "out" / "Papirus-Colorful"
            stats = generator.build_theme(source, destination, "Papirus Colorful")

            self.assertEqual(stats.reused_existing_color, 0)
            self.assertEqual(stats.recolored_semantic, 7)
            self.assertEqual(stats.dynamic_remaining, 0)

            expected = {
                "system-suspend.svg": "#ff9800",
                "system-suspend-hibernate.svg": "#ff9800",
                "system-reboot.svg": "#4285f4",
                "system-shutdown.svg": "#f44336",
                "window-pin.svg": "#ff9800",
                "list-add.svg": "#4caf50",
                "edit-delete.svg": "#f44336",
            }
            for name, color in expected.items():
                text = (destination / "22x22/actions" / name).read_text(encoding="utf-8").lower()
                self.assertIn(color, text, name)
                self.assertNotIn("currentcolor", text, name)

    def assert_real_theme_is_fully_fixed_color(self, theme_name: str) -> None:
        source = REPO_ROOT / theme_name
        self.assertTrue((source / "index.theme").is_file())

        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / f"{theme_name}-Colorful"
            stats = generator.build_theme(source, destination, f"{theme_name} Colorful Test")
            palette = dict(stats.palette)

            print(
                f"REAL {theme_name} result: "
                f"symbolic={stats.symbolic_files}, "
                f"dynamic-before={stats.dynamic_before}, "
                f"reused-existing-color={stats.reused_existing_color}, "
                f"semantic-recolors={stats.recolored_semantic}, "
                f"dynamic-remaining={stats.dynamic_remaining}, "
                f"palette={palette}",
                flush=True,
            )

            self.assertGreater(stats.symbolic_files, 0)
            self.assertGreater(stats.dynamic_before, 0)
            self.assertGreater(stats.reused_existing_color, 0)
            self.assertGreater(stats.recolored_semantic, 0)
            self.assertEqual(stats.dynamic_remaining, 0)

            remaining = [
                path
                for path in destination.rglob("*.svg")
                if path.is_file() and generator.uses_dynamic_theme_color(path)
            ]
            self.assertEqual(remaining, [])

            # These are the monochrome controls visible in KDE Kickoff/context
            # menus from the screenshot that motivated this change.
            representatives = {
                "22x22/actions/system-suspend.svg": "NeutralText",
                "22x22/actions/system-suspend-hibernate.svg": "NeutralText",
                "22x22/actions/system-reboot.svg": "Highlight",
                "22x22/actions/system-shutdown.svg": "NegativeText",
                "22x22/actions/window-pin.svg": "NeutralText",
            }

            replacement_targets = {item.target for item in stats.replacements}
            recolored_targets = set(stats.recolored)

            for rel, semantic_key in representatives.items():
                icon = destination / rel
                self.assertTrue(icon.is_file(), f"missing representative icon: {theme_name}/{rel}")
                self.assertFalse(generator.uses_dynamic_theme_color(icon), rel)

                # If Papirus ships real fixed-color art, using it is preferred.
                # Otherwise verify our fallback baked the selected variant's own
                # semantic palette color into the original action icon.
                if rel in recolored_targets:
                    self.assertIn(palette[semantic_key], icon.read_text(encoding="utf-8", errors="ignore").lower())
                else:
                    self.assertIn(rel, replacement_targets)

            index_text = (destination / "index.theme").read_text(encoding="utf-8")
            self.assertIn(f"Name={theme_name} Colorful Test", index_text)

    def test_real_papirus_is_fully_fixed_color(self) -> None:
        self.assert_real_theme_is_fully_fixed_color("Papirus")

    def test_real_papirus_dark_is_fully_fixed_color(self) -> None:
        self.assert_real_theme_is_fully_fixed_color("Papirus-Dark")

    def test_real_papirus_light_is_fully_fixed_color(self) -> None:
        self.assert_real_theme_is_fully_fixed_color("Papirus-Light")


if __name__ == "__main__":
    unittest.main(verbosity=2)
