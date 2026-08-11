# Papirus Colorful

This fork includes a generator for user-local Papirus variants that replace KDE's theme-driven monochrome UI artwork with colorful Papirus-style artwork.

The generator follows [`tools/work/DESIGN.md`](tools/work/DESIGN.md). It does **not** invent arbitrary hex colors: generated fallback colors come only from [`tools/work/examples-papirus.svg`](tools/work/examples-papirus.svg), which `DESIGN.md` explicitly points to as a source of good Papirus colors.

## Design rules

For every dynamic SVG (`currentColor`, `context-fill`, or `context-stroke`):

1. If the selected Papirus variant already contains a fixed-color version with the same semantic icon name, that existing artwork is copied exactly.
2. Otherwise the original geometry is preserved and converted into a simple colored Papirus base using colors from `examples-papirus.svg`.
3. Generated 22px and 24px icons receive the Papirus 0.5px shadow/highlight treatment described in `DESIGN.md`; 32px, 48px and 64px use 1px. 16px icons receive no generated shadow/highlight.
4. Shadows are pure black at 20%. Highlights are pure white at 20% (10% for dark-grey bases), matching the design notes.
5. No gradients are introduced.
6. Existing fixed-color light/dark artwork always wins, so `Papirus-Light-Colorful` and `Papirus-Dark-Colorful` retain variant-specific artwork when Papirus provides it.

The generated base colors are the exact example colors already stored in `tools/work/examples-papirus.svg`: blue `#248afd`, green `#4bae4f`, red `#c2352a`, pink `#f9548f`, orange `#e97e10`, purple `#7767c0`, light grey `#cccccc`, and dark grey `#5d5d5d`.

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
