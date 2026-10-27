"""Back-office SIÈCLE : articles, déclinaisons, synchronisation, fidélité.

`apps/ecommerce/views_siecle.py` portait **dix-huit vues et aucune route**,
et il n'était même pas importable : il réclamait deux modèles
(`StoreProductVariant`, `SyncLog`) et un formset
(`StoreProductVariantFormSet`) qui n'existaient nulle part dans le projet.
Ses huit gabarits citaient quinze noms d'URL inexistants.

Tout ce lot était donc mort : création et édition d'articles, images,
déclinaisons, journal de synchronisation, SIÈCLE STATUS et parrainage.

**Les modèles sont DÉDUITS, pas inventés.** Chaque champ de
`StoreProductVariant` est nommé un par un par
`templates/ecommerce/article_variants.html`, et chaque champ de `SyncLog`
est écrit par les vues ou affiché par `sync_log_list.html` — dont
`get_direction_display`, qui exige des `choices`. Les trois statuts sont
ceux que ce gabarit propose en filtre.

**Deux champs manquaient aussi sur un modèle existant.**
`article_image_upload` passait `variant_label` et `is_primary` à
`StoreProductImage.objects.create()`, et `article_image_set_primary`
affectait `is_primary` — trois colonnes absentes. Comme rien n'était
routé, aucun de ces `TypeError` n'avait jamais été levé.
"""

import io
import os

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ── Fixtures ───────────────────────────────────────────────────────────────

def _image(nom='photo.png'):
    """Un PNG minimal valide, pour que ImageField l'accepte."""
    from PIL import Image

    tampon = io.BytesIO()
    Image.new('RGB', (4, 4), (12, 12, 12)).save(tampon, format='PNG')
    return SimpleUploadedFile(nom, tampon.getvalue(), content_type='image/png')


@pytest.fixture
def decor(client, django_user_model):
    """Une boutique SIÈCLE complète : site, catégorie, article, image.

    Le site doit avoir slug='siecle', site_type='ecommerce' et is_active :
    `_get_siecle_website` filtre sur ces trois valeurs, et sans lui les
    vues d'articles n'ont pas de boutique où écrire.
    """
    from apps.accounts.models import UserProfile
    from apps.core.models import Company
    from apps.private_saas.models import ALL_MODULE_CODES, CompanyModule
    from apps.websites.models import (
        StoreCategory, StoreProduct, StoreProductImage, StoreProductVariant,
        SyncLog, Website)

    entreprise = Company.objects.create(name='Siècle SA', slug='siecle-sa')
    for code in ALL_MODULE_CODES:
        CompanyModule.objects.update_or_create(
            company=entreprise, module_code=code,
            defaults={'is_enabled': True})

    utilisateur = django_user_model.objects.create_user(
        'horloger', password='x', is_superuser=True, is_staff=True)
    profil, _ = UserProfile.objects.get_or_create(user=utilisateur)
    profil.role = 'superadmin'
    profil.save()
    profil.companies.add(entreprise)

    client.force_login(django_user_model.objects.get(pk=utilisateur.pk))
    session = client.session
    session['current_company_id'] = entreprise.pk
    session.save()

    site = Website.objects.create(
        company=entreprise, name='SIÈCLE', slug='siecle',
        site_type='ecommerce', is_active=True)
    categorie = StoreCategory.objects.create(
        website=site, name='Montres', is_active=True)
    article = StoreProduct.objects.create(
        website=site, name='Méridien 39', category=categorie)
    image = StoreProductImage.objects.create(
        product=article, image=_image(), is_primary=True,
        variant_label='Bracelet cuir brun')
    declinaison = StoreProductVariant.objects.create(
        product=article, name='39 mm acier', size='39', color='Acier',
        sku='MER-39-AC', is_default=True)
    journal = SyncLog.objects.create(
        company=entreprise, product=article, product_name=article.name,
        direction='erp_to_site', status='success', message='Création.')

    return {
        'entreprise': entreprise, 'utilisateur': utilisateur, 'site': site,
        'categorie': categorie, 'article': article, 'image': image,
        'declinaison': declinaison, 'journal': journal,
    }


# ── 1. Ce qui manquait existe ──────────────────────────────────────────────

def test_les_deux_modeles_existent_et_sont_enregistres():
    from django.apps import apps

    for nom in ('StoreProductVariant', 'SyncLog'):
        modele = apps.get_model('websites', nom)
        assert modele is not None


def test_les_champs_de_declinaison_sont_ceux_du_gabarit():
    """Le gabarit nomme ses champs un par un : ils doivent tous exister.

    Un champ absent ici rendrait une case vide sans erreur, et
    l'utilisateur ne pourrait simplement pas le remplir. Un champ ajouté
    au modèle sans l'être au gabarit serait invisible.
    """
    import re

    from apps.websites.models import StoreProductVariant

    chemin = os.path.join(RACINE, 'templates', 'ecommerce',
                          'article_variants.html')
    with open(chemin, encoding='utf-8') as fichier:
        cites = set(re.findall(r'\bform\.([a-z_]+)\b', fichier.read()))

    # « errors » et « instance » sont des attributs de formulaire, pas des
    # champs du modele.
    cites -= {'errors', 'instance'}

    champs = {c.name for c in StoreProductVariant._meta.get_fields()
              if getattr(c, 'concrete', False)}

    assert cites <= champs, (
        'Le gabarit nomme des champs absents du modele : '
        + ', '.join(sorted(cites - champs)))


def test_le_formset_porte_les_memes_champs():
    import re

    from apps.ecommerce.forms import StoreProductVariantFormSet

    chemin = os.path.join(RACINE, 'templates', 'ecommerce',
                          'article_variants.html')
    with open(chemin, encoding='utf-8') as fichier:
        cites = set(re.findall(r'\bform\.([a-z_]+)\b', fichier.read()))
    cites -= {'errors', 'instance'}

    du_formset = set(StoreProductVariantFormSet.form.base_fields)
    assert cites <= du_formset, (
        'Champs affiches par le gabarit et absents du formset : '
        + ', '.join(sorted(cites - du_formset)))


def test_l_image_porte_les_trois_champs_que_les_vues_ecrivent():
    """`article_image_upload` levait un TypeError sur ces colonnes.

    Il les passait a objects.create() alors qu'elles n'existaient pas, et
    `article_image_set_primary` affectait is_primary. Trois defauts qu'aucun
    appel n'avait jamais declenches, le module n'etant route nulle part.
    """
    from apps.websites.models import StoreProductImage

    champs = {c.name for c in StoreProductImage._meta.get_fields()
              if getattr(c, 'concrete', False)}
    for attendu in ('variant_label', 'is_primary', 'order', 'alt_text'):
        assert attendu in champs, f'StoreProductImage.{attendu} manquant.'


def test_l_image_principale_est_triee_en_premier():
    """Sinon les vignettes montrent une image au hasard.

    Le tri par « order » seul ne dit rien de l'image principale.
    """
    from apps.websites.models import StoreProductImage

    assert StoreProductImage._meta.ordering[0] == '-is_primary'


def test_la_migration_existe_sur_le_disque():
    dossier = os.path.join(RACINE, 'apps', 'websites', 'migrations')
    contenu = ''
    for nom in sorted(os.listdir(dossier)):
        if nom.endswith('.py') and nom != '__init__.py':
            with open(os.path.join(dossier, nom), encoding='utf-8') as f:
                contenu += f.read()

    for attendu in ('StoreProductVariant', 'SyncLog', 'variant_label',
                    'is_primary'):
        assert attendu in contenu, f'{attendu} absent des migrations.'


# ── 2. Les pages s'affichent ──────────────────────────────────────────────

@pytest.mark.django_db
@pytest.mark.parametrize('nom', ['article_list', 'article_create',
                                  'sync_log_list', 'loyalty_status_list',
                                  'referral_list'])
def test_les_pages_sans_argument_s_affichent(client, decor, nom):
    reponse = client.get(reverse(f'ecommerce:{nom}'))
    assert reponse.status_code == 200, (
        f'ecommerce:{nom} rend {reponse.status_code}')


@pytest.mark.django_db
@pytest.mark.parametrize('nom', ['article_detail', 'article_edit',
                                  'article_variants'])
def test_les_pages_d_un_article_s_affichent(client, decor, nom):
    reponse = client.get(reverse(f'ecommerce:{nom}',
                                 kwargs={'pk': decor['article'].pk}))
    assert reponse.status_code == 200, (
        f'ecommerce:{nom} rend {reponse.status_code}')


@pytest.mark.django_db
def test_la_fiche_affiche_declinaisons_et_journal(client, decor):
    """Les deux modèles manquants servaient ICI, dans la même page.

    `article_detail` lit `article.variants.all()` et
    `SyncLog.objects.filter(product=article)` : sans eux, la page ne
    pouvait pas s'afficher du tout.
    """
    reponse = client.get(reverse('ecommerce:article_detail',
                                 kwargs={'pk': decor['article'].pk}))

    assert reponse.status_code == 200
    contenu = reponse.content.decode()
    assert 'MER-39-AC' in contenu or '39 mm acier' in contenu


# ── 3. Les actions en POST ────────────────────────────────────────────────

@pytest.mark.django_db
def test_les_actions_refusent_la_methode_get(client, decor):
    """Un GET est rejouable par un rafraîchissement de page."""
    article = decor['article'].pk
    for nom, kwargs in (
        ('article_publish', {'pk': article}),
        ('article_image_upload', {'pk': article}),
        ('article_image_delete', {'pk': article,
                                  'image_pk': decor['image'].pk}),
        ('article_variant_delete', {'pk': article,
                                    'variant_pk': decor['declinaison'].pk}),
        ('sync_retry', {'log_pk': decor['journal'].pk}),
    ):
        reponse = client.get(reverse(f'ecommerce:{nom}', kwargs=kwargs))
        assert reponse.status_code == 405, (
            f'ecommerce:{nom} accepte un GET ({reponse.status_code})')


@pytest.mark.django_db
def test_une_image_se_televerse_avec_sa_declinaison(client, decor):
    """Le TypeError d'origine, mesuré de bout en bout."""
    from apps.websites.models import StoreProductImage

    avant = StoreProductImage.objects.filter(product=decor['article']).count()

    reponse = client.post(
        reverse('ecommerce:article_image_upload',
                kwargs={'pk': decor['article'].pk}),
        {'image': _image('cadran.png'), 'alt_text': 'Cadran',
         'variant_label': 'Cadran ardoise', 'is_primary': '1'})

    assert reponse.status_code == 302
    apres = StoreProductImage.objects.filter(product=decor['article'])
    assert apres.count() == avant + 1
    ajoutee = apres.order_by('-pk').first()
    assert ajoutee.variant_label == 'Cadran ardoise'
    assert ajoutee.is_primary is True


@pytest.mark.django_db
def test_une_declinaison_se_supprime(client, decor):
    from apps.websites.models import StoreProductVariant

    reponse = client.post(reverse(
        'ecommerce:article_variant_delete',
        kwargs={'pk': decor['article'].pk,
                'variant_pk': decor['declinaison'].pk}))

    assert reponse.status_code == 302
    assert not StoreProductVariant.objects.filter(
        pk=decor['declinaison'].pk).exists()


@pytest.mark.django_db
def test_un_reessai_de_synchronisation_ajoute_une_trace(client, decor):
    """Le journal doit garder les deux lignes : l'échec ET le réessai.

    Écraser la première ferait perdre la trace de ce qui s'est passé, ce
    qui est tout l'objet d'un journal.
    """
    from apps.websites.models import SyncLog

    avant = SyncLog.objects.filter(company=decor['entreprise']).count()

    reponse = client.post(reverse('ecommerce:sync_retry',
                                  kwargs={'log_pk': decor['journal'].pk}))

    assert reponse.status_code == 302
    assert SyncLog.objects.filter(
        company=decor['entreprise']).count() == avant + 1


# ── 4. Le bornage par entreprise ──────────────────────────────────────────

@pytest.mark.django_db
def test_un_article_d_une_autre_entreprise_est_refuse(client, decor,
                                                      django_user_model):
    """Ces pages exposent prix d'achat, stocks et marges."""
    from apps.accounts.models import UserProfile
    from apps.core.models import Company
    from apps.private_saas.models import ALL_MODULE_CODES, CompanyModule

    autre = Company.objects.create(name='Concurrent SA', slug='concurrent-sa')
    for code in ALL_MODULE_CODES:
        CompanyModule.objects.update_or_create(
            company=autre, module_code=code, defaults={'is_enabled': True})
    espion = django_user_model.objects.create_user(
        'espion', password='x', is_superuser=True, is_staff=True)
    profil, _ = UserProfile.objects.get_or_create(user=espion)
    profil.role = 'superadmin'
    profil.save()
    profil.companies.add(autre)

    client.force_login(django_user_model.objects.get(pk=espion.pk))
    session = client.session
    session['current_company_id'] = autre.pk
    session.save()

    reponse = client.get(reverse('ecommerce:article_detail',
                                 kwargs={'pk': decor['article'].pk}))
    assert reponse.status_code == 404


@pytest.mark.django_db
def test_un_visiteur_anonyme_est_renvoye(client, decor):
    client.logout()
    reponse = client.get(reverse('ecommerce:article_list'))
    assert reponse.status_code == 302


# ── 5. Les propriétés dérivées ────────────────────────────────────────────

@pytest.mark.django_db
def test_une_declinaison_sans_prix_suit_celui_de_l_article(decor):
    """`price_override` est nul par défaut, et c'est le sens du nom.

    Mettre 0 par défaut aurait affiché des articles gratuits.
    """
    declinaison = decor['declinaison']
    assert declinaison.price_override is None
    assert declinaison.prix_effectif == getattr(decor['article'], 'price', None)


@pytest.mark.django_db
def test_une_declinaison_non_suivie_est_toujours_disponible(decor):
    declinaison = decor['declinaison']
    declinaison.track_stock = False
    declinaison.stock_quantity = 0
    assert declinaison.en_stock is True

    declinaison.track_stock = True
    assert declinaison.en_stock is False

    declinaison.stock_quantity = 3
    assert declinaison.en_stock is True


# -- 6. Creer et modifier un article : les deux vues qui exigeaient ---------
#       les vingt-cinq champs editoriaux


@pytest.mark.django_db
def test_un_article_se_cree_avec_sa_fiche_editoriale(client, decor):
    """La vue qui ne pouvait pas tourner, mesuree de bout en bout.

    `article_create` renseigne trente-six champs sur StoreProduct, dont
    vingt-cinq n'existaient pas. Elle levait donc avant meme d'arriver au
    rendu -- et son `except Exception` transformait l'echec en simple
    message, ce qui l'aurait rendu encore plus discret si la route avait
    existe.
    """
    from apps.websites.models import StoreProduct, SyncLog

    reponse = client.post(reverse('ecommerce:article_create'), {
        'name': 'Abyssal 300',
        'sku': 'ABY-300',
        'archive_ref': 'ARCH-1962',
        'category': decor['categorie'].pk,
        'short_description': 'Plongeuse automatique.',
        'description': 'Trois cents metres.',
        'price': '2450',
        'stock_quantity': '4',
        'status': 'draft',
        'available_sizes_json': '[]',
        'early_access_type': 'gold_early_access',
        'story_title': 'Nee pour les profondeurs',
        'story_content': 'Un long recit.',
        'selection_reason': 'Sa lunette.',
        'materials': 'Acier 316L',
        'dimensions': '41 mm',
        'weight': '142 g',
        'origin_country': 'Suisse',
        'condition': 'Neuf',
        'is_siecle_selection': 'on',
        'is_limited_edition': 'on',
        'edition_quantity': '300',
        'product_highlights_json': '["Lunette ceramique", "300 m"]',
        'technical_details_json': '{"Mouvement": "Automatique"}',
        'faq_items_json': '[{"q": "Etanche ?", "r": "300 m."}]',
    })

    assert reponse.status_code == 302
    article = StoreProduct.objects.get(name='Abyssal 300')
    assert article.archive_ref == 'ARCH-1962'
    assert article.early_access_type == 'gold_early_access'
    assert article.is_siecle_selection is True
    assert article.is_limited_edition is True
    assert article.edition_quantity == 300
    assert article.product_highlights == ['Lunette ceramique', '300 m']
    assert article.technical_details == {'Mouvement': 'Automatique'}
    assert len(article.faq_items) == 1
    # La creation laisse une trace dans le journal de synchronisation.
    assert SyncLog.objects.filter(product=article).exists()


@pytest.mark.django_db
def test_un_json_illisible_ne_fait_pas_echouer_la_creation(client, decor):
    """La vue retombe sur une liste vide, et c'est voulu.

    Ces champs viennent d'un editeur JavaScript : une saisie incomplete ne
    doit pas perdre tout le reste de la fiche.
    """
    from apps.websites.models import StoreProduct

    client.post(reverse('ecommerce:article_create'), {
        'name': 'Ceramique 36',
        'category': decor['categorie'].pk,
        'price': '1200',
        'status': 'draft',
        'available_sizes_json': '[]',
        'product_highlights_json': 'ceci n est pas du JSON',
        'technical_details_json': '[1, 2, 3]',
        'faq_items_json': '',
    })

    article = StoreProduct.objects.get(name='Ceramique 36')
    assert article.product_highlights == []
    # Une liste la ou un dictionnaire est attendu est refusee aussi.
    assert article.technical_details == {}
    assert article.faq_items == []


@pytest.mark.django_db
def test_un_article_se_modifie(client, decor):
    reponse = client.post(
        reverse('ecommerce:article_edit', kwargs={'pk': decor['article'].pk}),
        {
            'name': 'Meridien 39 — revu',
            'category': decor['categorie'].pk,
            'price': '1990',
            'status': 'published',
            'available_sizes_json': '[]',
            'story_title': 'Le meridien',
            'early_access_type': 'public',
        })

    assert reponse.status_code == 302
    decor['article'].refresh_from_db()
    assert decor['article'].name == 'Meridien 39 — revu'
    assert decor['article'].story_title == 'Le meridien'


@pytest.mark.django_db
def test_les_declinaisons_s_enregistrent_par_le_formset(client, decor):
    """Le formset qui n'existait pas, employe pour de vrai."""
    from apps.websites.models import StoreProductVariant

    avant = StoreProductVariant.objects.filter(
        product=decor['article']).count()

    reponse = client.post(
        reverse('ecommerce:article_variants',
                kwargs={'pk': decor['article'].pk}),
        {
            'variants-TOTAL_FORMS': '2',
            'variants-INITIAL_FORMS': '1',
            'variants-MIN_NUM_FORMS': '0',
            'variants-MAX_NUM_FORMS': '1000',
            'variants-0-id': str(decor['declinaison'].pk),
            'variants-0-name': '39 mm acier',
            'variants-0-sku': 'MER-39-AC',
            'variants-0-size': '39',
            'variants-0-color': 'Acier',
            'variants-0-stock_quantity': '2',
            'variants-0-display_order': '0',
            'variants-1-name': '36 mm or',
            'variants-1-sku': 'MER-36-OR',
            'variants-1-size': '36',
            'variants-1-color': 'Or',
            'variants-1-stock_quantity': '1',
            'variants-1-display_order': '1',
        })

    assert reponse.status_code in (200, 302)
    apres = StoreProductVariant.objects.filter(product=decor['article'])
    assert apres.count() == avant + 1, (
        f'{apres.count()} declinaison(s) au lieu de {avant + 1}')
    assert apres.filter(sku='MER-36-OR').exists()
