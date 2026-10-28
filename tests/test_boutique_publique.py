"""Boutique publique : elle répondait 500 dès qu'elle avait un produit.

Trois défauts, tous mesurés et non supposés.

**1. Ni `Product` ni `ProductCategory` n'avait de champ `slug`**, alors que
les routes sont déclarées `boutique/produit/<slug:slug>/` et
`boutique/categorie/<slug:slug>/`, et que les gabarits construisent leurs
liens avec `p.slug`. L'attribut rendait une chaîne vide, le convertisseur
`slug` refusait le vide, `{% url %}` levait `NoReverseMatch` — et la page
entière avec. Mesure d'origine, avec un seul produit au catalogue :

    /boutique/            -> NoReverseMatch pour 'store_category'  ('',)
    /boutique/recherche/  -> NoReverseMatch pour 'store_product_detail'

**2. `store_product_detail` n'employait pas le slug reçu.** Sa requête
était `get_object_or_404(Product, company=company, is_active=True)` : avec
un seul produit, toutes les adresses affichaient le même ; avec plusieurs,
`MultipleObjectsReturned` était avalé par un `except Exception` qui
retombait sur `pk=slug`, et un slug non numérique levait alors
`ValueError` — un 500 déclenchable depuis la barre d'adresse.

**3. `store_category` avait exactement le même défaut.**

Le catalogue vide est ce qui masquait tout : mon parcours des 1052
adresses du projet n'a rien vu, parce que la base de test ne contenait
aucun produit. C'est la leçon de ce fichier — une page ne se teste pas
seulement à vide.
"""

import os
import re

import pytest
from django.urls import reverse

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def boutique(client, django_user_model):
    """Une entreprise, deux catégories, trois produits.

    Deux de chaque au minimum : avec un seul objet, les requêtes fautives
    d'origine « fonctionnaient » par accident — elles rendaient l'unique
    ligne pour n'importe quelle adresse.
    """
    from apps.accounts.models import UserProfile
    from apps.core.models import Company
    from apps.inventory.models import Product, ProductCategory

    entreprise = Company.objects.create(name='Boutique SA',
                                        slug='boutique-sa')

    montres = ProductCategory.objects.create(company=entreprise,
                                             name='Montres')
    bracelets = ProductCategory.objects.create(company=entreprise,
                                               name='Bracelets')

    abyssal = Product.objects.create(
        company=entreprise, name='Abyssal 300', category=montres,
        is_active=True, sale_price=2450)
    meridien = Product.objects.create(
        company=entreprise, name='Méridien 39', category=montres,
        is_active=True, sale_price=1990)
    cuir = Product.objects.create(
        company=entreprise, name='Bracelet cuir', category=bracelets,
        is_active=True, sale_price=120)

    utilisateur = django_user_model.objects.create_user(
        'visiteur-boutique', password='x', is_superuser=True, is_staff=True)
    profil, _ = UserProfile.objects.get_or_create(user=utilisateur)
    profil.role = 'superadmin'
    profil.save()
    profil.companies.add(entreprise)

    client.force_login(django_user_model.objects.get(pk=utilisateur.pk))
    session = client.session
    session['current_company_id'] = entreprise.pk
    session.save()

    return {
        'entreprise': entreprise, 'montres': montres,
        'bracelets': bracelets, 'abyssal': abyssal,
        'meridien': meridien, 'cuir': cuir,
    }


# ── 1. Le champ qui manquait ───────────────────────────────────────────────

@pytest.mark.django_db
def test_un_produit_recoit_un_slug_a_l_enregistrement(boutique):
    assert boutique['abyssal'].slug == 'abyssal-300'
    assert boutique['montres'].slug == 'montres'


@pytest.mark.django_db
def test_deux_produits_de_meme_nom_ont_des_slugs_distincts(boutique):
    """L'unicité est bornée à l'entreprise, donc les collisions internes
    doivent être résolues — sinon l'enregistrement échoue sur la
    contrainte."""
    from apps.inventory.models import Product

    premier = Product.objects.create(
        company=boutique['entreprise'], name='Écrou M8', is_active=True)
    second = Product.objects.create(
        company=boutique['entreprise'], name='Écrou M8', is_active=True)

    assert premier.slug == 'ecrou-m8'
    assert second.slug == 'ecrou-m8-2'
    assert premier.slug != second.slug


@pytest.mark.django_db
def test_deux_entreprises_peuvent_avoir_le_meme_slug(boutique):
    """Une unicité GLOBALE ferait échouer la seconde société.

    Deux entreprises vendent légitimement un « Écrou M8 » ; l'adresse
    publique est de toute façon résolue avec l'entreprise.
    """
    from apps.core.models import Company
    from apps.inventory.models import Product

    autre = Company.objects.create(name='Autre SA', slug='autre-sa')
    chez_nous = Product.objects.create(
        company=boutique['entreprise'], name='Vis inox', is_active=True)
    chez_eux = Product.objects.create(
        company=autre, name='Vis inox', is_active=True)

    assert chez_nous.slug == chez_eux.slug == 'vis-inox'


@pytest.mark.django_db
def test_un_nom_sans_caractere_slugifiable_reste_enregistrable(boutique):
    """Un nom en idéogrammes ou en ponctuation donne un slug vide.

    Sans repli, l'adresse serait vide et la contrainte d'unicité ferait
    échouer le deuxième produit dans ce cas.
    """
    from apps.inventory.models import Product

    premier = Product.objects.create(
        company=boutique['entreprise'], name='!!!', is_active=True)
    second = Product.objects.create(
        company=boutique['entreprise'], name='???', is_active=True)

    assert premier.slug == 'sans-nom'
    assert second.slug == 'sans-nom-2'


# ── 2. Les pages qui rendaient 500 ────────────────────────────────────────

@pytest.mark.django_db
def test_l_accueil_de_la_boutique_s_affiche_avec_des_produits(client,
                                                               boutique):
    """LE test de la panne. Avant, NoReverseMatch sur store_category."""
    reponse = client.get(reverse('store:store_home'))

    assert reponse.status_code == 200
    contenu = reponse.content.decode()
    assert 'Abyssal 300' in contenu


@pytest.mark.django_db
def test_la_recherche_s_affiche_avec_des_resultats(client, boutique):
    """Avant, NoReverseMatch sur store_product_detail."""
    reponse = client.get(reverse('store:store_search'), {'q': 'Abyssal'})

    assert reponse.status_code == 200
    assert 'Abyssal 300' in reponse.content.decode()


@pytest.mark.django_db
def test_une_categorie_s_affiche(client, boutique):
    reponse = client.get(reverse('store:store_category',
                                 args=[boutique['montres'].slug]))
    assert reponse.status_code == 200


# ── 3. La bonne fiche, et pas une autre ──────────────────────────────────

@pytest.mark.django_db
def test_la_fiche_produit_affiche_LE_produit_demande(client, boutique):
    """Le défaut le plus trompeur : la page répondait 200 avec le MAUVAIS
    produit.

    La requête d'origine ne filtrait pas sur le slug. Avec un seul produit
    au catalogue elle rendait toujours celui-là, donc un test naïf aurait
    passé. D'où trois produits dans la fixture.
    """
    reponse = client.get(reverse('store:store_product_detail',
                                 args=[boutique['meridien'].slug]))

    assert reponse.status_code == 200
    contenu = reponse.content.decode()
    assert 'Méridien 39' in contenu
    assert 'Abyssal 300' not in contenu or contenu.count('Méridien 39') >= 1


@pytest.mark.django_db
def test_la_categorie_affiche_LA_categorie_demandee(client, boutique):
    """Même défaut, même vérification : les bracelets ne sont pas des montres."""
    reponse = client.get(reverse('store:store_category',
                                 args=[boutique['bracelets'].slug]))

    assert reponse.status_code == 200
    contenu = reponse.content.decode()
    assert 'Bracelet cuir' in contenu
    assert 'Abyssal 300' not in contenu


# ── 4. Les adresses inventées ────────────────────────────────────────────

@pytest.mark.django_db
def test_un_slug_de_produit_inconnu_rend_404_et_non_500(client, boutique):
    """Déclenchable depuis la barre d'adresse par n'importe quel visiteur.

    Avant : ValueError « Field 'id' expected a number but got
    'inexistant' », donc 500 sur une boutique publique.
    """
    reponse = client.get(reverse('store:store_product_detail',
                                 args=['produit-qui-nexiste-pas']))
    assert reponse.status_code == 404


@pytest.mark.django_db
def test_un_slug_de_categorie_inconnu_rend_404(client, boutique):
    reponse = client.get(reverse('store:store_category',
                                 args=['categorie-inconnue']))
    assert reponse.status_code == 404


@pytest.mark.django_db
def test_un_ancien_lien_par_identifiant_fonctionne_encore(client, boutique):
    """Le repli par identifiant est conservé, mais BORNÉ au numérique.

    D'anciens liens peuvent pointer sur /boutique/produit/42/ ; les
    accepter coûte deux lignes et évite des 404 chez les visiteurs qui ont
    gardé l'adresse.
    """
    reponse = client.get(reverse('store:store_product_detail',
                                 args=[str(boutique['cuir'].pk)]))

    assert reponse.status_code == 200
    assert 'Bracelet cuir' in reponse.content.decode()


@pytest.mark.django_db
def test_un_produit_d_une_autre_entreprise_est_introuvable(client, boutique):
    """Le bornage par entreprise ne doit pas disparaître avec le slug."""
    from apps.core.models import Company
    from apps.inventory.models import Product

    autre = Company.objects.create(name='Concurrent SA',
                                   slug='concurrent-boutique')
    chez_eux = Product.objects.create(
        company=autre, name='Secret industriel', is_active=True)

    reponse = client.get(reverse('store:store_product_detail',
                                 args=[chez_eux.slug]))
    assert reponse.status_code == 404


@pytest.mark.django_db
def test_un_produit_inactif_n_est_pas_servi(client, boutique):
    """`is_active` était dans la requête d'origine : il doit y rester."""
    boutique['abyssal'].is_active = False
    boutique['abyssal'].save()

    reponse = client.get(reverse('store:store_product_detail',
                                 args=[boutique['abyssal'].slug]))
    assert reponse.status_code == 404


# ── 5. L'ordre des opérations de la migration ────────────────────────────

def test_la_migration_remplit_les_slugs_avant_la_contrainte():
    """Sans cet ordre, la migration échoue sur toute base déjà peuplée.

    Django avait généré AddField puis AlterUniqueTogether : le champ
    arrive vide pour toutes les lignes, et la contrainte (company, slug)
    refuse alors la deuxième ligne d'une même entreprise. Le RunPython a
    été inséré ENTRE les deux à la main.

    Ce test lit l'ordre dans le fichier, parce qu'une migration ne
    s'éprouve pas autrement sans base peuplée.
    """
    dossier = os.path.join(RACINE, 'apps', 'inventory', 'migrations')
    fichier = [f for f in os.listdir(dossier) if f.startswith('0004_')]
    assert fichier, 'Migration 0004 des slugs introuvable.'

    with open(os.path.join(dossier, fichier[0]), encoding='utf-8') as f:
        contenu = f.read()

    # On ne lit que la LISTE DES OPÉRATIONS. Chercher dans tout le fichier
    # trouvait « AlterUniqueTogether » dans la docstring, qui explique
    # justement le piège — le test échouait sur son propre commentaire.
    debut = contenu.find('operations = [')
    assert debut != -1, 'Liste des operations introuvable.'
    operations = contenu[debut:]

    position_remplissage = operations.find('RunPython')
    position_contrainte = operations.find('AlterUniqueTogether')

    assert position_remplissage != -1, (
        'Aucun RunPython : la migration echouera sur une base peuplee.')
    assert position_contrainte != -1
    assert position_remplissage < position_contrainte, (
        'Le remplissage des slugs doit preceder la contrainte d unicite.')


def test_la_migration_est_reversible():
    """Une migration de donnees sans marche arrière bloque un rollback."""
    dossier = os.path.join(RACINE, 'apps', 'inventory', 'migrations')
    fichier = [f for f in os.listdir(dossier) if f.startswith('0004_')][0]
    with open(os.path.join(dossier, fichier), encoding='utf-8') as f:
        contenu = f.read()

    trouve = re.search(r'RunPython\(([^)]*)\)', contenu, re.S)
    assert trouve, 'RunPython introuvable.'
    assert ',' in trouve.group(1), (
        'RunPython sans fonction inverse : le rollback serait impossible.')
