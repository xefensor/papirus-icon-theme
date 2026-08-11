# Papirus Colorful

This fork includes a generator for user-local Papirus variants that replace KDE's theme-driven monochrome UI artwork with colorful Papirus-style artwork.

The generator follows [`tools/work/DESIGN.md`](tools/work/DESIGN.md). Existing fixed-color Papirus artwork always has priority and is copied unchanged. Only icons with no real fixed-color counterpart are generated.

## Design rules

For every dynamic SVG (`currentColor`, `context-fill`, or `context-stroke`):

1. If the selected Papirus variant already contains a fixed-color version with the same semantic icon name, that existing artwork is copied exactly.
2. Otherwise the original geometry is preserved and converted into a generated fallback using the unified semantic system in [`tools/work/generated-color-spec.md`](tools/work/generated-color-spec.md).
3. Generated 22px and 24px icons receive the Papirus 0.5px shadow/highlight treatment described in `DESIGN.md`; 32px, 48px and 64px use 1px. 16px icons receive no generated shadow/highlight.
4. Shadows are pure black at 20%. Highlights are pure white at 20%, matching the design notes for these generated mid-value colors.
5. No gradients are introduced.
6. Existing fixed-color light/dark artwork always wins, so `Papirus-Light-Colorful` and `Papirus-Dark-Colorful` retain variant-specific artwork whenever Papirus provides it.

## Generated-only colors

The generator no longer assigns a broad rainbow of colors to monochrome icons. Generated fallbacks use only four semantic families:

- **Blue** — neutral system controls, editing/configuration, navigation, devices, audio, displays, network/Bluetooth, restart/session.
- **Green** — add/create/apply/save/install/enable/connect/start/resume/success.
- **Amber** — suspend/hibernate/sleep/pause, pin/favorite/bookmark/lock, warning/limited states.
- **Red** — remove/delete/uninstall/disable/disconnect/shutdown/cancel/close/error/critical/muted states.

The hues come from the Papirus example palette in `tools/work/examples-papirus.svg`, but generated UI fallbacks cap HLS saturation at 45% so they sit more quietly beside original Papirus artwork instead of looking like bright accent-colored symbolic icons.

Current generated palette:

```text
blue  #5f8ec2
green #4bae4f
amber #b57d44
red   #ab4941
```

This muted palette applies **only to generated fallbacks**. Existing Papirus color artwork is never desaturated or recolored.

## Functional consistency

Related generated icons intentionally share a family. Examples:

```text
Sleep / Hibernate   -> amber
Restart / Session   -> blue
Shutdown            -> red

Add / Save / Apply  -> green
Edit / Settings     -> blue
Pin / Favorite      -> amber
Remove / Delete     -> red

Audio normal        -> blue
Audio muted/error   -> red

Network/Bluetooth normal -> blue
Limited/warning          -> amber
Disconnected/error       -> red

Battery healthy/charging -> green
Battery low              -> amber
Battery critical/empty   -> red
```

Explicit KDE semantic classes (`ColorScheme-PositiveText`, `NegativeText`, `NeutralText`, and `Highlight`) are preserved as green, red, amber, and blue respectively.

## Build

From the repository root:

```bash
make colorful-dark
```

creates:

```text
~/.local/share/icons/Papirus-Dark-Colorful
```

For the other variants:

```bash
make colorful-normal
make colorful-light
```

Or build all three:

```bash
make colorful-all
```

The generated themes are:

```text
Papirus-Colorful
Papirus-Dark-Colorful
Papirus-Light-Colorful
```

Then select the desired theme in:

```text
System Settings -> Colors & Themes -> Icons
```

If Plasma does not immediately repaint every icon:

```bash
systemctl --user restart plasma-plasmashell.service
```

Some third-party tray applications may need to be restarted separately.

## Why the generator keeps separate variants

`Papirus`, `Papirus-Dark`, and `Papirus-Light` can contain different artwork or overrides. Each generated theme starts from its corresponding source variant and dereferences Papirus' relative symlinks, producing a self-contained theme while preserving any real variant-specific colored icons.
