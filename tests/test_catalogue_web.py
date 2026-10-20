"""Import d'un catalogue fournisseur publié sur le web.

Trois propriétés gouvernent ce fichier.

**Le prix de vente n'est JAMAIS écrasé.** Le prix d'achat vient du
fournisseur et suit le fichier ; le prix de vente porte la marge de
l'exploitant. Sans cette asymétrie, une synchronisation nocturne effacerait
en silence toute la tarification, et personne ne s'en apercevrait avant de
lire un devis parti chez un client.

**L'adresse est fournie par l'utilisateur et récupérée par le SERVEUR.**
Une adresse menant à `127.0.0.1`, `10.0.0.0/8` ou `169.254.169.254`
transformerait l'import en lecteur du réseau interne — base de données,
Redis, métadonnées d'instance. Chaque redirection est revérifiée, sinon une
adresse publique redirigeant vers le bouclage contournerait tout.

**Rien n'est jamais supprimé.** Un article que le fournisseur ne publie
plus est signalé, jamais effacé : il peut figurer dans un devis déjà envoyé.
"""

import io
from decimal import Decimal

import pytest

pytestmark = pytest.mark.django_db


# ── Terrain ─────────────────────────────────────────────────────────────────

CSV_TARIF = (
    'Reference;Designation;Unite;Prix HT;Famille\n'
    'CIM-35;Ciment CEM II 35 kg;sac;6,40;Gros oeuvre\n'
    'SAB-04;Sable 0/4 en vrac;t;32,50;Gros oeuvre\n'
    'BA13;Plaque de platre BA13;m2;4,15;Platrerie\n'
)


@pytest.fixture
def entreprise(db):
    from apps.core.models import Company
    return Company.objects.create(name='Dupont SA', slug='dupont-sa')


@pytest.fixture
def autre_entreprise(db):
    from apps.core.models import Company
    return Company.objects.create(name='Martin SA', slug='martin-sa')


@pytest.fixture
def source(entreprise):
    from apps.btp.models import CatalogueSource
    return CatalogueSource.objects.create(
        company=entreprise, name='Negoce — tarifs',
        url='https://exemple-fournisseur.test/tarifs.csv',
        format='csv', delimiteur=';',
        nature_par_defaut='material',
        colonnes={
            'reference': 'Reference', 'nom': 'Designation',
            'unite': 'Unite', 'prix_achat': 'Prix HT',
            'categorie': 'Famille',
        })


@pytest.fixture
def connecte(client, entreprise, django_user_model):
    user = django_user_model.objects.create_user(
        username='patron', password='motdepasse-test')
    user.profile.companies.add(entreprise)
    user.profile.current_company = entreprise
    user.profile.save()
    client.force_login(user)
    return client


def _lignes(texte=CSV_TARIF, source=None):
    """Les lignes analysées, sans passer par le réseau."""
    from apps.btp.catalogue_import import analyser
    return analyser(texte.encode('utf-8'), source)


# ═══ L'ADRESSE : REFUS DU RÉSEAU INTERNE ════════════════════════════════════

@pytest.mark.parametrize('url', [
    'http://127.0.0.1/tarifs.csv',
    'http://localhost:8000/tarifs.csv',
    'http://169.254.169.254/latest/meta-data/',
    'http://10.0.0.5/tarifs.csv',
    'http://192.168.1.10/tarifs.csv',
    'http://172.16.0.1/tarifs.csv',
    'http://[::1]/tarifs.csv',
    'http://0.0.0.0/tarifs.csv',
])
def test_une_adresse_interne_est_refusee(url):
    """Le serveur atteint la base, Redis, Ollama et, sur un hébergeur, les
    métadonnées d'instance. Une adresse de catalogue est publique."""
    from apps.btp.catalogue_import import CatalogueError, _verifier_adresse

    with pytest.raises(CatalogueError) as echec:
        _verifier_adresse(url)
    assert 'interne' in str(echec.value) or 'introuvable' in str(echec.value)


@pytest.mark.parametrize('url', [
    'ftp://exemple.test/tarifs.csv',
    'file:///etc/passwd',
    'gopher://exemple.test/',
    '',
    None,
    'pas-une-adresse',
])
def test_un_schema_non_http_est_refuse(url):
    from apps.btp.catalogue_import import CatalogueError, _verifier_adresse

    with pytest.raises(CatalogueError):
        _verifier_adresse(url)


def test_toutes_les_adresses_resolues_sont_controlees(monkeypatch):
    """Un nom peut résoudre à la fois vers une adresse publique ET vers
    127.0.0.1. Ne vérifier que la première laisserait passer."""
    import socket

    from apps.btp.catalogue_import import CatalogueError, _verifier_adresse

    def faux_getaddrinfo(hote, port, *args, **kwargs):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.216.34', 0)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('127.0.0.1', 0)),
        ]

    monkeypatch.setattr(socket, 'getaddrinfo', faux_getaddrinfo)
    with pytest.raises(CatalogueError):
        _verifier_adresse('https://piege.test/tarifs.csv')


def test_une_adresse_publique_passe(monkeypatch):
    """Le contrôle ne doit pas tout refuser : sans ce test, les précédents
    passeraient avec une fonction qui lève toujours."""
    import socket

    from apps.btp.catalogue_import import _verifier_adresse

    monkeypatch.setattr(socket, 'getaddrinfo', lambda *a, **k: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.216.34', 0))])
    assert _verifier_adresse('https://exemple.test/tarifs.csv') == \
        'exemple.test'


# ═══ LA LECTURE DU FICHIER ══════════════════════════════════════════════════

def test_un_csv_francais_se_lit(source):
    lignes = _lignes(source=source)
    assert len(lignes) == 3
    assert lignes[0]['Designation'] == 'Ciment CEM II 35 kg'


def test_le_separateur_se_devine_quand_il_n_est_pas_dit(source):
    source.delimiteur = ''
    lignes = _lignes(source=source)
    assert len(lignes) == 3


def test_un_csv_en_windows_1252_se_lit(source):
    """Les tarifs des négoces français sortent de tableurs Windows."""
    from apps.btp.catalogue_import import analyser

    texte = 'Reference;Designation\nCIM;Ciment prédosé à béton\n'
    lignes = analyser(texte.encode('cp1252'), source)
    assert lignes[0]['Designation'] == 'Ciment prédosé à béton'


def test_un_encodage_impose_qui_ne_marche_pas_est_dit(source):
    from apps.btp.catalogue_import import CatalogueError, analyser

    source.encodage = 'ascii'
    with pytest.raises(CatalogueError) as echec:
        analyser('Designation\nCiment prédosé\n'.encode('utf-8'), source)
    assert 'ascii' in str(echec.value)


def test_un_json_en_liste_se_lit(source):
    import json

    from apps.btp.catalogue_import import analyser

    source.format = 'json'
    charge = json.dumps([{'Designation': 'Ciment', 'Prix HT': '6.40'}])
    lignes = analyser(charge.encode('utf-8'), source)
    assert lignes[0]['Designation'] == 'Ciment'


def test_un_json_encapsule_dans_un_objet_se_lit(source):
    import json

    from apps.btp.catalogue_import import analyser

    source.format = 'json'
    charge = json.dumps({'produits': [{'Designation': 'Sable'}]})
    lignes = analyser(charge.encode('utf-8'), source)
    assert lignes[0]['Designation'] == 'Sable'


def test_un_json_ambigu_n_est_pas_devine(source):
    """Deux listes dans l'objet : on ne choisit pas au hasard."""
    import json

    from apps.btp.catalogue_import import CatalogueError, analyser

    source.format = 'json'
    charge = json.dumps({'a': [{'x': 1}], 'b': [{'y': 2}]})
    with pytest.raises(CatalogueError):
        analyser(charge.encode('utf-8'), source)


def test_un_excel_se_lit(source):
    from openpyxl import Workbook

    from apps.btp.catalogue_import import analyser

    source.format = 'excel'
    classeur = Workbook()
    feuille = classeur.active
    feuille.append(['Reference', 'Designation', 'Prix HT'])
    feuille.append(['CIM-35', 'Ciment CEM II', 6.40])
    tampon = io.BytesIO()
    classeur.save(tampon)

    lignes = analyser(tampon.getvalue(), source)
    assert lignes[0]['Designation'] == 'Ciment CEM II'
    assert lignes[0]['Prix HT'] == 6.40


def test_un_fichier_sans_entete_est_dit(source):
    from apps.btp.catalogue_import import CatalogueError, analyser

    with pytest.raises(CatalogueError):
        analyser(b'', source)


# ═══ LES PRIX ═══════════════════════════════════════════════════════════════

@pytest.mark.parametrize('brut,attendu', [
    ('6,40', Decimal('6.40')),
    ('1 234,56', Decimal('1234.56')),
    ('1.234,56', Decimal('1234.56')),
    ('1,234.56', Decimal('1234.56')),
    ('1234.56', Decimal('1234.56')),
    ('12,50 €', Decimal('12.50')),
    ('0', Decimal('0')),
    (18, Decimal('18')),
])
def test_tous_les_formats_de_prix_se_lisent(brut, attendu):
    from apps.btp.catalogue_import import _nombre

    assert _nombre(brut) == attendu


@pytest.mark.parametrize('brut', ['', None, 'abc', '-', '.'])
def test_un_prix_illisible_vaut_None_et_non_zero(brut):
    """Zéro est un prix, et un devis le facturerait. Un prix illisible doit
    laisser le champ tranquille, pas le mettre à zéro."""
    from apps.btp.catalogue_import import _nombre

    assert _nombre(brut) is None


# ═══ L'IMPORT : CRÉATION ════════════════════════════════════════════════════

def test_l_import_cree_les_articles(source):
    from apps.btp.catalogue_import import importer
    from apps.btp.models import Material

    rapport = importer(source, _lignes(source=source))

    assert rapport.crees == 3
    assert rapport.lignes_lues == 3
    ciment = Material.objects.get(reference='CIM-35')
    assert ciment.name == 'Ciment CEM II 35 kg'
    assert ciment.unit == 'sac'
    assert ciment.purchase_price == Decimal('6.4000')
    assert ciment.category == 'Gros oeuvre'
    assert ciment.company == source.company
    assert ciment.catalogue_source == source


def test_la_nature_par_defaut_s_applique(source):
    from apps.btp.catalogue_import import importer
    from apps.btp.models import Material

    source.nature_par_defaut = 'supply'
    importer(source, _lignes(source=source))
    assert all(a.kind == 'supply' for a in Material.objects.all())


def test_une_colonne_de_nature_est_lue(source):
    from apps.btp.catalogue_import import analyser, importer
    from apps.btp.models import Material

    source.colonnes = dict(source.colonnes, nature='Type')
    texte = ('Reference;Designation;Type\n'
             'A;Ciment;materiau\n'
             'B;Colle;fourniture\n'
             'C;Pose carrelage;action\n')
    importer(source, analyser(texte.encode('utf-8'), source))

    assert Material.objects.get(reference='A').kind == 'material'
    assert Material.objects.get(reference='B').kind == 'supply'
    assert Material.objects.get(reference='C').kind == 'action'


def test_une_ligne_sans_designation_est_ignoree_et_nommee(source):
    from apps.btp.catalogue_import import analyser, importer

    texte = 'Reference;Designation;Prix HT\nA;;6,40\nB;Sable;32\n'
    rapport = importer(source, analyser(texte.encode('utf-8'), source))

    assert rapport.crees == 1
    assert rapport.ignores == 1
    assert any('Ligne 2' in e for e in rapport.erreurs)


def test_sans_colonne_de_designation_l_import_refuse(source):
    from apps.btp.catalogue_import import CatalogueError, importer

    source.colonnes = {'reference': 'Reference'}
    with pytest.raises(CatalogueError) as echec:
        importer(source, _lignes(source=source))
    assert 'désignation' in str(echec.value)


# ═══ L'IMPORT : LA RÈGLE SUR LES PRIX ═══════════════════════════════════════

def test_le_prix_d_achat_suit_le_fournisseur(source):
    from apps.btp.catalogue_import import analyser, importer
    from apps.btp.models import Material

    importer(source, _lignes(source=source))
    ciment = Material.objects.get(reference='CIM-35')
    assert ciment.purchase_price == Decimal('6.4000')

    hausse = 'Reference;Designation;Unite;Prix HT;Famille\nCIM-35;Ciment CEM II 35 kg;sac;7,10;Gros oeuvre\n'
    importer(source, analyser(hausse.encode('utf-8'), source))

    ciment.refresh_from_db()
    assert ciment.purchase_price == Decimal('7.1000')


def test_le_prix_de_vente_n_est_JAMAIS_ecrase(source):
    """La propriété centrale. Une synchro nocturne ne doit pas pouvoir
    effacer la marge de l'exploitant."""
    from apps.btp.catalogue_import import analyser, importer
    from apps.btp.models import Material

    importer(source, _lignes(source=source))
    ciment = Material.objects.get(reference='CIM-35')
    ciment.sale_price = Decimal('9.90')
    ciment.save()

    # Le fournisseur publie maintenant un prix de vente conseille.
    source.colonnes = dict(source.colonnes, prix_vente='PV conseille')
    texte = ('Reference;Designation;Unite;Prix HT;Famille;PV conseille\n'
             'CIM-35;Ciment CEM II 35 kg;sac;6,40;Gros oeuvre;7,50\n')
    importer(source, analyser(texte.encode('utf-8'), source))

    ciment.refresh_from_db()
    assert ciment.sale_price == Decimal('9.9000')


def test_un_prix_de_vente_VIDE_se_remplit(source):
    """Ne jamais écraser ne veut pas dire ne jamais remplir : un article
    sans prix de vente poserait une ligne à 0 € dans un devis."""
    from apps.btp.catalogue_import import analyser, importer
    from apps.btp.models import Material

    source.colonnes = dict(source.colonnes, prix_vente='PV conseille')
    texte = ('Reference;Designation;Unite;Prix HT;Famille;PV conseille\n'
             'CIM-35;Ciment;sac;6,40;GO;7,50\n')
    importer(source, analyser(texte.encode('utf-8'), source))

    assert Material.objects.get(reference='CIM-35').sale_price == \
        Decimal('7.5000')


def test_un_prix_illisible_ne_met_pas_le_prix_a_zero(source):
    from apps.btp.catalogue_import import analyser, importer
    from apps.btp.models import Material

    importer(source, _lignes(source=source))
    texte = ('Reference;Designation;Unite;Prix HT;Famille\n'
             'CIM-35;Ciment CEM II 35 kg;sac;sur demande;Gros oeuvre\n')
    importer(source, analyser(texte.encode('utf-8'), source))

    assert Material.objects.get(reference='CIM-35').purchase_price == \
        Decimal('6.4000')


# ═══ L'IMPORT : LE RAPPROCHEMENT ════════════════════════════════════════════

def test_un_second_import_ne_duplique_rien(source):
    from apps.btp.catalogue_import import importer
    from apps.btp.models import Material

    importer(source, _lignes(source=source))
    rapport = importer(source, _lignes(source=source))

    assert Material.objects.count() == 3
    assert rapport.crees == 0
    assert rapport.inchanges == 3


def test_le_compteur_distingue_modifie_et_inchange(source):
    """« 400 inchangés, 3 modifiés » rassure ; « 0 inchangé, 403 modifiés »
    veut dire que le fichier ou la correspondance a changé."""
    from apps.btp.catalogue_import import analyser, importer

    importer(source, _lignes(source=source))
    texte = ('Reference;Designation;Unite;Prix HT;Famille\n'
             'CIM-35;Ciment CEM II 35 kg;sac;7,10;Gros oeuvre\n'
             'SAB-04;Sable 0/4 en vrac;t;32,50;Gros oeuvre\n')
    rapport = importer(source, analyser(texte.encode('utf-8'), source))

    assert rapport.mis_a_jour == 1
    assert rapport.inchanges == 1


def test_sans_reference_le_rapprochement_se_fait_sur_le_nom(source):
    from apps.btp.catalogue_import import analyser, importer
    from apps.btp.models import Material

    source.colonnes = {'nom': 'Designation', 'prix_achat': 'Prix HT'}
    texte = 'Designation;Prix HT\nCiment CEM II;6,40\n'
    importer(source, analyser(texte.encode('utf-8'), source))
    importer(source, analyser(texte.encode('utf-8'), source))

    assert Material.objects.filter(name='Ciment CEM II').count() == 1


def test_l_import_ne_touche_pas_le_catalogue_d_une_autre_entreprise(
        source, autre_entreprise):
    from apps.btp.catalogue_import import importer
    from apps.btp.models import Material

    voisin = Material.objects.create(
        company=autre_entreprise, reference='CIM-35', name='Autre ciment',
        purchase_price=Decimal('99'))

    importer(source, _lignes(source=source))

    voisin.refresh_from_db()
    assert voisin.name == 'Autre ciment'
    assert voisin.purchase_price == Decimal('99.0000')
    assert Material.objects.filter(company=source.company).count() == 3


# ═══ L'ESSAI À BLANC ════════════════════════════════════════════════════════

def test_l_essai_a_blanc_compte_sans_rien_ecrire(source):
    """La seule façon de vérifier une correspondance de colonnes sans
    risque sur un catalogue de plusieurs centaines d'articles."""
    from apps.btp.catalogue_import import importer
    from apps.btp.models import Material

    rapport = importer(source, _lignes(source=source), a_blanc=True)

    assert rapport.crees == 3
    assert Material.objects.count() == 0


def test_l_essai_a_blanc_voit_les_modifications(source):
    from apps.btp.catalogue_import import analyser, importer
    from apps.btp.models import Material

    importer(source, _lignes(source=source))
    texte = ('Reference;Designation;Unite;Prix HT;Famille\n'
             'CIM-35;Ciment CEM II 35 kg;sac;7,10;Gros oeuvre\n')
    rapport = importer(source, analyser(texte.encode('utf-8'), source),
                       a_blanc=True)

    assert rapport.mis_a_jour == 1
    assert Material.objects.get(reference='CIM-35').purchase_price == \
        Decimal('6.4000')


# ═══ LE JOURNAL ═════════════════════════════════════════════════════════════

def test_un_echec_est_journalise(source, monkeypatch):
    """Une source qui ne répond plus depuis trois semaines doit se voir : un
    import qui échoue en silence est pire qu'un import absent."""
    from apps.btp import catalogue_import
    from apps.btp.models import CatalogueImport

    def tombe(*args, **kwargs):
        raise catalogue_import.CatalogueError('serveur injoignable')

    monkeypatch.setattr(catalogue_import, 'telecharger', tombe)
    journal = catalogue_import.executer(source)

    assert journal.statut == 'echec'
    assert 'injoignable' in journal.message
    assert CatalogueImport.objects.count() == 1


def test_un_essai_a_blanc_ne_marque_pas_la_source_comme_executee(
        source, monkeypatch):
    """Sinon l'import programmé croirait la source à jour et attendrait le
    prochain intervalle."""
    from apps.btp import catalogue_import

    monkeypatch.setattr(catalogue_import, 'telecharger',
                        lambda s, **k: CSV_TARIF.encode('utf-8'))
    catalogue_import.executer(source, a_blanc=True)

    source.refresh_from_db()
    assert source.derniere_execution is None


def test_un_import_reel_marque_la_source(source, monkeypatch):
    from apps.btp import catalogue_import

    monkeypatch.setattr(catalogue_import, 'telecharger',
                        lambda s, **k: CSV_TARIF.encode('utf-8'))
    catalogue_import.executer(source)

    source.refresh_from_db()
    assert source.derniere_execution is not None


def test_les_erreurs_sont_bornees(source):
    """Un fichier entièrement mal mappé produirait des milliers d'erreurs
    identiques, illisibles et lourdes à stocker."""
    from apps.btp.catalogue_import import analyser, importer

    lignes = 'Reference;Designation\n' + ''.join(
        f'REF{n};\n' for n in range(200))
    rapport = importer(source, analyser(lignes.encode('utf-8'), source))

    assert rapport.ignores == 200
    assert len(rapport.erreurs) <= 50


# ═══ LES ARTICLES DISPARUS ══════════════════════════════════════════════════

def test_un_article_disparu_est_signale_et_non_supprime(source, monkeypatch):
    """Il peut figurer dans un devis déjà envoyé."""
    from apps.btp import catalogue_import
    from apps.btp.models import Material

    monkeypatch.setattr(catalogue_import, 'telecharger',
                        lambda s, **k: CSV_TARIF.encode('utf-8'))
    catalogue_import.executer(source)
    assert Material.objects.count() == 3

    reduit = ('Reference;Designation;Unite;Prix HT;Famille\n'
              'CIM-35;Ciment CEM II 35 kg;sac;6,40;Gros oeuvre\n')
    monkeypatch.setattr(catalogue_import, 'telecharger',
                        lambda s, **k: reduit.encode('utf-8'))

    disparus = catalogue_import.articles_disparus(source)

    assert {a.reference for a in disparus} == {'SAB-04', 'BA13'}
    assert Material.objects.count() == 3


# ═══ LES ÉCRANS ═════════════════════════════════════════════════════════════

def test_la_liste_des_sources_s_affiche(connecte, source):
    from django.urls import reverse

    corps = connecte.get(
        reverse('btp:catalogue_source_list')).content.decode()
    assert 'Negoce' in corps


def test_la_liste_ignore_les_sources_d_une_autre_entreprise(
        connecte, source, autre_entreprise):
    from django.urls import reverse

    from apps.btp.models import CatalogueSource

    CatalogueSource.objects.create(
        company=autre_entreprise, name='Source confidentielle',
        url='https://x.test/a.csv', colonnes={'nom': 'N'})

    corps = connecte.get(
        reverse('btp:catalogue_source_list')).content.decode()
    assert 'Negoce' in corps
    assert 'confidentielle' not in corps


def test_une_source_d_une_autre_entreprise_est_introuvable(
        connecte, autre_entreprise):
    from django.urls import reverse

    from apps.btp.models import CatalogueSource

    etrangere = CatalogueSource.objects.create(
        company=autre_entreprise, name='Ailleurs',
        url='https://x.test/a.csv', colonnes={'nom': 'N'})

    reponse = connecte.get(
        reverse('btp:catalogue_source_detail', args=[etrangere.pk]))
    assert reponse.status_code == 404


def test_le_formulaire_exige_la_colonne_de_designation(entreprise):
    from apps.btp.forms_catalogue import CatalogueSourceForm

    form = CatalogueSourceForm({
        'name': 'Test', 'url': 'https://exemple.test/a.csv', 'format': 'csv',
        'delimiteur': ';', 'encodage': 'auto',
        'nature_par_defaut': 'material', 'intervalle_minutes': '1440',
        'colonne_reference': 'Ref',
    }, company=entreprise)

    assert not form.is_valid()
    assert 'colonne_nom' in form.errors


def test_le_formulaire_assemble_la_correspondance(entreprise):
    from apps.btp.forms_catalogue import CatalogueSourceForm

    form = CatalogueSourceForm({
        'name': 'Test', 'url': 'https://exemple.test/a.csv', 'format': 'csv',
        'delimiteur': ';', 'encodage': 'auto',
        'nature_par_defaut': 'material', 'intervalle_minutes': '1440',
        'colonne_nom': 'Designation', 'colonne_reference': 'Ref',
        'colonne_prix_achat': '  Prix HT  ',
    }, company=entreprise)

    assert form.is_valid(), form.errors
    form.instance.company = entreprise
    source = form.save()
    assert source.colonnes == {
        'nom': 'Designation', 'reference': 'Ref', 'prix_achat': 'Prix HT'}


def test_l_import_depuis_l_ecran_refuse_un_GET(connecte, source):
    from django.urls import reverse

    for nom in ('btp:catalogue_source_run', 'btp:catalogue_source_delete',
                'btp:catalogue_source_disparus'):
        reponse = connecte.get(reverse(nom, args=[source.pk]))
        assert reponse.status_code == 405, nom


def test_supprimer_la_source_garde_les_articles(connecte, source,
                                                monkeypatch):
    from django.urls import reverse

    from apps.btp import catalogue_import
    from apps.btp.models import CatalogueSource, Material

    monkeypatch.setattr(catalogue_import, 'telecharger',
                        lambda s, **k: CSV_TARIF.encode('utf-8'))
    catalogue_import.executer(source)
    assert Material.objects.count() == 3

    connecte.post(reverse('btp:catalogue_source_delete', args=[source.pk]))

    assert not CatalogueSource.objects.filter(pk=source.pk).exists()
    assert Material.objects.count() == 3
    assert Material.objects.filter(catalogue_source__isnull=True).count() == 3


def test_les_sources_figurent_dans_le_menu():
    from apps.core.context_processors import NAV_MODULES

    groupe = next(m for m in NAV_MODULES if m['id'] == 'btp')
    cibles = [e['url_name'] for e in groupe['children']]
    assert 'btp:catalogue_source_list' in cibles


# ═══ LA COMMANDE PROGRAMMÉE ═════════════════════════════════════════════════

def test_la_commande_respecte_l_intervalle(source, monkeypatch):
    from datetime import timedelta

    from django.core.management import call_command
    from django.utils import timezone

    from apps.btp import catalogue_import
    from apps.btp.models import CatalogueImport

    monkeypatch.setattr(catalogue_import, 'telecharger',
                        lambda s, **k: CSV_TARIF.encode('utf-8'))

    source.derniere_execution = timezone.now() - timedelta(minutes=10)
    source.intervalle_minutes = 1440
    source.save()

    call_command('importer_catalogues')
    assert CatalogueImport.objects.count() == 0

    call_command('importer_catalogues', '--forcer')
    assert CatalogueImport.objects.count() == 1


def test_la_commande_ignore_une_source_inactive(source, monkeypatch):
    from django.core.management import call_command

    from apps.btp import catalogue_import
    from apps.btp.models import CatalogueImport

    monkeypatch.setattr(catalogue_import, 'telecharger',
                        lambda s, **k: CSV_TARIF.encode('utf-8'))
    source.is_active = False
    source.save()

    call_command('importer_catalogues', '--forcer')
    assert CatalogueImport.objects.count() == 0


def test_une_source_en_panne_n_arrete_pas_les_autres(entreprise,
                                                      monkeypatch):
    """Un fournisseur dont le serveur est en panne ne doit pas priver
    l'exploitant de ses cinq autres tarifs."""
    from django.core.management import call_command

    from apps.btp import catalogue_import
    from apps.btp.models import CatalogueSource, Material

    cassee = CatalogueSource.objects.create(
        company=entreprise, name='A-cassee', url='https://a.test/a.csv',
        colonnes={'nom': 'Designation'})
    bonne = CatalogueSource.objects.create(
        company=entreprise, name='B-bonne', url='https://b.test/b.csv',
        delimiteur=';',
        colonnes={'nom': 'Designation', 'reference': 'Reference'})

    def selon_la_source(s, **k):
        if s.pk == cassee.pk:
            raise RuntimeError('panne imprevue')
        return CSV_TARIF.encode('utf-8')

    monkeypatch.setattr(catalogue_import, 'telecharger', selon_la_source)
    call_command('importer_catalogues', '--forcer')

    assert Material.objects.filter(catalogue_source=bonne).count() == 3


# ═══ LE TÉLÉCHARGEMENT LUI-MÊME ═════════════════════════════════════════════
#
# La revérification des REDIRECTIONS est le contournement le plus évident :
# une adresse publique qui répond « 302 vers http://127.0.0.1 » ferait lire
# le réseau interne par un import dont l'adresse configurée paraît
# irréprochable. Les tests qui suivent éprouvent ce chemin, et non seulement
# le contrôle d'adresse pris isolément.


class _Reponse:
    """Une réponse HTTP minimale, telle que requests la présente."""

    def __init__(self, code=200, entetes=None, corps=b'', redirection=False):
        self.status_code = code
        self.headers = entetes or {}
        self._corps = corps
        self.is_redirect = redirection
        self.is_permanent_redirect = False
        self.ferme = False

    def iter_content(self, chunk_size=65536):
        for debut in range(0, len(self._corps), chunk_size):
            yield self._corps[debut:debut + chunk_size]

    def close(self):
        self.ferme = True


class _Session:
    """Enregistre les adresses demandées, et rend les réponses prévues."""

    def __init__(self, reponses):
        self.reponses = list(reponses)
        self.demandees = []

    def get(self, url, **kwargs):
        self.demandees.append(url)
        return self.reponses.pop(0)


@pytest.fixture
def adresses_publiques(monkeypatch):
    """Tout nom résout vers une adresse publique, sauf « interne.test »."""
    import socket

    def faux(hote, port, *args, **kwargs):
        ip = '127.0.0.1' if hote == 'interne.test' else '93.184.216.34'
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (ip, 0))]

    monkeypatch.setattr(socket, 'getaddrinfo', faux)


def test_le_telechargement_rend_les_octets(source, adresses_publiques):
    from apps.btp.catalogue_import import telecharger

    session = _Session([_Reponse(corps=CSV_TARIF.encode('utf-8'))])
    octets = telecharger(source, session=session)

    assert octets == CSV_TARIF.encode('utf-8')
    assert session.demandees == [source.url]


def test_une_redirection_vers_le_reseau_interne_est_REFUSEE(
        source, adresses_publiques):
    """Le contournement le plus évident, et celui qu'on oublie le plus
    souvent : l'adresse configurée est publique, la destination ne l'est
    pas."""
    from apps.btp.catalogue_import import CatalogueError, telecharger

    session = _Session([
        _Reponse(code=302, redirection=True,
                 entetes={'Location': 'http://interne.test/secret'}),
        _Reponse(corps=b'jamais atteint'),
    ])

    with pytest.raises(CatalogueError) as echec:
        telecharger(source, session=session)

    assert 'interne' in str(echec.value)
    # La seconde requete n'a PAS ete faite.
    assert len(session.demandees) == 1


def test_une_redirection_vers_une_adresse_publique_est_suivie(
        source, adresses_publiques):
    """Le contrôle ne doit pas tout refuser : un tarif derrière une
    redirection légitime doit s'importer."""
    from apps.btp.catalogue_import import telecharger

    session = _Session([
        _Reponse(code=302, redirection=True,
                 entetes={'Location': 'https://cdn.exemple.test/t.csv'}),
        _Reponse(corps=CSV_TARIF.encode('utf-8')),
    ])

    octets = telecharger(source, session=session)
    assert octets == CSV_TARIF.encode('utf-8')
    assert session.demandees[-1] == 'https://cdn.exemple.test/t.csv'


def test_une_boucle_de_redirections_s_arrete(source, adresses_publiques):
    from apps.btp.catalogue_import import (
        REDIRECTIONS_MAX, CatalogueError, telecharger,
    )

    session = _Session([
        _Reponse(code=302, redirection=True,
                 entetes={'Location': 'https://exemple.test/encore'})
        for _ in range(REDIRECTIONS_MAX + 2)
    ])

    with pytest.raises(CatalogueError) as echec:
        telecharger(source, session=session)
    assert 'redirection' in str(echec.value).lower()


def test_une_redirection_sans_destination_est_dite(source,
                                                    adresses_publiques):
    from apps.btp.catalogue_import import CatalogueError, telecharger

    session = _Session([_Reponse(code=302, redirection=True, entetes={})])
    with pytest.raises(CatalogueError):
        telecharger(source, session=session)


@pytest.mark.parametrize('code', [401, 403, 404, 500, 503])
def test_un_code_d_erreur_est_rapporte(source, adresses_publiques, code):
    from apps.btp.catalogue_import import CatalogueError, telecharger

    session = _Session([_Reponse(code=code)])
    with pytest.raises(CatalogueError) as echec:
        telecharger(source, session=session)
    assert str(code) in str(echec.value)


def test_un_fichier_trop_volumineux_est_coupe(source, adresses_publiques,
                                              monkeypatch):
    """Un fichier de 2 Go ne doit pas tenir dans la mémoire du serveur."""
    from apps.btp import catalogue_import

    monkeypatch.setattr(catalogue_import, 'TAILLE_MAX', 1024)
    session = _Session([_Reponse(corps=b'x' * 4096)])

    with pytest.raises(catalogue_import.CatalogueError) as echec:
        catalogue_import.telecharger(source, session=session)
    assert 'volumineux' in str(echec.value)


def test_un_fichier_vide_est_dit(source, adresses_publiques):
    from apps.btp.catalogue_import import CatalogueError, telecharger

    session = _Session([_Reponse(corps=b'')])
    with pytest.raises(CatalogueError) as echec:
        telecharger(source, session=session)
    assert 'vide' in str(echec.value)
