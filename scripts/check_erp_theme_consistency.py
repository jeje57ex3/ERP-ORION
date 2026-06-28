from pathlib import Path
import sys

ROOTS = [
    Path("templates"),
    Path("frontend/erp"),
    Path("frontend/admin"),
    Path("frontend/shared"),
]

EXCLUDED_PARTS = [
    "templates/store",
    "templates/public",
    "templates/siecle",
    "templates/lunea",
    "frontend/siecle-store",
    "frontend/lunea-store",
]

FORBIDDEN_PATTERNS = [
    # Hard-coded Bootstrap blue button class not overridden by CSS
    "btn-primary",
    # Hard-coded blue hex values
    "#0d6efd",
    "#007bff",
    "rgb(13, 110, 253)",
    "background: blue",
    "background-color: blue",
    # Note: text-primary and bg-primary are NOT forbidden here because
    # orion-theme.css overrides them to gold via CSS cascade.
]


def is_excluded(path):
    normalized = str(path).replace("\\", "/")
    return any(part in normalized for part in EXCLUDED_PARTS)


def main():
    errors = []

    for root in ROOTS:
        if not root.exists():
            continue

        for path in root.rglob("*"):
            # CSS files may define these selectors legitimately — skip them
            if path.suffix.lower() not in [".html", ".jsx", ".tsx", ".js", ".ts"]:
                continue

            if is_excluded(path):
                continue

            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            for pattern in FORBIDDEN_PATTERNS:
                if pattern in text:
                    errors.append((path, pattern))

    if errors:
        print("Incohérences thème ERP détectées :")
        for path, pattern in errors:
            print(f"  - {path}: {pattern!r}")
        sys.exit(1)

    print("Thème ERP cohérent : aucune couleur interdite détectée.")


if __name__ == "__main__":
    main()
