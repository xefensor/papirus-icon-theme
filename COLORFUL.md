# Papirus Colorful

This fork includes a generator for a Papirus variant that keeps KDE Plasma's
`*-symbolic` icon names but serves the regular colorful Papirus artwork under
those names whenever a matching icon exists.

This is useful on recent KDE Plasma versions that explicitly prefer symbolic
icons in the panel/system tray.

## Install for the current user

From the repository root:

```bash
python3 tools/make-colorful-theme.py
```

By default this reads `Papirus-Dark` from the checked-out repository and writes:

```text
~/.local/share/icons/Papirus-Dark-Colorful
```

Then select **Papirus-Dark Colorful** in:

```text
System Settings -> Colors & Themes -> Icons
```

If Plasma does not immediately repaint every tray icon, restart Plasma Shell:

```bash
systemctl --user restart plasma-plasmashell.service
```

Some third-party tray applications may also need to be restarted.

## Other variants

For regular Papirus:

```bash
python3 tools/make-colorful-theme.py --source Papirus
```

For Papirus-Light:

```bash
python3 tools/make-colorful-theme.py --source Papirus-Light
```

You can choose another output directory or theme name:

```bash
python3 tools/make-colorful-theme.py \
  --source Papirus-Dark \
  --output-root ~/.local/share/icons \
  --name Papirus-Xef \
  --display-name "Papirus Xef"
```

## How it works

Deleting symbolic icons is not sufficient because KDE can fall back to a
symbolic icon from another inherited theme. The generator instead preserves
symbolic filenames such as:

```text
audio-volume-high-symbolic.svg
```

but replaces their contents with the normal colorful counterpart when one is
available.

Papirus-Dark contains many symlinks into the base Papirus theme. The generator
dereferences these links while copying, making the generated theme
self-contained.

Icons without an identifiable colorful counterpart are left untouched and are
listed in:

```text
unmatched-symbolic-icons.txt
```

inside the generated theme.
