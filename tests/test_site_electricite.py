"""Le site Électricité et son configurateur de devis.

CE QUE CE LOT LIVRE

Un chantier de 2 000 lignes qui existait sur le disque et que RIEN ne
suivait : douze pages publiques, un configurateur de devis en quatre
étapes, et sa chaîne — calcul d'estimation, prospect CRM, devis BTP, PDF.
Les modèles dont il dépend (GuidedQuoteRequest, ElectricityPriceLibrary,
BTPQuote…) étaient déjà sur le serveur ; seule la plomberie de livraison
manquait.

POURQUOI CES TESTS EXISTENT

Un gabarit cassé ne se voit pas à l'import, seulement au rendu. Et le
configurateur écrit dans trois applications à la fois : une erreur y crée
un prospect sans devis, ou un devis sans ligne, sans que rien ne proteste.
Chaque page est donc appelée pour de vrai, et le parcours complet est joué
de bout en bout.
"""
import pytest


PAGES = [
    '', 'a-propos/', 'services/', 'realisations/', 'avis/', 'faq/',
    'calculateur/', 'contact/', 'espace-client/', 'mentions-legales/',
    'confidentialite/',
]


@pytest.fixture
def entreprise(db):
    from apps.core.models import Company
    return Company.objects.create(
        name='ÉlecPro', slug='elecpro', sector='btp',
        email='contact@elecpro.fr', phone='01 23 45 67 89')


@pytest.fixture
def site(entreprise):
    from apps.websites.models import Website, WebsiteTheme

    theme = WebsiteTheme.objects.create(
        company=entreprise, name='Électricité', accent_color='#F5B93D')
    return Website.objects.create(
        company=entreprise, name='ÉlecPro — Électricité',
        slug='elecpro-electricite', site_type='electricite',
        status='published', is_active=True, is_published=True, theme=theme,
        meta_description='Installation et mise aux normes électriques.')


# ── 1. Les pages se rendent VRAIMENT ─────────────────────────────────────────

@pytest.mark.django_db
@pytest.mark.parametrize('chemin', PAGES)
def test_chaque_page_publique_se_rend(client, site, chemin):
    reponse = client.get(f'/sites/{site.slug}/electricite/{chemin}')
    assert reponse.status_code == 200, (
        f'/electricite/{chemin} ne se rend pas')


@pytest.mark.django_db
def test_le_detail_d_un_service_se_rend(client, site):
    reponse = client.get(
        f'/sites/{site.slug}/electricite/services/domotique/')
    assert reponse.status_code == 200
    assert 'Domotique' in reponse.content.decode()


@pytest.mark.django_db
def test_un_service_inconnu_rend_404(client, site):
    reponse = client.get(
        f'/sites/{site.slug}/electricite/services/teleportation/')
    assert reponse.status_code == 404


@pytest.mark.django_db
def test_le_site_est_joignable_par_le_slug_du_site(client, site):
    """LA CORRECTION D'ACCÈS.

    La recherche ne se faisait que par le slug de l'ENTREPRISE, alors que
    les pages génériques du même préfixe acceptent d'abord celui du SITE.
    Un site dont le slug diffère de celui de son entreprise répondait donc
    sur « /sites/<slug>/ » et rendait 404 sur
    « /sites/<slug>/electricite/ » — même machine, un segment près.
    """
    assert site.slug != site.company.slug, 'le test perdrait son sens'
    assert client.get(f'/sites/{site.slug}/electricite/').status_code == 200


@pytest.mark.django_db
def test_le_site_reste_joignable_par_le_slug_de_l_entreprise(client, site):
    """La contrepartie : l'ancienne adresse ne doit pas cesser de marcher."""
    reponse = client.get(f'/sites/{site.company.slug}/electricite/')
    assert reponse.status_code == 200


@pytest.mark.django_db
def test_un_slug_inconnu_rend_404(client, site):
    reponse = client.get('/sites/entreprise-qui-nexiste-pas/electricite/')
    assert reponse.status_code == 404


@pytest.mark.django_db
def test_une_boutique_n_est_pas_servie_avec_le_dessin_electricite(
        client, entreprise):
    """Deux sites de la même entreprise : on doit servir CELUI qui est de
    type électricité, pas le premier venu."""
    from apps.websites.models import Website

    boutique = Website.objects.create(
        company=entreprise, name='Boutique', slug='elecpro-boutique',
        site_type='ecommerce', is_active=True)
    electrique = Website.objects.create(
        company=entreprise, name='Élec', slug='elecpro-elec',
        site_type='electricite', is_active=True)

    reponse = client.get(f'/sites/{entreprise.slug}/electricite/')
    assert reponse.status_code == 200
    assert reponse.context['site'].pk == electrique.pk, (
        'c’est la boutique qui a été servie avec le dessin électricité')


# ── 2. Le configurateur, de bout en bout ─────────────────────────────────────

@pytest.fixture
def tarifs(entreprise):
    """Quelques lignes de tarif : le calcul d'estimation s'appuie dessus."""
    from apps.btp.models import ElectricityPriceLibrary

    lignes = []
    for code, libelle, prix in (
            ('prise', 'Prise 16A', 45),
            ('interrupteur', 'Interrupteur', 38),
            ('tableau', 'Tableau électrique', 850)):
        lignes.append(ElectricityPriceLibrary.objects.create(
            company=entreprise, code=code, name=libelle,
            price_min=prix, price_avg=prix, price_max=prix,
            duration_hours=1, is_active=True))
    return lignes


def _parcourir_le_configurateur(client, site, *, request_type='depannage',
                                create_portal=False):
    """Joue les quatre étapes et rend la réponse finale."""
    base = f'/sites/{site.slug}/electricite/devis/'

    client.post(base, {'building_type': 'maison',
                       'request_type': request_type})

    if request_type == 'depannage':
        client.post(base + 'etape-2/', {
            'urgency': 'urgent', 'problem_type': 'breaker',
            'safety_issue': 'yes', 'availability': 'matin'})
    else:
        client.post(base + 'etape-2/', {
            'surface': '95', 'quality_level': 'standard',
            'equipments': ['prise', 'interrupteur'],
            'comments': 'Rénovation complète.'})

    client.post(base + 'etape-3/', {
        'first_name': 'Jean', 'last_name': 'Dupont',
        'email': 'jean.dupont@exemple.fr', 'phone': '0612345678',
        'address': '3 rue des Lilas', 'zip_code': '69001', 'city': 'Lyon',
        'client_notes': 'Interphone à revoir aussi.',
        **({'create_portal': 'on'} if create_portal else {}),
    })

    return client.post(base + 'etape-4/', {}, follow=True)


@pytest.mark.django_db
@pytest.mark.parametrize('etape', ['', 'etape-2/', 'etape-3/', 'etape-4/'])
def test_chaque_etape_du_configurateur_se_rend(client, site, etape):
    reponse = client.get(f'/sites/{site.slug}/electricite/devis/{etape}')
    assert reponse.status_code == 200


@pytest.mark.django_db
def test_le_configurateur_cree_une_demande(client, site, tarifs):
    """LE PARCOURS COMPLET.

    Ce test vaut pour tout le lot : il traverse les quatre étapes, la
    session, le calcul d'estimation, et les écritures dans trois
    applications.
    """
    from apps.btp.models import GuidedQuoteRequest

    reponse = _parcourir_le_configurateur(client, site)
    assert reponse.status_code == 200

    demande = GuidedQuoteRequest.objects.filter(company=site.company).first()
    assert demande is not None, 'aucune demande enregistrée'
    assert demande.client_email == 'jean.dupont@exemple.fr'
    assert demande.client_last_name == 'Dupont'
    assert demande.city == 'Lyon'
    assert demande.request_type == 'depannage'
    assert demande.urgency == 'urgent'
    assert demande.reference, 'la demande doit porter une référence'


@pytest.mark.django_db
def test_le_configurateur_cree_un_prospect_crm(client, site, tarifs):
    """Une demande qui n'arrive pas au CRM est une demande perdue."""
    from apps.crm.models import Prospect

    _parcourir_le_configurateur(client, site)

    prospects = Prospect.objects.filter(company=site.company)
    assert prospects.exists(), 'aucun prospect créé dans le CRM'


@pytest.mark.django_db
def test_le_configurateur_cree_un_devis_btp(client, site, tarifs):
    """Le pré-devis doit exister côté ERP, pas seulement côté visiteur."""
    from apps.btp.models import BTPQuote

    _parcourir_le_configurateur(client, site, request_type='chantier')

    devis = BTPQuote.objects.filter(company=site.company).first()
    assert devis is not None, 'aucun devis BTP créé'


@pytest.mark.django_db
def test_la_session_est_videe_apres_envoi(client, site, tarifs):
    """Sans ce nettoyage, une seconde demande hériterait des réponses de la
    première — et le visiteur recevrait un devis qui n'est pas le sien."""
    _parcourir_le_configurateur(client, site)

    for cle in ('elec_building_type', 'elec_request_type', 'elec_answers',
                'elec_contact', 'elec_quality_level'):
        assert cle not in client.session, f'{cle} traîne encore en session'


@pytest.mark.django_db
def test_le_recapitulatif_montre_ce_qui_a_ete_saisi(client, site):
    """L'étape 4 doit rendre les réponses, pas une page vide."""
    base = f'/sites/{site.slug}/electricite/devis/'
    client.post(base, {'building_type': 'maison', 'request_type': 'chantier'})
    client.post(base + 'etape-2/', {'surface': '95',
                                    'quality_level': 'standard'})
    client.post(base + 'etape-3/', {
        'first_name': 'Jean', 'last_name': 'Dupont',
        'email': 'jean@exemple.fr'})

    reponse = client.get(base + 'etape-4/')
    assert reponse.status_code == 200
    contenu = reponse.content.decode()
    assert 'Jean' in contenu
    assert '95' in contenu


@pytest.mark.django_db
def test_la_page_de_confirmation_se_rend(client, site, tarifs):
    reponse = _parcourir_le_configurateur(client, site)
    assert reponse.status_code == 200
    assert reponse.redirect_chain, 'l’envoi doit rediriger vers la confirmation'
    assert 'confirmation' in reponse.redirect_chain[-1][0]


@pytest.mark.django_db
def test_le_pdf_du_pre_devis_est_un_pdf(client, site, tarifs):
    """Le PDF est généré par apps.btp.guided_quote_pdf, qui faisait partie
    du chantier non suivi : sans lui, cette adresse tombait en erreur."""
    from apps.btp.models import GuidedQuoteRequest

    _parcourir_le_configurateur(client, site)
    demande = GuidedQuoteRequest.objects.filter(company=site.company).first()

    reponse = client.get(
        f'/sites/{site.slug}/electricite/devis/{demande.pk}/pdf/')
    assert reponse.status_code == 200

    # La vue rend un FileResponse : le contenu arrive en FLUX, et
    # `.content` leve une AttributeError. C'est la bonne facon de servir un
    # fichier -- on lit donc `streaming_content`.
    contenu = b''.join(reponse.streaming_content)
    assert contenu[:4] == b'%PDF', 'la réponse n’est pas un PDF'
    assert len(contenu) > 500, 'le PDF est anormalement court'


@pytest.mark.django_db
def test_la_page_de_photos_se_rend(client, site, tarifs):
    from apps.btp.models import GuidedQuoteRequest

    _parcourir_le_configurateur(client, site)
    demande = GuidedQuoteRequest.objects.filter(company=site.company).first()

    reponse = client.get(
        f'/sites/{site.slug}/electricite/devis/{demande.pk}/photos/')
    assert reponse.status_code == 200


# ── 3. Le bouton de création dans l'ERP ──────────────────────────────────────

def _patron(client, entreprise, django_user_model):
    utilisateur = django_user_model.objects.create_superuser(
        username='patron', password='motdepasse-test', email='p@elecpro.fr')
    utilisateur.profile.companies.add(entreprise)
    client.force_login(utilisateur)
    return utilisateur


@pytest.mark.django_db
def test_le_bouton_cree_le_site_electricite(client, entreprise,
                                            django_user_model):
    """SANS LIGNE DE COMMANDE.

    `manage.py seed_electricity_site` fabrique une entreprise de
    DÉMONSTRATION : utile pour développer, inutilisable pour un exploitant
    qui veut le site de sa société.
    """
    from apps.websites.models import Website

    _patron(client, entreprise, django_user_model)

    reponse = client.post('/websites/sites/creer/electricite/', follow=True)
    assert reponse.status_code == 200

    site = Website.objects.filter(
        company=entreprise, site_type='electricite').first()
    assert site is not None
    assert site.is_published is True
    assert site.theme is not None


@pytest.mark.django_db
def test_le_site_cree_par_le_bouton_se_rend(client, entreprise,
                                            django_user_model):
    """Le chemin qui aboutit : créer un site qui ne s'affiche pas ne sert à
    rien."""
    from apps.websites.models import Website

    _patron(client, entreprise, django_user_model)
    client.post('/websites/sites/creer/electricite/')
    site = Website.objects.get(company=entreprise, site_type='electricite')

    client.logout()
    assert client.get(
        f'/sites/{site.slug}/electricite/').status_code == 200


@pytest.mark.django_db
def test_recliquer_ne_cree_pas_un_second_site(client, entreprise,
                                              django_user_model):
    from apps.websites.models import Website

    _patron(client, entreprise, django_user_model)
    client.post('/websites/sites/creer/electricite/')
    client.post('/websites/sites/creer/electricite/')

    assert Website.objects.filter(
        company=entreprise, site_type='electricite').count() == 1


@pytest.mark.django_db
def test_le_bouton_refuse_le_get(client, entreprise, django_user_model):
    from apps.websites.models import Website

    _patron(client, entreprise, django_user_model)

    reponse = client.get('/websites/sites/creer/electricite/')
    assert reponse.status_code == 405
    assert Website.objects.filter(company=entreprise).count() == 0


# ── 4. Ce lot ne doit rien laisser hors du dépôt ─────────────────────────────

def test_toute_la_chaine_electricite_est_versionnee():
    """LE RISQUE QUE CE LOT EFFACE.

    `public_urls.py` importait `electricite_public_views` et
    `electricite_wizard_views`, deux modules que git ne suivait pas. Le
    résolveur charge l'arbre d'adresses ENTIER à la première requête : un
    import vers un fichier absent du dépôt n'aurait pas cassé cette
    branche, mais TOUT l'ERP.

    Ce test vérifie que chaque maillon est bien dans le dépôt — y compris
    le générateur de PDF, que seule la quatrième étape appelle.
    """
    import subprocess

    suivis = set(subprocess.run(
        ['git', 'ls-files'], capture_output=True, text=True,
    ).stdout.splitlines())

    attendus = [
        'apps/websites/electricite_public_views.py',
        'apps/websites/electricite_wizard_views.py',
        'apps/websites/public_urls.py',
        'apps/websites/public_views.py',
        'apps/btp/guided_quote_pdf.py',
        'templates/websites/public/electricite/base.html',
        'templates/websites/public/electricite/home.html',
        'templates/websites/public/electricite/wizard/step1_type.html',
        'templates/websites/public/electricite/wizard/step4_recap.html',
    ]
    absents = [chemin for chemin in attendus if chemin not in suivis]
    assert not absents, f'maillon(s) hors du dépôt : {absents}'


def test_les_fonctions_empruntees_existent_bien():
    """`electricite_public_views` importe des aides de `public_views` qui
    n'existaient QUE dans un fichier non commité. Les livrer ensemble était
    la condition pour que rien ne tombe."""
    from apps.websites import public_views

    for nom in ('translate_static_items', 'translate_faq_items',
                '_base_context', '_get_ip'):
        assert hasattr(public_views, nom), f'{nom} manque à public_views'
