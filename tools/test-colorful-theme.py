#!/usr/bin/env python3
"""Regression tests for semantic, theme-aware generated Papirus fallbacks."""

from __future__ import annotations

import colorsys
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
COLOR_SPEC_PATH = REPO_ROOT / "tools" / "work" / "generated-color-spec.md"

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


def hls_saturation(color: str) -> float:
    value = color.lstrip("#")
    r, g, b = (int(value[i : i + 2], 16) / 255 for i in (0, 2, 4))
    return colorsys.rgb_to_hls(r, g, b)[2]


class ColorfulThemeTests(unittest.TestCase):
    def test_design_sources_and_generated_spec_exist(self) -> None:
        self.assertTrue(DESIGN_PATH.is_file())
        self.assertTrue(EXAMPLE_PATH.is_file())
        self.assertTrue(COLOR_SPEC_PATH.is_file())
        example = EXAMPLE_PATH.read_text(encoding="utf-8", errors="ignore").lower()
        for color in generator.DESIGN_COLORS.values():
            self.assertIn(color, example)

    def test_generated_semantic_palette_has_restored_strength(self) -> None:
        self.assertEqual(set(generator.GENERATED_COLORS), {"blue", "green", "amber", "red"})
        self.assertAlmostEqual(generator.GENERATED_SATURATION_CAP, 0.58)

        source_map = {
            "blue": "blue",
            "green": "green",
            "amber": "orange",
            "red": "red",
        }
        for family, source_name in source_map.items():
            color = generator.GENERATED_COLORS[family]
            self.assertEqual(color, generator._muted_example_color(generator.DESIGN_COLORS[source_name]))
            self.assertLessEqual(
                hls_saturation(color),
                generator.GENERATED_SATURATION_CAP + 0.005,
                family,
            )

        # The high-saturation anchors are still softened, just less aggressively
        # than the previous 45% cap.
        self.assertLess(
            hls_saturation(generator.GENERATED_COLORS["blue"]),
            hls_saturation(generator.DESIGN_COLORS["blue"]),
        )
        self.assertLess(
            hls_saturation(generator.GENERATED_COLORS["amber"]),
            hls_saturation(generator.DESIGN_COLORS["orange"]),
        )

    def test_variant_neutral_colors_are_theme_appropriate(self) -> None:
        self.assertEqual(generator.generated_neutral_color("Papirus-Dark"), "#cccccc")
        self.assertEqual(generator.generated_neutral_color("Papirus-Light"), "#5d5d5d")
        self.assertEqual(generator.generated_neutral_color("Papirus"), "#5d5d5d")

    def test_generated_function_groups_are_unified_and_unknown_is_neutral(self) -> None:
        base = Path("/tmp/Papirus/22x22/actions")
        expected = {
            "system-suspend.svg": "amber",
            "system-suspend-hibernate.svg": "amber",
            "system-reboot.svg": "blue",
            "system-restart.svg": "blue",
            "system-shutdown.svg": "red",
            "session-switch.svg": "blue",
            "window-pin.svg": "amber",
            "bookmark-new.svg": "amber",
            "favorite.svg": "amber",
            "list-add.svg": "green",
            "document-save.svg": "green",
            "edit-delete.svg": "red",
            "list-remove.svg": "red",
            "document-edit.svg": "blue",
            "configure.svg": "blue",
            "unlock.svg": "green",
            "system-log-out.svg": "red",
            "window-close.svg": "red",
            "audio-volume-low.svg": "blue",
            "audio-volume-medium.svg": "blue",
            "audio-volume-high.svg": "blue",
            "audio-volume-muted.svg": "red",
            "network-wireless.svg": "blue",
            "network-wired.svg": "blue",
            "bluetooth-active.svg": "blue",
            "network-wireless-limited.svg": "amber",
            "network-wireless-disconnected.svg": "red",
            "battery-level-100.svg": "green",
            "battery-level-55.svg": "green",
            "battery-level-40.svg": "amber",
            "battery-level-20.svg": "amber",
            "battery-level-15.svg": "red",
            "battery-level-0.svg": "red",
            "battery-charging.svg": "green",
            # No semantic reason to color these blue merely because they exist.
            "view-list-details.svg": "neutral",
            "draw-freehand.svg": "neutral",
            "transform-move.svg": "neutral",
        }
        for name, family in expected.items():
            self.assertEqual(generator.generated_color_family(base / name), family, name)

    def test_explicit_kde_semantic_class_overrides_default_family(self) -> None:
        path = Path("/tmp/Papirus/22x22/actions/settings.svg")
        text = dynamic_svg(
            '<path class="ColorScheme-NegativeText" style="fill:currentColor" '
            'd="M1 1h20v20H1z"/>'
        )
        changed, _base, family = generator.replace_dynamic_markers(
            text, path, "Papirus-Dark"
        )
        self.assertEqual(family, "blue")
        self.assertIn(generator.GENERATED_COLORS["red"], changed.lower())
        self.assertNotIn("currentcolor", changed.lower())

    def test_unknown_generated_icon_uses_variant_neutral(self) -> None:
        path = Path("/tmp/Papirus/22x22/actions/view-list-details.svg")
        source = dynamic_svg(
            '<path class="ColorScheme-Text" style="fill:currentColor" '
            'd="M1 1h20v20H1z"/>'
        )

        dark, _color, family = generator.replace_dynamic_markers(
            source, path, "Papirus-Dark"
        )
        light, _color2, family2 = generator.replace_dynamic_markers(
            source, path, "Papirus-Light"
        )
        self.assertEqual(family, "neutral")
        self.assertEqual(family2, "neutral")
        self.assertIn("#cccccc", dark.lower())
        self.assertIn("#5d5d5d", light.lower())
        self.assertNotEqual(dark, light)

    def test_relative_papirus_symlinks_are_followed_and_fixed_art_wins(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "repo"
            papirus = root / "Papirus" / "22x22"
            dark = root / "Papirus-Dark"
            (papirus / "status").mkdir(parents=True)
            (papirus / "symbolic" / "status").mkdir(parents=True)
            (dark / "22x22").mkdir(parents=True)

            fixed_bytes = (
                '<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22">'
                '<path fill="#123456" d="M1 1h20v20H1z"/></svg>\n'
            ).encode()
            (papirus / "status" / "network-wireless.svg").write_bytes(fixed_bytes)
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

    def test_22px_semantic_fallback_uses_design_effects(self) -> None:
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
            text = (destination / "22x22/actions/system-suspend.svg").read_text(
                encoding="utf-8"
            ).lower()
            self.assertEqual(dict(stats.family_counts), {"amber": 1})
            self.assertIn(generator.GENERATED_COLORS["amber"], text)
            self.assertIn('flood-color="#000000"', text)
            self.assertIn('flood-opacity="0.2"', text)
            self.assertIn('flood-color="#ffffff"', text)
            self.assertIn('dy="0.5"', text)
            self.assertNotIn("currentcolor", text)
            self.assertNotIn("<lineargradient", text)
            self.assertNotIn("<radialgradient", text)

    def test_neutral_dark_and_light_effect_opacity(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for theme_name, expected_color, expected_highlight in (
                ("Papirus-Dark", "#cccccc", "0.2"),
                ("Papirus-Light", "#5d5d5d", "0.1"),
            ):
                source = root / theme_name
                actions = source / "22x22/actions"
                actions.mkdir(parents=True)
                (source / "index.theme").write_text(
                    f"[Icon Theme]\nName={theme_name}\nComment=fixture\nInherits=hicolor\n",
                    encoding="utf-8",
                )
                (actions / "view-list-details.svg").write_text(
                    dynamic_svg(
                        '<path class="ColorScheme-Text" style="fill:currentColor" '
                        'd="M2 2h18v18H2z"/>'
                    ),
                    encoding="utf-8",
                )
                destination = root / "out" / f"{theme_name}-Colorful"
                stats = generator.build_theme(source, destination, f"{theme_name} Colorful")
                text = (destination / "22x22/actions/view-list-details.svg").read_text(
                    encoding="utf-8"
                ).lower()
                self.assertEqual(dict(stats.family_counts), {"neutral": 1})
                self.assertEqual(stats.neutral_color, expected_color)
                self.assertIn(expected_color, text)
                self.assertIn(f'flood-opacity="{expected_highlight}"', text)

    def test_16px_generated_fallback_has_no_generated_shadow_or_highlight(self) -> None:
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
            self.assertIn(generator.GENERATED_COLORS["red"], text)
            self.assertNotIn("papirus-colorful-layering", text)
            self.assertNotIn("currentcolor", text)

    def assert_real_theme(self, theme_name: str) -> None:
        source = REPO_ROOT / theme_name
        self.assertTrue((source / "index.theme").is_file())
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / f"{theme_name}-Colorful"
            stats = generator.build_theme(source, destination, f"{theme_name} Colorful Test")
            families = dict(stats.family_counts)
            print(
                f"REAL {theme_name} result: "
                f"symbolic={stats.symbolic_files}, "
                f"dynamic-before={stats.dynamic_before}, "
                f"reused-existing-color={stats.reused_existing_color}, "
                f"generated-fallbacks={stats.designed_fallbacks}, "
                f"dynamic-remaining={stats.dynamic_remaining}, "
                f"families={families}, neutral={stats.neutral_color}, "
                f"palette={generator.GENERATED_COLORS}",
                flush=True,
            )
            self.assertGreater(stats.symbolic_files, 0)
            self.assertGreater(stats.dynamic_before, 0)
            self.assertGreater(stats.reused_existing_color, 0)
            self.assertGreater(stats.designed_fallbacks, 0)
            self.assertEqual(stats.dynamic_remaining, 0)
            self.assertGreater(families.get("neutral", 0), 0)
            for family in ("amber", "blue", "green", "red"):
                self.assertGreater(families.get(family, 0), 0, family)

            remaining = [
                path for path in destination.rglob("*.svg")
                if path.is_file() and generator.uses_dynamic_theme_color(path)
            ]
            self.assertEqual(remaining, [])

            expected = {
                "22x22/actions/system-suspend.svg": "amber",
                "22x22/actions/system-suspend-hibernate.svg": "amber",
                "22x22/actions/system-reboot.svg": "blue",
                "22x22/actions/system-shutdown.svg": "red",
                "22x22/actions/window-pin.svg": "amber",
            }
            replacements = {item.target for item in stats.replacements}
            designed = set(stats.designed)
            for rel, family in expected.items():
                icon = destination / rel
                self.assertTrue(icon.is_file(), f"missing {theme_name}/{rel}")
                self.assertFalse(generator.uses_dynamic_theme_color(icon), rel)
                if rel in designed:
                    self.assertIn(
                        generator.GENERATED_COLORS[family],
                        icon.read_text(encoding="utf-8", errors="ignore").lower(),
                        rel,
                    )
                else:
                    self.assertIn(rel, replacements)

    def test_real_papirus(self) -> None:
        self.assert_real_theme("Papirus")

    def test_real_papirus_dark(self) -> None:
        self.assert_real_theme("Papirus-Dark")

    def test_real_papirus_light(self) -> None:
        self.assert_real_theme("Papirus-Light")


if __name__ == "__main__":
    unittest.main(verbosity=2)
