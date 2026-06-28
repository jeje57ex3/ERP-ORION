"""
Vérifier la cohérence du thème Orion Internal dans les templates ERP.

Règles :
  - Pas de classe Bootstrap brute non migrée (btn-primary, badge bg-primary, etc.)
  - Pas de couleur hex codée en dur (Bootstrap bleu, bleu historique)
  - Pas d'extends vers erp_base.html dans les répertoires internes

Retourne exit(1) si des incohérences sont trouvées.
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

EXCLUDED_PARTS = [
    "templates/store",
    "templates/public",
    "templates/siecle",
    "templates/lunea",
    "frontend/siecle-store",
    "frontend/lunea-store",
    "/migrations/",
]

# Patterns forbidden in HTML/JS/TS templates (not CSS)
FORBIDDEN = [
    # Bootstrap blue hardcoded
    "#0d6efd",
    "#007bff",
    "rgb(13, 110, 253)",
    # Old Bootstrap class names (specific, not the generic btn btn- combo)
    "btn-primary",
    "btn-secondary",
    "btn-danger",
    "btn-warning",
    "btn-success",
    # Old Bootstrap alert classes
    "alert alert-danger",
    "alert alert-warning",
    "alert alert-success",
    "alert alert-info",
]

# Warn-only patterns (less critical, but worth flagging)
WARNINGS = [
    "card-header",   # should be orion-card-header
    "card-body",     # should be orion-card-body
]

EXTENDS_ERP_BASE = re.compile(r'\{%\s*extends\s+["\']erp_base\.html["\']\s*%\}')


def is_excluded(path: Path) -> bool:
    s = str(path).replace("\\", "/")
    return any(ex in s for ex in EXCLUDED_PARTS)


def check_file(path: Path):
    errors, warns = [], []

    if path.suffix.lower() in {".css", ".scss"}:
        return errors, warns  # CSS files may define these selectors

    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return errors, warns

    for pattern in FORBIDDEN:
        if pattern in text:
            errors.append(f"Interdit: {pattern!r}")

    for pattern in WARNINGS:
        if pattern in text:
            warns.append(f"À migrer: {pattern!r}")

    if EXTENDS_ERP_BASE.search(text):
        errors.append("Étend erp_base.html au lieu de layouts/orion_internal.html")

    return errors, warns


def main():
    all_errors = []
    all_warnings = []

    # Check all internal template dirs
    files_checked = 0
    for d in INTERNAL_DIRS:
        if not d.exists():
            continue
        for path in d.rglob("*"):
            if path.suffix.lower() not in {".html", ".jsx", ".tsx", ".js", ".ts"}:
                continue
            if is_excluded(path):
                continue
            errs, warns = check_file(path)
            if errs:
                all_errors.append((path, errs))
            if warns:
                all_warnings.append((path, warns))
            files_checked += 1

    print(f"Fichiers analyses : {files_checked}")

    if all_warnings:
        print(f"\nAvertissements ({len(all_warnings)} fichiers) :")
        for path, ws in all_warnings:
            print(f"  {path}")
            for w in ws:
                print(f"    [WARN]  {w}")

    if all_errors:
        print(f"\nErreurs ({len(all_errors)} fichiers) :")
        for path, errs in all_errors:
            print(f"  {path}")
            for e in errs:
                print(f"    [ERR]  {e}")
        sys.exit(1)

    print("\nTheme Orion Internal coherent OK")


if __name__ == "__main__":
    main()
