# Papirus Colorful

This fork includes a generator for Papirus variants that remove KDE's
theme-driven monochrome artwork while keeping the original Papirus shapes and
variant-specific styling.

It covers both `*-symbolic` names and ordinary KDE UI/action icons that still use
`currentColor`, such as suspend, hibernate, reboot, shutdown, pin, edit, remove,
panel, status and context-menu icons.

## Variants

The generator supports all three Papirus variants independently:

- `Papirus-Colorful`
- `Papirus-Dark-Colorful`
- `Papirus-Light-Colorful`

Light and dark variants are generated from their matching Papirus source theme.
If Papirus already ships different fixed-color artwork for light and dark, the
matching variant is used. If no fixed-color artwork exists, the SVG keeps its
original geometry and receives colors from that source variant's own embedded
Papirus/KDE semantic palette.

This means light/dark-specific artwork and palette choices are never collapsed
into one generic theme.

## Install for the current user

From the repository root, build the dark variant:

```bash
make colorful
```

`make colorful` is an alias for:

```bash
make colorful-dark
```

For the other variants:

```bash
make colorful-normal
make colorful-light
```

To build all three:

```bash
make colorful-all
```

They are written to:

```text
~/.local/share/icons/Papirus-Colorful
~/.local/share/icons/Papirus-Dark-Colorful
~/.local/share/icons/Papirus-Light-Colorful
```

Then select the matching Colorful theme in:

```text
System Settings -> Colors & Themes -> Icons
```

If Plasma does not immediately repaint every icon, restart Plasma Shell:

```bash
systemctl --user restart plasma-plasmashell.service
```

Some third-party tray applications may also need to be restarted because they
cache their icon.

## How coloring works

The generator uses this priority:

1. **Existing fixed-color Papirus artwork wins.** If the selected Papirus variant
   already contains fixed-color artwork with the same semantic icon name, that
   file is copied exactly.
2. **Otherwise the original SVG is colorized without changing its geometry.**
   `currentColor`, `context-fill` and `context-stroke` are replaced using the
   palette embedded by Papirus itself.
3. Existing semantic classes remain meaningful: positive artwork stays green,
   negative/error artwork stays red, warning/attention artwork stays orange and
   highlight artwork stays blue.
4. Plain foreground UI actions are assigned a semantic color by their icon name.
   Examples: Sleep/Hibernate use NeutralText orange, Restart/edit/navigation use
   Highlight blue, Shutdown/remove/uninstall use NegativeText red, and add/apply
   style actions use PositiveText green.

The generator processes every dynamic SVG, not only symbolic directories. The
build fails its regression tests if any `currentColor`, `context-fill` or
`context-stroke` artwork remains in the generated real Papirus, Papirus-Dark or
Papirus-Light theme.

Papirus-Dark and Papirus-Light contain relative symlinks into sibling themes.
Those links are dereferenced during generation, so each generated theme is a
self-contained user-local theme.

## Direct use

The Python tool can also be called directly:

```bash
python3 tools/make-colorful-theme.py --source Papirus-Dark
python3 tools/make-colorful-theme.py --source Papirus
python3 tools/make-colorful-theme.py --source Papirus-Light
```

Custom output names are supported:

```bash
python3 tools/make-colorful-theme.py \
  --source Papirus-Dark \
  --output-root ~/.local/share/icons \
  --name Papirus-Xef \
  --display-name "Papirus Xef"
```
