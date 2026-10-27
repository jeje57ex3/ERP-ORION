"""Accès aux fichiers téléversés : /media/ en production.

**Le défaut corrigé.** `static(MEDIA_URL, ...)` était derrière
`if settings.DEBUG`. En production nginx relaie `/media/` vers gunicorn,
Django n'avait aucune route pour ce préfixe, et WhiteNoise ne sert que
`STATIC_ROOT`. Sur l'appliance, **aucun fichier téléversé n'était
accessible** — ni photo de produit, ni logo, ni PDF.

**Pourquoi la correction évidente était un piège**, et c'est l'objet de la
moitié de ces tests : servir `MEDIA_ROOT` en statique aurait publié
`employee_private/`, c'est-à-dire les contrats, bulletins de paie et
documents médicaux que `hr.private_document_download` protège par un
contrôle de rôle et un journal d'accès. Une URL devinée aurait suffi à
contourner les deux — et aurait rouvert d'un coup la fuite fermée la
veille. Avec eux `bank_statements/`, `supplier_invoices/` (où figurent les
prix d'achat) et `expense_receipts/`.

D'où un **refus par défaut** : la politique autorise des préfixes nommés,
tout le reste rend 404. Le dernier test de ce fichier est celui qui compte
dans six mois : il échoue si un `upload_to` est ajouté à un modèle sans
qu'on ait décidé qui peut le lire.
"""

import pytest

pytestmark = pytest.mark.django_db


# ── Le décor ────────────────────────────────────────────────────────────────

@pytest.fixture
def media(tmp_path, settings):
    """Un MEDIA_ROOT jetable, pour ne pas écrire dans le dépôt."""
    settings.MEDIA_ROOT = str(tmp_path)
    return tmp_path


def _fichier(racine, chemin_relatif, contenu=b'\x89PNG\r\n\x1a\nfaux'):
    cible = racine / chemin_relatif
    cible.parent.mkdir(parents=True, exist_ok=True)
    cible.write_bytes(contenu)
    return cible


def _connecte(client, django_user_model, nom='salarie'):
    from apps.accounts.models import UserProfile
    from apps.core.models import Company

    entreprise = Company.objects.create(name='Orion SAS', slug=f'o-{nom}')
    utilisateur = django_user_model.objects.create_user(nom, password='x')
    profil, _ = UserProfile.objects.get_or_create(user=utilisateur)
    profil.companies.add(entreprise)
    client.force_login(django_user_model.objects.get(pk=utilisateur.pk))
    return utilisateur


# ── 1. Le défaut de départ : les fichiers publics doivent s'afficher ────────

def test_une_image_de_site_vitrine_est_servie(client, media):
    """Le besoin initial : plus aucun fichier téléversé ne s'affichait."""
    _fichier(media, 'websites/logos/siecle.png')
    reponse = client.get('/media/websites/logos/siecle.png')
    assert reponse.status_code == 200
    assert b'PNG' in b''.join(reponse.streaming_content)


@pytest.mark.parametrize('chemin', [
    'websites/store/products/table.png',
    'sites/theme/logos/marque.png',
    'lunea/products/creme.png',
    'products/videos/demo.png',
    'companies/logos/entreprise.png',
    'builder_assets/2026/10/fond.png',
    'seo/og/partage.png',
])
def test_les_prefixes_publics_sont_servis_sans_compte(client, media, chemin):
    """Ces fichiers existent pour être vus par des inconnus."""
    _fichier(media, chemin)
    assert client.get(f'/media/{chemin}').status_code == 200


# ── 2. LA fuite à ne pas rouvrir ────────────────────────────────────────────

def test_un_bulletin_de_paie_n_est_pas_servi_a_un_anonyme(client, media):
    """Le test le plus important du fichier.

    Servir MEDIA_ROOT en statique — la correction qui vient d'abord à
    l'esprit — aurait publié ce fichier et contourné d'un coup le contrôle
    de rôle ET le journal d'accès de hr.private_document_download.
    """
    _fichier(media, 'employee_private/bulletin_marie_janvier.pdf', b'%PDF-1.4')
    reponse = client.get('/media/employee_private/bulletin_marie_janvier.pdf')
    assert reponse.status_code == 404


def test_un_bulletin_de_paie_n_est_pas_servi_meme_a_un_connecte(
        client, media, django_user_model):
    """Être salarié de l'entreprise ne suffit pas.

    C'est exactement la fuite corrigée dans les dossiers privés RH : le
    contrôle d'entreprise arrête le client d'une autre société, pas le
    collègue du bureau d'à côté.
    """
    _connecte(client, django_user_model)
    _fichier(media, 'employee_private/bulletin.pdf', b'%PDF-1.4')
    assert client.get('/media/employee_private/bulletin.pdf').status_code == 404


def test_un_bulletin_de_paie_n_est_pas_servi_meme_a_un_superadmin(
        client, media, django_user_model):
    """Y compris au super administrateur, et c'est volontaire.

    Il y a droit — mais par `private_document_download`, qui inscrit sa
    lecture au journal. Une porte dérobée par /media/ rendrait ce journal
    incomplet, donc inutile pour répondre à « qui a lu ce document ».
    """
    utilisateur = django_user_model.objects.create_user(
        'root', password='x', is_superuser=True, is_staff=True)
    client.force_login(django_user_model.objects.get(pk=utilisateur.pk))
    _fichier(media, 'employee_private/bulletin.pdf', b'%PDF-1.4')
    assert client.get('/media/employee_private/bulletin.pdf').status_code == 404


@pytest.mark.parametrize('chemin', [
    'employee_private/contrat.pdf',
    'employee_certifications/caces_marie.pdf',
    'bank_statements/releve_2026_10.pdf',
    'supplier_invoices/facture_hager.pdf',
    'expense_receipts/ticket.jpg',
    'signatures/marie.png',
    'documents/2026/10/interne.pdf',
    'smart_documents/analyse.pdf',
    'project_documents/chantier.pdf',
    'client_messages/piece_jointe.pdf',
    'guided_quotes/photos/salon.jpg',
    'tickets/capture.png',
])
def test_aucun_prefixe_sensible_n_est_servi(client, media,
                                            django_user_model, chemin):
    """Les douze préfixes refusés, anonyme et connecté.

    `supplier_invoices/` mérite une mention : ces factures portent vos
    prix d'achat, que rien ne doit exposer.
    """
    _fichier(media, chemin, b'%PDF-1.4 secret')
    assert client.get(f'/media/{chemin}').status_code == 404

    _connecte(client, django_user_model)
    assert client.get(f'/media/{chemin}').status_code == 404


def test_un_prefixe_inconnu_est_refuse(client, media, django_user_model):
    """Le refus par défaut, qui est tout le sens de la politique.

    Un `upload_to` ajouté demain sans décision tombe ici — refusé — et
    non publié. L'inverse rendrait public en silence le prochain dossier
    sensible.
    """
    _connecte(client, django_user_model)
    _fichier(media, 'un_dossier_jamais_declare/fichier.pdf')
    assert client.get(
        '/media/un_dossier_jamais_declare/fichier.pdf').status_code == 404


# ── 3. Le niveau intermédiaire ──────────────────────────────────────────────

def test_un_avatar_demande_un_compte(client, media, django_user_model):
    _fichier(media, 'avatars/marie.png')
    assert client.get('/media/avatars/marie.png').status_code == 404

    _connecte(client, django_user_model)
    assert client.get('/media/avatars/marie.png').status_code == 200


def test_un_logo_de_concurrent_n_est_pas_public(client, media,
                                                django_user_model):
    """Le logo est une marque publique ; votre veille ne l'est pas.

    Une page vitrine qui chargerait ces images annoncerait quels
    concurrents vous suivez.
    """
    _fichier(media, 'competitors/logos/rival.png')
    assert client.get('/media/competitors/logos/rival.png').status_code == 404

    _connecte(client, django_user_model)
    assert client.get('/media/competitors/logos/rival.png').status_code == 200


# ── 4. Sortir de MEDIA_ROOT ─────────────────────────────────────────────────

@pytest.mark.parametrize('suffixe', [
    'websites/../../erp_btp/settings/base.py',
    'websites/../../../etc/passwd',
    'websites/..%2f..%2fbase.py',
    'websites/./../../manage.py',
])
def test_on_ne_sort_pas_de_la_racine_des_medias(client, media, suffixe):
    """`safe_join` lève sur « ../ » — vérifié, pas supposé.

    Un préfixe autorisé suivi de « ../ » est la forme la plus naturelle
    de l'attaque : la politique dit « oui » sur le début du chemin.
    """
    reponse = client.get(f'/media/{suffixe}')
    assert reponse.status_code == 404


def test_un_lien_symbolique_qui_sort_est_refuse(client, media):
    """Un lien posé dans un dossier téléversable rendrait tout lisible."""
    import os

    cible = media.parent / 'secret_dehors.txt'
    cible.write_text('mot de passe')
    (media / 'websites').mkdir(parents=True, exist_ok=True)
    lien = media / 'websites' / 'fuite.txt'
    try:
        os.symlink(cible, lien)
    except (OSError, NotImplementedError):
        pytest.skip('création de lien symbolique non autorisée ici')

    assert client.get('/media/websites/fuite.txt').status_code == 404


def test_un_dossier_ne_se_telecharge_pas(client, media):
    _fichier(media, 'websites/logos/image.png')
    assert client.get('/media/websites/logos/').status_code == 404


# ── 5. Ce que le navigateur doit faire du fichier ───────────────────────────

def test_une_image_s_affiche_dans_le_navigateur(client, media):
    _fichier(media, 'websites/logos/marque.png')
    reponse = client.get('/media/websites/logos/marque.png')
    assert reponse['Content-Type'] == 'image/png'
    assert reponse['Content-Disposition'].startswith('inline')


def test_un_svg_est_telecharge_et_non_affiche(client, media):
    """Un SVG affiché depuis l'origine du site exécute son script.

    C'est le même raisonnement que le refus d'upload de SVG dans
    l'éditeur visuel : un SVG est un document XML qui peut porter un
    <script>, et servi en ligne il s'exécute avec les droits du visiteur.
    """
    _fichier(media, 'websites/pages/piege.svg',
             b'<svg xmlns="http://www.w3.org/2000/svg">'
             b'<script>alert(1)</script></svg>')
    reponse = client.get('/media/websites/pages/piege.svg')
    assert reponse.status_code == 200
    assert reponse['Content-Disposition'].startswith('attachment')


def test_un_html_est_telecharge_et_non_affiche(client, media):
    _fichier(media, 'websites/pages/piege.html',
             b'<html><script>alert(1)</script></html>')
    reponse = client.get('/media/websites/pages/piege.html')
    assert reponse['Content-Disposition'].startswith('attachment')


def test_le_navigateur_ne_devine_pas_le_type(client, media):
    """nosniff : c'est ce qui empêche un .txt d'être interprété en HTML."""
    _fichier(media, 'websites/logos/marque.png')
    reponse = client.get('/media/websites/logos/marque.png')
    assert reponse['X-Content-Type-Options'] == 'nosniff'


def test_un_fichier_interne_n_est_pas_mis_en_cache_partage(
        client, media, django_user_model):
    """« private » : un proxy d'entreprise ne doit pas le garder."""
    _connecte(client, django_user_model)
    _fichier(media, 'avatars/marie.png')
    reponse = client.get('/media/avatars/marie.png')
    assert 'private' in reponse['Cache-Control']

    public = client.get('/media/websites/logos/x.png') if _fichier(
        media, 'websites/logos/x.png') else None
    assert 'public' in public['Cache-Control']


# ── 6. Les vidéos, qui ont besoin des intervalles ───────────────────────────

def test_une_demande_d_intervalle_rend_206(client, media):
    """Sans cela, une vidéo ne se déplace pas dans la timeline.

    Certains navigateurs refusent même de lire une vidéo si le serveur
    ignore `Range` : ils demandent un intervalle et une réponse complète
    ne leur suffit pas.
    """
    _fichier(media, 'products/videos/demo.mp4', bytes(range(256)))
    reponse = client.get('/media/products/videos/demo.mp4',
                         HTTP_RANGE='bytes=10-19')
    assert reponse.status_code == 206
    assert reponse['Content-Range'] == 'bytes 10-19/256'
    assert reponse['Content-Length'] == '10'
    assert b''.join(reponse) == bytes(range(10, 20))


def test_un_intervalle_sans_fin_va_jusqu_au_bout(client, media):
    _fichier(media, 'products/videos/demo.mp4', bytes(range(256)))
    reponse = client.get('/media/products/videos/demo.mp4',
                         HTTP_RANGE='bytes=250-')
    assert reponse.status_code == 206
    assert reponse['Content-Range'] == 'bytes 250-255/256'
    assert b''.join(reponse) == bytes(range(250, 256))


def test_un_intervalle_par_la_fin_est_compris(client, media):
    """« bytes=-8 » : les huit derniers octets, pas « jusqu'à 8 »."""
    _fichier(media, 'products/videos/demo.mp4', bytes(range(256)))
    reponse = client.get('/media/products/videos/demo.mp4',
                         HTTP_RANGE='bytes=-8')
    assert reponse.status_code == 206
    assert reponse['Content-Range'] == 'bytes 248-255/256'


@pytest.mark.parametrize('entete', [
    'bytes=500-600',     # au-delà de la taille
    'bytes=100-50',      # début après la fin
    'octets=0-10',       # unité inconnue
    'bytes=abc-def',     # illisible
    'bytes=-',           # vide
])
def test_un_intervalle_invalide_rend_le_fichier_entier(client, media, entete):
    """Mieux vaut tout servir que renvoyer une erreur sur un en-tête sale."""
    _fichier(media, 'products/videos/demo.mp4', bytes(range(256)))
    reponse = client.get('/media/products/videos/demo.mp4',
                         HTTP_RANGE=entete)
    assert reponse.status_code == 200
    assert reponse['Content-Length'] == '256'


def test_un_intervalle_sur_un_fichier_refuse_ne_fuit_rien(client, media):
    """La politique passe AVANT la lecture du fichier.

    Un `Range` ne doit pas servir d'échappatoire pour lire octet par
    octet un fichier que la politique refuse.
    """
    _fichier(media, 'employee_private/bulletin.pdf', bytes(range(256)))
    reponse = client.get('/media/employee_private/bulletin.pdf',
                         HTTP_RANGE='bytes=0-9')
    assert reponse.status_code == 404


# ── 7. La politique elle-même ───────────────────────────────────────────────

def test_la_route_n_est_plus_derriere_DEBUG():
    """Le défaut d'origine : la route n'existait qu'en développement."""
    import os
    import re

    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(racine, 'erp_btp', 'urls.py'),
              encoding='utf-8-sig') as flux:
        contenu = flux.read()

    bloc = contenu[contenu.index('if settings.DEBUG'):]
    assert 'MEDIA_URL' not in bloc, (
        'MEDIA_URL ne doit plus etre servi uniquement sous DEBUG')
    assert re.search(r"re_path\(\s*r'\^media/", contenu), (
        'la route /media/ doit etre montee en permanence')


def test_les_listes_ne_se_chevauchent_pas():
    """Un préfixe dans deux listes rendrait la politique ambiguë."""
    from apps.core.media_access import (
        PREFIXES_AUTHENTIFIES, PREFIXES_INTERDITS, PREFIXES_PUBLICS,
    )

    for interdit in PREFIXES_INTERDITS:
        for autorise in PREFIXES_PUBLICS + PREFIXES_AUTHENTIFIES:
            assert not interdit.startswith(autorise), (
                f'{interdit} est interdit mais couvert par {autorise}')


def test_la_raison_du_refus_n_est_jamais_renvoyee(client, media):
    """Expliquer qu'un fichier existe mais est protégé est déjà une
    information — surtout sur employee_private/."""
    _fichier(media, 'employee_private/bulletin.pdf', b'%PDF')
    reponse = client.get('/media/employee_private/bulletin.pdf')
    corps = reponse.content.decode('utf-8', 'ignore').lower()
    assert 'bulletin' not in corps
    assert 'employee_private' not in corps


# ── 8. Le test qui compte dans six mois ─────────────────────────────────────

def test_tout_upload_to_declare_est_couvert_par_la_politique():
    """La garde qui survivra à ce travail.

    Le refus par défaut est le bon défaut, mais il a un coût : un
    `upload_to` ajouté demain tombe dans le refus **en silence**, et la
    page qui affiche ces images montre des cadres vides sans message.

    Ce test lit les `upload_to` sur les modèles chargés — pas une liste
    écrite à la main, qui se périmerait — et échoue si l'un d'eux n'a pas
    reçu de décision. Il oblige à choisir : public, réservé aux comptes
    connectés, ou servi par une vue qui contrôle les droits.
    """
    from apps.core.management.commands.verifier_acces_media import (
        prefixes_declares,
    )
    from apps.core.media_access import PREFIXES_INTERDITS, niveau_requis

    statiques, _dynamiques = prefixes_declares()
    oublies = {}
    for prefixe, champs in statiques.items():
        if niveau_requis(prefixe) != 'interdit':
            continue
        if any(prefixe.startswith(p) or p.startswith(prefixe)
               for p in PREFIXES_INTERDITS):
            continue
        oublies[prefixe] = champs

    assert not oublies, (
        'Emplacements declares par un modele et sans decision :\n  '
        + '\n  '.join(f'{p} ({", ".join(c)})' for p, c in oublies.items())
        + '\nAjoutez chacun a PREFIXES_PUBLICS, PREFIXES_AUTHENTIFIES ou '
          'PREFIXES_INTERDITS dans apps/core/media_access.py.')


def test_la_commande_de_verification_passe():
    """Le même contrôle, utilisable au déploiement."""
    from io import StringIO

    from django.core.management import call_command

    sortie = StringIO()
    call_command('verifier_acces_media', stdout=sortie)
    assert 'couverts par la politique' in sortie.getvalue()


# -- 9. Apres un deplacement de disque : MEDIA_ROOT devient un lien ---------
#
# L'ecran des disques permet desormais de poser les medias sur un autre
# volume. Le mecanisme repose sur un lien symbolique : le chemin configure
# reste fixe et pointe ailleurs (voir apps/system_health/stockage_actions.py).
#
# Cette politique de /media/ doit continuer de fonctionner dans ce cas, et
# surtout continuer de REFUSER. C'est le cas le plus facile a casser sans
# s'en apercevoir : tout marche en developpement, ou MEDIA_ROOT est un vrai
# dossier, et plus rien ne se sert le jour ou l'administrateur deplace ses
# fichiers -- ou, pire, le confinement cede et employee_private/ devient
# lisible.


def _lier_un_dossier(cible, lien):
    """Un lien de dossier, par le moyen que la plateforme accepte.

    Sous Windows, os.symlink exige un privilege (WinError 1314) mais une
    JONCTION de repertoire non, et os.path.realpath la resout comme un
    lien. On s'en sert pour eprouver pour de vrai le cas « medias
    deplaces », au lieu de sauter le test sur le poste de developpement.
    """
    import os

    try:
        os.symlink(str(cible), str(lien))
        return True
    except (OSError, NotImplementedError, AttributeError):
        pass
    try:
        import _winapi
        _winapi.CreateJunction(str(cible), str(lien))
        return True
    except (ImportError, AttributeError, OSError):
        return False


def test_un_media_root_deplace_sert_toujours_les_fichiers(client, tmp_path,
                                                          settings):
    """Le chemin configure est un lien ; les fichiers sont ailleurs.

    Si la racine n'etait pas resolue AVANT l'assemblage du chemin, le
    controle de confinement comparerait un chemin resolu a une racine non
    resolue, ne correspondrait jamais, et rendrait 404 sur tout.
    """
    reel = tmp_path / 'autre_disque' / 'medias'
    reel.mkdir(parents=True)
    lien = tmp_path / 'media'
    if not _lier_un_dossier(reel, lien):
        pytest.skip('ni lien symbolique ni jonction disponibles ici.')

    settings.MEDIA_ROOT = str(lien)
    _fichier(reel, 'websites/logos/marque.png')

    reponse = client.get('/media/websites/logos/marque.png')
    assert reponse.status_code == 200


def test_un_media_root_deplace_refuse_toujours_les_dossiers_interdits(
        client, tmp_path, settings):
    """Le refus par defaut doit survivre au deplacement.

    Un confinement qui cederait ici publierait les contrats et bulletins
    de paie, sur une appliance ou l'administrateur a simplement voulu
    gagner de la place.
    """
    reel = tmp_path / 'autre_disque' / 'medias'
    reel.mkdir(parents=True)
    lien = tmp_path / 'media'
    if not _lier_un_dossier(reel, lien):
        pytest.skip('ni lien symbolique ni jonction disponibles ici.')

    settings.MEDIA_ROOT = str(lien)
    _fichier(reel, 'employee_private/contrat.pdf', b'%PDF-1.4 salaire')

    assert client.get('/media/employee_private/contrat.pdf').status_code == 404


def test_une_racine_non_normalisee_sert_quand_meme(client, tmp_path,
                                                   settings):
    """Meme mecanisme, sans aucun lien : une racine a normaliser.

    « <tmp>/x/../media » designe « <tmp>/media ». Si la racine n'etait pas
    passee par realpath avant l'assemblage, le confinement comparerait
    « <tmp>/media/f.png » a « <tmp>/x/../media/ » et refuserait tout.

    Ce test tient donc la meme propriete que les deux precedents, et il ne
    peut jamais etre saute -- ce qui compte, puisque c'est precisement sur
    le poste de developpement que les liens manquent.
    """
    (tmp_path / 'x').mkdir()
    vrai_media = tmp_path / 'media'
    vrai_media.mkdir()
    settings.MEDIA_ROOT = str(tmp_path / 'x' / '..' / 'media')
    _fichier(vrai_media, 'websites/logos/marque.png')

    reponse = client.get('/media/websites/logos/marque.png')
    assert reponse.status_code == 200
