"""
Management command: orion_ui_cleanup

Runs all Orion UI consistency checks and optional cleanup operations.

Usage:
    python manage.py orion_ui_cleanup
    python manage.py orion_ui_cleanup --check-only
    python manage.py orion_ui_cleanup --list-widgets
    python manage.py orion_ui_cleanup --list-duplicates
"""

from django.core.management.base import BaseCommand
from pathlib import Path
import re


INTERNAL_TEMPLATE_DIRS = [
    Path("templates/orion_admin"),
    Path("templates/private_saas"),
    Path("templates/high_availability"),
    Path("templates/orion_ai"),
    Path("templates/continuous_improvement"),
    Path("templates/lunea_beauty_profile"),
    Path("templates/siecle_creations"),
    Path("templates/website_shop_settings"),
]

PUBLIC_DIRS = [
    Path("templates/store"),
    Path("templates/public"),
    Path("templates/siecle"),
    Path("templates/lunea"),
    Path("frontend/siecle-store"),
    Path("frontend/lunea-store"),
]

FORBIDDEN_IN_INTERNAL = [
    "#0d6efd",
    "#007bff",
    "btn-primary",
]

FORBIDDEN_IN_PUBLIC = [
    "orion-internal.css",
    "orion-erp.css",
    "orion-sidebar",
    "orion-app-shell",
]


class Command(BaseCommand):
    help = "Vérifie et nettoie la cohérence du système UI Orion Internal."

    def add_arguments(self, parser):
        parser.add_argument(
            "--check-only",
            action="store_true",
            help="Vérifier uniquement, sans modifier de fichier.",
        )
        parser.add_argument(
            "--list-widgets",
            action="store_true",
            help="Lister tous les widgets de dashboard enregistrés.",
        )
        parser.add_argument(
            "--list-duplicates",
            action="store_true",
            help="Chercher les doublons de widgets et modules nav.",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("Orion UI Cleanup\n"))

        if options["list_widgets"]:
            self._list_widgets()
            return

        if options["list_duplicates"]:
            self._list_duplicates()
            return

        errors = 0
        errors += self._check_internal_templates()
        errors += self._check_public_templates()

        if errors:
            self.stdout.write(self.style.ERROR(f"\n{errors} problème(s) détecté(s). Voir ci-dessus."))
        else:
            self.stdout.write(self.style.SUCCESS("\nTout est cohérent ✓"))

    def _check_internal_templates(self) -> int:
        self.stdout.write("  Vérification templates internes…")
        errors = 0

        for d in INTERNAL_TEMPLATE_DIRS:
            if not d.exists():
                continue
            for path in d.rglob("*.html"):
                if path.suffix.lower() == ".css":
                    continue
                try:
                    text = path.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                for pattern in FORBIDDEN_IN_INTERNAL:
                    if pattern in text:
                        self.stdout.write(
                            self.style.WARNING(f"    {path}: {pattern!r}")
                        )
                        errors += 1

        return errors

    def _check_public_templates(self) -> int:
        self.stdout.write("  Vérification templates publics (pas de fuite thème interne)…")
        errors = 0

        for d in PUBLIC_DIRS:
            if not d.exists():
                continue
            for path in d.rglob("*"):
                if path.suffix.lower() not in {".html", ".js", ".css"}:
                    continue
                try:
                    text = path.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                for pattern in FORBIDDEN_IN_PUBLIC:
                    if pattern in text:
                        self.stdout.write(
                            self.style.ERROR(f"    FUITE: {path}: {pattern!r}")
                        )
                        errors += 1

        return errors

    def _list_widgets(self):
        try:
            from apps.dashboard_widgets.registry import get_all_widgets
            widgets = get_all_widgets()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Impossible de charger les widgets: {e}"))
            return

        self.stdout.write(f"\n{len(widgets)} widget(s) enregistré(s):\n")
        for code, w in sorted(widgets.items(), key=lambda kv: kv[1].get("order", 100)):
            brand = f" [{w.get('brand_key')}]" if w.get("brand_key") else ""
            self.stdout.write(
                f"  {w.get('order', 100):>3}.  {code:<30}  {w.get('title','')}{brand}"
            )

    def _list_duplicates(self):
        try:
            from apps.dashboard_widgets.services import get_widgets_by_module
            groups = get_widgets_by_module()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Erreur: {e}"))
            return

        self.stdout.write("\nWidgets par module:\n")
        for module, codes in sorted(groups.items()):
            self.stdout.write(f"  {module}: {', '.join(sorted(codes))}")
