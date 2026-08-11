# Generated colorful fallback rules

This file defines the semantic color system used **only** for icons that have no existing fixed-color Papirus counterpart.

Existing fixed-color artwork always wins unchanged. This includes variant-specific artwork in Papirus, Papirus-Dark, and Papirus-Light.

## Goals

Generated fallbacks should be close in visual strength to surrounding Papirus artwork, consistent across related functions, and visibly part of the Papirus family. They must follow `tools/work/DESIGN.md`: warm/non-toxic colors, no gradients, Papirus shadow/highlight treatment, and size-specific handling.

## Generated semantic palette

Generated semantic colors are derived from the Papirus example palette in `tools/work/examples-papirus.svg`. The example hue is preserved, HLS saturation is capped at **72%**, and only tiny family-specific lightness lifts are applied to the generated-only blue, amber, and red. This keeps the generated UI glyphs close to real Papirus color strength without copying the most extreme saturation of the full artwork.

```text
blue  #4a91e1  (+0.020 lightness)
green #4bae4f  (unchanged)
amber #dc8225  (+0.015 lightness)
red   #c6362b  (+0.010 lightness)
```

- **Blue** — explicitly neutral/system/device information: edit/configure/settings, audio, display, network, Bluetooth, restart/session, navigation.
- **Green** — add/create/apply/save/install/enable/connect/start/resume/success.
- **Amber** — suspend/hibernate/sleep/pause, pin/favorite/bookmark/lock, warning/attention/limited states.
- **Red** — remove/delete/uninstall/disable/disconnect/shutdown/cancel/close/error/failure/critical/muted.

Blue is **not** the generic fallback. Icons with no clear semantic reason to be colored use a theme-aware neutral instead.

## Theme-aware neutral fallback

Ambiguous/generated-only icons use a neutral grey from the Papirus example palette:

```text
Papirus-Dark  #cccccc  light neutral on dark UI
Papirus-Light #5d5d5d  dark neutral on light UI
Papirus       #5d5d5d  dark neutral default
```

This keeps generic actions from looking artificially active merely because the generator could not classify them.

## Category and state rules

### Power/session
- sleep + hibernate -> amber
- restart/reboot -> blue
- shutdown/power off -> red
- session/switch user -> blue
- log out -> red

### Common actions
- add/new/create/apply/save/install/enable/unlock -> green
- edit/configure/settings/properties/info -> blue
- pin/favorite/bookmark/lock -> amber
- remove/delete/uninstall/disable/cancel/close -> red
- ambiguous generic action -> theme-aware neutral

### Audio
- normal device/output/input/volume identity -> blue
- muted/disabled/broken/disconnected -> red
- warnings -> amber

### Network/Bluetooth
- normal identity -> blue
- explicit connect/enable action -> green
- limited/warning -> amber
- disconnected/disabled/error -> red

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
