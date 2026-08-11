#!/usr/bin/env python3
"""Tests for tools/make-colorful-theme.py.

This intentionally includes both a tiny regression fixture and a full build of
this repository's real Papirus-Dark theme. The latter exists so a change that
silently produces `Symbolic: 0` or merely copies another currentColor icon
cannot pass CI again.
"""

from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest
from collections import Counter
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATOR_PATH = REPO_ROOT / "tools" / "make-colorful-theme.py"

spec = importlib.util.spec_from_file_location("make_colorful_theme", GENERATOR_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Could not load {GENERATOR_PATH}")

generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)


class ColorfulThemeTests(unittest.TestCase):
    def test_relative_papirus_symlinks_are_followed_and_replaced(self) -> None:
        """Regression test for Papirus-Dark's ../../Papirus/... symlinks."""
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

            # Match the real layout used by Papirus-Dark.
            os.symlink("../../Papirus/22x22/status", dark / "22x22" / "status")
            os.symlink("../../Papirus/22x22/symbolic", dark / "22x22" / "symbolic")

            destination = Path(temp_dir) / "out" / "Papirus-Dark-Colorful"
            total, replaced, unresolved = generator.build_theme(
                dark,
                destination,
                "Papirus-Dark Colorful",
            )

            generated = destination / "22x22" / "symbolic" / "status" / "network-wireless-symbolic.svg"
            generated_text = generated.read_text(encoding="utf-8")

            self.assertEqual(total, 1)
            self.assertEqual(replaced, 1)
            self.assertEqual(unresolved, [])
            self.assertFalse(generator.uses_dynamic_theme_color(generated))
            self.assertIn("#3999e6", generated_text)
            self.assertNotIn("currentColor", generated_text)

    def test_real_papirus_dark_build_produces_fixed_color_audio_icon(self) -> None:
        """Build the actual fork and verify a real Plasma tray icon is colorful."""
        source = REPO_ROOT / "Papirus-Dark"
        self.assertTrue((source / "index.theme").is_file())

        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / "Papirus-Dark-Colorful"
            total, replaced, unresolved = generator.build_theme(
                source,
                destination,
                "Papirus-Dark Colorful Test",
            )

            unique_unresolved = sorted({generator.normalized_stem(path) for path in unresolved})
            context_counts = Counter(
                generator.context_key(path, destination) or "unknown" for path in unresolved
            )
            already_fixed = total - replaced - len(unresolved)
            print(
                f"REAL Papirus-Dark result: symbolic={total}, already-fixed={already_fixed}, "
                f"replaced={replaced}, unresolved={len(unresolved)}, "
                f"unique-unresolved={len(unique_unresolved)}",
                flush=True,
            )
            print(
                "UNRESOLVED contexts: "
                + ", ".join(f"{name}={count}" for name, count in sorted(context_counts.items())),
                flush=True,
            )
            print(
                "UNRESOLVED sample: " + ", ".join(unique_unresolved[:120]),
                flush=True,
            )

            self.assertGreater(total, 0, "real Papirus-Dark build found zero symbolic icons")
            self.assertGreater(replaced, 0, "real Papirus-Dark build replaced zero dynamic symbolic icons")

            # Plasma PA explicitly asks for audio-volume-high-symbolic. The
            # generated theme must therefore keep that name but provide actual
            # fixed-color artwork. Papirus' 22x22 panel icon is also currentColor,
            # so this additionally catches selecting a visually monochrome
            # non-symbolic candidate by mistake.
            audio = destination / "22x22" / "symbolic" / "status" / "audio-volume-high-symbolic.svg"
            self.assertTrue(audio.is_file(), f"missing generated representative icon: {audio}")
            audio_text = audio.read_text(encoding="utf-8", errors="ignore")
            self.assertFalse(
                generator.uses_dynamic_theme_color(audio),
                "audio-volume-high-symbolic is still theme/currentColor artwork",
            )
            self.assertNotIn("currentColor", audio_text)
            self.assertIn("#3999e6", audio_text.lower())

            index_text = (destination / "index.theme").read_text(encoding="utf-8")
            self.assertIn("Name=Papirus-Dark Colorful Test", index_text)
            self.assertIn("Inherits=hicolor", index_text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
