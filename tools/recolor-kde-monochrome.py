#!/usr/bin/env python3
"""Apply the Papirus semantic palette to KDE monochrome icon sources.

The pass is intentionally conservative: an icon receives color only when its
name communicates an unambiguous action or state. Object/category identities
and generic layout, navigation, selection, transform, and settings glyphs
remain theme-aware monochrome.

Supported KDE monochrome roots follow tools/work/DESIGN.md:

* actions: 16x16, 22x22, 24x24
* devices and places: 16x16
* panel: 22x22, 24x24

Papirus-Light inherits these sources from Papirus, so only Papirus and
Papirus-Dark need independent edits. Symlinks are never rewritten.
"""

from __future__ import annotations

import argparse
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

try:
    from xef_palette import XEF_COLORS, XEF_LIGHT_COLORS
except ModuleNotFoundError:  # Support importing as tools.recolor_kde_monochrome.
    from tools.xef_palette import XEF_COLORS, XEF_LIGHT_COLORS


SUPPORTED_ROOTS = (
    "16x16/actions",
    "16x16/devices",
    "16x16/places",
    "22x22/actions",
    "22x22/panel",
    "24x24/actions",
    "24x24/panel",
)

THEMES = ("Papirus", "Papirus-Dark")

FAMILY_CLASS = {
    "neutral": "ColorScheme-Text",
    "blue": "ColorScheme-Highlight",
    "green": "ColorScheme-PositiveText",
    "orange": "ColorScheme-NeutralText",
    "red": "ColorScheme-NegativeText",
    "yellow": "ColorScheme-YellowText",
    "cyan": "ColorScheme-CyanText",
    "purple": "ColorScheme-PurpleText",
    "pink": "ColorScheme-PinkText",
}

CUSTOM_COLORS = {
    "Papirus": {
        "ColorScheme-YellowText": XEF_LIGHT_COLORS["yellow"],
        "ColorScheme-CyanText": XEF_LIGHT_COLORS["cyan"],
        "ColorScheme-PurpleText": XEF_LIGHT_COLORS["purple"],
        "ColorScheme-PinkText": XEF_LIGHT_COLORS["pink"],
    },
    "Papirus-Dark": {
        "ColorScheme-YellowText": XEF_COLORS["yellow"],
        "ColorScheme-CyanText": XEF_COLORS["cyan"],
        "ColorScheme-PurpleText": XEF_COLORS["purple"],
        "ColorScheme-PinkText": XEF_COLORS["pink"],
    },
}

STANDARD_KDE_COLORS = {
    "Papirus": {
        "ColorScheme-Highlight": XEF_LIGHT_COLORS["accent"],
        "ColorScheme-PositiveText": XEF_LIGHT_COLORS["success"],
        "ColorScheme-NeutralText": XEF_LIGHT_COLORS["warning"],
        "ColorScheme-NegativeText": XEF_LIGHT_COLORS["error"],
    },
    "Papirus-Dark": {
        "ColorScheme-Highlight": XEF_COLORS["accent"],
        "ColorScheme-PositiveText": XEF_COLORS["success"],
        "ColorScheme-NeutralText": XEF_COLORS["warning"],
        "ColorScheme-NegativeText": XEF_COLORS["error"],
    },
}

# Values emitted by earlier versions. Marked custom-family SVGs may already
# contain these fixed fills, so reset_previous_fallback() recognizes them and
# can safely rebake the icon with the shared Xef/Papirus palette.
LEGACY_CUSTOM_COLORS = {
    "ColorScheme-YellowText": ("#f9a825", "#fecd38"),
    "ColorScheme-CyanText": ("#00bcd4",),
    "ColorScheme-PurpleText": ("#9c27b0", "#7767c0"),
    "ColorScheme-PinkText": ("#e91e63", "#f9548f"),
}

FULL_OPACITY_ICONS = {"network-disconnect"}
SEMANTIC_FALLBACK_MARKER = "<!-- papirus-colorful-semantic-fallback -->"
SEMANTIC_FALLBACK_RE = re.compile(
    r"<!--\s*papirus-colorful-semantic-fallback(?:\s*:\s*(?P<family>[a-z]+))?\s*-->"
)

CLASS_TEXT_RE = re.compile(r'(class\s*=\s*["\'][^"\']*)\bColorScheme-Text\b')
START_TAG_RE = re.compile(
    r"<(?![!?/])(?P<tag>[A-Za-z_][\w:.-]*)(?P<attrs>[^<>]*)>", re.DOTALL
)
CLASS_ATTR_RE = re.compile(r"\s+class\s*=\s*([\"'])(?P<value>.*?)\1", re.DOTALL)
STYLE_RE = re.compile(
    r'(<style\b[^>]*\bid\s*=\s*["\']current-color-scheme["\'][^>]*>)(.*?)(</style>)',
    re.IGNORECASE | re.DOTALL,
)
SVG_OPEN_RE = re.compile(r"<svg\b[^>]*>", re.IGNORECASE | re.DOTALL)
BATTERY_LEVEL_RE = re.compile(r"(?:battery|power).*?(?:level[-_]?)(\d{1,3})")
BATTERY_PERCENT_RE = re.compile(r"battery[-_](\d{1,3})(?:$|[-_])")


@dataclass(frozen=True)
class Decision:
    family: str
    reason: str


@dataclass(frozen=True)
class Result:
    path: Path
    family: str
    reason: str
    changed: bool


EXACT_FAMILIES = {
    # Decisions made explicitly during the initial review.
    "action-unavailable": "red",
    "archive": "orange",
    "audio-volume-high": "neutral",
    "audio-volume-low": "neutral",
    "audio-volume-medium": "neutral",
    "autocorrection": "purple",
    "call-start": "green",
    "chronometer-pause": "orange",
    "chronometer-start": "green",
    "color-fill": "purple",
    "color-select": "purple",
    "contrast": "yellow",
    "dialog-information": "blue",
    "dialog-password": "yellow",
    "dialog-path-effects": "purple",
    "document-share": "cyan",
    "draw-brush": "purple",
    "draw-watercolor": "purple",
    "edit-copy": "blue",
    "edit-cut": "orange",
    "edit-paste": "green",
    "edit-redo": "blue",
    "edit-undo": "blue",
    "games-hint": "yellow",
    "image-filter": "purple",
    "insert-emoticon": "pink",
    "insert-link": "cyan",
    "kdenlive-show-audio": "neutral",
    "link": "cyan",
    "list-add": "green",
    "list-remove": "red",
    "love": "pink",
    "love-amarok": "pink",
    "mail-mark-unread": "cyan",
    "media-playback-pause": "orange",
    "media-playback-start": "green",
    "media-playback-stop": "red",
    "media-record": "red",
    "network-connect": "green",
    "network-disconnect": "orange",
    "no": "red",
    "boost": "green",
    "cm_markinvert": "blue",
    "cm_markminus": "red",
    "cm_markplus": "green",
    "donate": "green",
    "games-achievements": "yellow",
    "key-enter": "blue",
    "stock_bell": "orange",
    "tag": "yellow",
    "zone-in": "green",
    "zone-out": "orange",
    "object-select": "green",
    "pgp-keys": "yellow",
    "process-stop": "red",
    "rating": "yellow",
    "run-build": "green",
    "semi-starred": "yellow",
    "send-to": "cyan",
    "system-run": "green",
    "system-shutdown": "red",
    "system-reboot": "orange",
    "system-restart": "orange",
    "system-suspend": "cyan",
    "system-suspend-hibernate": "purple",
    "system-switch-user": "green",
    "view-conversation-balloon": "cyan",
    "view-filter": "purple",
    "view-refresh": "blue",
    "window-close": "red",
    "zoom-1-to-2": "blue",
    "zoom-2-to-1": "blue",
    "zoom-fit-best": "blue",
    "zoom-fit-drawing": "blue",
    "zoom-fit-height": "blue",
    "zoom-fit-page": "blue",
    "zoom-fit-selection": "blue",
    "zoom-fit-width": "blue",
    "zoom-in": "green",
    "zoom-in-x": "green",
    "zoom-in-y": "green",
    "zoom-original": "blue",
    "zoom-out": "orange",
    "zoom-out-x": "orange",
    "zoom-out-y": "orange",
    "y-zoom-in": "green",
    # Tools and informational actions that broad word rules can misread.
    "draw-eraser": "purple",
    "tool_color_eraser": "purple",
    "tools-report-bug": "blue",
    "mail-mark-notjunk": "green",
}


def normalized_name(path: Path) -> str:
    name = path.stem.lower().replace(".symbolic", "")
    return re.sub(r"-symbolic$", "", name)


def contains(name: str, terms: tuple[str, ...]) -> str | None:
    return next((term for term in terms if term in name), None)


def contains_token(name: str, terms: tuple[str, ...]) -> str | None:
    """Match semantic words without catching fragments such as ban in bank."""
    for term in terms:
        if re.search(rf"(^|[-_]){re.escape(term)}($|[-_])", name):
            return term
    return None


def decide_family(path: Path, context: str | None = None) -> Decision:
    """Choose a semantic family. Rule order is deliberate and tested."""
    name = normalized_name(path)
    context = context or path.parent.name

    if name in EXACT_FAMILIES:
        return Decision(EXACT_FAMILIES[name], "reviewed-exact")

    if context == "panel" and contains(name, ("weather-clear", "weather-sun")):
        return Decision("yellow", "panel-clear-weather")

    if contains(name, ("security-high", "trusted", "valid-ticket", "state-ok", "sign-ok")):
        return Decision("green", "healthy-security-state")
    if contains(name, ("security-medium", "expiring", "appointment-soon")):
        return Decision("orange", "caution-security-state")
    if contains(
        name,
        (
            "security-low", "no-valid-ticket", "sign-bad", "past-due",
            "quarantined", "panic",
        ),
    ):
        return Decision("red", "bad-security-state")

    if name.startswith("flag-"):
        suffix = name.removeprefix("flag-")
        family = {
            "red": "red",
            "blue": "blue",
            "green": "green",
            "yellow": "yellow",
        }.get(suffix, "neutral")
        return Decision(family, f"explicit-flag-{suffix}")

    if name in {"rating-unrated", "non-starred", "star-off", "no-rating"}:
        return Decision("neutral", "unselected-rating")

    # Media-library entries are navigation categories, not playback states.
    # Keep this before generic words such as favorite, playing, audio, or media.
    if name.startswith("view-media-") or name in {
        "icon_radio",
        "im-user",
        "media-album-track",
        "media-playlist-normal",
        "media-playlist-play",
        "tools-rip-audio-cd",
    }:
        return Decision("neutral", "media-library-navigation")

    if "battery" in name or name.startswith("power-level"):
        term = contains(name, ("charging", "charged", "full", "good"))
        if term:
            return Decision("green", f"battery-{term}")
        term = contains_token(
            name, ("critical", "empty", "missing", "error", "failed", "low")
        )
        if term:
            return Decision("red", f"battery-{term}")
        term = contains_token(name, ("caution", "medium", "warning"))
        if term:
            return Decision("orange", f"battery-{term}")
        match = BATTERY_LEVEL_RE.search(name)
        if not match:
            match = BATTERY_PERCENT_RE.search(name)
        if match:
            level = max(0, min(100, int(match.group(1))))
            if level <= 15:
                return Decision("red", "battery-low")
            if level <= 40:
                return Decision("orange", "battery-medium")
            return Decision("green", "battery-healthy")
        return Decision("neutral", "battery-identity")

    # Recording and genuinely destructive/failing actions take highest general
    # precedence over object identity such as media, mail, or network.
    term = contains_token(
        name,
        (
            "record", "recording", "delete", "trash", "shred", "uninstall", "shutdown",
            "power-off", "poweroff", "hangup", "hang-up", "reject", "denied",
            "forbid", "blocked", "error", "failed", "failure", "broken",
            "critical", "unavailable", "erase", "clear", "discard", "close",
            "cancel", "stop", "kill", "abort", "log-out", "logout", "remove",
            "exit", "quit", "panic", "quarantined", "dnd", "disturb",
            "danger", "junk", "spam", "ban", "kick", "forget", "stopped",
        ),
    )
    if term:
        return Decision("red", f"destructive-{term}")
    if re.search(r"(^|[-_])dead($|[-_])", name):
        return Decision("red", "destructive-dead")

    # Removing a connection is cautionary; removing data was handled above.
    term = contains_token(name, ("disconnect", "unlink", "remove-link"))
    if term:
        return Decision("orange", f"disconnect-{term}")

    # Disabled/muted glyphs should visually recede rather than masquerade as an
    # error. Their SVG opacity remains intact.
    term = contains_token(
        name, ("disabled", "disable", "inactive", "invisible", "muted", "mute")
    )
    if term:
        return Decision("neutral", f"disabled-{term}")
    if name == "off" or re.search(r"[-_]off$", name):
        return Decision("neutral", "disabled-off")
    if contains_token(name, ("closed",)):
        return Decision("neutral", "inactive-closed")

    term = contains_token(
        name,
        (
            "pause", "suspend", "hibernate", "sleep", "warning", "caution",
            "attention", "pending", "busy", "wait", "offline", "limited",
            "degraded", "archive", "disconnected",
            "away", "idle", "missed", "alarm", "appointment", "alert",
            "due", "stalled",
            "quota", "speed-limit", "earthquake",
        ),
    )
    if term:
        return Decision("orange", f"caution-{term}")

    term = contains_token(
        name, ("next", "previous", "forward", "rewind", "skip", "seek")
    )
    if term:
        return Decision("neutral", f"navigation-{term}")
    if name.startswith("go-"):
        return Decision("neutral", "navigation-go")

    if contains_token(name, ("paused",)):
        return Decision("orange", "caution-paused")
    if contains_token(name, ("playing",)):
        return Decision("green", "positive-playing")
    if name.startswith("media-") and contains_token(
        name, ("eject", "repeat", "shuffle", "random", "playlist")
    ):
        return Decision("neutral", "media-mode-control")

    if contains_token(name, ("reboot", "restart")):
        return Decision("orange", "system-restart")
    if contains_token(name, ("restore",)):
        return Decision("blue", "system-restore")

    if contains(name, ("unlock", "unlocked")):
        return Decision("green", "positive-unlock")

    # Favorites/security identity wins over generic "new" in composite names.
    term = contains_token(
        name,
        (
            "favorite", "favourite", "star", "rating", "bookmark", "password",
            "credential", "keyring", "pgp-key", "keychain", "hint", "tip",
            "brightness", "highlight", "lightbulb", "idea", "important",
            "security", "certificate", "flag", "achievement", "magnet",
        ),
    )
    if term:
        return Decision("yellow", f"highlight-{term}")
    if re.search(r"(^|[-_])(?:pin|pinned|lock|locked)($|[-_])", name):
        return Decision("yellow", "highlight-pin-lock")

    # A bare key is security-yellow, but keyboard keys and keyframes are editing
    # controls and should retain their category/default semantics.
    if re.search(r"(^|[-_])key(s)?($|[-_])", name) and not contains(
        name, ("keyboard", "keyframe", "key-enter", "key-enter")
    ):
        return Decision("yellow", "security-key")

    if contains(name, ("updates-available", "update-available")):
        return Decision("orange", "caution-update-available")

    if name.startswith(("pan-start", "selection-start")):
        return Decision("neutral", "structural-start")

    term = contains_token(
        name,
        (
            "connect", "add", "create", "new", "insert", "apply", "accept",
            "confirm", "install", "enable", "start", "play",
            "resume", "run", "success", "complete", "available", "online",
            "unlock", "paste", "approve", "validate", "finish",
            "logged-in", "boosted", "up-to-date",
        ),
    )
    if term:
        return Decision("green", f"positive-{term}")

    term = contains_token(name, ("save", "update", "upgrade", "check"))
    if term:
        return Decision("blue", f"primary-{term}")

    # Geometry-management controls are intentionally neutral. Action words
    # above still color meaningful variants such as layer-new or node-delete.
    term = contains(
        name,
        (
            "align", "distribute", "selection", "select", "transform", "resize",
            "rotate", "flip", "layout", "grid", "guides", "snap", "boundingbox",
            "zorder", "object-order", "layer-raise", "layer-lower", "layer-top",
            "layer-bottom", "sort", "duplicate", "combine", "merge", "reverse",
            "exchange", "reconcile", "debug-step", "workspaces", "keyboard",
            "arrow-", "pan-", "direction", "fitbest", "fitheight", "fitsize",
            "fitwidth", "clipboard", "edit-", "format-", "text-", "path-",
            "node-", "object-", "layer-", "keyframe", "timeline", "trim-",
        ),
    )
    if term:
        return Decision("neutral", f"structural-{term}")

    # Emotion/reaction actions can carry the pink family. Media, audio, video,
    # artist, album, genre, radio, and similar content identities deliberately
    # fall through to monochrome.
    term = contains(
        name,
        (
            "heart", "love", "emoji", "emoticon", "smile", "reaction",
        ),
    )
    if term:
        return Decision("pink", f"expressive-{term}")
    if re.search(r"(^|[-_])emote($|[-_])", name):
        return Decision("pink", "expressive-emote")

    term = contains(
        name,
        (
            "picker", "eyedropper", "paint", "brush", "watercolor", "draw-",
            "bezier", "calligraph", "spray",
        ),
    )
    if term:
        return Decision("purple", f"creative-{term}")

    if context == "panel" and contains(name, ("tray", "indicator", "-panel")):
        return Decision("neutral", "panel-application-indicator")

    term = contains(
        name,
        (
            "information", "info", "help", "download", "upload", "import",
            "export", "open", "refresh", "reload", "sync", "search", "find",
            "undo", "redo", "zoom", "navigate", "go-", "next", "previous",
            "forward", "back", "print", "scan", "reboot", "restart",
            "switch-user", "session-switch", "execute", "convert", "commit",
        ),
    )
    if term:
        return Decision("blue", f"primary-{term}")

    # Context-aware identities for supported KDE roots.
    if context == "places":
        return Decision("neutral", "places-identity")

    if context == "devices":
        return Decision("neutral", "devices-identity")

    if context == "panel":
        term = contains(name, ("alarm", "event"))
        if term:
            return Decision("orange", f"panel-{term}")
        term = contains(name, ("notification", "clock", "time"))
        if term:
            return Decision("neutral", f"panel-{term}")
        term = contains(name, ("weather-clear", "weather-sun", "daytime", "night-light"))
        if term:
            return Decision("yellow", f"panel-{term}")
        term = contains(name, ("weather", "cloud", "rain", "snow", "temperature"))
        if term:
            return Decision("cyan", f"panel-{term}")

    return Decision("neutral", "ambiguous")


def ensure_custom_style(text: str, theme: str, class_name: str) -> str:
    color = CUSTOM_COLORS[theme].get(class_name)
    if color is None or re.search(rf"\.{re.escape(class_name)}\s*\{{", text):
        return text

    declaration = f" .{class_name} {{ color:{color}; }}"

    def insert(match: re.Match[str]) -> str:
        body = match.group(2)
        if "\n" in body:
            indent_match = re.search(r"\n([ \t]*)\S", body)
            indent = indent_match.group(1) if indent_match else "   "
            body = body.rstrip() + f"\n{indent}.{class_name} {{ color:{color}; }}\n"
        else:
            body = body.rstrip() + declaration
        return match.group(1) + body + match.group(3)

    changed, count = STYLE_RE.subn(insert, text, count=1)
    if count != 1:
        raise ValueError("missing current-color-scheme style block")
    return changed


def synchronize_standard_palette(text: str, theme: str) -> str:
    """Update KDE semantic fallback rules while leaving the classes dynamic."""
    changed = text
    for class_name, color in STANDARD_KDE_COLORS[theme].items():
        changed = re.sub(
            rf"(\.{re.escape(class_name)}\s*\{{[^}}]*\bcolor\s*:\s*)"
            rf"#[0-9a-fA-F]{{6}}(\s*;)",
            rf"\g<1>{color}\g<2>",
            changed,
            flags=re.IGNORECASE,
        )
    return changed


def bake_custom_colors(text: str, theme: str) -> str:
    """Bake non-KDE palette families into element fills/strokes.

    Plasma replaces the SVG stylesheet with rules for KDE's five recognized
    ColorScheme classes. Unknown custom classes therefore lose their `color`
    value and `currentColor` renders black. Fixed fills are required for the
    additional yellow, cyan, purple, and pink families.
    """
    colors = CUSTOM_COLORS[theme]

    def replace_tag(match: re.Match[str]) -> str:
        tag_text = match.group(0)
        class_match = CLASS_ATTR_RE.search(tag_text)
        if not class_match:
            return tag_text
        classes = class_match.group("value").split()
        custom_classes = [class_name for class_name in classes if class_name in colors]
        if not custom_classes:
            return tag_text
        if len(custom_classes) != 1:
            raise ValueError(f"multiple custom color classes on one SVG element: {tag_text}")

        class_name = custom_classes[0]
        color = colors[class_name]
        changed = re.sub(r"currentColor", color, tag_text, flags=re.IGNORECASE)
        changed = re.sub(r"context-fill", color, changed, flags=re.IGNORECASE)
        changed = re.sub(r"context-stroke", color, changed, flags=re.IGNORECASE)

        remaining = [item for item in classes if item != class_name]
        changed_class = CLASS_ATTR_RE.search(changed)
        if changed_class is None:
            raise ValueError(f"class attribute vanished while baking color: {tag_text}")
        if remaining:
            quote = changed_class.group(1)
            replacement = f' class={quote}{" ".join(remaining)}{quote}'
        else:
            replacement = ""
        return changed[: changed_class.start()] + replacement + changed[changed_class.end() :]

    changed = START_TAG_RE.sub(replace_tag, text)
    for class_name in colors:
        changed = re.sub(
            rf"\s*\.{re.escape(class_name)}\s*\{{\s*color\s*:\s*#[0-9a-fA-F]{{6}}\s*;\s*\}}",
            "",
            changed,
        )
    return changed


def mark_semantic_fallback(text: str, family: str) -> str:
    """Identify artwork generated by this pass for the theme builder.

    The marker lets ``make-colorful-theme.py`` distinguish a baked custom
    color from genuine fixed-color Papirus artwork. It is deliberately an SVG
    comment, so it has no effect on rendering in Plasma or other icon loaders.
    """
    marker = f"<!-- papirus-colorful-semantic-fallback:{family} -->"
    if SEMANTIC_FALLBACK_RE.search(text):
        return SEMANTIC_FALLBACK_RE.sub(marker, text, count=1)
    match = SVG_OPEN_RE.search(text)
    if match is None:
        raise ValueError("SVG opening tag not found while marking fallback")
    return text[: match.end()] + marker + text[match.end() :]


def reset_previous_fallback(text: str, theme: str) -> tuple[str, bool]:
    """Restore this tool's previous family before applying a new decision."""
    marker_match = SEMANTIC_FALLBACK_RE.search(text)
    if marker_match is None:
        return text, False

    previous_family = marker_match.group("family")
    changed = SEMANTIC_FALLBACK_RE.sub("", text, count=1)
    if previous_family not in FAMILY_CLASS:
        return changed, True

    previous_class = FAMILY_CLASS[previous_family]
    current_color = CUSTOM_COLORS[theme].get(previous_class)
    if current_color is None:
        if previous_class != "ColorScheme-Text":
            changed = re.sub(
                rf'(class\s*=\s*["\'][^"\']*)\b{re.escape(previous_class)}\b',
                rf"\1ColorScheme-Text",
                changed,
            )
        return changed, True

    def restore_tag(match: re.Match[str]) -> str:
        tag_text = match.group(0)
        candidates = (current_color,) + LEGACY_CUSTOM_COLORS.get(previous_class, ())
        previous_color = next(
            (
                color
                for color in candidates
                if re.search(re.escape(color), tag_text, re.IGNORECASE) is not None
            ),
            None,
        )
        if previous_color is None:
            return tag_text
        restored = re.sub(
            re.escape(previous_color), "currentColor", tag_text, flags=re.IGNORECASE
        )
        class_match = CLASS_ATTR_RE.search(restored)
        if class_match:
            classes = class_match.group("value").split()
            if "ColorScheme-Text" not in classes:
                classes.append("ColorScheme-Text")
            quote = class_match.group(1)
            replacement = f' class={quote}{" ".join(classes)}{quote}'
            return (
                restored[: class_match.start()]
                + replacement
                + restored[class_match.end() :]
            )
        insert_at = len(restored) - (2 if restored.endswith("/>") else 1)
        return restored[:insert_at] + ' class="ColorScheme-Text"' + restored[insert_at:]

    return START_TAG_RE.sub(restore_tag, changed), True


def recolor_text(
    text: str, theme: str, decision: Decision, icon_name: str | None = None
) -> str:
    class_name = FAMILY_CLASS[decision.family]
    changed, was_fallback = reset_previous_fallback(text, theme)
    changed = synchronize_standard_palette(changed, theme)
    reset_text = changed
    if class_name != "ColorScheme-Text":
        changed = CLASS_TEXT_RE.sub(rf"\1{class_name}", changed)
        if changed != reset_text and class_name not in CUSTOM_COLORS[theme]:
            changed = ensure_custom_style(changed, theme, class_name)
    changed = bake_custom_colors(changed, theme)
    if icon_name in FULL_OPACITY_ICONS:
        changed = re.sub(r";?opacity\s*:\s*(?:0?\.35|35%)", "", changed)

    # Standard KDE color classes remain dynamically detectable. The four
    # additional families use fixed fills because Plasma drops unknown CSS
    # classes, so mark those baked fallbacks explicitly. This also migrates
    # files produced by earlier versions of this tool that lack the marker.
    custom_color = CUSTOM_COLORS[theme].get(class_name)
    custom_fallback = (
        custom_color is not None
        and custom_color.lower() in changed.lower()
        and STYLE_RE.search(changed) is not None
    )
    standard_fallback = (
        decision.family != "neutral"
        and class_name not in CUSTOM_COLORS[theme]
        and re.search(
            rf'class\s*=\s*["\'][^"\']*\b{re.escape(class_name)}\b',
            changed,
        )
        is not None
        and STYLE_RE.search(changed) is not None
    )
    # Neutral monochrome icons must remain ordinary KDE color-scheme icons.
    # In particular, do not mark them for the colorful-theme builder: marked
    # fallbacks are baked to a fixed Papirus grey during installation, whereas
    # ColorScheme-Text/currentColor follows the active text brightness just as
    # it does in Breeze. A rerun also removes old ``:neutral`` markers through
    # reset_previous_fallback() above.
    should_mark = decision.family != "neutral" and (
        was_fallback or changed != text or custom_fallback or standard_fallback
    )
    if should_mark:
        changed = mark_semantic_fallback(changed, decision.family)
    return changed


def iter_sources(repo_root: Path):
    for theme in THEMES:
        for relative_root in SUPPORTED_ROOTS:
            root = repo_root / theme / relative_root
            if not root.is_dir():
                raise FileNotFoundError(root)
            # Several Dark roots inherit the Papirus directory wholesale.
            # Process the owning root once; otherwise the Dark pass rewrites
            # the same physical light-theme files with the vivid palette.
            if root.is_symlink():
                continue
            for path in sorted(root.glob("*.svg")):
                if path.is_symlink():
                    continue
                yield theme, relative_root.split("/")[-1], path


def run(repo_root: Path, apply: bool) -> list[Result]:
    results: list[Result] = []
    for theme, context, path in iter_sources(repo_root):
        text = path.read_text(encoding="utf-8", errors="strict")
        decision = decide_family(path, context)
        changed_text = recolor_text(text, theme, decision, normalized_name(path))
        changed = changed_text != text
        if apply and changed:
            path.write_text(changed_text, encoding="utf-8")
        results.append(Result(path, decision.family, decision.reason, changed))
    return results


def print_report(results: list[Result], repo_root: Path) -> None:
    families = Counter(result.family for result in results)
    changes = Counter(result.family for result in results if result.changed)
    reasons = Counter(result.reason for result in results if result.changed)
    print(f"Sources reviewed: {len(results)}")
    print(f"Sources needing changes: {sum(changes.values())}")
    print("Decisions: " + ", ".join(f"{key}={value}" for key, value in sorted(families.items())))
    print("Changes: " + ", ".join(f"{key}={value}" for key, value in sorted(changes.items())))
    print("Top change rules:")
    for reason, count in reasons.most_common(20):
        print(f"  {count:4}  {reason}")
    ambiguous = [
        str(result.path.relative_to(repo_root))
        for result in results
        if result.family == "neutral" and result.reason == "ambiguous"
    ]
    print(f"Intentional ambiguous neutrals: {len(ambiguous)}")
    for path in ambiguous[:30]:
        print(f"  {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Papirus repository root",
    )
    parser.add_argument("--apply", action="store_true", help="write changes in place")
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    results = run(repo_root, apply=args.apply)
    print_report(results, repo_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
