"""Le site vitrine Électricité & Étanchéité.

CE QUI EST LIVRÉ, ET COMMENT

Le CODE arrive par la mise à jour : gabarits, vues, adresses. Le SITE,
lui, se crée d'un clic depuis la liste des sites de l'ERP.

Pourquoi pas une migration de données : elle sèmerait cette vitrine sur
TOUTES les installations, y compris celles d'un autre métier, qui
hériteraient d'un site d'électricien que personne n'a demandé.

POURQUOI DES SECTIONS ET NON UN GABARIT FIGÉ

Un site dont les textes sont écrits en dur ne s'édite pas depuis l'ERP :
il faudrait un accès au code pour changer un numéro de téléphone. Le
contenu passe donc par WebsiteSection, le modèle que l'éditeur de sites
manipule déjà. Seule la mise en page reste dans les gabarits.
"""
import pytest


@pytest.fixture
def entreprise(db):
    from apps.core.models import Company
    return Company.objects.create(name='Volt SARL', slug='volt-sarl')


@pytest.fixture
def site(entreprise):
    from apps.websites.vitrine_etancheite import creer_le_site
    site, _ = creer_le_site(entreprise)
    return site


# ── 1. La création ───────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_le_site_se_cree_avec_son_contenu(entreprise):
    from apps.websites.models import Website, WebsiteSection
    from apps.websites.vitrine_etancheite import SLUG, creer_le_site

    site, cree = creer_le_site(entreprise)

    assert cree is True
    assert site.slug == SLUG
    assert site.company == entreprise
    assert site.is_published is True
    assert site.theme is not None, 'le site doit porter la palette du dessin'

    accueil = site.home_page
    assert accueil is not None
    types = list(WebsiteSection.objects
                 .filter(page=accueil).order_by('order')
                 .values_list('section_type', flat=True))
    assert types == ['hero', 'stats', 'services_grid', 'projects_grid', 'cta']


@pytest.mark.django_db
def test_le_contenu_est_editable_depuis_l_erp(site):
    """La preuve que rien n'est figé : les textes du dessin sont des
    enregistrements, pas des chaînes dans un gabarit."""
    from apps.websites.models import WebsiteSection

    hero = WebsiteSection.objects.get(
        page=site.home_page, section_type='hero')
    assert 'Sécuriser' in hero.title

    services = WebsiteSection.objects.get(
        page=site.home_page, section_type='services_grid')
    items = services.extra_config['items']
    assert len(items) == 4
    assert {i['titre'] for i in items} == {
        'Électricité générale', 'Mise aux normes',
        'Étanchéité toiture', 'Étanchéité terrasses'}


@pytest.mark.django_db
def test_recreer_ne_duplique_pas_et_n_ecrase_pas(entreprise):
    """LA LEÇON DU SEMIS DES MODULES.

    Une fonction de création rappelée ne doit ni doubler le site, ni
    réécrire des textes retouchés à la main. C'est exactement ce que
    faisait le semis des modules, qui effaçait un choix d'exploitant à
    chaque affichage de page.
    """
    from apps.websites.models import Website, WebsiteSection
    from apps.websites.vitrine_etancheite import creer_le_site

    site, _ = creer_le_site(entreprise)
    hero = WebsiteSection.objects.get(
        page=site.home_page, section_type='hero')
    hero.title = 'Un titre écrit à la main'
    hero.save()

    encore, cree = creer_le_site(entreprise)

    assert cree is False
    assert encore.pk == site.pk
    assert Website.objects.filter(company=entreprise).count() == 1
    hero.refresh_from_db()
    assert hero.title == 'Un titre écrit à la main', (
        'un texte retouché a été écrasé par une seconde création')


@pytest.mark.django_db
def test_la_reconstruction_reste_possible_mais_explicite(entreprise):
    from apps.websites.models import WebsiteSection
    from apps.websites.vitrine_etancheite import creer_le_site

    site, _ = creer_le_site(entreprise)
    hero = WebsiteSection.objects.get(
        page=site.home_page, section_type='hero')
    hero.title = 'Un titre écrit à la main'
    hero.save()

    creer_le_site(entreprise, reconstruire_le_contenu=True)

    rebatie = WebsiteSection.objects.get(
        page=site.home_page, section_type='hero')
    assert 'Sécuriser' in rebatie.title


@pytest.mark.django_db
def test_sans_entreprise_la_creation_refuse(db):
    from apps.websites.vitrine_etancheite import creer_le_site

    with pytest.raises(ValueError):
        creer_le_site(None)


# ── 2. Les pages se rendent VRAIMENT ─────────────────────────────────────────
#
# Un gabarit cassé ne se voit pas à l'import : il échoue au rendu. Ces
# tests appellent chaque adresse et vérifient le contenu, pas seulement le
# code HTTP.

@pytest.mark.django_db
def test_la_page_d_accueil_montre_le_dessin(client, site):
    reponse = client.get(f'/sites/{site.slug}/etancheite/')
    assert reponse.status_code == 200
    contenu = reponse.content.decode()

    # Le hero
    assert 'Sécuriser, alimenter, protéger vos bâtiments' in contenu
    assert 'EXPERT BTP EN ÉLECTRICITÉ &amp; ÉTANCHÉITÉ' in contenu \
        or 'EXPERT BTP EN ÉLECTRICITÉ & ÉTANCHÉITÉ' in contenu
    # Les quatre gages
    assert '15+ ans d’expérience' in contenu
    assert 'Interventions certifiées' in contenu
    # Les services
    assert 'Étanchéité toiture' in contenu
    # Les réalisations et leurs filtres
    assert 'NOS RÉALISATIONS' in contenu
    assert 'Rénovation' in contenu


@pytest.mark.django_db
@pytest.mark.parametrize('chemin', [
    '', 'services/', 'realisations/', 'entreprise/', 'contact/', 'devis/',
])
def test_chaque_page_se_rend(client, site, chemin):
    reponse = client.get(f'/sites/{site.slug}/etancheite/{chemin}')
    assert reponse.status_code == 200


@pytest.mark.django_db
def test_le_detail_d_un_service_se_rend(client, site):
    reponse = client.get(
        f'/sites/{site.slug}/etancheite/services/etancheite-toiture/')
    assert reponse.status_code == 200
    assert 'Étanchéité toiture' in reponse.content.decode()


@pytest.mark.django_db
def test_un_service_inconnu_rend_404(client, site):
    reponse = client.get(
        f'/sites/{site.slug}/etancheite/services/plomberie-zen/')
    assert reponse.status_code == 404


@pytest.mark.django_db
def test_le_filtre_des_realisations_est_une_adresse(client, site):
    """Les filtres sont des LIENS et non du JavaScript : une page filtrée
    doit rester une adresse qu'on peut envoyer et mettre en favori."""
    reponse = client.get(
        f'/sites/{site.slug}/etancheite/realisations/?categorie=etancheite')
    assert reponse.status_code == 200
    contenu = reponse.content.decode()

    assert 'Toiture plate' in contenu
    assert 'éclairage et domotique' not in contenu, (
        'le filtre n’a pas écarté les réalisations d’une autre catégorie')


@pytest.mark.django_db
def test_une_categorie_vide_ne_casse_pas_la_page(client, site):
    reponse = client.get(
        f'/sites/{site.slug}/etancheite/realisations/?categorie=maintenance')
    assert reponse.status_code == 200
    assert 'Aucune réalisation' in reponse.content.decode()


@pytest.mark.django_db
def test_une_section_supprimee_ne_casse_pas_l_accueil(client, site):
    """Supprimer « Nos réalisations » depuis l'éditeur doit retirer la
    bande, pas rendre la page inutilisable."""
    from apps.websites.models import WebsiteSection

    WebsiteSection.objects.filter(
        page=site.home_page, section_type='projects_grid').delete()

    reponse = client.get(f'/sites/{site.slug}/etancheite/')
    assert reponse.status_code == 200
    contenu = reponse.content.decode()
    assert 'NOS RÉALISATIONS' not in contenu
    assert 'Sécuriser' in contenu, 'le reste de la page doit subsister'


@pytest.mark.django_db
def test_le_theme_du_site_pilote_la_palette(client, site):
    """La palette vient du THÈME et non du gabarit : l'éditeur de thèmes
    doit pouvoir la changer sans toucher au code."""
    site.theme.accent_color = '#FF0000'
    site.theme.save()

    reponse = client.get(f'/sites/{site.slug}/etancheite/')
    assert '#FF0000' in reponse.content.decode()


# ── 3. Les formulaires enregistrent ──────────────────────────────────────────

@pytest.mark.django_db
def test_le_formulaire_de_contact_enregistre(client, site):
    from apps.websites.models import ContactMessage

    reponse = client.post(f'/sites/{site.slug}/etancheite/contact/', {
        'name': 'Jean Dupont',
        'email': 'jean@exemple.fr',
        'phone': '0612345678',
        'subject': 'Devis toiture',
        'message': 'Bonjour, je souhaite un devis.',
    }, follow=True)

    assert reponse.status_code == 200
    message = ContactMessage.objects.filter(website=site).first()
    assert message is not None, 'le message n’a pas été enregistré'
    assert message.email == 'jean@exemple.fr'


@pytest.mark.django_db
def test_le_pot_de_miel_ecarte_un_robot(client, site):
    """Un champ que seul un robot remplit. On n'enregistre rien ET on ne lui
    dit pas qu'il a été repéré — le lui dire lui apprendrait à passer."""
    from apps.websites.models import ContactMessage

    client.post(f'/sites/{site.slug}/etancheite/contact/', {
        'name': 'Robot', 'email': 'robot@spam.fr',
        'message': 'achetez ceci', 'website_url_field': 'http://spam',
    }, follow=True)

    assert ContactMessage.objects.filter(website=site).count() == 0


@pytest.mark.django_db
def test_une_erreur_de_formulaire_s_affiche(client, site):
    """Sur une vitrine, un message perdu est un client perdu : le visiteur
    doit savoir pourquoi son envoi a été refusé."""
    reponse = client.post(f'/sites/{site.slug}/etancheite/contact/',
                          {'name': 'Jean'})

    assert reponse.status_code == 200
    contenu = reponse.content.decode()

    # On evite l'apostrophe dans l'assertion : celle du gabarit est droite
    # et Django l'echappe en « &#x27; ». Comparer une apostrophe
    # typographique a une apostrophe echappee faisait echouer ce test alors
    # que la page etait juste.
    assert 'pas pu' in contenu and 'envoy' in contenu
    assert 'alert-danger' in contenu, 'le bloc d’erreurs ne s’affiche pas'


@pytest.mark.django_db
def test_la_demande_de_devis_enregistre(client, site):
    from apps.websites.models import QuoteRequest

    client.post(f'/sites/{site.slug}/etancheite/devis/', {
        'name': 'Marie Martin',
        'email': 'marie@exemple.fr',
        'description': 'Étanchéité de 120 m² de terrasse.',
    }, follow=True)

    demande = QuoteRequest.objects.filter(website=site).first()
    assert demande is not None
    assert demande.email == 'marie@exemple.fr'


# ── 4. Le bouton de l'ERP ────────────────────────────────────────────────────

def _patron_connecte(client, entreprise, django_user_model):
    utilisateur = django_user_model.objects.create_superuser(
        username='patron', password='motdepasse-test', email='p@volt.fr')
    utilisateur.profile.companies.add(entreprise)
    client.force_login(utilisateur)
    return utilisateur


@pytest.mark.django_db
def test_le_bouton_cree_le_site(client, entreprise, django_user_model):
    """Sans ligne de commande : c'est la règle de cet ERP."""
    from apps.websites.models import Website
    from apps.websites.vitrine_etancheite import SLUG

    _patron_connecte(client, entreprise, django_user_model)

    reponse = client.post('/websites/sites/creer/vitrine-etancheite/',
                          follow=True)
    assert reponse.status_code == 200
    assert Website.objects.filter(company=entreprise, slug=SLUG).exists()


@pytest.mark.django_db
def test_le_bouton_refuse_le_get(client, entreprise, django_user_model):
    """Une création ne doit pas pouvoir partir d'un simple lien, ni d'un
    rechargement de page."""
    from apps.websites.models import Website

    _patron_connecte(client, entreprise, django_user_model)

    reponse = client.get('/websites/sites/creer/vitrine-etancheite/')
    assert reponse.status_code == 405
    assert Website.objects.filter(company=entreprise).count() == 0


# ── 5. Ce que ce lot ne doit PAS emporter ────────────────────────────────────

def test_les_adresses_n_importent_aucun_module_absent_du_depot():
    """LE PIÈGE ÉVITÉ.

    apps/websites/public_urls.py porte un travail en cours qui importe
    `electricite_public_views` et `electricite_wizard_views`, deux modules
    NON SUIVIS par git. Le committer poserait sur le serveur un import vers
    un fichier absent — et le résolveur charge l'arbre ENTIER à la première
    requête, donc tout l'ERP tomberait, pas seulement cette branche.

    Ce lot est donc monté depuis erp_btp/urls.py, dans ses propres modules.
    Ce test garde cette séparation.
    """
    from pathlib import Path

    source = Path('apps/websites/etancheite_urls.py').read_text(
        encoding='utf-8')
    assert 'electricite_public_views' not in source
    assert 'electricite_wizard_views' not in source

    racine = Path('erp_btp/urls.py').read_text(encoding='utf-8')
    assert 'apps.websites.etancheite_urls' in racine

    # Et le montage doit precéder l'include générique, dont la première
    # règle « <slug:site_slug>/ » absorberait tout ce qui suit.
    assert (racine.index('apps.websites.etancheite_urls')
            < racine.index('apps.websites.public_urls')), (
        'la branche étanchéité est montée après l’include générique : elle '
        'ne serait jamais atteinte')
