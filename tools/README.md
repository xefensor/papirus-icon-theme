# Tools

* `ffsvg.sh PATH...` — finds, fixes and cleans SVG files
* `_clean_attrs.sed` — removes unused attributes and removes attributes with default values from elements inside SVG files (part of `ffsvg.sh`)
* `_clean_style_attr.sed` — removes unused properties and removes properties with default values from style attributes inside SVG files (part of `ffsvg.sh`)
* `_fix_color_scheme.sh FILE...` — looks in the SVG files for certain colors and replaces them with the corresponding stylesheet class. Fixes a color scheme after Inkscape (part of `ffsvg.sh`)
* `_scour.sh FILE...` — Scour wrapper (part of `ffsvg.sh`)
* `svgo.config.js` — [SVGO](https://github.com/svg/svgo) configuration (part of `ffsvg.sh`)
* `recolor-kde-monochrome.py` — reviews the KDE monochrome source roots and
  applies the semantic colorful palette in place. It is dry-run by default;
  pass `--apply` to write changes.
* `test-recolor-kde-monochrome.py` — regression tests for semantic precedence,
  palette values, custom SVG classes, and idempotence.
* `install-colorful-kde-themes.sh` — installs standalone user-local copies of
  Papirus Colorful, Papirus Dark Colorful, and Papirus Light Colorful.

## KDE semantic color pass

Preview the decisions without changing files:

```
python3 tools/recolor-kde-monochrome.py
```

Apply the reviewed rules to Papirus and Papirus-Dark (Papirus-Light inherits
the Papirus sources):

```
python3 tools/recolor-kde-monochrome.py --apply
python3 tools/test-recolor-kde-monochrome.py
```

Install all three resulting variants for the current user:

```
./tools/install-colorful-kde-themes.sh
```

The shared light and dark Xef/Papirus palettes live in `xef_palette.py`.
Papirus and Papirus-Light use darker semantic colors with at least roughly 3:1
contrast against the standard `#e4e4e4` surface. Papirus-Dark keeps the vivid
reference colors: cyan `#00bcd4`, purple `#673ab7`, orange `#ff9800`, red
`#f44336`, and green `#4caf50`. Ambiguous
layout, selection, transformation, settings, and application-indicator glyphs
remain monochrome with KDE's `ColorScheme-Text`, so their brightness follows
the active text color like Breeze instead of using a generated light or dark
grey. Blue, green, orange, and red use KDE's native semantic classes. The
additional cyan, purple, pink, and yellow families use fixed fills because
Plasma discards unknown color-scheme classes.

Semantically colored SVGs carry a non-rendering fallback marker; neutral
monochrome SVGs deliberately do not. During installation,
`make-colorful-theme.py` uses it (alongside KDE's dynamic color markers) to
prefer genuine fixed-color Papirus artwork with the same icon name. Semantic
recoloring remains only where no full-color counterpart exists.

Those unmatched fallbacks then use the surface-appropriate palette. Generated
blue is `#1976d2` on light surfaces and `#4a91e1` on dark surfaces.
At 22 px and above the installer adds the design guide's subtle black lower
shadow and white upper highlight; 16 px icons remain flat for pixel clarity.
Original full-color artwork is copied unchanged and never receives this effect.

The semantic audit follows a conservative rule: color communicates only a
meaningful state, urgency, or an unambiguous constructive/destructive action.
Object and content identities—including music, audio, artist, album, genre,
radio, folder, device, and network categories—remain monochrome alongside
generic navigation, formatting, layout, and application-indicator controls.
Generated SVG markers record assigned families so later audits can safely
recolor an icon or return it to neutral.


## Useful snippets

Optimize and fix SVG files that are added or modified but not committed (recommended)

```
git status --porcelain | awk '/A|M/{print $2}' | xargs ./tools/ffsvg.sh
```

Optimize and fix SVG files that are committed in [043906b](https://github.com/PapirusDevelopmentTeam/papirus-icon-theme/commit/043906b0edbcc86b732640bc391898d0aaaa410c)

```
git show --name-only 043906b | xargs ./tools/ffsvg.sh
```
