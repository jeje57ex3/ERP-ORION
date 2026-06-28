from pathlib import Path

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

REPLACEMENTS = {
    "btn btn-primary": "orion-btn primary",
    "btn-primary": "orion-btn primary",
    "btn btn-secondary": "orion-btn",
    "btn-secondary": "orion-btn",
    "btn btn-danger": "orion-btn danger",
    "btn-danger": "orion-btn danger",
    "btn btn-warning": "orion-btn warning",
    "btn-warning": "orion-btn warning",
    "btn btn-success": "orion-btn success",
    "btn-success": "orion-btn success",
    "btn btn-sm": "orion-btn sm",
    "btn-sm": "orion-btn sm",
    "card-header": "orion-card-header",
    "card-body": "orion-card-body",
    "table table-striped": "orion-table",
    "table table-hover": "orion-table",
    "alert alert-danger": "orion-alert danger",
    "alert alert-warning": "orion-alert warning",
    "alert alert-success": "orion-alert success",
    "alert alert-info": "orion-alert info",
    "badge bg-primary": "orion-badge gold",
    "badge bg-success": "orion-badge success",
    "badge bg-danger": "orion-badge danger",
    "badge bg-warning": "orion-badge warning",
    "badge bg-info": "orion-badge info",
    "badge bg-secondary": "orion-badge neutral",
}


def is_excluded(path):
    normalized = str(path).replace("\\", "/")
    return any(part in normalized for part in EXCLUDED_PARTS)


def process_file(path):
    if is_excluded(path):
        return False

    text = path.read_text(encoding="utf-8")
    original = text

    for old, new in REPLACEMENTS.items():
        text = text.replace(old, new)

    if text != original:
        path.write_text(text, encoding="utf-8")
        return True

    return False


def main():
    changed = []

    for root in ROOTS:
        if not root.exists():
            continue

        for path in root.rglob("*"):
            if path.suffix.lower() not in [".html", ".jsx", ".tsx", ".js", ".ts"]:
                continue

            if process_file(path):
                changed.append(path)

    print("Fichiers modifiés :")
    for path in changed:
        print(f"  - {path}")

    print(f"\nTotal : {len(changed)}")


if __name__ == "__main__":
    main()
