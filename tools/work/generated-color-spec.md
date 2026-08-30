# Generated colorful fallback rules

This file defines the semantic color system used **only** for icons that have no existing fixed-color Papirus counterpart.

Existing fixed-color artwork always wins unchanged. This includes variant-specific artwork in Papirus, Papirus-Dark, and Papirus-Light.

The exact variant values are defined once in `tools/xef_palette.py`. KDE SVG
classes keep `currentColor` and therefore remain theme-dynamic; their embedded
stylesheet defaults use the matching light or dark palette.

```text
role/family  Papirus + Papirus-Light  Papirus-Dark
blue         #1976d2                  #4a91e1
green        #388e3c                  #4caf50
amber        #e45100                  #ff9800
red          #d32f2f                  #f44336
cyan         #00838f                  #00bcd4
purple       #673ab7                  #673ab7
pink         #d81b60                  #f9548f
yellow       #a87900                  #fecd38
```

## Goals

Generated fallbacks should be close in visual strength to surrounding Papirus artwork, consistent across related functions, and visibly part of the Papirus family. They must follow `tools/work/DESIGN.md`: warm/non-toxic colors, no gradients, Papirus shadow/highlight treatment, and size-specific handling.

## Generated semantic palette

Papirus-Dark uses the vivid reference palette. Papirus and Papirus-Light use
darker counterparts so small colored monochrome glyphs remain readable against
the standard light `#e4e4e4` surface.

```text
blue  #1976d2
green #388e3c
amber #e45100
red   #d32f2f
```

Fixed additional light-theme families use purple `#673ab7`, pink `#d81b60`,
yellow `#a87900`, and cyan `#00838f`.

- **Blue** — explicit informational, refresh, download/upload, import/export, and restore actions.
- **Green** — add/create/apply/save/install/enable/connect/start/resume/success.
- **Amber** — restart/reboot/pause, pin/favorite/bookmark/lock, warning/attention/limited states.
- **Red** — remove/delete/uninstall/shutdown/cancel/close/error/failure/critical.

Blue is **not** the generic fallback. Icons with no clear semantic reason to be colored use a theme-aware neutral instead.

## Theme-aware neutral fallback

Ambiguous/generated-only icons use a neutral grey from the Papirus example palette:

```text
Papirus-Dark  #cccccc  light neutral on dark UI
Papirus-Light #5d5d5d  dark neutral on light UI
Papirus       #5d5d5d  dark neutral default
```

This keeps object/category identities and generic actions from looking
artificially active merely because the generator could not classify them.

## Category and state rules

### Power/session
- sleep/suspend -> cyan
- hibernate -> purple
- restart/reboot -> amber
- shutdown/power off -> red
- switch user -> green
- generic session identity -> monochrome
- log out -> red

### Common actions
- add/new/create/apply/save/install/enable/unlock -> green
- info/help/refresh/download/upload/import/export/restore -> blue
- pin/favorite/bookmark/lock -> amber
- remove/delete/uninstall/cancel/close -> red
- disabled/muted/inactive -> monochrome
- ambiguous generic action -> theme-aware neutral

### Audio
- normal device/output/input/volume identity -> monochrome
- muted/disabled -> monochrome
- broken -> red; disconnected -> amber
- warnings -> amber

### Network/Bluetooth
- normal identity -> monochrome
- explicit connect/enable action -> green
- limited/warning -> amber
- disconnected -> amber
- disabled -> monochrome
- error -> red

### Battery
- charging and levels above 40% -> green
- 16-40% -> amber
- 0-15% / critical / missing / error -> red

## KDE semantic classes

Explicit KDE semantic classes override filename/category defaults:

- `ColorScheme-PositiveText` -> green
- `ColorScheme-NegativeText` -> red
- `ColorScheme-NeutralText` -> amber
- `ColorScheme-Highlight` -> blue
- plain `ColorScheme-Text` -> the icon's function family or theme-aware neutral

## Variant behavior

If a real fixed-color icon exists in the selected variant, that exact file is used. This remains the highest-priority rule, so existing Papirus light/dark-specific colored artwork is never replaced by a generated fallback.
