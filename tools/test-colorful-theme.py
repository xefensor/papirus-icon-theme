#!/usr/bin/env python3
"""Tests for tools/make-colorful-theme.py.

This intentionally includes both a tiny regression fixture and a full build of
this repository's real Papirus-Dark theme. The latter exists so a change that
silently produces `Symbolic: 0` cannot pass CI again.
"""

from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest
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
            colorful.write_text("COLORFUL-ARTWORK\n", encoding="utf-8")
            symbolic.write_text("MONOCHROME-ARTWORK\n", encoding="utf-8")

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
            total, replaced, unmatched = generator.build_theme(
                dark,
                destination,
                "Papirus-Dark Colorful",
            )

            self.assertEqual(total, 1)
            self.assertEqual(replaced, 1)
            self.assertEqual(unmatched, [])
            self.assertEqual(
                (destination / "22x22" / "symbolic" / "status" / "network-wireless-symbolic.svg").read_text(
                    encoding="utf-8"
                ),
                "COLORFUL-ARTWORK\n",
            )

    def test_real_papirus_dark_build_contains_and_replaces_symbolic_icons(self) -> None:
        """Build the actual fork so CI catches a real-world Symbolic: 0 result."""
        source = REPO_ROOT / "Papirus-Dark"
        self.assertTrue((source / "index.theme").is_file())

        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / "Papirus-Dark-Colorful"
            total, replaced, _unmatched = generator.build_theme(
                source,
                destination,
                "Papirus-Dark Colorful Test",
            )

            self.assertGreater(total, 0, "real Papirus-Dark build found zero symbolic icons")
            self.assertGreater(replaced, 0, "real Papirus-Dark build replaced zero symbolic icons")

            index_text = (destination / "index.theme").read_text(encoding="utf-8")
            self.assertIn("Name=Papirus-Dark Colorful Test", index_text)
            self.assertIn("Inherits=hicolor", index_text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
