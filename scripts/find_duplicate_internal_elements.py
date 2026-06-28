"""
Detect duplicate UI element registrations in internal ERP templates:
  - Nav modules with the same id registered multiple times
  - Dashboard widget codes registered more than once
  - Template files overriding the same {% block %} in multiple child templates

Output: human-readable report with file locations.
"""

from pathlib import Path
import re
from collections import defaultdict


TEMPLATE_DIRS = [
    Path("templates"),
    Path("apps"),
]

EXCLUDED = [
    "templates/store",
    "templates/public",
    "templates/siecle",
    "templates/lunea",
    "templates/layouts",
    "frontend/siecle-store",
    "frontend/lunea-store",
]


def is_excluded(path: Path) -> bool:
    s = str(path).replace("\\", "/")
    return any(ex in s for ex in EXCLUDED)


def collect_html_files():
    files = []
    for root in TEMPLATE_DIRS:
        if not root.exists():
            continue
        for p in root.rglob("*.html"):
            if not is_excluded(p):
                files.append(p)
    return files


def find_block_names(text: str):
    return re.findall(r'\{%\s*block\s+(\w+)\s*%\}', text)


def find_extends(text: str):
    m = re.search(r'\{%\s*extends\s+["\']([^"\']+)["\']\s*%\}', text)
    return m.group(1) if m else None


def find_nav_module_ids(text: str):
    return re.findall(r"['\"]id['\"]\s*:\s*['\"]([^'\"]+)['\"]", text)


def find_widget_codes(path: Path) -> list[str]:
    """Scan Python files for @register(code=...) widget registrations."""
    codes = []
    text = path.read_text(encoding="utf-8", errors="ignore")
    codes += re.findall(r'@register\(code=["\']([^"\']+)["\']', text)
    codes += re.findall(r'register\(code=["\']([^"\']+)["\']', text)
    return codes


def main():
    print("=" * 60)
    print("ORION — Détection doublons éléments UI")
    print("=" * 60)

    # ── 1. Blocs définis deux fois dans le même fichier template ──
    print("\n[1] Blocs Django définis plus d'une fois dans le même template\n")

    found_block_dupes = False
    for path in collect_html_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        blocks = find_block_names(text)
        seen: dict[str, int] = {}
        for b in blocks:
            seen[b] = seen.get(b, 0) + 1
        dupes = {b: c for b, c in seen.items() if c > 1}
        if dupes:
            found_block_dupes = True
            print(f"  {path}")
            for b, c in sorted(dupes.items()):
                print(f"    >> bloc {b!r} défini {c} fois")

    if not found_block_dupes:
        print("  OK Aucun bloc défini deux fois dans le même template.")

    # ── 2. Codes widget en double ─────────────────────────────────
    print("\n[2] Codes de widgets enregistrés plusieurs fois\n")
    widget_code_files: dict[str, list[Path]] = defaultdict(list)

    for root in [Path("apps")]:
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            codes = find_widget_codes(path)
            for code in codes:
                widget_code_files[code].append(path)

    found_widget_dupes = False
    for code, files in sorted(widget_code_files.items()):
        if len(files) > 1:
            found_widget_dupes = True
            print(f"  Widget code: {code!r}  ({len(files)} fichiers)")
            for f in files:
                print(f"    - {f}")

    if not found_widget_dupes:
        print("  OK Aucun code de widget en doublon.")

    # ── 3. IDs de modules nav en double ──────────────────────────
    print("\n[3] IDs de modules nav potentiellement dupliqués\n")
    nav_id_files: dict[str, list[Path]] = defaultdict(list)

    for root in [Path("apps")]:
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="ignore")
            for mid in find_nav_module_ids(text):
                nav_id_files[mid].append(path)

    found_nav_dupes = False
    for mid, files in sorted(nav_id_files.items()):
        if len(files) > 1:
            found_nav_dupes = True
            print(f"  Module id: {mid!r}  ({len(files)} fichiers)")
            for f in files:
                print(f"    - {f}")

    if not found_nav_dupes:
        print("  OK Aucun doublon d'ID de module nav.")

    print("\n" + "=" * 60)
    print("Analyse terminée.")


if __name__ == "__main__":
    main()
