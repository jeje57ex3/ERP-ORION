"""Qui peut lire quoi sous /media/, et comment ces fichiers sont servis.

**Le défaut corrigé.** `erp_btp/urls.py` ne servait `MEDIA_URL` que derrière
`if settings.DEBUG`. En production, nginx relaie `/media/` vers gunicorn
(voir `deployment/proxmox-appliance/nginx/orion-proxmox.conf.tmpl`), et
Django n'avait aucune route pour ce préfixe : WhiteNoise ne sert que
`STATIC_ROOT`. Résultat mesuré sur l'appliance : **aucun fichier téléversé
n'était accessible** — ni photo de produit, ni logo, ni PDF.

**Pourquoi la correction évidente était un piège.** Servir `MEDIA_ROOT` en
statique, comme le fait le mode DEBUG, aurait publié `employee_private/` —
les contrats, bulletins de paie et documents médicaux que
`hr.private_document_download` protège par un contrôle de rôle et un
journal d'accès. Une URL devinée aurait suffi à contourner les deux. Et
avec eux `bank_statements/`, `supplier_invoices/` (où figurent les prix
d'achat) et `expense_receipts/`.

**D'où un refus par défaut.** La politique ci-dessous autorise des
préfixes nommés ; tout le reste rend 404. L'inverse — « tout sauf cette
liste » — rendrait public, en silence, le prochain `upload_to` privé que
quelqu'un ajoutera. Il y a aujourd'hui une soixantaine de préfixes dans le
projet et la liste bougera encore ; le sens du défaut décide donc de ce qui
arrive quand on oublie de mettre quelque chose à jour. Le bon défaut est
celui qui ne fuit pas.

**Trois niveaux, et non deux.**

* `PREFIXES_PUBLICS` — destinés aux visiteurs anonymes des sites vitrines
  et de la boutique. C'est leur raison d'être.
* `PREFIXES_AUTHENTIFIES` — fichiers internes que l'ERP montre déjà à ses
  utilisateurs connectés, et dont le modèle ne porte aucune règle plus
  fine. Très loin d'être parfait, mais sans commune mesure avec l'anonyme.
* Tout le reste — jamais servi par `/media/`. Ces fichiers restent
  accessibles par les vues qui les contrôlent vraiment (contrôle de rôle,
  appartenance à l'entreprise, journal d'accès).

**Ce qui reste cassé, et je préfère le dire.** Plusieurs gabarits pointent
vers l'URL brute d'un fichier du troisième niveau : `templates/documents/`,
`templates/client_portal/project_documents.html`,
`templates/client_portal/conversation_detail.html` et
`templates/btp/client_conversation_detail.html`. Ces liens sont cassés
aujourd'hui et le restent : les ouvrir au niveau authentifié laisserait le
client de l'entreprise A télécharger les documents de l'entreprise B en
changeant l'URL. Il leur faut une vue de téléchargement bornée par
entreprise, comme `hr.private_document_download` en a une. Faire marcher un
lien en ouvrant une fuite n'est pas une correction.
"""

import mimetypes
import os
import re

from django.http import FileResponse, Http404, HttpResponse
from django.utils._os import safe_join
from django.utils.http import http_date

# ─── Niveau 1 : visiteurs anonymes ──────────────────────────────────────────
#
# Ces fichiers existent POUR être vus par des inconnus : images d'un site
# vitrine, photos de produits de la boutique, logos, favicons, vignettes
# de partage. Les servir est leur fonction.
PREFIXES_PUBLICS = (
    'websites/',            # Tout le contenu des sites vitrines
    'sites/',               # Thèmes, sections et blocs de site_customization
    'lunea/',               # Boutique LUNEA : produits, looks, routines
    'products/',            # Produits de la boutique, images et vidéos
    'store/logos/',         # Logos de boutique
    'watches/',             # Configurateur de montres : presets et options
    'configurator/previews/',
    'seo/og/',              # Vignettes Open Graph — faites pour être partagées
    'companies/logos/',
    'companies/favicons/',
    'carriers/',            # Logos de transporteurs, affichés au panier
    'builder_assets/',      # Images posées dans l'éditeur visuel de pages
    'community/posts/',     # Publications de la communauté publique
    'testimonials/',
)

# ─── Niveau 2 : utilisateurs connectés de l'ERP ─────────────────────────────
#
# Fichiers internes que l'ERP affiche déjà dans ses pages à tout salarié
# connecté, et dont le modèle ne porte aucun champ de confidentialité ni
# aucune règle de visibilité.
#
# Ce niveau N'EST PAS borné par entreprise, et c'est une limite assumée :
# un compte de l'entreprise A pourrait atteindre un fichier de
# l'entreprise B en devinant l'URL. On ne l'accepte donc QUE pour des
# catégories sans enjeu de confidentialité déclaré — jamais pour un
# document dont un modèle dit qu'il est confidentiel.
PREFIXES_AUTHENTIFIES = (
    'avatars/',                 # Photo de profil, visible dans l'ERP
    'equipment/',               # Photos de matériel et d'engins
    'training/',                # Supports de formation interne
    'devis/modeles/',           # Modèles de devis (mise en page, pas de prix)
    'pdca/actions/',            # Pièces jointes d'actions d'amélioration
    'reservations/',
    'products/video_thumbs/',   # Déjà couvert par products/, explicite ici
    # Le logo d'un concurrent est une marque publique, mais le FAIT que
    # vous suiviez ce concurrent ne l'est pas : une page vitrine qui
    # chargerait ces images annoncerait votre veille. Niveau authentifié.
    'competitors/logos/',
)

# ─── Jamais par /media/ ─────────────────────────────────────────────────────
#
# Documenté pour que ce soit un choix lisible et non un oubli. Ces préfixes
# tomberaient de toute façon dans le refus par défaut ; les nommer permet
# de répondre « non, délibérément » à qui se demandera pourquoi.
PREFIXES_INTERDITS = {
    'employee_private/': 'Contrats, bulletins de paie, pièces d\'identité, '
                         'RIB, visites médicales, sanctions. Passe par '
                         'hr.private_document_download, qui contrôle le rôle '
                         'et journalise chaque lecture.',
    'employee_certifications/': 'Scans d\'habilitations et de diplômes. '
                                'Passe par hr.certification_scan_download.',
    'bank_statements/': 'Relevés bancaires.',
    'supplier_invoices/': 'Factures fournisseurs — elles portent vos prix '
                          'd\'achat.',
    'expense_receipts/': 'Justificatifs de notes de frais.',
    'signatures/': 'Images de signature : exposées, elles se recopient.',
    'documents/': 'Documents internes de l\'entreprise. Il leur faut une '
                  'vue bornée par entreprise.',
    'smart_documents/': 'Documents analysés automatiquement.',
    'project_documents/': 'Documents de chantier montrés au portail client : '
                          'il leur faut une vue bornée par entreprise ET '
                          'par client.',
    'client_messages/': 'Pièces jointes des conversations client : même '
                        'besoin.',
    'guided_quotes/': 'Photos et pièces déposées par un prospect dans le '
                      'devis guidé.',
    'tickets/': 'Pièces jointes de tickets de support.',
}

# Types servis pour affichage direct. Tout le reste part en téléchargement :
# un SVG ou un HTML téléversé puis affiché depuis l'origine du site est du
# script qui s'exécute avec les droits du visiteur.
TYPES_AFFICHABLES = (
    'image/png', 'image/jpeg', 'image/gif', 'image/webp', 'image/avif',
    'image/bmp', 'image/x-icon', 'image/vnd.microsoft.icon',
    'application/pdf',
    'video/mp4', 'video/webm', 'video/ogg',
    'audio/mpeg', 'audio/ogg', 'audio/wav',
    'text/plain',
)

MOTIF_INTERVALLE = re.compile(r'^bytes=(\d*)-(\d*)$')


def _normaliser(chemin_relatif):
    """Le chemin, en séparateurs web et sans fioritures.

    Les préfixes de la politique s'écrivent avec des « / ». Comparer un
    chemin Windows en antislashs les ferait tous échouer — donc tout
    refuser sur un poste de développement, et masquer la politique
    réelle au moment où on la met au point.
    """
    return str(chemin_relatif or '').replace('\\', '/').lstrip('/')


def niveau_requis(chemin_relatif):
    """« public », « authentifie » ou « interdit » pour ce chemin.

    Les préfixes publics sont examinés avant les authentifiés : c'est sans
    conséquence aujourd'hui, mais rend l'ordre explicite si un préfixe
    venait à figurer dans les deux listes.
    """
    chemin = _normaliser(chemin_relatif)
    if not chemin:
        return 'interdit'
    for prefixe in PREFIXES_PUBLICS:
        if chemin.startswith(prefixe):
            return 'public'
    for prefixe in PREFIXES_AUTHENTIFIES:
        if chemin.startswith(prefixe):
            return 'authentifie'
    return 'interdit'


def peut_lire(utilisateur, chemin_relatif):
    """Le droit de lire ce fichier par /media/."""
    niveau = niveau_requis(chemin_relatif)
    if niveau == 'public':
        return True
    if niveau == 'authentifie':
        return bool(utilisateur and utilisateur.is_authenticated)
    return False


def raison_du_refus(chemin_relatif):
    """Pourquoi ce préfixe n'est pas servi — pour les diagnostics.

    N'est JAMAIS renvoyé au visiteur : expliquer qu'un chemin existe mais
    est protégé est déjà une information. Sert aux journaux et à la
    commande de vérification.
    """
    chemin = _normaliser(chemin_relatif)
    for prefixe, motif in PREFIXES_INTERDITS.items():
        if chemin.startswith(prefixe):
            return motif
    return ('Préfixe non déclaré dans la politique. Le défaut est le refus : '
            'ajoutez-le à PREFIXES_PUBLICS ou PREFIXES_AUTHENTIFIES après '
            'avoir vérifié que son contenu peut être lu par ce public.')


def _chemin_sur_le_disque(chemin_relatif):
    """Le chemin absolu, ou None s'il sort de MEDIA_ROOT.

    `safe_join` lève sur « ../ » ; on écarte en plus les liens symboliques
    qui pointeraient hors de MEDIA_ROOT, qu'un lien posé dans un dossier
    téléversable rendrait sinon lisible.
    """
    from django.conf import settings
    from django.core.exceptions import SuspiciousFileOperation

    racine = os.path.realpath(str(settings.MEDIA_ROOT))
    try:
        complet = safe_join(racine, _normaliser(chemin_relatif))
    except (SuspiciousFileOperation, ValueError):
        return None

    reel = os.path.realpath(complet)
    if reel != racine and not reel.startswith(racine + os.sep):
        return None
    if not os.path.isfile(reel):
        return None
    return reel


def _intervalle_demande(entete, taille):
    """Analyse un en-tête Range. Rend (debut, fin) ou None.

    Sans cela, une vidéo ne se déplace pas dans la timeline et certains
    navigateurs refusent de la lire : ils demandent un intervalle, et une
    réponse 200 complète ne leur suffit pas.
    """
    if not entete:
        return None
    trouve = MOTIF_INTERVALLE.match(entete.strip())
    if not trouve:
        return None
    debut_brut, fin_brut = trouve.groups()

    if debut_brut == '' and fin_brut == '':
        return None
    if debut_brut == '':
        # « bytes=-500 » : les 500 derniers octets.
        longueur = min(int(fin_brut), taille)
        if longueur <= 0:
            return None
        return taille - longueur, taille - 1

    debut = int(debut_brut)
    fin = int(fin_brut) if fin_brut else taille - 1
    fin = min(fin, taille - 1)
    if debut > fin or debut >= taille:
        return None
    return debut, fin


class _Tranche:
    """Lecteur d'une portion de fichier, pour une réponse 206.

    Itérable plutôt que lecture complète en mémoire : une vidéo de
    plusieurs centaines de mégaoctets ne doit pas être chargée entièrement
    pour en renvoyer un morceau.
    """

    def __init__(self, chemin, debut, longueur, bloc=8192):
        self.chemin = chemin
        self.debut = debut
        self.longueur = longueur
        self.bloc = bloc

    def __iter__(self):
        restant = self.longueur
        with open(self.chemin, 'rb') as flux:
            flux.seek(self.debut)
            while restant > 0:
                morceau = flux.read(min(self.bloc, restant))
                if not morceau:
                    break
                restant -= len(morceau)
                yield morceau


def servir_media(request, chemin):
    """Sert un fichier de MEDIA_ROOT selon la politique ci-dessus.

    Monté en production ET en développement, volontairement. Servir tout
    en local et filtrer en production rendrait la politique invisible
    pendant qu'on la met au point — c'est le même défaut que
    `settings/testing.py`, qui remplace STATICFILES_STORAGE et masque
    toute une classe de pannes de production.

    Rend 404 et non 403 sur un refus : un 403 confirmerait que le fichier
    existe, et sur `employee_private/` cela renseigne déjà.
    """
    if not peut_lire(getattr(request, 'user', None), chemin):
        raise Http404

    reel = _chemin_sur_le_disque(chemin)
    if reel is None:
        raise Http404

    type_mime, encodage = mimetypes.guess_type(reel)
    type_mime = type_mime or 'application/octet-stream'

    stat = os.stat(reel)
    taille = stat.st_size

    # Cache navigateur. Les médias sont immuables en pratique (un nouvel
    # envoi crée un nouveau nom), mais on reste prudent : une minute de
    # validation suffit à éviter de retransmettre chaque image à chaque
    # page, sans figer un remplacement.
    entetes = {
        'Last-Modified': http_date(stat.st_mtime),
        'Content-Type': type_mime,
        # Le navigateur ne doit pas deviner un type plus dangereux que
        # celui annonce -- c'est ce qui transforme un .txt en HTML.
        'X-Content-Type-Options': 'nosniff',
        'Accept-Ranges': 'bytes',
    }
    if niveau_requis(chemin) == 'public':
        entetes['Cache-Control'] = 'public, max-age=60'
    else:
        # Un fichier interne n'a pas à rester dans le cache partagé d'un
        # proxy d'entreprise.
        entetes['Cache-Control'] = 'private, max-age=60'

    if type_mime in TYPES_AFFICHABLES and not encodage:
        disposition = 'inline'
    else:
        # Un SVG, un XML ou un HTML téléversé puis affiché depuis
        # l'origine du site exécuterait son script avec les droits du
        # visiteur. On force le téléchargement.
        disposition = 'attachment'
    nom = os.path.basename(reel).replace('"', '')
    entetes['Content-Disposition'] = f'{disposition}; filename="{nom}"'

    intervalle = _intervalle_demande(request.META.get('HTTP_RANGE'), taille)
    if intervalle is not None:
        debut, fin = intervalle
        longueur = fin - debut + 1
        reponse = HttpResponse(
            _Tranche(reel, debut, longueur), status=206, headers=entetes)
        reponse['Content-Range'] = f'bytes {debut}-{fin}/{taille}'
        reponse['Content-Length'] = str(longueur)
        return reponse

    # Les en-tetes sont poses APRES la construction, et non via
    # `headers=`. `FileResponse.set_headers()` s'execute a l'attachement du
    # fichier et REECRIT Content-Disposition et Content-Type d'apres le nom
    # du fichier : passes au constructeur, ils etaient silencieusement
    # remplaces. Concretement, un .svg repartait en « inline » -- donc son
    # script s'executait chez le visiteur, exactement ce que cette
    # politique est censee empecher.
    reponse = FileResponse(open(reel, 'rb'))
    for cle, valeur in entetes.items():
        reponse[cle] = valeur
    reponse['Content-Length'] = str(taille)
    return reponse


def servir_fichier_autorise(fichier, nom=None, afficher_si_image=False):
    """Sert un fichier dont l'appelant a DEJA verifie les droits de lecture.

    Les prefixes de `PREFIXES_INTERDITS` ne sont pas servis par /media/ :
    seule une vue qui sait QUI a le droit de lire peut les rendre, et c'est
    elle qui porte le controle. Cette fonction n'en fait aucun -- elle ne
    fait que poser les bons en-tetes, et elle existe pour que le piege
    ci-dessous ne soit pas a retenir dans chaque vue.

    **En « attachment » par defaut.** Ces fichiers sont televerses par des
    tiers : un client depose une piece jointe dans une conversation, un
    prospect une photo dans un devis guide. Un SVG ou un HTML affiche
    depuis l'origine du site executerait son script avec les droits du
    lecteur -- qui est ici un salarie connecte a l'ERP. Le telechargement
    force supprime ce risque sans rien couter d'autre qu'un clic.

    `afficher_si_image=True` leve cette contrainte pour les seuls types
    d'IMAGE de `TYPES_AFFICHABLES`, et c'est necessaire : une vignette doit
    s'afficher dans la page. Un SVG ne figure pas dans cette liste, donc il
    repart en telechargement meme avec ce drapeau.

    **Les en-tetes sont poses APRES la construction**, et non via
    `headers=` : `FileResponse.set_headers()` s'execute a l'attachement du
    fichier et REECRIT Content-Disposition et Content-Type d'apres le nom
    du fichier. Passes au constructeur, ils sont silencieusement remplaces.
    C'est ainsi qu'un .svg repartait « inline » dans la premiere version de
    `servir_media`.
    """
    from django.http import FileResponse, Http404

    try:
        flux = fichier.open('rb')
    except (OSError, ValueError):
        # Fichier absent du disque ou champ vide : 404, et surtout pas une
        # erreur 500 qui exposerait le chemin dans une page de debug.
        raise Http404

    propre = os.path.basename(str(nom or fichier.name) or 'fichier')
    propre = propre.replace('"', '').replace('\r', '').replace('\n', '')

    # Les noms affiches viennent de champs libres -- « name », « title » --
    # et n'ont souvent AUCUNE extension. Un fichier telecharge sous le nom
    # « Contrat de sous-traitance » n'ouvre aucun logiciel : le systeme ne
    # sait pas de quoi il s'agit. On recupere donc l'extension du fichier
    # reellement stocke.
    if not os.path.splitext(propre)[1]:
        extension = os.path.splitext(fichier.name or '')[1]
        if extension:
            propre += extension

    # `afficher_si_image` sert aux vignettes : une photo deposee par un
    # prospect doit s'afficher dans la page, pas se telecharger. Reserve aux
    # types d'IMAGE de TYPES_AFFICHABLES, et a eux seuls -- un SVG n'y
    # figure pas, et c'est voulu : il est un document XML qui peut porter
    # un <script>.
    disposition = 'attachment'
    type_mime = 'application/octet-stream'
    if afficher_si_image:
        devine, encodage = mimetypes.guess_type(fichier.name or '')
        if (devine in TYPES_AFFICHABLES and not encodage
                and devine.startswith('image/')):
            disposition = 'inline'
            type_mime = devine

    reponse = FileResponse(flux)
    reponse['Content-Type'] = type_mime
    reponse['Content-Disposition'] = f'{disposition}; filename="{propre}"'
    reponse['X-Content-Type-Options'] = 'nosniff'
    # Aucun cache partage : ces fichiers sont, par construction, reserves a
    # un lecteur precis.
    reponse['Cache-Control'] = 'private, no-store'
    return reponse
