"""
Vérifier que les templates et assets publics n'ont aucune référence
aux classes ou fichiers CSS du système interne Orion.

Règle : les sites publics (SIÈCLE, LUNEA, Store) ne doivent jamais charger
orion-internal.css, orion-erp.css, ni utiliser des classes comme orion-btn,
orion-card, orion-sidebar, etc.

Retourne exit(1) si des violations sont trouvées.
"""

from pathlib import Path
import sys

PUBLIC_DIRS = [
    Path("templates/store"),
    Path("templates/public"),
    Path("templates/siecle"),
    Path("templates/lunea"),
    Path("frontend/siecle-store"),
    Path("frontend/lunea-store"),
]

FORBIDDEN_INTERNAL = [
    "orion/css/orion-internal",
    "orion/css/orion-erp",
    "erp/css/orion-erp",
    "orion-internal.css",
    "orion-erp.css",
    # Internal CSS classes that must not appear in public templates
    "orion-sidebar",
    "orion-app-shell",
    "orion-topbar",
    "orion-widget-grid",
    "orion-metric-card",
    "orion-nav-link",
    "orion-breadcrumb",
    "erp-shell",
    "orion-erp",
]

ALLOWED_SHARED = [
    # These may legitimately appear in public templates
    # (none for now — extend if a shared component is added)
]


def is_public_file(path: Path) -> bool:
    return path.suffix.lower() in {".html", ".jsx", ".tsx", ".js", ".css", ".scss"}


def main():
    violations = []

    for root in PUBLIC_DIRS:
        if not root.exists():
            continue

        for path in root.rglob("*"):
            if not is_public_file(path):
                continue

            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            for pattern in FORBIDDEN_INTERNAL:
                if any(allowed in pattern for allowed in ALLOWED_SHARED):
                    continue
                if pattern in text:
                    violations.append((path, pattern))

    if violations:
        print("ERREUR — Fuite thème interne vers sites publics :")
        for path, pattern in violations:
            print(f"  {path}  →  {pattern!r}")
        print(f"\n{len(violations)} violation(s) trouvée(s).")
        sys.exit(1)

    print("OK — Aucun thème interne détecté dans les templates publics.")


if __name__ == "__main__":
    main()
