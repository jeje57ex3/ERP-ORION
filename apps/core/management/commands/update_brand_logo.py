"""
python manage.py update_brand_logo --url="https://..."

Télécharge un logo depuis une URL et l'installe dans static/img/brand/.
Options :
  --url          URL de l'image (obligatoire)
  --name         Nom de fichier cible sans extension (défaut: orion-logo)
  --variant      Variante: main | white | icon | icon-white (défaut: main)
  --force        Écrase sans demander confirmation
"""
import os
import urllib.request
import urllib.error
import mimetypes
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings


ALLOWED_MIME = {
    "image/svg+xml":  ".svg",
    "image/png":      ".png",
    "image/jpeg":     ".jpg",
    "image/webp":     ".webp",
    "image/gif":      ".gif",
}

VARIANT_NAMES = {
    "main":        "orion-logo",
    "white":       "orion-logo-white",
    "icon":        "orion-icon",
    "icon-white":  "orion-icon-white",
    "favicon":     "orion-icon",  # same as icon
}


class Command(BaseCommand):
    help = "Met à jour le logo Orion ERP depuis une URL distante."

    def add_arguments(self, parser):
        parser.add_argument("--url",     type=str, required=True,  help="URL de l'image à télécharger")
        parser.add_argument("--name",    type=str, default="",     help="Nom de fichier sans extension (écrase --variant si fourni)")
        parser.add_argument("--variant", type=str, default="main", choices=list(VARIANT_NAMES), help="Variante du logo (main|white|icon|icon-white)")
        parser.add_argument("--force",   action="store_true",       help="Écrase le fichier existant sans demander")

    def handle(self, *args, **options):
        url     = options["url"].strip()
        variant = options["variant"]
        name    = options["name"].strip() or VARIANT_NAMES.get(variant, "orion-logo")
        force   = options["force"]

        self.stdout.write(self.style.HTTP_INFO(f"\nTéléchargement : {url}"))

        # ── Téléchargement ────────────────────────────────────────────────
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "OrionERP/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                if resp.status != 200:
                    raise CommandError(f"Erreur HTTP {resp.status} lors du téléchargement.")

                content_type = resp.headers.get("Content-Type", "").split(";")[0].strip()
                # Fallback : deviner depuis l'URL
                if content_type not in ALLOWED_MIME:
                    guessed, _ = mimetypes.guess_type(url)
                    if guessed in ALLOWED_MIME:
                        content_type = guessed
                    else:
                        raise CommandError(
                            f"Type MIME non supporté : {content_type!r}.\n"
                            f"Types acceptés : {', '.join(ALLOWED_MIME)}"
                        )

                ext      = ALLOWED_MIME[content_type]
                data     = resp.read()

        except urllib.error.URLError as exc:
            raise CommandError(f"Impossible de télécharger l'image : {exc.reason}")

        # ── Dossier cible ─────────────────────────────────────────────────
        brand_dir = Path(settings.STATICFILES_DIRS[0]) / "img" / "brand"
        brand_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{name}{ext}"
        dest     = brand_dir / filename

        if dest.exists() and not force:
            answer = input(f"\nFichier {dest} déjà présent. Écraser ? [o/N] ").strip().lower()
            if answer not in ("o", "oui", "y", "yes"):
                self.stdout.write(self.style.WARNING("Annulé."))
                return

        # ── Écriture ──────────────────────────────────────────────────────
        dest.write_bytes(data)
        size_kb = len(data) / 1024

        self.stdout.write(self.style.SUCCESS(
            f"\n✔  Logo enregistré : {dest}  ({size_kb:.1f} Ko, type: {content_type})"
        ))

        # ── Conseils post-installation ────────────────────────────────────
        self.stdout.write(
            f"\nPensez à lancer :\n"
            f"  python manage.py collectstatic --noinput\n\n"
            f"Le logo est disponible dans les templates via :\n"
            f"  {{% static 'img/brand/{filename}' %}}\n"
            f"ou via la variable de contexte :\n"
            f"  {{% static BRAND_LOGO_PATH %}}\n"
        )
