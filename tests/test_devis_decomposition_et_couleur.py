"""Devis : taux de TVA, décomposition du chiffrage, couleur et multiligne.

Cinq ajouts, et chacun a sa propriété à tenir :

- **Le taux de TVA est LU sur les lignes, jamais saisi.** C'est le taux
  *appliqué* qui est demandé ; un champ saisi à part pourrait contredire le
  calcul, et c'est le document remis au client qui mentirait. Plusieurs taux
  sur un devis sont courants en BTP (10 % rénovation, 20 % neuf) : ils sont
  alors tous nommés, car n'en afficher qu'un rendrait le devis inexact.

- **Les trois coûts n'entrent pas dans les totaux.** Ils expliquent comment
  le prix est composé, ils ne le fabriquent pas. Les additionner doublerait
  le devis.

- **Les tâches se remplissent du HAUT du cadre vers le bas.** Centrées
  verticalement, la liste se déplacerait à chaque tâche ajoutée.

- **La couleur arrive jusqu'au PDF**, vérifiée dans le flux décompressé et
  non supposée.

- **La couleur et le multiligne voyagent avec les cadres.** L'éditeur visuel
  REMPLACE tous les cadres à l'enregistrement : les laisser au seul
  formulaire les ferait effacer au premier passage par l'éditeur.
"""

import io
import json
import re
from decimal import Decimal

import pytest
from django.core.files.base import ContentFile
from django.urls import reverse

pytestmark = pytest.mark.django_db


# ── Terrain ─────────────────────────────────────────────────────────────────

def _pdf_vierge(pages=1, largeur=595, hauteur=842):
    from reportlab.pdfgen import canvas

    tampon = io.BytesIO()
    feuille = canvas.Canvas(tampon, pagesize=(largeur, hauteur))
    for _ in range(pages):
        feuille.setFont('Helvetica-Bold', 16)
        feuille.drawString(40, hauteur - 50, 'ENTREPRISE DUPONT')
        feuille.showPage()
    feuille.save()
    tampon.seek(0)
    return tampon.getvalue()


def _flux_du_pdf(octets_ou_tampon):
    """Le contenu de la première page, DÉCOMPRESSÉ.

    reportlab compresse le flux : chercher « 1 1 1 rg » dans les octets bruts
    ne trouve jamais rien, et un test écrit ainsi passerait pour de mauvaises
    raisons — vérifié avant d'écrire ces tests.
    """
    from pypdf import PdfReader

    if isinstance(octets_ou_tampon, bytes):
        octets_ou_tampon = io.BytesIO(octets_ou_tampon)
    page = PdfReader(octets_ou_tampon).pages[0]
    return page.get_contents().get_data().decode('latin-1')


class Cadre:
    """Un cadre en mémoire : ces fonctions ne touchent pas la base."""

    def __init__(self, **kw):
        defauts = dict(cle='objet', page=1, x=50, y=500, largeur=200,
                       hauteur=20, taille=10, gras=False, alignement='left',
                       couleur='#000000', multiligne=False, prefixe='',
                       suffixe='')
        defauts.update(kw)
        self.__dict__.update(defauts)


@pytest.fixture
def entreprise(db):
    from apps.core.models import Company
    return Company.objects.create(name='Dupont SA', slug='dupont-sa')


@pytest.fixture
def modele(entreprise):
    from apps.sales.models import QuoteTemplate
    objet = QuoteTemplate.objects.create(
        company=entreprise, name='Devis standard', is_default=True)
    objet.pdf.save('modele.pdf', ContentFile(_pdf_vierge()), save=True)
    return objet


@pytest.fixture
def devis(entreprise):
    from apps.crm.models import Customer
    from apps.sales.models import Quote

    client = Customer.objects.create(company=entreprise, name='Client Test')
    return Quote.objects.create(
        company=entreprise, number='DEV-0042', customer=client,
        total_ht=Decimal('1000'), total_tva=Decimal('200'),
        total_ttc=Decimal('1200'))


@pytest.fixture
def connecte(client, entreprise, django_user_model):
    user = django_user_model.objects.create_user(
        username='patron', password='motdepasse-test')
    user.profile.companies.add(entreprise)
    user.profile.current_company = entreprise
    user.profile.save()
    client.force_login(user)
    return client


# ═══ LE TAUX DE TVA ═════════════════════════════════════════════════════════

@pytest.mark.parametrize('valeur,attendu', [
    (20, '20 %'),
    ('20.00', '20 %'),
    ('10.00', '10 %'),
    ('100', '100 %'),
    ('5.50', '5,5 %'),
    ('2.10', '2,1 %'),
    (0, '0 %'),
])
def test_le_taux_est_formate_sans_decimale_inutile(valeur, attendu):
    """Le rognage des zéros ne doit porter QUE sur la partie décimale.

    Appliqué sans condition, il transformait « 20 » en « 2 » et « 10 » en
    « 1 » : un taux faux imprimé sur un devis. Attrapé à la vérification,
    et verrouillé ici.
    """
    from apps.sales.quote_pdf import _format_taux

    assert _format_taux(valeur) == attendu


def test_un_seul_taux_est_lu_sur_les_lignes(devis):
    from apps.sales.models import QuoteLine
    from apps.sales.quote_pdf import valeurs_du_devis

    QuoteLine.objects.create(quote=devis, description='Carrelage', quantity=1,
                             unit_price=Decimal('500'),
                             vat_rate=Decimal('10'))
    QuoteLine.objects.create(quote=devis, description='Plinthes', quantity=1,
                             unit_price=Decimal('100'),
                             vat_rate=Decimal('10'))

    assert valeurs_du_devis(devis)['taux_tva'] == '10 %'


def test_plusieurs_taux_sont_tous_nommes(devis):
    """10 % en rénovation et 20 % en neuf sur un même devis est courant.
    N'en afficher qu'un ferait du devis une pièce inexacte."""
    from apps.sales.models import QuoteLine
    from apps.sales.quote_pdf import valeurs_du_devis

    QuoteLine.objects.create(quote=devis, description='Rénovation',
                             quantity=1, unit_price=Decimal('500'),
                             vat_rate=Decimal('10'))
    QuoteLine.objects.create(quote=devis, description='Extension neuve',
                             quantity=1, unit_price=Decimal('500'),
                             vat_rate=Decimal('20'))

    assert valeurs_du_devis(devis)['taux_tva'] == '10 % / 20 %'


def test_les_lignes_de_soustotal_et_de_texte_ne_comptent_pas(devis):
    """Elles ne portent pas de TVA : leur taux par défaut ferait apparaître
    un 20 % imaginaire sur un devis entièrement à 10 %."""
    from apps.sales.models import QuoteLine
    from apps.sales.quote_pdf import valeurs_du_devis

    QuoteLine.objects.create(quote=devis, description='Travaux', quantity=1,
                             unit_price=Decimal('500'),
                             vat_rate=Decimal('10'))
    QuoteLine.objects.create(quote=devis, description='Sous-total lot 1',
                             line_type='subtotal', vat_rate=Decimal('20'))
    QuoteLine.objects.create(quote=devis, description='Mention libre',
                             line_type='text', vat_rate=Decimal('20'))

    assert valeurs_du_devis(devis)['taux_tva'] == '10 %'


def test_l_apercu_du_modele_ne_tombe_pas_en_panne(entreprise):
    """devis_exemple() n'est PAS enregistré : interroger ses lignes lève
    « instance needs to have a primary key » et ferait tomber l'écran qui
    sert justement à régler les cadres. Constaté avant livraison."""
    from apps.sales.quote_pdf import devis_exemple, valeurs_du_devis

    valeurs = valeurs_du_devis(devis_exemple(entreprise))
    # 2 480 / 12 400 = 20 %
    assert valeurs['taux_tva'] == '20 %'


def test_sans_ligne_le_taux_se_deduit_des_totaux(devis):
    from apps.sales.quote_pdf import valeurs_du_devis

    assert valeurs_du_devis(devis)['taux_tva'] == '20 %'


def test_sans_rien_le_taux_reste_vide(entreprise):
    """Un cadre sans valeur n'imprime rien — mieux qu'un « 0 % » inventé."""
    from apps.crm.models import Customer
    from apps.sales.models import Quote
    from apps.sales.quote_pdf import valeurs_du_devis

    client = Customer.objects.create(company=entreprise, name='Vide')
    vide = Quote.objects.create(company=entreprise, customer=client)
    assert valeurs_du_devis(vide)['taux_tva'] == ''


# ═══ LA DÉCOMPOSITION DU CHIFFRAGE ══════════════════════════════════════════

def test_les_trois_couts_sont_formates_a_la_francaise(devis):
    from apps.sales.quote_pdf import valeurs_du_devis

    devis.cout_materiels = Decimal('5200')
    devis.cout_fournitures = Decimal('1450.50')
    devis.cout_main_oeuvre = Decimal('12750')
    devis.save()

    valeurs = valeurs_du_devis(devis)
    assert valeurs['cout_materiels'] == '5 200,00'
    assert valeurs['cout_fournitures'] == '1 450,50'
    assert valeurs['cout_main_oeuvre'] == '12 750,00'


def test_un_cout_a_zero_n_imprime_rien(devis):
    """« 0,00 € » de matériel sur un devis de maçonnerie se lit comme une
    erreur, pas comme un champ non renseigné."""
    from apps.sales.quote_pdf import valeurs_du_devis

    valeurs = valeurs_du_devis(devis)
    assert valeurs['cout_materiels'] == ''
    assert valeurs['cout_fournitures'] == ''
    assert valeurs['cout_main_oeuvre'] == ''


def test_les_couts_n_entrent_PAS_dans_les_totaux(devis):
    """La garantie qui évite de doubler un devis : le total vient des
    lignes, ces montants ne font que l'expliquer."""
    from apps.sales.models import QuoteLine

    QuoteLine.objects.create(quote=devis, description='Travaux', quantity=1,
                             unit_price=Decimal('1000'),
                             vat_rate=Decimal('20'))
    devis.cout_materiels = Decimal('5200')
    devis.cout_fournitures = Decimal('1450')
    devis.cout_main_oeuvre = Decimal('12750')
    devis.save()

    devis.calculate_totals()
    devis.refresh_from_db()
    assert devis.total_ht == Decimal('1000.00')
    assert devis.total_ttc == Decimal('1200.00')


def test_le_formulaire_de_devis_offre_les_quatre_saisies(connecte):
    corps = connecte.get(reverse('sales:quote_create')).content.decode()
    for nom in ('cout_materiels', 'cout_fournitures', 'cout_main_oeuvre',
                'taches_principales'):
        assert f'name="{nom}"' in corps, nom


# ═══ LES TÂCHES, SUR PLUSIEURS LIGNES ═══════════════════════════════════════

def test_les_retours_a_la_ligne_saisis_sont_respectes():
    """Recoller une liste de tâches en un paragraphe perdrait
    l'information : une tâche est une ligne."""
    from apps.sales.quote_pdf import _page_de_texte

    cadre = Cadre(cle='taches_principales', multiligne=True, largeur=300,
                  hauteur=80, taille=9, y=500)
    flux = _flux_du_pdf(_page_de_texte(
        [cadre], {'taches_principales': 'Depose\nRagreage\nPose'}, 595, 842))

    for tache in ('Depose', 'Ragreage', 'Pose'):
        assert f'({tache}) Tj' in flux, tache


def test_une_ligne_trop_longue_est_coupee_a_la_largeur_du_cadre():
    from apps.sales.quote_pdf import _page_de_texte

    cadre = Cadre(cle='taches_principales', multiligne=True, largeur=110,
                  hauteur=80, taille=9, y=500)
    texte = 'Depose de l ancien revetement de sol du rez de chaussee'
    flux = _flux_du_pdf(_page_de_texte(
        [cadre], {'taches_principales': texte}, 595, 842))

    # Plus d'une ligne ecrite, et aucune ne contient le texte entier.
    assert flux.count(') Tj') >= 3
    assert f'({texte}) Tj' not in flux


def test_le_bloc_se_remplit_du_haut_vers_le_bas():
    """Du haut, et non centré : une liste de tâches doit commencer à un
    endroit prévisible, sous le coût de main-d'œuvre. Centrée, elle
    remonterait à chaque tâche ajoutée."""
    import re

    from apps.sales.quote_pdf import INTERLIGNE, _page_de_texte

    cadre = Cadre(cle='taches_principales', multiligne=True, largeur=300,
                  hauteur=80, taille=10, y=500)
    flux = _flux_du_pdf(_page_de_texte(
        [cadre], {'taches_principales': 'Une\nDeux\nTrois'}, 595, 842))

    ordonnees = [float(v) for v in re.findall(r'1 0 0 1 50 ([\d.]+) Tm', flux)]
    assert len(ordonnees) == 3
    # Decroissantes : on descend.
    assert ordonnees == sorted(ordonnees, reverse=True)
    # La premiere est sous le haut du cadre (500 + 80), d'une majuscule.
    assert ordonnees[0] == pytest.approx(580 - 10, abs=0.01)
    assert ordonnees[0] - ordonnees[1] == pytest.approx(10 * INTERLIGNE,
                                                        abs=0.01)


def test_un_bloc_trop_haut_est_reduit_pour_tenir():
    from apps.sales.quote_pdf import _page_de_texte

    cadre = Cadre(cle='taches_principales', multiligne=True, largeur=300,
                  hauteur=30, taille=12, y=500)
    texte = '\n'.join(f'Tache numero {n}' for n in range(1, 9))
    flux = _flux_du_pdf(_page_de_texte(
        [cadre], {'taches_principales': texte}, 595, 842))

    # reportlab ecrit toujours « /F1 12 Tf » en preambule du flux, avant
    # tout champ : chercher « 12 Tf » dans l'ensemble le trouvait la, et
    # l'assertion echouait alors que la reduction avait bien eu lieu.
    # On ne regarde donc que ce qui suit l'operateur de couleur.
    apres_couleur = flux.split('rg', 1)[1]
    tailles = [int(t) for t in re.findall(r'/F\d+ (\d+) Tf', apres_couleur)]
    assert tailles, 'aucune taille de police ecrite pour le champ'
    assert max(tailles) < 12, tailles


def test_l_apostrophe_typographique_s_imprime():
    """U+2019 appartient à WinAnsi, contrairement à U+202F qui s'imprimait
    en carré noir — leçon déjà payée sur le séparateur de milliers."""
    from apps.sales.quote_pdf import _page_de_texte

    cadre = Cadre(cle='taches_principales', multiligne=True, largeur=300,
                  hauteur=40, taille=10, y=500)
    flux = _flux_du_pdf(_page_de_texte(
        [cadre], {'taches_principales': 'Depose de l’ancien sol'},
        595, 842))

    # Un glyphe manquant couperait le texte en plusieurs morceaux, ou
    # ferait apparaitre un carre de substitution. Une seule ecriture, et
    # l'apostrophe presente dans le flux en encodage WinAnsi (0x92).
    assert flux.count(') Tj') == 1
    # reportlab echappe l'octet en octal dans le flux : « \222 » vaut 0x92,
    # qui EST la position de l'apostrophe typographique dans WinAnsi. Sa
    # presence prouve que le glyphe existe, la ou U+202F donnait un carre.
    assert chr(92) + '222' in flux


def test_sans_multiligne_le_texte_reste_sur_une_ligne():
    """Le comportement d'avant est conservé : seul le cadre coché change."""
    from apps.sales.quote_pdf import _page_de_texte

    cadre = Cadre(cle='objet', multiligne=False, largeur=300, hauteur=20,
                  taille=10, y=500)
    flux = _flux_du_pdf(_page_de_texte(
        [cadre], {'objet': 'Un texte assez long pour tenir sur une ligne'},
        595, 842))

    assert flux.count(') Tj') == 1


# ═══ LA COULEUR DU TEXTE ════════════════════════════════════════════════════

@pytest.mark.parametrize('valeur,attendu', [
    ('#FFFFFF', (1.0, 1.0, 1.0)),
    ('#000000', (0.0, 0.0, 0.0)),
    ('FFFFFF', (1.0, 1.0, 1.0)),
    (None, (0.0, 0.0, 0.0)),
    ('', (0.0, 0.0, 0.0)),
    ('#zzzzzz', (0.0, 0.0, 0.0)),
    ('#ABC', (0.0, 0.0, 0.0)),
])
def test_la_couleur_se_convertit_et_tolere_l_absurde(valeur, attendu):
    """Un réglage douteux ne doit pas faire échouer la génération d'un
    devis : on retombe sur le noir."""
    from apps.sales.quote_pdf import _couleur

    assert _couleur(Cadre(couleur=valeur)) == attendu


def test_le_blanc_arrive_jusque_dans_le_PDF():
    """Vérifié dans le flux décompressé, et non supposé."""
    from apps.sales.quote_pdf import _page_de_texte

    cadre = Cadre(cle='numero_devis', couleur='#FFFFFF', taille=12)
    flux = _flux_du_pdf(_page_de_texte(
        [cadre], {'numero_devis': 'DEV-0042'}, 595, 842))

    assert '1 1 1 rg' in flux
    assert '(DEV-0042) Tj' in flux


def test_le_noir_reste_la_valeur_par_defaut():
    from apps.sales.models import QuoteTemplateField

    assert QuoteTemplateField._meta.get_field('couleur').default == '#000000'


def test_deux_cadres_de_couleurs_differentes_ne_se_contaminent_pas():
    """reportlab garde la couleur courante : sans remise à jour avant chaque
    cadre, le second héritetrait de la couleur du premier."""
    from apps.sales.quote_pdf import _page_de_texte

    flux = _flux_du_pdf(_page_de_texte([
        Cadre(cle='numero_devis', couleur='#FFFFFF', y=700),
        Cadre(cle='objet', couleur='#000000', y=600),
    ], {'numero_devis': 'DEV-1', 'objet': 'Objet'}, 595, 842))

    assert '1 1 1 rg' in flux
    assert '0 0 0 rg' in flux


# ═══ LA MIGRATION DE DONNÉES ════════════════════════════════════════════════

def test_la_migration_passe_en_blanc_les_trois_valeurs_demandees(modele):
    from django.apps import apps as registre

    # Le module ne peut pas s'importer par « from ... import » : son nom
    # commence par un chiffre, ce qui n'est pas un identifiant Python.
    module = __import__(
        'apps.sales.migrations.0007_cadres_en_blanc_numero_date_ttc',
        fromlist=['passer_en_blanc'])
    from apps.sales.models import QuoteTemplateField

    for cle in ('numero_devis', 'date', 'total_ttc', 'nom_client'):
        QuoteTemplateField.objects.create(
            template=modele, cle=cle, x=10, y=10, couleur='#000000')

    module.passer_en_blanc(registre, None)

    couleurs = dict(QuoteTemplateField.objects
                    .filter(template=modele)
                    .values_list('cle', 'couleur'))
    assert couleurs['numero_devis'] == '#FFFFFF'
    assert couleurs['date'] == '#FFFFFF'
    assert couleurs['total_ttc'] == '#FFFFFF'
    # Les autres valeurs ne sont pas concernees.
    assert couleurs['nom_client'] == '#000000'


def test_la_migration_respecte_une_couleur_choisie_a_la_main(modele):
    """Écraser un choix délibéré au nom d'un réglage global est précisément
    ce qu'une migration de données ne doit pas faire."""
    from django.apps import apps as registre

    module = __import__(
        'apps.sales.migrations.0007_cadres_en_blanc_numero_date_ttc',
        fromlist=['passer_en_blanc'])
    from apps.sales.models import QuoteTemplateField

    champ = QuoteTemplateField.objects.create(
        template=modele, cle='numero_devis', x=10, y=10, couleur='#B43B3B')

    module.passer_en_blanc(registre, None)

    champ.refresh_from_db()
    assert champ.couleur == '#B43B3B'


# ═══ LES CADRES GARDENT LEUR COULEUR ════════════════════════════════════════

def test_l_enregistrement_accepte_la_couleur_et_le_multiligne(connecte,
                                                              modele):
    from apps.sales.models import QuoteTemplateField

    reponse = connecte.post(
        reverse('sales:quote_template_save_frames', args=[modele.pk]),
        data=json.dumps({'cadres': [{
            'cle': 'total_ttc', 'page': 1, 'x': 100, 'y': 200,
            'largeur': 150, 'hauteur': 18, 'taille': 12,
            'couleur': '#FFFFFF', 'multiligne': False,
        }, {
            'cle': 'taches_principales', 'page': 1, 'x': 60, 'y': 400,
            'largeur': 300, 'hauteur': 90, 'taille': 9,
            'couleur': '#000000', 'multiligne': True,
        }]}),
        content_type='application/json')

    assert reponse.status_code == 200, reponse.content
    champs = {c.cle: c for c in QuoteTemplateField.objects.filter(
        template=modele)}
    assert champs['total_ttc'].couleur == '#FFFFFF'
    assert champs['total_ttc'].multiligne is False
    assert champs['taches_principales'].multiligne is True


def test_une_couleur_inconnue_retombe_sur_le_noir(connecte, modele):
    """Une valeur forgée ne doit pas entrer en base : la couleur sert ensuite
    à écrire dans le PDF."""
    from apps.sales.models import QuoteTemplateField

    connecte.post(
        reverse('sales:quote_template_save_frames', args=[modele.pk]),
        data=json.dumps({'cadres': [{
            'cle': 'total_ttc', 'page': 1, 'x': 10, 'y': 10,
            'largeur': 100, 'hauteur': 16, 'taille': 10,
            'couleur': 'javascript:alert(1)',
        }]}),
        content_type='application/json')

    assert QuoteTemplateField.objects.get(
        template=modele).couleur == '#000000'


def test_l_editeur_transmet_la_couleur_et_les_couleurs_possibles(connecte,
                                                                 modele):
    """Si l'éditeur ne les renvoyait pas, son enregistrement — qui REMPLACE
    tous les cadres — les effacerait au premier passage."""
    from apps.sales.models import QuoteTemplateField

    QuoteTemplateField.objects.create(
        template=modele, cle='total_ttc', x=10, y=10, couleur='#FFFFFF',
        multiligne=False)

    reponse = connecte.get(
        reverse('sales:quote_template_editor', args=[modele.pk]))
    corps = reponse.content.decode()

    cadres = json.loads(reponse.context['cadres_json'])
    assert cadres[0]['couleur'] == '#FFFFFF'
    assert cadres[0]['multiligne'] is False
    # La liste des couleurs vient du modele, pas d-une copie dans le script.
    couleurs = json.loads(reponse.context['couleurs_json'])
    assert {c['valeur'] for c in couleurs} == {
        v for v, _ in QuoteTemplateField.COULEURS}
    assert 'data-couleurs' in corps


# ═══ LES NOUVELLES VALEURS SONT PROPOSÉES ═══════════════════════════════════

def test_les_cinq_nouvelles_valeurs_sont_placables():
    from apps.sales.models import QuoteTemplateField

    cles = {cle for cle, _ in QuoteTemplateField.CLES}
    for attendue in ('taux_tva', 'cout_materiels', 'cout_fournitures',
                     'cout_main_oeuvre', 'taches_principales'):
        assert attendue in cles, attendue


def test_l_editeur_propose_les_nouvelles_valeurs(connecte, modele):
    corps = connecte.get(
        reverse('sales:quote_template_editor', args=[modele.pk])
    ).content.decode()

    for cle in ('taux_tva', 'cout_materiels', 'cout_fournitures',
                'cout_main_oeuvre', 'taches_principales'):
        assert f'data-cle="{cle}"' in corps, cle


def test_valeurs_du_devis_fournit_une_valeur_par_cle(devis):
    """Une clé placable sans valeur correspondante poserait un cadre qui
    n'écrira jamais rien."""
    from apps.sales.models import QuoteTemplateField
    from apps.sales.quote_pdf import valeurs_du_devis

    valeurs = valeurs_du_devis(devis)
    for cle, _ in QuoteTemplateField.CLES:
        assert cle in valeurs, cle


# ═══ LE CALCUL DES LIGNES, TOUT EN DÉCIMAL ══════════════════════════════════
#
# Défaut pré-existant, rencontré en écrivant les tests ci-dessus et corrigé
# à cette occasion : le défaut Python d'un DecimalField est l'ENTIER 0, donc
# « 1 - self.discount_rate / 100 » produisait un float, et
# « Decimal * float » levait TypeError. Une ligne créée sans remise
# explicite — le cas courant — ne pouvait pas être enregistrée du tout.
# Personne ne l'avait vu parce qu'aucun écran ne créait de ligne.


def test_une_ligne_de_devis_se_cree_sans_remise_explicite(devis):
    from apps.sales.models import QuoteLine

    ligne = QuoteLine.objects.create(
        quote=devis, description='Carrelage', quantity=Decimal('40'),
        unit_price=Decimal('25'), vat_rate=Decimal('10'))

    assert ligne.total_ht == Decimal('1000.00')
    assert ligne.total_tva == Decimal('100.00')


def test_une_ligne_de_devis_applique_la_remise(devis):
    from apps.sales.models import QuoteLine

    ligne = QuoteLine.objects.create(
        quote=devis, description='Carrelage', quantity=Decimal('10'),
        unit_price=Decimal('100'), discount_rate=Decimal('10'),
        vat_rate=Decimal('20'))

    assert ligne.total_ht == Decimal('900.00')
    assert ligne.total_tva == Decimal('180.00')


def test_une_ligne_de_facture_se_cree_aussi_sans_remise(entreprise):
    """Le même défaut était dans InvoiceLine : les deux sont corrigés."""
    from apps.crm.models import Customer
    from apps.sales.models import Invoice, InvoiceLine

    client = Customer.objects.create(company=entreprise, name='Client F')
    facture = Invoice.objects.create(company=entreprise, customer=client)
    ligne = InvoiceLine.objects.create(
        invoice=facture, description='Prestation', quantity=Decimal('2'),
        unit_price=Decimal('150'), vat_rate=Decimal('20'))

    assert ligne.total_ht == Decimal('300.00')
    assert ligne.total_tva == Decimal('60.00')


def test_une_ligne_sans_prix_ni_quantite_ne_casse_pas(devis):
    """Une ligne de texte ou de sous-total n'a ni prix ni quantité."""
    from apps.sales.models import QuoteLine

    ligne = QuoteLine.objects.create(
        quote=devis, description='Sous-total lot 1', line_type='subtotal')

    assert ligne.total_ht == Decimal('0.00')
    assert ligne.total_tva == Decimal('0.00')
