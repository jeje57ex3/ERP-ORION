"""
Orion ERP — Configuration de marque centralisée.
Modifier ce fichier pour changer le logo, les couleurs ou les textes de la marque.
"""

BRAND_NAME       = "Orion ERP"
BRAND_SHORT_NAME = "Orion"
BRAND_TAGLINE    = "Pilotez votre entreprise avec précision"
BRAND_VERSION    = "v1.0.0"

# ── Logos ──────────────────────────────────────────────────────────────────
# Logo principal (fond clair) — wordmark + icône géométrique
BRAND_LOGO_PATH       = "img/brand/orion-logo.svg"
# Logo fond sombre — version crème/blanche
BRAND_LOGO_LIGHT_PATH = "img/brand/orion-logo-white.svg"
# Alias pour rétrocompatibilité
LOGO_PATH             = BRAND_LOGO_PATH
LOGO_WHITE_PATH       = BRAND_LOGO_LIGHT_PATH

# Icône seule (carré, sans wordmark) — sidebar, favicon, petits espaces
BRAND_ICON_PATH       = "img/brand/orion-icon.svg"
BRAND_ICON_LIGHT_PATH = "img/brand/orion-icon-white.svg"

# Favicon
BRAND_FAVICON_PATH    = "img/brand/orion-icon.svg"

# ── Palette ────────────────────────────────────────────────────────────────
BRAND_PRIMARY_COLOR   = "#2B1808"    # Brun foncé (L gauche/bas du logo)
BRAND_SECONDARY_COLOR = "#C6A15B"    # Or/champagne (L droite/haut du logo)
BRAND_ACCENT_COLOR    = "#E8D8B0"    # Sable clair
BRAND_BG_COLOR        = "#F8F3EA"    # Fond crème

BRAND_COLORS = {
    "primary":        BRAND_PRIMARY_COLOR,
    "primary_dark":   "#1C100A",
    "secondary":      BRAND_SECONDARY_COLOR,
    "secondary_dark": "#9D7A3F",
    "accent":         BRAND_ACCENT_COLOR,
    "bg":             BRAND_BG_COLOR,
    "text":           "#2B2118",
}

# ── Short aliases (rétrocompatibilité) ─────────────────────────────────────
BRAND_SHORT = BRAND_SHORT_NAME
