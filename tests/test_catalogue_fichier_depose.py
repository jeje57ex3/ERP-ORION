"""Importer un tarif depuis un fichier déposé, et non depuis une URL.

**Le manque que ce fichier comble.** L'importeur de catalogues ne savait
aller chercher qu'une adresse publique. Or les tarifs des grands
fabricants — Schneider, Legrand, Hager, Soprema — se téléchargent à la main
depuis un portail réservé aux professionnels : ils n'ont **aucune adresse
publique** que l'ERP pourrait atteindre. Le besoin « importe tout le
catalogue Schneider » était donc inatteignable, non par manque de code mais
par manque de chemin.

**Un seul chemin de lecture pour les deux voies.** `executer()` accepte des
octets déjà en main ; le reste — analyse, correspondance des colonnes,
import, journal — est strictement le même. Deux fonctions auraient divergé,
et le même fichier n'aurait pas donné le même résultat selon qu'il arrive
par le réseau ou par le navigateur. Un test le vérifie en comparant les
deux voies sur le même contenu.

**Aucune référence n'est inventée.** La commande `creer_sources_fabricants`
prépare les quatre sources et leurs fournisseurs, et n'importe **aucun**
article : ces tarifs sont derrière un portail protégé, et fabriquer des
références plausibles avec des prix inventés les enverrait dans des devis
chez des clients. Une référence absente se remarque ; une référence fausse
se facture.
"""

import io
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.accounts.models import UserProfile
from apps.btp.catalogue_import import CatalogueError, executer, telecharger
from apps.btp.models import CatalogueSource, Material

pytestmark = pytest.mark.django_db


# ── Terrain ─────────────────────────────────────────────────────────────────

CSV_TARIF = (
    'Reference;Designation;Unite;Prix HT;Famille\n'
    'A9F74210;Disjoncteur iC60N 2P 10A;u;42,30;Protection modulaire\n'
    'A9F74216;Disjoncteur iC60N 2P 16A;u;43,10;Protection modulaire\n'
    'LGR-67001;Interrupteur Celiane;u;18,75;Appareillage\n'
)

# Les CLÉS sont les champs de l'ERP, pas des noms libres : nom, reference,
# prix_achat, prix_vente, nature, categorie, unite,
# reference_fournisseur, description. Une clé inconnue est silencieusement
# ignorée, et l'import lit les lignes sans en tirer aucun article.
COLONNES = {
    'reference': 'Reference',
    'nom': 'Designation',
    'unite': 'Unite',
    'prix_achat': 'Prix HT',
    'categorie': 'Famille',
}


@pytest.fixture
def entreprise(db):
    from apps.core.models import Company
    return Company.objects.create(name='Dupont SA', slug='dupont-sa')


@pytest.fixture
def autre_entreprise(db):
    from apps.core.models import Company
    return Company.objects.create(name='Martin SA', slug='martin-sa')


def creer_compte(nom, company, role='admin'):
    utilisateur = User.objects.create_user(username=nom, password='x')
    profil, _ = UserProfile.objects.get_or_create(user=utilisateur)
    profil.role = role
    profil.save()
    profil.companies.add(company)
    return User.objects.get(pk=utilisateur.pk)


@pytest.fixture
def agent(entreprise):
    return creer_compte('agent', entreprise)


def creer_source(company, url='', nom='Tarif Schneider'):
    return CatalogueSource.objects.create(
        company=company, name=nom, url=url, format='csv',
        delimiteur=';', encodage='utf-8', colonnes=COLONNES,
        nature_par_defaut='material', is_active=True)


def deposer(client, source, octets, a_blanc=False, nom='tarif.csv'):
    donnees = {'fichier': SimpleUploadedFile(nom, octets,
                                             content_type='text/csv')}
    if a_blanc:
        donnees['a_blanc'] = '1'
    return client.post(
        reverse('btp:catalogue_source_upload', args=[source.pk]), donnees)


# ── 1. Une source sans adresse est désormais valide ─────────────────────────

def test_une_source_sans_url_peut_exister(entreprise):
    """Exiger une URL rendait ces sources impossibles à créer.

    Un tarif de fabricant n'a pas d'adresse : il se dépose.
    """
    source = creer_source(entreprise, url='')
    source.full_clean()
    assert source.url == ''


def test_telecharger_refuse_clairement_une_source_sans_url(entreprise):
    """Une phrase utile, pas une erreur de bibliothèque.

    `None` passé à requests donnerait une trace incompréhensible ; ici le
    message dit quoi faire.
    """
    source = creer_source(entreprise, url='')
    with pytest.raises(CatalogueError) as echec:
        telecharger(source)
    assert 'déposant le fichier' in str(echec.value)


# ── 2. L'import depuis des octets ───────────────────────────────────────────

def test_l_import_depuis_un_fichier_cree_les_articles(entreprise):
    source = creer_source(entreprise)
    journal = executer(source, octets=CSV_TARIF.encode('utf-8'))

    assert journal.statut != 'echec', journal.message
    assert journal.lignes_lues == 3
    assert journal.crees == 3
    assert Material.objects.filter(company=entreprise).count() == 3

    article = Material.objects.get(reference='A9F74210')
    assert article.name == 'Disjoncteur iC60N 2P 10A'
    assert article.purchase_price == Decimal('42.30')


def test_l_essai_a_blanc_n_ecrit_rien(entreprise):
    """Une colonne mal nommée produirait des milliers d'articles au mauvais
    nom, dans un catalogue qui sert ensuite à chiffrer."""
    source = creer_source(entreprise)
    journal = executer(source, a_blanc=True, octets=CSV_TARIF.encode('utf-8'))

    assert journal.lignes_lues == 3
    assert journal.crees == 3          # ce qui SERAIT créé
    assert Material.objects.count() == 0


def test_l_import_depuis_un_fichier_ne_telecharge_rien(entreprise,
                                                        monkeypatch):
    """La preuve que la voie fichier court-circuite bien le réseau.

    Une source sans URL passerait de toute façon ; ici la source EN a une,
    et le téléchargement ne doit pas être tenté pour autant.
    """
    from apps.btp import catalogue_import

    def interdit(*args, **kwargs):
        raise AssertionError('le réseau a été appelé alors que le fichier '
                             'était déjà en main')

    monkeypatch.setattr(catalogue_import, 'telecharger', interdit)
    source = creer_source(entreprise, url='https://exemple.fr/tarif.csv')
    journal = executer(source, octets=CSV_TARIF.encode('utf-8'))
    assert journal.crees == 3


def test_les_deux_voies_donnent_le_meme_resultat(entreprise, autre_entreprise,
                                                  monkeypatch):
    """Un seul chemin de lecture, et c'est vérifié.

    Deux fonctions auraient divergé, et le même fichier n'aurait pas donné
    le même résultat selon qu'il arrive par le réseau ou par le
    navigateur.
    """
    from apps.btp import catalogue_import

    octets = CSV_TARIF.encode('utf-8')

    par_fichier = creer_source(entreprise)
    journal_fichier = executer(par_fichier, octets=octets)

    monkeypatch.setattr(catalogue_import, 'telecharger',
                        lambda source, session=None: octets)
    par_url = creer_source(autre_entreprise,
                           url='https://exemple.fr/tarif.csv')
    journal_url = executer(par_url)

    for cle in ('lignes_lues', 'crees', 'mis_a_jour', 'inchanges', 'ignores'):
        assert getattr(journal_fichier, cle) == getattr(journal_url, cle), cle


def test_un_second_depot_met_a_jour_sans_dupliquer(entreprise):
    source = creer_source(entreprise)
    executer(source, octets=CSV_TARIF.encode('utf-8'))

    modifie = CSV_TARIF.replace('42,30', '45,90')
    journal = executer(source, octets=modifie.encode('utf-8'))

    assert journal.crees == 0
    assert journal.mis_a_jour == 1
    assert Material.objects.filter(company=entreprise).count() == 3
    assert Material.objects.get(
        reference='A9F74210').purchase_price == Decimal('45.90')


def test_le_prix_de_vente_n_est_jamais_ecrase(entreprise):
    """La règle du module, qui vaut aussi par cette voie.

    Le prix d'achat vient du fabricant ; le prix de vente porte la marge de
    l'exploitant. Un dépôt de tarif qui l'écraserait effacerait en silence
    toute la tarification.
    """
    source = creer_source(entreprise)
    executer(source, octets=CSV_TARIF.encode('utf-8'))

    article = Material.objects.get(reference='A9F74210')
    article.sale_price = Decimal('89.00')
    article.save()

    executer(source, octets=CSV_TARIF.replace('42,30', '50,00').encode('utf-8'))

    article.refresh_from_db()
    assert article.purchase_price == Decimal('50.00')
    assert article.sale_price == Decimal('89.00')


def test_un_fichier_illisible_est_journalise_et_non_tu(entreprise):
    """Un import qui échoue en silence est pire qu'un import absent."""
    source = creer_source(entreprise)
    source.format = 'excel'
    source.save()
    journal = executer(source, octets=b'ceci n est pas un classeur Excel')
    assert journal.statut == 'echec'
    assert journal.message


# ── 3. L'écran de dépôt ─────────────────────────────────────────────────────

def test_le_depot_par_l_ecran_importe(client, agent, entreprise):
    source = creer_source(entreprise)
    client.force_login(agent)
    reponse = deposer(client, source, CSV_TARIF.encode('utf-8'))
    assert reponse.status_code in (301, 302)
    assert Material.objects.filter(company=entreprise).count() == 3


def test_le_depot_en_essai_a_blanc_n_ecrit_rien(client, agent, entreprise):
    source = creer_source(entreprise)
    client.force_login(agent)
    deposer(client, source, CSV_TARIF.encode('utf-8'), a_blanc=True)
    assert Material.objects.count() == 0


def test_un_depot_sans_fichier_est_refuse(client, agent, entreprise):
    source = creer_source(entreprise)
    client.force_login(agent)
    reponse = client.post(
        reverse('btp:catalogue_source_upload', args=[source.pk]), {},
        follow=True)
    assert 'Aucun fichier' in reponse.content.decode()
    assert Material.objects.count() == 0


def test_le_depot_exige_un_post(client, agent, entreprise):
    source = creer_source(entreprise)
    client.force_login(agent)
    assert client.get(reverse('btp:catalogue_source_upload',
                              args=[source.pk])).status_code == 405


def test_le_depot_sur_une_source_d_une_autre_entreprise_est_introuvable(
        client, agent, autre_entreprise):
    source = creer_source(autre_entreprise)
    client.force_login(agent)
    reponse = deposer(client, source, CSV_TARIF.encode('utf-8'))
    assert reponse.status_code == 404
    assert Material.objects.count() == 0


def test_un_anonyme_ne_depose_rien(client, entreprise):
    source = creer_source(entreprise)
    reponse = deposer(client, source, CSV_TARIF.encode('utf-8'))
    assert reponse.status_code in (301, 302)
    assert Material.objects.count() == 0


def test_la_fiche_propose_le_depot_et_cache_le_telechargement(client, agent,
                                                               entreprise):
    """Un bouton « Importer maintenant » sur une source sans adresse
    promettrait une action impossible."""
    source = creer_source(entreprise, url='')
    client.force_login(agent)
    corps = client.get(reverse('btp:catalogue_source_detail',
                               args=[source.pk])).content.decode()
    assert reverse('btp:catalogue_source_upload', args=[source.pk]) in corps
    assert reverse('btp:catalogue_source_run', args=[source.pk]) not in corps


def test_la_fiche_d_une_source_avec_url_garde_le_telechargement(client, agent,
                                                                 entreprise):
    source = creer_source(entreprise, url='https://exemple.fr/tarif.csv')
    client.force_login(agent)
    corps = client.get(reverse('btp:catalogue_source_detail',
                               args=[source.pk])).content.decode()
    assert reverse('btp:catalogue_source_run', args=[source.pk]) in corps
    assert reverse('btp:catalogue_source_upload', args=[source.pk]) in corps


# ── 4. La commande qui prépare les quatre fabricants ────────────────────────

def test_la_commande_cree_les_quatre_sources(entreprise):
    from django.core.management import call_command

    sortie = io.StringIO()
    call_command('creer_sources_fabricants', entreprise=entreprise.slug,
                 stdout=sortie)

    noms = set(CatalogueSource.objects.filter(
        company=entreprise).values_list('name', flat=True))
    assert noms == {'Tarif Schneider Electric', 'Tarif Legrand',
                    'Tarif Hager', 'Tarif Soprema'}


def test_la_commande_n_importe_aucun_article(entreprise):
    """LA propriété de cette commande.

    Ces tarifs sont derrière un portail protégé. Fabriquer des références
    plausibles avec des prix inventés les enverrait dans des devis chez des
    clients : une référence absente se remarque, une référence fausse se
    facture.
    """
    from django.core.management import call_command

    call_command('creer_sources_fabricants', entreprise=entreprise.slug,
                 stdout=io.StringIO())
    assert Material.objects.count() == 0


def test_les_sources_creees_n_ont_pas_d_url_ni_de_synchro(entreprise):
    """Il n'y a rien à aller chercher : une synchro nocturne échouerait
    chaque nuit et remplirait le journal d'échecs."""
    from django.core.management import call_command

    call_command('creer_sources_fabricants', entreprise=entreprise.slug,
                 stdout=io.StringIO())
    for source in CatalogueSource.objects.filter(company=entreprise):
        assert source.url == ''
        assert source.intervalle_minutes == 0


def test_soprema_est_en_fournitures_et_non_en_materiel(entreprise):
    """Étanchéité : des rouleaux et des primaires, consommés sur le
    chantier. Pas du matériel installé une fois."""
    from django.core.management import call_command

    call_command('creer_sources_fabricants', entreprise=entreprise.slug,
                 stdout=io.StringIO())
    soprema = CatalogueSource.objects.get(company=entreprise,
                                          name='Tarif Soprema')
    schneider = CatalogueSource.objects.get(company=entreprise,
                                            name='Tarif Schneider Electric')
    assert soprema.nature_par_defaut == 'supply'
    assert schneider.nature_par_defaut == 'material'


def test_la_commande_cree_aussi_les_fournisseurs(entreprise):
    from django.core.management import call_command

    from apps.purchases.models import Supplier

    call_command('creer_sources_fabricants', entreprise=entreprise.slug,
                 stdout=io.StringIO())
    noms = set(Supplier.objects.filter(
        company=entreprise).values_list('name', flat=True))
    assert {'Schneider Electric', 'Legrand', 'Hager', 'Soprema'} <= noms


def test_la_commande_est_rejouable(entreprise):
    """Relancée, elle ne duplique rien : on l'exécutera plusieurs fois."""
    from django.core.management import call_command

    for _ in range(3):
        call_command('creer_sources_fabricants', entreprise=entreprise.slug,
                     stdout=io.StringIO())
    assert CatalogueSource.objects.filter(company=entreprise).count() == 4


def test_la_commande_limite_aux_fabricants_demandes(entreprise):
    from django.core.management import call_command

    call_command('creer_sources_fabricants', entreprise=entreprise.slug,
                 seulement='hager,soprema', stdout=io.StringIO())
    noms = set(CatalogueSource.objects.filter(
        company=entreprise).values_list('name', flat=True))
    assert noms == {'Tarif Hager', 'Tarif Soprema'}


def test_une_entreprise_inconnue_est_signalee():
    from django.core.management import call_command
    from django.core.management.base import CommandError

    with pytest.raises(CommandError) as echec:
        call_command('creer_sources_fabricants', entreprise='inexistante',
                     stdout=io.StringIO())
    assert 'inexistante' in str(echec.value)


# ── 5. La commande d'import d'un fichier local ──────────────────────────────

def test_la_commande_importe_un_fichier_local(entreprise, tmp_path):
    from django.core.management import call_command

    source = creer_source(entreprise)
    chemin = tmp_path / 'tarif.csv'
    chemin.write_text(CSV_TARIF, encoding='utf-8')

    sortie = io.StringIO()
    call_command('importer_fichier_catalogue', str(chemin),
                 source=source.pk, ecrire=True, stdout=sortie)

    assert Material.objects.filter(company=entreprise).count() == 3
    assert 'lignes lues' in sortie.getvalue()


def test_la_commande_est_en_essai_a_blanc_par_defaut(entreprise, tmp_path):
    """Sur un fichier de cent mille lignes, une correspondance fausse
    créerait cent mille articles aberrants, et les défaire prendrait plus
    longtemps que de relire la sortie d'un essai."""
    from django.core.management import call_command

    source = creer_source(entreprise)
    chemin = tmp_path / 'tarif.csv'
    chemin.write_text(CSV_TARIF, encoding='utf-8')

    sortie = io.StringIO()
    call_command('importer_fichier_catalogue', str(chemin),
                 source=source.pk, stdout=sortie)

    assert Material.objects.count() == 0
    assert 'ESSAI À BLANC' in sortie.getvalue()


def test_la_commande_signale_un_fichier_introuvable(entreprise):
    from django.core.management import call_command
    from django.core.management.base import CommandError

    source = creer_source(entreprise)
    with pytest.raises(CommandError) as echec:
        call_command('importer_fichier_catalogue', '/nexiste/pas.csv',
                     source=source.pk, stdout=io.StringIO())
    assert 'introuvable' in str(echec.value)


def test_la_commande_signale_une_source_inconnue(tmp_path):
    from django.core.management import call_command
    from django.core.management.base import CommandError

    chemin = tmp_path / 'tarif.csv'
    chemin.write_text(CSV_TARIF, encoding='utf-8')
    with pytest.raises(CommandError) as echec:
        call_command('importer_fichier_catalogue', str(chemin),
                     source=999999, stdout=io.StringIO())
    assert '999999' in str(echec.value)


def test_la_commande_signale_une_correspondance_de_colonnes_fausse(
        entreprise, tmp_path):
    """Des lignes lues sans aucun article signale presque toujours une
    correspondance fausse — pas un fichier vide.

    Le cas testé est le défaut RÉALISTE : la clé est valide (`nom`), mais
    l'intitulé de colonne qu'elle désigne ne figure pas dans le fichier.
    C'est ce qui arrive quand le fabricant renomme ses en-têtes d'une
    année sur l'autre.

    L'autre cas — aucune clé de désignation du tout — est déjà refusé
    d'entrée par l'importeur, avec son propre message. Il n'avait donc pas
    besoin de cet avertissement, et le tester ici ne prouvait rien.

    Le dire évite de relancer trois fois le même import en cherchant la
    panne ailleurs.
    """
    from django.core.management import call_command

    source = creer_source(entreprise)
    source.colonnes = {'reference': 'Colonne Qui N Existe Pas',
                       'nom': 'Intitule Renomme Par Le Fabricant'}
    source.save()

    chemin = tmp_path / 'tarif.csv'
    chemin.write_text(CSV_TARIF, encoding='utf-8')

    from django.core.management.base import CommandError

    with pytest.raises(CommandError) as echec:
        call_command('importer_fichier_catalogue', str(chemin),
                     source=source.pk, stdout=io.StringIO())
    assert 'correspondance des colonnes' in str(echec.value)


def test_un_echec_d_import_n_est_jamais_sans_cause(entreprise):
    """« Échec : cause inconnue » était la réponse, et elle n'aide personne.

    Or la cause est déductible : des lignes lues, aucun article produit,
    donc la correspondance ne désigne pas les intitulés réels. Le défaut
    était dans `executer()` et touchait les deux voies — fichier et URL.
    """
    source = creer_source(entreprise)
    source.colonnes = {'nom': 'Intitule Absent'}
    source.save()

    journal = executer(source, octets=CSV_TARIF.encode('utf-8'))
    assert journal.statut == 'echec'
    assert journal.message
    assert 'cause inconnue' not in journal.message
    assert 'correspondance des colonnes' in journal.message


def test_un_fichier_vide_est_distingue_d_une_correspondance_fausse(
        entreprise):
    """Les deux ne se corrigent pas de la même façon.

    Un fichier vide se redemande au fournisseur ; une correspondance
    fausse se répare sur la fiche de la source.
    """
    source = creer_source(entreprise)
    journal = executer(source, octets=b'Reference;Designation;Unite;Prix HT;Famille\n')
    assert journal.statut == 'echec'
    assert 'vide' in journal.message
