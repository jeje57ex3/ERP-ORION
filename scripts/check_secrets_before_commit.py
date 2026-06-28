"""
Détecte les secrets et clés privées avant commit.
Utilisé par le hook .git/hooks/pre-commit.

Usage :
    python scripts/check_secrets_before_commit.py

Retourne exit(1) si un secret est détecté — le commit est bloqué.
"""

import re
import subprocess
import sys
from pathlib import Path

SECRET_PATTERNS: dict[str, str] = {
    "Stripe live secret":       r"sk_live_[A-Za-z0-9_]+",
    "Stripe webhook secret":    r"whsec_[A-Za-z0-9_]+",
    "OpenAI key":               r"sk-proj-[A-Za-z0-9_\-]+|sk-[A-Za-z0-9_\-]{20,}",
    "AWS access key":           r"AKIA[0-9A-Z]{16}",
    "Private key block":        r"-----BEGIN (RSA |EC |OPENSSH |)?PRIVATE KEY-----",
    "Django hardcoded secret":  r"SECRET_KEY\s*=\s*['\"][^'\"]{20,}['\"]",
}

# Extensions de fichiers à ignorer (binaires, images, etc.)
SKIP_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".webp",
    ".pdf", ".zip", ".tar", ".gz", ".whl", ".pyc", ".pyo",
    ".mo", ".po", ".map", ".min.js", ".min.css",
    ".pem", ".key", ".p12", ".pfx",  # ceux-là ne devraient jamais être commités
}

# Fichiers à ignorer même s'ils correspondent
SKIP_FILES = {
    ".env.example",
    "check_secrets_before_commit.py",  # ce script lui-même contient les patterns
}


def get_staged_files() -> list[Path]:
    """Retourne la liste des fichiers stagés (ajoutés à l'index git)."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    return [Path(f.strip()) for f in result.stdout.splitlines() if f.strip()]


def get_staged_content(path: Path) -> str:
    """Retourne le contenu stagé d'un fichier (pas la version disque)."""
    result = subprocess.run(
        ["git", "show", f":{path}"],
        capture_output=True,
        text=True,
        errors="ignore",
    )
    return result.stdout if result.returncode == 0 else ""


def scan_content(name: str, content: str) -> list[tuple[str, str]]:
    """Renvoie la liste (label, extrait) des secrets trouvés dans content."""
    found = []
    for label, pattern in SECRET_PATTERNS.items():
        for m in re.finditer(pattern, content):
            snippet = m.group(0)[:60]
            found.append((label, snippet))
    return found


def main() -> int:
    staged = get_staged_files()
    if not staged:
        print("check-secrets: aucun fichier stage, OK")
        return 0

    violations: list[tuple[Path, str, str]] = []

    for path in staged:
        if path.suffix.lower() in SKIP_EXTENSIONS:
            continue
        if path.name in SKIP_FILES:
            continue

        content = get_staged_content(path)
        if not content:
            continue

        for label, snippet in scan_content(path.name, content):
            violations.append((path, label, snippet))

    if violations:
        print()
        print("=" * 60)
        print("COMMIT BLOQUE — secrets detectes dans les fichiers stages :")
        print("=" * 60)
        for path, label, snippet in violations:
            print(f"  Fichier : {path}")
            print(f"  Type    : {label}")
            print(f"  Extrait : {snippet!r}")
            print()
        print("Actions :")
        print("  1. Retirer le secret du fichier")
        print("  2. Stocker la valeur dans .env (jamais commite)")
        print("  3. Relancer : git add <fichier> && git commit")
        print("=" * 60)
        print()
        return 1

    print(f"check-secrets: {len(staged)} fichier(s) verifies, aucun secret detecte OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
