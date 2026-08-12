#!/bin/sh

# Install standalone copies of all three semantically recolored KDE variants.
# The source tree is resolved relative to this script, so the command works
# regardless of the caller's current directory.

set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_root=$(dirname -- "$script_dir")
data_root=${XDG_DATA_HOME:-"$HOME/.local/share"}
dest_root=${PAPIRUS_COLORFUL_DEST_ROOT:-"$data_root/icons"}

mkdir -p "$dest_root"
stage_dir=$(mktemp -d "$dest_root/.papirus-colorful-stage.XXXXXX")

cleanup() {
    rm -rf "$stage_dir"
}
trap cleanup EXIT HUP INT TERM

build_variant() {
    source_name=$1
    target_name=$2
    display_name=$3
    built_path="$stage_dir/$target_name"
    installed_path="$dest_root/$target_name"

    printf 'Building %s ...\n' "$display_name"
    python3 "$script_dir/make-colorful-theme.py" \
        --source "$repo_root/$source_name" \
        --output-root "$stage_dir" \
        --name "$target_name" \
        --display-name "$display_name" \
        --keep-semantic-fallbacks \
        --polish-semantic-fallbacks

    # The target names belong exclusively to this generated family. Build in a
    # temporary directory first so a copy failure cannot damage an installed
    # version, then replace the old generated copy.
    rm -rf "$installed_path"
    mv "$built_path" "$installed_path"

    if command -v gtk-update-icon-cache >/dev/null 2>&1; then
        gtk-update-icon-cache -f -q "$installed_path" || true
    fi
}

build_variant Papirus Papirus-Colorful "Papirus Colorful"
build_variant Papirus-Dark Papirus-Dark-Colorful "Papirus Dark Colorful"
build_variant Papirus-Light Papirus-Light-Colorful "Papirus Light Colorful"

if [ "${PAPIRUS_COLORFUL_SKIP_CACHE_REFRESH:-0}" != 1 ]; then
    rm -f "$HOME/.cache/icon-cache.kcache"
    if command -v kbuildsycoca6 >/dev/null 2>&1; then
        kbuildsycoca6 --noincremental
    elif command -v kbuildsycoca5 >/dev/null 2>&1; then
        kbuildsycoca5 --noincremental
    fi
fi

printf '\nInstalled in %s:\n' "$dest_root"
printf '  Papirus Colorful\n'
printf '  Papirus Dark Colorful\n'
printf '  Papirus Light Colorful\n'
