"""
Replace Bootstrap 5 class names with Orion Internal class names
in internal ERP templates.

Operates on class="..." attribute values only (not arbitrary text).
Run with --dry-run to preview. Pass --dir=<path> to limit scope.
"""

from pathlib import Path
import sys
import re

INTERNAL_DIRS = [
    Path("templates/orion_admin"),
    Path("templates/private_saas"),
    Path("templates/high_availability"),
    Path("templates/orion_ai"),
    Path("templates/continuous_improvement"),
    Path("templates/lunea_beauty_profile"),
    Path("templates/siecle_creations"),
    Path("templates/website_shop_settings"),
    Path("templates/dashboard_widgets"),
]

# Order matters: longer/more-specific patterns first
REPLACEMENTS = [
    # Buttons — specific combos first
    ("btn btn-primary btn-sm",  "orion-btn primary sm"),
    ("btn btn-danger btn-sm",   "orion-btn danger sm"),
    ("btn btn-success btn-sm",  "orion-btn success sm"),
    ("btn btn-warning btn-sm",  "orion-btn warning sm"),
    ("btn btn-primary",         "orion-btn primary"),
    ("btn btn-secondary",       "orion-btn"),
    ("btn btn-danger",          "orion-btn danger"),
    ("btn btn-success",         "orion-btn success"),
    ("btn btn-warning",         "orion-btn warning"),
    ("btn btn-outline-primary", "orion-btn outline"),
    ("btn btn-sm",              "orion-btn sm"),
    ("btn-primary",             "orion-btn primary"),
    ("btn-secondary",           "orion-btn"),
    ("btn-danger",              "orion-btn danger"),
    ("btn-success",             "orion-btn success"),
    ("btn-warning",             "orion-btn warning"),
    ("btn-sm",                  "orion-btn sm"),
    # Tables
    ("table table-striped table-hover", "orion-table"),
    ("table table-striped",     "orion-table"),
    ("table table-hover",       "orion-table"),
    # Alerts
    ("alert alert-danger",      "orion-alert danger"),
    ("alert alert-warning",     "orion-alert warning"),
    ("alert alert-success",     "orion-alert success"),
    ("alert alert-info",        "orion-alert info"),
    # Badges
    ("badge bg-primary",        "orion-badge gold"),
    ("badge bg-success",        "orion-badge success"),
    ("badge bg-danger",         "orion-badge danger"),
    ("badge bg-warning",        "orion-badge warning"),
    ("badge bg-info",           "orion-badge info"),
    ("badge bg-secondary",      "orion-badge neutral"),
]

# Regex to find class="..." or class='...' attribute values
CLASS_ATTR_RE = re.compile(r'(class=["\'])([^"\']+)(["\'])')


def replace_classes(value: str) -> str:
    for old, new in REPLACEMENTS:
        value = value.replace(old, new)
    return value


def process_file(path: Path, dry_run: bool) -> bool:
    text = path.read_text(encoding="utf-8", errors="ignore")
    original = text

    def replacer(m):
        prefix, classes, suffix = m.group(1), m.group(2), m.group(3)
        return prefix + replace_classes(classes) + suffix

    new_text = CLASS_ATTR_RE.sub(replacer, text)

    if new_text == original:
        return False

    if dry_run:
        print(f"  [DRY-RUN] Would update: {path}")
    else:
        path.write_text(new_text, encoding="utf-8")
        print(f"  Updated: {path}")

    return True


def main():
    dry_run = "--dry-run" in sys.argv

    # Allow limiting scope via --dir=templates/orion_admin
    custom_dir = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--dir=")), None)
    dirs = [Path(custom_dir)] if custom_dir else INTERNAL_DIRS

    if dry_run:
        print("Mode DRY-RUN — aucun fichier ne sera modifié.\n")

    changed = []
    for d in dirs:
        if not d.exists():
            print(f"  [SKIP] Répertoire introuvable : {d}")
            continue

        for path in d.rglob("*.html"):
            if process_file(path, dry_run):
                changed.append(path)

    print(f"\nTotal modifiés : {len(changed)}")
    if dry_run and changed:
        print("Relancez sans --dry-run pour appliquer.")


if __name__ == "__main__":
    main()
