"""
apps/websites/security.py — Sécurité des formulaires publics de sites web
"""
import hashlib
import io
import logging
import re
from django.core.cache import cache
from django.utils.html import strip_tags
import bleach

logger = logging.getLogger('orion')

ALLOWED_HTML_TAGS = ['p', 'b', 'i', 'u', 'em', 'strong', 'a', 'ul', 'ol', 'li', 'br']
ALLOWED_HTML_ATTRS = {'a': ['href', 'title']}

RATE_LIMIT_PERIOD = 3600  # 1 heure
RATE_LIMIT_MAX = 10       # max 10 soumissions par heure par IP


def check_honeypot(post_data: dict, field_name: str = 'website_url_field') -> bool:
    """Retourne True si le honeypot est vide (formulaire valide), False si spam."""
    return not bool(post_data.get(field_name, ''))


def get_ip_hash(ip_address: str) -> str:
    """Retourne un hash de l'IP (pas de stockage direct de l'IP)."""
    if not ip_address:
        return ''
    return hashlib.sha256(ip_address.encode()).hexdigest()[:16]


def rate_limit_submission(ip_address: str, website_id: int) -> tuple[bool, int]:
    """
    Vérifie la limite de soumissions par IP par heure.
    Retourne (allowed, remaining_submissions).
    """
    ip_hash = get_ip_hash(ip_address)
    key = f'ws_form_rate_{website_id}_{ip_hash}'
    count = cache.get(key, 0)
    if count >= RATE_LIMIT_MAX:
        return False, 0
    cache.set(key, count + 1, RATE_LIMIT_PERIOD)
    return True, RATE_LIMIT_MAX - count - 1


def sanitize_html_content(content: str) -> str:
    """Nettoie le contenu HTML pour éviter les injections XSS."""
    try:
        return bleach.clean(content, tags=ALLOWED_HTML_TAGS, attributes=ALLOWED_HTML_ATTRS)
    except ImportError:
        return strip_tags(content)


#: Ce qu'un formulaire public peut déposer. Les documents bureautiques
#: sont exclus : on ne sait pas vérifier leur contenu, et un .docx est une
#: archive qui peut porter des macros. Un prospect qui veut joindre un
#: cahier des charges envoie un PDF ou une image.
EXTENSIONS_PUBLIQUES = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.pdf'}

TAILLE_MAX_PUBLIQUE = 10 * 1024 * 1024  # 10 Mo

#: Les premiers octets d'un PDF. Pour une image, c'est Pillow qui tranche.
ENTETE_PDF = b'%PDF-'


def assainir_css(css: str) -> str:
    """Le CSS personnalisé d'un thème, rendu incapable de fermer sa balise.

    LA SORTIE DE BALISE. `templates/websites/public/base.html` écrit
    `{{ theme.custom_css|safe }}` À L'INTÉRIEUR d'un élément `<style>`.
    Le filtre `safe` désactive l'échappement, et l'analyseur HTML ferme un
    élément `<style>` au premier `</style>` qu'il rencontre, SANS tenir
    compte de la syntaxe CSS. Une valeur contenant

        </style><script>…</script>

    sortait donc de la balise et exécutait son script sur une page
    PUBLIQUE, pour chaque visiteur. C'est un XSS stocké, déclenché par un
    champ que l'éditeur de thèmes de l'ERP propose.

    POURQUOI RETIRER « < » ET « > » PLUTÔT QU'ÉCHAPPER. Les échapper
    casserait le CSS — `&lt;` n'est pas une syntaxe valide dans une feuille
    de style, la règle entière serait ignorée. Et CSS n'a aucun besoin de
    ces deux caractères : ni un sélecteur, ni une propriété, ni une valeur
    n'en emploie. Les retirer ne coûte donc rien de légitime et ferme la
    sortie de balise, qui est la seule chose à craindre ici.

    On retire aussi les commentaires HTML, qu'un analyseur traite à part
    dans un élément `<style>`.
    """
    if not css:
        return ''
    propre = str(css)
    for interdit in ('<', '>'):
        propre = propre.replace(interdit, '')
    return propre


def validate_public_upload(file) -> tuple[bool, str]:
    """Valide un fichier déposé depuis un formulaire public.

    LES OCTETS SONT LUS, PAS SEULEMENT L'EXTENSION ET LE TYPE DÉCLARÉ.

    `file.content_type` vient de l'en-tête que le CLIENT a écrit dans sa
    requête, et l'extension du nom qu'il a choisi : les deux se falsifient
    d'un seul clic. Un fichier quelconque peut donc arriver sous le nom
    « photo.jpg » et le type « image/jpeg ».

    Le dépôt sait déjà le faire ailleurs — `apps/site_builder/api.py`
    ouvre l'image avec Pillow et appelle `verify()`, et
    `apps/accounts/signature.py` fait de même. La méthode existait à deux
    modules d'ici, et ce formulaire-ci, le seul qui soit PUBLIC, ne
    l'employait pas.

    Ce qu'on y gagne concrètement : un fichier qui n'est pas une image ne
    s'enregistre plus, et une image « bombe » — quelques kilooctets qui se
    décompressent en gigaoctets — est écartée par la borne de Pillow avant
    qu'une vignette ne la fasse tomber.
    """
    import os

    if not file:
        return True, ''

    extension = os.path.splitext(file.name or '')[1].lower()
    if extension not in EXTENSIONS_PUBLIQUES:
        return False, (
            f'Extension {extension or "(aucune)"} non autorisée. '
            f'Formats acceptés : '
            f'{", ".join(sorted(EXTENSIONS_PUBLIQUES))}.')

    if file.size > TAILLE_MAX_PUBLIQUE:
        return False, 'Fichier trop lourd (10 Mo maximum).'

    try:
        debut = file.read(2048)
        file.seek(0)
    except (OSError, ValueError):
        return False, 'Fichier illisible.'

    if extension == '.pdf':
        if not debut.startswith(ENTETE_PDF):
            return False, (
                'Ce fichier porte l’extension .pdf mais son contenu n’en '
                'est pas un.')
        return True, ''

    # Une image : c'est Pillow qui dit si les octets en sont une.
    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError:  # pragma: no cover
        # Sans Pillow on ne sait pas trancher. On refuse plutôt que
        # d'accepter : ce formulaire est public.
        return False, 'Validation des images indisponible.'

    try:
        contenu = file.read()
        file.seek(0)
        with Image.open(io.BytesIO(contenu)) as sonde:
            # `verify()` lit la structure sans décoder tous les pixels :
            # il écarte un fichier tronqué ou maquillé sans dépenser la
            # mémoire d'une image entière.
            sonde.verify()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        return False, (
            'Ce fichier n’est pas une image lisible, malgré son nom et son '
            'type déclaré.')

    return True, ''


def log_suspicious_submission(ip_address: str, website_id: int, reason: str) -> None:
    """Enregistre une soumission suspecte dans les logs."""
    logger.warning(
        f'[WEBSITES] Soumission suspecte — website={website_id} ip={ip_address} raison={reason}'
    )
