"""Shared Xef/Papirus colors used by the colorful-theme tools."""

XEF_COLORS = {
    # Main identity
    "accent": "#127bdc",
    "accent_dark": "#0e62b0",
    "generated_blue": "#4a91e1",

    # Semantic colors
    "success": "#4caf50",
    "warning": "#ff9800",
    "error": "#f44336",

    # Additional Papirus families
    "purple": "#673ab7",
    "pink": "#f9548f",
    "yellow": "#fecd38",
    "cyan": "#00bcd4",

    # Generated neutral icons
    "dark_theme_neutral": "#cccccc",
    "light_theme_neutral": "#5d5d5d",

    # Papirus material limits
    "light_limit": "#e4e4e4",
    "dark_limit": "#4f4f4f",

    # Layer effects
    "shadow": "#000000",
    "highlight": "#ffffff",
}

# Higher-contrast counterparts for Papirus and Papirus-Light. These are used
# only when colored monochrome artwork is baked for a light surface; the vivid
# palette above remains unchanged for Papirus-Dark.
XEF_LIGHT_COLORS = {
    **XEF_COLORS,
    "accent": "#1565c0",
    "generated_blue": "#1976d2",
    "success": "#388e3c",
    "warning": "#e45100",
    "error": "#d32f2f",
    "purple": "#673ab7",
    "pink": "#d81b60",
    "yellow": "#a87900",
    "cyan": "#00838f",
}
