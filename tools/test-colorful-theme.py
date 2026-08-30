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
        '.ColorScheme-Highlight { color:#127bdc; } '
        '.ColorScheme-NeutralText { color:#ff9800; } '
        '.ColorScheme-PositiveText { color:#4caf50; } '
        '.ColorScheme-NegativeText { color:#f44336; }'
        '</style></defs>'
        f"{body}</svg>\n"
    )


def hls_values(color: str) -> tuple[float, float, float]:
    value = color.lstrip("#")
    r, g, b = (int(value[i : i + 2], 16) / 255 for i in (0, 2, 4))
    return colorsys.rgb_to_hls(r, g, b)


def hls_saturation(color: str) -> float:
    return hls_values(color)[2]


def hls_lightness(color: str) -> float:
    return hls_values(color)[1]


class ColorfulThemeTests(unittest.TestCase):
    def test_shared_xef_palette_drives_every_generator_role(self) -> None:
        palette = generator.XEF_COLORS
        light_palette = generator.XEF_LIGHT_COLORS
        self.assertEqual(
            generator.GENERATED_COLORS,
            {
                "blue": palette["generated_blue"],
                "green": palette["success"],
                "amber": palette["warning"],
                "red": palette["error"],
            },
        )
        self.assertEqual(
            generator.ADDITIONAL_COLORS,
            {name: palette[name] for name in ("yellow", "cyan", "purple", "pink")},
        )
        self.assertEqual(
            generator.LIGHT_GENERATED_COLORS,
            {
                "blue": light_palette["generated_blue"],
                "green": light_palette["success"],
                "amber": light_palette["warning"],
                "red": light_palette["error"],
            },
        )
        self.assertEqual(
            generator.LIGHT_ADDITIONAL_COLORS,
            {
                name: light_palette[name]
                for name in ("yellow", "cyan", "purple", "pink")
            },
        )
        self.assertEqual(generator.DESIGN_BRIGHT_LIMIT, palette["light_limit"])
        self.assertEqual(generator.DESIGN_DARK_LIMIT, palette["dark_limit"])

    def test_design_sources_and_generated_spec_exist(self) -> None:
        self.assertTrue(DESIGN_PATH.is_file())
        self.assertTrue(EXAMPLE_PATH.is_file())
        self.assertTrue(COLOR_SPEC_PATH.is_file())
        example = EXAMPLE_PATH.read_text(encoding="utf-8", errors="ignore").lower()
        for color in generator.DESIGN_COLORS.values():
            self.assertIn(color, example)

    def test_generated_semantic_palette_matches_papirus_more_closely(self) -> None:
        self.assertEqual(set(generator.GENERATED_COLORS), {"blue", "green", "amber", "red"})
        self.assertAlmostEqual(generator.GENERATED_SATURATION_CAP, 0.72)
        self.assertEqual(
            generator.GENERATED_LIGHTNESS_LIFTS,
            {"blue": 0.020, "green": 0.000, "amber": 0.015, "red": 0.010},
        )

        blue = generator.GENERATED_COLORS["blue"]
        self.assertEqual(
            blue,
            generator._muted_example_color(
                generator.DESIGN_COLORS["blue"],
                generator.GENERATED_LIGHTNESS_LIFTS["blue"],
            ),
        )
        self.assertLessEqual(
            hls_saturation(blue), generator.GENERATED_SATURATION_CAP + 0.005
        )

        # Regression values for the tuned generated-only palette. These remain
        # derived from examples-papirus.svg, but are much closer in strength to
        # real fixed-color Papirus artwork than the previous 58% palette.
        self.assertEqual(
            generator.GENERATED_COLORS,
            {
                "blue": "#4a91e1",
                "green": "#4caf50",
                "amber": "#ff9800",
                "red": "#f44336",
            },
        )

        self.assertLess(
            hls_saturation(generator.GENERATED_COLORS["blue"]),
            hls_saturation(generator.DESIGN_COLORS["blue"]),
        )
        self.assertGreater(
            hls_lightness(generator.GENERATED_COLORS["blue"]),
            hls_lightness(generator._muted_example_color(generator.DESIGN_COLORS["blue"])),
        )

    def test_variant_neutral_colors_are_theme_appropriate(self) -> None:
        self.assertEqual(generator.generated_neutral_color("Papirus-Dark"), "#cccccc")
        self.assertEqual(generator.generated_neutral_color("Papirus-Light"), "#5d5d5d")
        self.assertEqual(generator.generated_neutral_color("Papirus"), "#5d5d5d")

    def test_light_palette_has_graphical_object_contrast(self) -> None:
        def relative_luminance(color: str) -> float:
            channels = [int(color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
            linear = [
                value / 12.92
                if value <= 0.04045
                else ((value + 0.055) / 1.055) ** 2.4
                for value in channels
            ]
            return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

        background = relative_luminance("#e4e4e4")
        colors = {
            **generator.LIGHT_GENERATED_COLORS,
            **generator.LIGHT_ADDITIONAL_COLORS,
        }
        for family, color in colors.items():
            foreground = relative_luminance(color)
            ratio = (max(background, foreground) + 0.05) / (
                min(background, foreground) + 0.05
            )
            self.assertGreaterEqual(ratio, 3.0, family)

    def test_generated_function_groups_are_unified_and_unknown_is_neutral(self) -> None:
        base = Path("/tmp/Papirus/22x22/actions")
        expected = {
            "system-suspend.svg": "cyan",
            "system-suspend-hibernate.svg": "purple",
            "system-reboot.svg": "amber",
            "system-restart.svg": "amber",
            "system-shutdown.svg": "red",
            "session-switch.svg": "green",
            "window-pin.svg": "amber",
            "bookmark-new.svg": "amber",
            "favorite.svg": "amber",
            "list-add.svg": "green",
            "document-save.svg": "green",
            "edit-delete.svg": "red",
            "list-remove.svg": "red",
            "document-edit.svg": "neutral",
            "configure.svg": "neutral",
            "unlock.svg": "green",
            "system-log-out.svg": "red",
            "window-close.svg": "red",
            "audio-volume-low.svg": "neutral",
            "audio-volume-medium.svg": "neutral",
            "audio-volume-high.svg": "neutral",
            "audio-volume-muted.svg": "neutral",
            "network-wireless.svg": "neutral",
            "network-wired.svg": "neutral",
            "bluetooth-active.svg": "neutral",
            "network-wireless-limited.svg": "amber",
            "network-wireless-disconnected.svg": "amber",
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
            "view-media-album-cover.svg": "neutral",
            "view-media-artist.svg": "neutral",
            "view-media-genre.svg": "neutral",
            "view-media-playcount.svg": "neutral",
            "view-media-playlist.svg": "neutral",
            "view-media-track.svg": "neutral",
            "media-album-track.svg": "neutral",
            "media-playlist-play.svg": "neutral",
            "tools-rip-audio-cd.svg": "neutral",
            "icon_radio.svg": "neutral",
            "im-user.svg": "neutral",
            "folder-music.svg": "neutral",
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
        self.assertEqual(family, "neutral")
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

    def test_marked_baked_fallback_reuses_existing_color_art(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "Papirus"
            actions = source / "22x22/actions"
            apps = source / "22x22/apps"
            actions.mkdir(parents=True)
            apps.mkdir(parents=True)
            (source / "index.theme").write_text(
                "[Icon Theme]\nName=Papirus\nComment=fixture\nInherits=hicolor\n",
                encoding="utf-8",
            )
            (actions / "system-shutdown.svg").write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22">'
                f'{generator.SEMANTIC_FALLBACK_MARKER}'
                '<path fill="#e91e63" d="M1 1h20v20H1z"/></svg>\n',
                encoding="utf-8",
            )
            fixed_bytes = (
                '<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22">'
                '<path fill="#123456" d="M2 2h18v18H2z"/></svg>\n'
            ).encode()
            (apps / "system-shutdown.svg").write_bytes(fixed_bytes)

            destination = Path(temp_dir) / "out/Papirus-Colorful"
            stats = generator.build_theme(
                source,
                destination,
                "Papirus Colorful",
                polish_semantic_fallbacks=True,
            )
            target = destination / "22x22/actions/system-shutdown.svg"
            self.assertEqual(target.read_bytes(), fixed_bytes)
            self.assertEqual(stats.reused_existing_color, 1)
            self.assertEqual(stats.dynamic_remaining, 0)

    def test_replacement_only_mode_keeps_unmatched_semantic_art(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "Papirus"
            actions = source / "22x22/actions"
            actions.mkdir(parents=True)
            (source / "index.theme").write_text(
                "[Icon Theme]\nName=Papirus\nComment=fixture\nInherits=hicolor\n",
                encoding="utf-8",
            )
            source_svg = dynamic_svg(
                '<path class="ColorScheme-PositiveText" '
                'style="fill:currentColor" d="M1 1h20v20H1z"/>'
            )
            (actions / "unique-action.svg").write_text(source_svg, encoding="utf-8")

            destination = Path(temp_dir) / "out/Papirus-Colorful"
            stats = generator.build_theme(
                source,
                destination,
                "Papirus Colorful",
                generate_fallbacks=False,
            )
            target = destination / "22x22/actions/unique-action.svg"
            self.assertEqual(target.read_text(encoding="utf-8"), source_svg)
            self.assertEqual(stats.reused_existing_color, 0)
            self.assertEqual(stats.designed_fallbacks, 0)
            self.assertEqual(stats.dynamic_remaining, 1)

    def test_installer_keeps_unmarked_monochrome_icon_theme_aware(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "Papirus"
            actions = source / "22x22/actions"
            actions.mkdir(parents=True)
            (source / "index.theme").write_text(
                "[Icon Theme]\nName=Papirus\nComment=fixture\nInherits=hicolor\n",
                encoding="utf-8",
            )
            source_svg = dynamic_svg(
                '<path class="ColorScheme-Text" '
                'style="fill:currentColor" d="M1 1h20v20H1z"/>'
            )
            (actions / "view-list-details.svg").write_text(
                source_svg, encoding="utf-8"
            )

            destination = Path(temp_dir) / "out/Papirus-Colorful"
            stats = generator.build_theme(
                source,
                destination,
                "Papirus Colorful",
                generate_fallbacks=False,
                polish_semantic_fallbacks=True,
            )
            target = destination / "22x22/actions/view-list-details.svg"
            self.assertEqual(target.read_text(encoding="utf-8"), source_svg)
            self.assertIn("currentColor", source_svg)
            self.assertEqual(stats.designed_fallbacks, 0)
            self.assertEqual(stats.dynamic_remaining, 1)

    def test_polish_mode_layers_only_unmatched_marked_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "Papirus"
            actions = source / "22x22/actions"
            actions.mkdir(parents=True)
            (source / "index.theme").write_text(
                "[Icon Theme]\nName=Papirus\nComment=fixture\nInherits=hicolor\n",
                encoding="utf-8",
            )
            (actions / "view-conversation-balloon.svg").write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22">'
                '<!-- papirus-colorful-semantic-fallback:cyan -->'
                '<path fill="#00bcd4" d="M2 2h18v18H2z"/></svg>\n',
                encoding="utf-8",
            )

            destination = Path(temp_dir) / "out/Papirus-Colorful"
            stats = generator.build_theme(
                source,
                destination,
                "Papirus Colorful",
                generate_fallbacks=False,
                polish_semantic_fallbacks=True,
            )
            text = (destination / "22x22/actions/view-conversation-balloon.svg").read_text(
                encoding="utf-8"
            ).lower()
            self.assertIn("#00838f", text)
            self.assertIn("papirus-colorful-layering", text)
            self.assertIn('flood-opacity="0.2"', text)
            self.assertEqual(stats.reused_existing_color, 0)
            self.assertEqual(stats.designed_fallbacks, 1)
            self.assertEqual(dict(stats.family_counts), {"cyan": 1})

    def test_audited_neutral_marker_overrides_filename_heuristic(self) -> None:
        source = dynamic_svg(
            '<path class="ColorScheme-Text" style="fill:currentColor" '
            'd="M1 1h20v20H1z"/>'
        ).replace(
            '<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22">',
            '<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22">'
            '<!-- papirus-colorful-semantic-fallback:neutral -->',
        )
        changed, color, family = generator.replace_dynamic_markers(
            source,
            Path("/tmp/Papirus/22x22/actions/input-keyboard.svg"),
            "Papirus-Dark",
            default_family_override=generator.marked_semantic_family(source),
        )
        self.assertEqual(family, "neutral")
        self.assertEqual(color, "#cccccc")
        self.assertIn("#cccccc", changed)
        self.assertNotIn(generator.GENERATED_COLORS["blue"], changed)

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
            self.assertEqual(dict(stats.family_counts), {"cyan": 1})
            self.assertIn(generator.LIGHT_ADDITIONAL_COLORS["cyan"], text)
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
            self.assertIn(generator.LIGHT_GENERATED_COLORS["red"], text)
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
                "22x22/actions/system-suspend.svg": "cyan",
                "22x22/actions/system-suspend-hibernate.svg": "purple",
                "22x22/actions/system-reboot.svg": "amber",
                "22x22/actions/system-shutdown.svg": "red",
                "22x22/actions/window-pin.svg": "yellow",
            }
            replacements = {item.target for item in stats.replacements}
            designed = set(stats.designed)
            for rel, family in expected.items():
                icon = destination / rel
                self.assertTrue(icon.is_file(), f"missing {theme_name}/{rel}")
                self.assertFalse(generator.uses_dynamic_theme_color(icon), rel)
                if rel in designed:
                    additional = (
                        generator.ADDITIONAL_COLORS
                        if theme_name == "Papirus-Dark"
                        else generator.LIGHT_ADDITIONAL_COLORS
                    )
                    generated = (
                        generator.GENERATED_COLORS
                        if theme_name == "Papirus-Dark"
                        else generator.LIGHT_GENERATED_COLORS
                    )
                    expected_color = additional.get(
                        family, generated.get(family)
                    )
                    self.assertIsNotNone(expected_color, family)
                    self.assertIn(
                        expected_color,
                        icon.read_text(encoding="utf-8", errors="ignore").lower(),
                        rel,
                    )
                elif rel in replacements:
                    self.assertIn(rel, replacements)
                else:
                    # A custom family is already a fixed fill because Plasma
                    # drops unknown ColorScheme classes. It needs neither a
                    # genuine-art replacement nor generated dynamic fallback.
                    text = icon.read_text(encoding="utf-8", errors="ignore")
                    self.assertEqual(generator.marked_semantic_family(text), family)
                    additional = (
                        generator.ADDITIONAL_COLORS
                        if theme_name == "Papirus-Dark"
                        else generator.LIGHT_ADDITIONAL_COLORS
                    )
                    self.assertIn(additional[family], text.lower())

    def test_real_papirus(self) -> None:
        self.assert_real_theme("Papirus")

    def test_real_papirus_dark(self) -> None:
        self.assert_real_theme("Papirus-Dark")

    def test_real_papirus_light(self) -> None:
        self.assert_real_theme("Papirus-Light")


if __name__ == "__main__":
    unittest.main(verbosity=2)
