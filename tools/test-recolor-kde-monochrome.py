#!/usr/bin/env python3
"""Regression tests for the in-place KDE monochrome semantic pass."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


sys.dont_write_bytecode = True

SCRIPT = Path(__file__).with_name("recolor-kde-monochrome.py")
SPEC = importlib.util.spec_from_file_location("recolor_kde_monochrome", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Could not load {SCRIPT}")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def family(name: str, context: str = "actions") -> str:
    return MODULE.decide_family(Path(name), context).family


def svg() -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg"><defs>'
        '<style id="current-color-scheme" type="text/css">'
        '.ColorScheme-Text { color:#444444; } '
        '.ColorScheme-Highlight { color:#4285f4; } '
        '.ColorScheme-NeutralText { color:#ff9800; } '
        '.ColorScheme-PositiveText { color:#4caf50; } '
        '.ColorScheme-NegativeText { color:#f44336; }'
        '</style></defs>'
        '<path class="ColorScheme-Text" style="fill:currentColor" d="M0 0h1v1z"/>'
        '</svg>'
    )


class SemanticDecisionTests(unittest.TestCase):
    def test_reviewed_and_common_actions(self) -> None:
        expected = {
            "edit-cut.svg": "orange",
            "edit-copy.svg": "blue",
            "edit-paste.svg": "green",
            "list-add.svg": "green",
            "list-remove.svg": "red",
            "window-close.svg": "red",
            "media-record.svg": "red",
            "media-playback-start.svg": "green",
            "media-playback-pause.svg": "orange",
            "media-playback-next.svg": "neutral",
            "network-connect.svg": "green",
            "network-disconnect.svg": "orange",
            "document-share.svg": "cyan",
            "audio-volume-high.svg": "neutral",
            "draw-freehand.svg": "purple",
            "y-zoom-in.svg": "green",
            "dialog-password.svg": "yellow",
            "dialog-information.svg": "blue",
        }
        for name, expected_family in expected.items():
            self.assertEqual(family(name), expected_family, name)

    def test_precedence_avoids_substring_traps(self) -> None:
        expected = {
            "display-brightness.svg": "blue",
            "indicator-videocard.svg": "blue",
            "system-restart.svg": "orange",
            "system-unlock.svg": "green",
            "rating-unrated.svg": "neutral",
            "weather-clear.svg": "yellow",
            "password-show-off.svg": "neutral",
            "network-wireless-offline.svg": "orange",
            "code-block.svg": "blue",
            "fcitx-pinyin.svg": "neutral",
            "folder-remote.svg": "blue",
            "radiotray_off.svg": "neutral",
            "camera-video.svg": "purple",
            "view-bank.svg": "green",
            "kstars_grid.svg": "neutral",
            "view-multiple-objects.svg": "neutral",
            "connector-avoid.svg": "neutral",
            "folder-adwaita.svg": "blue",
            "go-next.svg": "neutral",
            "format-text-bold.svg": "neutral",
            "input-keyboard.svg": "neutral",
            "go-bottom.svg": "neutral",
            "selection-start.svg": "neutral",
            "media-eject.svg": "neutral",
            "media-playback-paused.svg": "orange",
            "media-playback-playing.svg": "green",
        }
        for name, expected_family in expected.items():
            context = "panel" if name == "weather-clear.svg" else "actions"
            self.assertEqual(family(name, context), expected_family, name)

    def test_battery_thresholds(self) -> None:
        expected = {
            "battery-level-100.svg": "green",
            "battery-level-55.svg": "green",
            "battery-level-40.svg": "orange",
            "battery-level-15.svg": "red",
            "battery-charging.svg": "green",
            "battery-missing.svg": "red",
            "keyboard-battery-low.svg": "red",
            "battery-caution.svg": "orange",
            "battery.svg": "neutral",
            "battery-000.svg": "red",
            "battery-020.svg": "orange",
            "battery-080.svg": "green",
            "battery-000-charging.svg": "green",
        }
        for name, expected_family in expected.items():
            self.assertEqual(family(name, "panel"), expected_family, name)

    def test_context_defaults_are_deliberate(self) -> None:
        self.assertEqual(family("folder-project.svg", "places"), "blue")
        self.assertEqual(family("drive-removable.svg", "devices"), "blue")
        self.assertEqual(family("align-horizontal-center.svg"), "neutral")
        self.assertEqual(family("edit-select-all.svg"), "neutral")
        self.assertEqual(family("transform-rotate.svg"), "neutral")
        self.assertEqual(family("configure.svg"), "neutral")


class RecolorTests(unittest.TestCase):
    def test_builtin_semantic_class(self) -> None:
        changed = MODULE.recolor_text(svg(), "Papirus", MODULE.Decision("green", "test"))
        self.assertIn('class="ColorScheme-PositiveText"', changed)
        self.assertNotIn('class="ColorScheme-Text"', changed)
        self.assertIn("papirus-colorful-semantic-fallback:green", changed)

    def test_extended_palette_uses_fixed_fills_for_plasma(self) -> None:
        expectations = {
            "yellow": ("ColorScheme-YellowText", "#f9a825"),
            "cyan": ("ColorScheme-CyanText", "#00bcd4"),
            "purple": ("ColorScheme-PurpleText", "#9c27b0"),
            "pink": ("ColorScheme-PinkText", "#e91e63"),
        }
        for color_family, (class_name, color) in expectations.items():
            with self.subTest(color_family=color_family):
                changed = MODULE.recolor_text(
                    svg(), "Papirus", MODULE.Decision(color_family, "test")
                )
                self.assertIn(f"fill:{color}", changed)
                self.assertNotIn(f'class="{class_name}"', changed)
                self.assertNotIn(f".{class_name} {{", changed)
                self.assertIn(
                    f"papirus-colorful-semantic-fallback:{color_family}", changed
                )

        dark_yellow = MODULE.recolor_text(
            svg(), "Papirus-Dark", MODULE.Decision("yellow", "test")
        )
        self.assertIn("#fecd38", dark_yellow)

    def test_recoloring_is_idempotent(self) -> None:
        once = MODULE.recolor_text(svg(), "Papirus", MODULE.Decision("cyan", "test"))
        twice = MODULE.recolor_text(once, "Papirus", MODULE.Decision("cyan", "test"))
        self.assertEqual(once, twice)
        self.assertEqual(once.count("#00bcd4"), 1)

    def test_old_custom_class_is_migrated_from_current_color(self) -> None:
        source = svg().replace(
            'class="ColorScheme-Text"', 'class="ColorScheme-PinkText"'
        ).replace(
            "</style>", " .ColorScheme-PinkText { color:#e91e63; }</style>"
        )
        changed = MODULE.recolor_text(
            source, "Papirus", MODULE.Decision("pink", "test")
        )
        self.assertIn("fill:#e91e63", changed)
        self.assertNotIn("ColorScheme-PinkText", changed)
        self.assertNotIn("currentColor", changed.split("</style>", 1)[1])

    def test_previous_generated_family_can_return_to_neutral(self) -> None:
        colored = MODULE.recolor_text(
            svg(), "Papirus", MODULE.Decision("green", "old")
        )
        neutral = MODULE.recolor_text(
            colored, "Papirus", MODULE.Decision("neutral", "audit")
        )
        self.assertIn('class="ColorScheme-Text"', neutral)
        self.assertNotIn('class="ColorScheme-PositiveText"', neutral)
        self.assertIn("papirus-colorful-semantic-fallback:neutral", neutral)

    def test_previous_baked_custom_family_can_be_reassigned(self) -> None:
        pink = MODULE.recolor_text(
            svg(), "Papirus", MODULE.Decision("pink", "old")
        )
        blue = MODULE.recolor_text(
            pink, "Papirus", MODULE.Decision("blue", "audit")
        )
        self.assertNotIn("#e91e63", blue)
        self.assertIn('class="ColorScheme-Highlight"', blue)
        self.assertIn("papirus-colorful-semantic-fallback:blue", blue)

    def test_existing_explicit_semantic_paths_are_preserved(self) -> None:
        source = svg().replace(
            "</svg>",
            '<path class="ColorScheme-NegativeText error" '
            'style="fill:currentColor" d="M1 1h1v1z"/></svg>',
        )
        changed = MODULE.recolor_text(
            source, "Papirus", MODULE.Decision("blue", "test")
        )
        self.assertIn('class="ColorScheme-Highlight"', changed)
        self.assertIn('class="ColorScheme-NegativeText error"', changed)

    def test_disconnect_action_is_not_left_faded(self) -> None:
        source = svg().replace("fill:currentColor", "fill:currentColor;opacity:.35")
        changed = MODULE.recolor_text(
            source,
            "Papirus",
            MODULE.Decision("orange", "test"),
            "network-disconnect",
        )
        self.assertIn('class="ColorScheme-NeutralText"', changed)
        self.assertNotIn("opacity:.35", changed)


if __name__ == "__main__":
    unittest.main()
