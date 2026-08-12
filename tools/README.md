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

The semantic palette is green `#4caf50`, red `#f44336`, orange `#ff9800`, blue
`#4285f4`, cyan `#00bcd4`, purple `#9c27b0`, pink `#e91e63`, and yellow
`#f9a825` on light/regular variants or `#fecd38` on Papirus-Dark. Ambiguous
layout, selection, transformation, settings, and application-indicator glyphs
remain theme-aware neutral grey. Blue, green, orange, and red use KDE's native
semantic classes. The additional cyan, purple, pink, and yellow families use
fixed fills because Plasma discards unknown color-scheme classes.

Recolored SVGs carry a non-rendering fallback marker. During installation,
`make-colorful-theme.py` uses it (alongside KDE's dynamic color markers) to
prefer genuine fixed-color Papirus artwork with the same icon name. Semantic
recoloring remains only where no full-color counterpart exists.

Those unmatched fallbacks then use the restrained Papirus-derived palette.
At 22 px and above the installer adds the design guide's subtle black lower
shadow and white upper highlight; 16 px icons remain flat for pixel clarity.
Original full-color artwork is copied unchanged and never receives this effect.

The semantic audit follows a conservative rule: color communicates an object
identity, a meaningful state, urgency, or a constructive/destructive action.
Generic navigation, formatting, keyboard, layout, layer/node/path, media-mode,
clock/history, and application-indicator controls remain neutral. Generated SVG
markers record their assigned family so later audits can safely recolor an icon
or return it to neutral without confusing it with original Papirus artwork.


## Useful snippets

Optimize and fix SVG files that are added or modified but not committed (recommended)

```
git status --porcelain | awk '/A|M/{print $2}' | xargs ./tools/ffsvg.sh
```

Optimize and fix SVG files that are committed in [043906b](https://github.com/PapirusDevelopmentTeam/papirus-icon-theme/commit/043906b0edbcc86b732640bc391898d0aaaa410c)

```
git show --name-only 043906b | xargs ./tools/ffsvg.sh
```
