"""
Replace {% extends "erp_base.html" %} / {% extends "base.html" %} with
{% extends "layouts/orion_internal.html" %} in internal-only template directories.

Safe directories (internal, not public-facing):
  templates/orion_admin/
  templates/private_saas/
  templates/high_availability/
  templates/orion_ai/
  templates/continuous_improvement/
  templates/lunea_beauty_profile/
  templates/siecle_creations/
  templates/website_shop_settings/

Run with --dry-run first to preview changes.
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
]

OLD_EXTENDS = [
    re.compile(r'{%\s*extends\s+["\']erp_base\.html["\']\s*%}'),
    re.compile(r'{%\s*extends\s+["\']layouts/erp_base\.html["\']\s*%}'),
]

NEW_EXTENDS = '{% extends "layouts/orion_internal.html" %}'

ALREADY_MIGRATED = re.compile(r'{%\s*extends\s+["\']layouts/orion_internal\.html["\']\s*%}')


def process_file(path: Path, dry_run: bool) -> bool:
    text = path.read_text(encoding="utf-8", errors="ignore")

    if ALREADY_MIGRATED.search(text):
        return False  # already on new layout

    new_text = text
    for pattern in OLD_EXTENDS:
        new_text = pattern.sub(NEW_EXTENDS, new_text)

    if new_text == text:
        return False

    if dry_run:
        print(f"  [DRY-RUN] Would update: {path}")
    else:
        path.write_text(new_text, encoding="utf-8")
        print(f"  Updated: {path}")

    return True


def main():
    dry_run = "--dry-run" in sys.argv
    if dry_run:
        print("Mode DRY-RUN — aucun fichier ne sera modifié.\n")

    changed, skipped = [], []

    for d in INTERNAL_DIRS:
        if not d.exists():
            print(f"  [SKIP] Répertoire introuvable : {d}")
            continue

        for path in d.rglob("*.html"):
            if process_file(path, dry_run):
                changed.append(path)
            else:
                skipped.append(path)

    print(f"\nModifiés : {len(changed)}")
    print(f"Ignorés  : {len(skipped)}")

    if dry_run and changed:
        print("\nRelancez sans --dry-run pour appliquer les modifications.")


if __name__ == "__main__":
    main()
