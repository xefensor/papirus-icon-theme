# Generated colorful fallback rules

This file defines the semantic color system used **only** for icons that have no existing fixed-color Papirus counterpart.

Existing fixed-color artwork always wins unchanged. This includes variant-specific artwork in Papirus, Papirus-Dark, and Papirus-Light.

## Goals

Generated fallbacks should be quieter than full application artwork, consistent across related functions, and visibly part of the Papirus family. They must follow `tools/work/DESIGN.md`: warm/non-toxic colors, no gradients, Papirus shadow/highlight treatment, and size-specific handling.

## Generated palette

Generated colors are derived from the Papirus example palette in `tools/work/examples-papirus.svg`, but saturation is capped so generated UI glyphs do not overpower existing Papirus artwork.

The semantic families are deliberately small:

- **Blue** — neutral system, edit/configure, navigation, devices, audio, display, network, Bluetooth, restart/session.
- **Green** — add/create/apply/save/install/enable/connect/start/resume/success.
- **Amber** — suspend/hibernate/sleep/pause, pin/favorite/bookmark/lock, warning/attention/limited states.
- **Red** — remove/delete/uninstall/disable/disconnect/shutdown/cancel/close/error/failure/critical/muted.

No generated purple, pink, cyan, or per-icon rainbow mapping is used.

## Category and state rules

### Power/session
- sleep + hibernate -> amber
- restart -> blue
- shutdown/power off -> red
- session/switch user -> blue

### Common actions
- add/new/create/apply/save/install/enable -> green
- edit/configure/settings/properties/open/info -> blue
- pin/favorite/bookmark -> amber
- remove/delete/uninstall/disable/cancel -> red

### Audio
- normal low/medium/high/device/output/input -> blue
- muted/disabled/broken/disconnected -> red
- warnings -> amber

### Network/Bluetooth
- normal/connected identity -> blue
- connect/enable action -> green
- limited/warning -> amber
- disconnected/disabled/error -> red

### Battery
- charging and healthy levels -> green
- low levels -> amber
- critical/empty/error -> red

## Variant behavior

If a real fixed-color icon exists in the selected variant, that exact file is used. Generated fallback hues are shared semantic families because Papirus base colors are designed to work on both light and dark backgrounds; variant-specific artwork is never collapsed or replaced by a generated version.
