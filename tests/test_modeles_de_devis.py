"""Modèles de devis : un PDF fourni, des valeurs superposées.

La mise en page du devis — en-tête, logo, conditions générales, mentions
légales — est fournie par l'exploitant sous forme de PDF. Orion n'en redessine
rien : il écrit par-dessus les seules valeurs qui changent d'un devis à
l'autre. C'est l'inverse d'un générateur, et délibérément : redessiner
supposerait de reproduire une charte dans du code, de la maintenir à chaque
changement de papier à en-tête, et d'expliquer pourquoi le rendu diffère de
l'original.

Les propriétés éprouvées ici sont celles qui se voient sur un document envoyé
à un client :

  - la mise en page d'origine survit au remplissage ;
  - les montants sont écrits au format français, et avec un séparateur que la
    police du PDF sait rendre — l'espace fine U+202F donne un carré noir ;
  - un champ placé sur une page inexistante est signalé, pas perdu ;
  - le cloisonnement par entreprise, sur le modèle comme sur le client.
"""

import io
from decimal import Decimal

import pytest
from django.core.files.base import ContentFile

pytestmark = pytest.mark.django_db


def _pdf_vierge(pages=1, largeur=595, hauteur=842, entete='ENTREPRISE DUPONT'):
    """Un PDF plausible : ce que l'exploitant déposerait."""
    from reportlab.pdfgen import canvas

    tampon = io.BytesIO()
    feuille = canvas.Canvas(tampon, pagesize=(largeur, hauteur))
    for numero in range(pages):
        feuille.setFont('Helvetica-Bold', 18)
        feuille.drawString(40, hauteur - 50, entete)
        feuille.setFont('Helvetica', 9)
        feuille.drawString(40, hauteur - 70, 'Page %s' % (numero + 1))
        feuille.showPage()
    feuille.save()
    tampon.seek(0)
    return tampon.getvalue()


@pytest.fixture
def entreprise(db):
    from apps.core.models import Company
    return Company.objects.create(name='Dupont SA', slug='dupont-sa')


@pytest.fixture
def autre_entreprise(db):
    from apps.core.models import Company
    return Company.objects.create(name='Martin SA', slug='martin-sa')


@pytest.fixture
def client_erp(entreprise):
    from apps.crm.models import Customer
    return Customer.objects.create(
        company=entreprise, code='CLI-0042', name='Entreprise Exemple SARL',
        contact_name='Jean Dupont', address='12 rue des Artisans',
        zip_code='57000', city='Metz', email='contact@exemple.fr',
        phone='03 87 00 00 00',
    )


@pytest.fixture
def modele(entreprise):
    from apps.sales.models import QuoteTemplate
    objet = QuoteTemplate.objects.create(
        company=entreprise, name='Devis standard', is_default=True)
    objet.pdf.save('modele.pdf', ContentFile(_pdf_vierge()), save=True)
    return objet


@pytest.fixture
def devis(entreprise, client_erp):
    from apps.sales.models import Quote
    return Quote.objects.create(
        company=entreprise, customer=client_erp, number='DEV-2026-0042',
        subject='Rénovation salle de bain',
        total_ht=Decimal('12400.00'), total_tva=Decimal('2480.00'),
        total_ttc=Decimal('14880.00'),
    )


def _champ(modele, cle, **kwargs):
    from apps.sales.models import QuoteTemplateField
    valeurs = {'page': 1, 'x': 100, 'y': 700}
    valeurs.update(kwargs)
    return QuoteTemplateField.objects.create(
        template=modele, cle=cle, **valeurs)


def _texte_du_pdf(octets):
    from pypdf import PdfReader
    lecteur = PdfReader(io.BytesIO(octets))
    return '\n'.join(page.extract_text() or '' for page in lecteur.pages)


# ── Le remplissage ──────────────────────────────────────────────────────────

def test_les_valeurs_sont_ecrites_sur_le_modele(modele, devis):
    from apps.sales.quote_pdf import remplir_modele

    _champ(modele, 'numero_devis', y=700)
    _champ(modele, 'numero_client', y=680)
    _champ(modele, 'nom_client', y=660)
    _champ(modele, 'total_ttc', y=200)

    octets = remplir_modele(devis, modele).getvalue()
    assert octets.startswith(b'%PDF')

    texte = _texte_du_pdf(octets).replace(' ', ' ')
    assert 'DEV-2026-0042' in texte
    assert 'CLI-0042' in texte
    assert 'Entreprise Exemple SARL' in texte
    assert '14 880,00' in texte


def test_la_mise_en_page_d_origine_survit(modele, devis):
    """C'est tout l'intérêt de superposer plutôt que de redessiner."""
    from apps.sales.quote_pdf import remplir_modele

    _champ(modele, 'numero_devis')
    texte = _texte_du_pdf(remplir_modele(devis, modele).getvalue())
    assert 'ENTREPRISE DUPONT' in texte


def test_aucun_carre_de_substitution_dans_le_document(modele, devis):
    """Vérifié : les polices standard du PDF utilisent l'encodage WinAnsi, qui
    ne contient pas l'espace fine U+202F. reportlab y substitue un carré noir,
    et le devis envoyé au client afficherait « 12■400,00 »."""
    from apps.sales.quote_pdf import remplir_modele

    _champ(modele, 'total_ht', y=300)
    _champ(modele, 'total_tva', y=280)
    _champ(modele, 'total_ttc', y=260)

    texte = _texte_du_pdf(remplir_modele(devis, modele).getvalue())
    assert '■' not in texte, 'caractère non encodable rendu en carré noir'


def test_le_format_des_montants_est_francais():
    from apps.sales.quote_pdf import _format_montant

    assert _format_montant(Decimal('12400.00')) == '12 400,00'
    assert _format_montant(Decimal('1234567.5')) == '1 234 567,50'
    assert _format_montant(Decimal('-980.4')) == '-980,40'
    assert _format_montant(Decimal('7.99')) == '7,99'
    assert _format_montant(None) == ''


def test_un_champ_sans_valeur_n_imprime_rien(modele, devis, client_erp):
    """« Client : » suivi du vide ferait croire à une donnée perdue."""
    from apps.sales.quote_pdf import remplir_modele

    client_erp.email = ''
    client_erp.save()
    _champ(modele, 'email_client', prefixe='Email : ', y=500)

    texte = _texte_du_pdf(remplir_modele(devis, modele).getvalue())
    assert 'Email :' not in texte


def test_une_page_entierement_vide_ne_fait_pas_echouer(modele, devis,
                                                      client_erp):
    """Cas limite trouvé en éprouvant le précédent : un canvas reportlab sur
    lequel rien n'est dessiné produit un document de ZÉRO page, et la fusion
    levait alors IndexError. Toute la génération échouait pour un client sans
    code ni email."""
    from apps.sales.quote_pdf import remplir_modele

    client_erp.email = ''
    client_erp.code = ''
    client_erp.save()
    _champ(modele, 'email_client', y=500)
    _champ(modele, 'numero_client', y=480)

    octets = remplir_modele(devis, modele).getvalue()
    assert octets.startswith(b'%PDF')
    # Le modèle est rendu tel quel, sans rien d'ajouté.
    assert 'ENTREPRISE DUPONT' in _texte_du_pdf(octets)


def test_un_champ_sur_une_page_inexistante_est_signale(modele, devis):
    """Perdu en silence, il se verrait comme une valeur manquante sur le
    devis — un symptôme qui ne désigne pas sa cause."""
    from apps.sales.quote_pdf import ModeleDevisError, remplir_modele

    _champ(modele, 'numero_devis', page=4)
    with pytest.raises(ModeleDevisError) as erreur:
        remplir_modele(devis, modele)
    assert '4' in str(erreur.value)
    assert 'page' in str(erreur.value).lower()


def test_deux_generations_de_suite_fonctionnent(modele, devis):
    """Le fichier du modèle était fermé après usage, et une FieldFile fermée
    ne se réouvre pas toujours : générer deux devis d'affilée échouait sur
    « The file cannot be reopened »."""
    from apps.sales.quote_pdf import generer_grille_de_calage, remplir_modele

    _champ(modele, 'numero_devis')
    premier = remplir_modele(devis, modele).getvalue()
    grille = generer_grille_de_calage(modele).getvalue()
    second = remplir_modele(devis, modele).getvalue()

    assert len(premier) > 0 and len(grille) > 0
    assert len(second) == len(premier)


def test_un_modele_sans_pdf_le_dit(entreprise, devis):
    from apps.sales.models import QuoteTemplate
    from apps.sales.quote_pdf import ModeleDevisError, remplir_modele

    vide = QuoteTemplate.objects.create(company=entreprise, name='Sans PDF')
    with pytest.raises(ModeleDevisError):
        remplir_modele(devis, vide)


def test_l_alignement_a_droite_est_pris_en_compte(modele, devis):
    """Un total aligné à gauche déborderait de sa colonne."""
    from apps.sales.quote_pdf import remplir_modele

    _champ(modele, 'total_ttc', x=540, y=200, alignement='right')
    octets = remplir_modele(devis, modele).getvalue()
    assert '14' in _texte_du_pdf(octets)


# ── La grille de calage ─────────────────────────────────────────────────────

def test_la_grille_porte_les_graduations(modele):
    """Sans elle, placer quinze champs demande autant d'essais successifs."""
    from apps.sales.quote_pdf import generer_grille_de_calage

    octets = generer_grille_de_calage(modele).getvalue()
    assert octets.startswith(b'%PDF')
    texte = _texte_du_pdf(octets)
    # Les graduations fortes sont cotees tous les 100 points.
    assert '100' in texte and '500' in texte
    # Et le repere est explicite : l'origine en bas n'est pas l'intuition.
    assert 'bas' in texte.lower() or 'HAUT' in texte


def test_la_grille_conserve_le_modele_dessous(modele):
    from apps.sales.quote_pdf import generer_grille_de_calage

    texte = _texte_du_pdf(generer_grille_de_calage(modele).getvalue())
    assert 'ENTREPRISE DUPONT' in texte


# ── Détection des champs de formulaire ──────────────────────────────────────

def test_un_pdf_plat_ne_declare_aucun_champ(modele):
    """Cas le plus courant : un PDF exporté d'un traitement de texte."""
    from apps.sales.quote_pdf import champs_de_formulaire_detectes

    assert champs_de_formulaire_detectes(modele) == []


def test_le_nombre_de_pages_est_lu_dans_le_pdf(entreprise):
    from apps.sales.models import QuoteTemplate
    from apps.sales.quote_pdf import nombre_de_pages

    trois = QuoteTemplate.objects.create(company=entreprise, name='Trois pages')
    trois.pdf.save('trois.pdf', ContentFile(_pdf_vierge(pages=3)), save=True)
    assert nombre_de_pages(trois) == 3


# ── Un seul modèle par défaut ──────────────────────────────────────────────

def test_un_seul_modele_par_defaut(entreprise, modele):
    """« Le » modèle par défaut dépendrait sinon de l'ordre de tri."""
    from apps.sales.models import QuoteTemplate

    second = QuoteTemplate.objects.create(
        company=entreprise, name='Devis rénovation', is_default=True)
    second.pdf.save('b.pdf', ContentFile(_pdf_vierge()), save=True)

    modele.refresh_from_db()
    assert second.is_default is True
    assert modele.is_default is False
    assert QuoteTemplate.objects.filter(
        company=entreprise, is_default=True).count() == 1


def test_le_defaut_d_une_entreprise_ne_touche_pas_l_autre(entreprise,
                                                          autre_entreprise,
                                                          modele):
    from apps.sales.models import QuoteTemplate

    chez_eux = QuoteTemplate.objects.create(
        company=autre_entreprise, name='Leur modèle', is_default=True)
    chez_eux.pdf.save('c.pdf', ContentFile(_pdf_vierge()), save=True)

    modele.refresh_from_db()
    assert modele.is_default is True, (
        "le modèle par défaut d'une autre entreprise a été dégradé"
    )


# ── Les écrans et le cloisonnement ─────────────────────────────────────────

@pytest.fixture
def connecte(client, django_user_model, entreprise, monkeypatch):
    utilisateur = django_user_model.objects.create_user(
        username='commercial', password='motdepasse-test')
    client.force_login(utilisateur)

    # L'entreprise active est posée par un intergiciel ; on la force pour
    # éprouver les vues sans dépendre de son mécanisme de résolution.
    from apps.sales import views_quote_templates as modeles
    monkeypatch.setattr(modeles, '_entreprise', lambda requete: entreprise)
    return client


def test_la_liste_affiche_les_modeles(connecte, modele):
    corps = connecte.get('/sales/devis/modeles/').content.decode()
    assert 'Devis standard' in corps


def test_un_modele_sans_champ_est_signale(connecte, modele):
    """Il produirait un PDF vierge : le dire sur la liste évite de le
    découvrir sur un devis envoyé."""
    corps = connecte.get('/sales/devis/modeles/').content.decode()
    assert 'vierge' in corps


def test_la_grille_est_telechargeable(connecte, modele):
    reponse = connecte.get(f'/sales/devis/modeles/{modele.pk}/grille/')
    assert reponse.status_code == 200
    assert reponse['Content-Type'] == 'application/pdf'
    assert reponse.content.startswith(b'%PDF')


def test_l_apercu_utilise_des_valeurs_d_exemple(connecte, modele):
    """On règle un modèle AVANT d'avoir un devis."""
    _champ(modele, 'nom_client', y=700)
    reponse = connecte.get(f'/sales/devis/modeles/{modele.pk}/apercu/')
    assert reponse.status_code == 200
    assert 'Exemple' in _texte_du_pdf(reponse.content)


def test_le_pdf_d_un_devis_est_servi(connecte, modele, devis):
    _champ(modele, 'numero_devis', y=700)
    reponse = connecte.get(f'/sales/devis/{devis.pk}/pdf/')
    assert reponse.status_code == 200
    assert reponse['Content-Type'] == 'application/pdf'
    assert 'DEV-2026-0042' in _texte_du_pdf(reponse.content)


def test_le_modele_d_une_autre_entreprise_est_hors_de_portee(
        connecte, autre_entreprise):
    from apps.sales.models import QuoteTemplate

    chez_eux = QuoteTemplate.objects.create(
        company=autre_entreprise, name='Leur modèle')
    chez_eux.pdf.save('d.pdf', ContentFile(_pdf_vierge()), save=True)

    for adresse in (
        f'/sales/devis/modeles/{chez_eux.pk}/',
        f'/sales/devis/modeles/{chez_eux.pk}/grille/',
        f'/sales/devis/modeles/{chez_eux.pk}/apercu/',
    ):
        assert connecte.get(adresse).status_code == 404, adresse


def test_un_devis_peut_etre_cree_depuis_un_modele(connecte, modele,
                                                  client_erp, entreprise):
    from apps.sales.models import Quote

    reponse = connecte.post('/sales/devis/depuis-modele/', {
        'template': modele.pk,
        'customer': client_erp.pk,
        'subject': 'Rénovation cuisine',
    })
    assert reponse.status_code == 302
    quote = Quote.objects.get(company=entreprise, subject='Rénovation cuisine')
    # Le numero vient du service atomique, donc au format prefixe-annee-rang.
    assert quote.number
    assert quote.number.count('-') == 2, quote.number


def test_un_client_d_une_autre_entreprise_est_refuse(connecte, modele,
                                                     autre_entreprise):
    """Les listes sont bornées à la validation, pas seulement à l'affichage :
    sinon un identifiant forgé rattache le devis au client d'un tiers."""
    from apps.crm.models import Customer
    from apps.sales.models import Quote

    chez_eux = Customer.objects.create(
        company=autre_entreprise, name='Client des autres')

    reponse = connecte.post('/sales/devis/depuis-modele/', {
        'template': modele.pk,
        'customer': chez_eux.pk,
        'subject': 'Tentative',
    })
    assert reponse.status_code == 200
    assert not Quote.objects.filter(customer=chez_eux).exists()


def test_un_modele_d_une_autre_entreprise_est_refuse(connecte, client_erp,
                                                     autre_entreprise):
    from apps.sales.models import Quote, QuoteTemplate

    chez_eux = QuoteTemplate.objects.create(
        company=autre_entreprise, name='Leur modèle')

    reponse = connecte.post('/sales/devis/depuis-modele/', {
        'template': chez_eux.pk,
        'customer': client_erp.pk,
        'subject': 'Tentative',
    })
    assert reponse.status_code == 200
    assert not Quote.objects.filter(subject='Tentative').exists()


def test_la_suppression_du_modele_exige_un_post(connecte, modele):
    from apps.sales.models import QuoteTemplate

    assert connecte.get(
        f'/sales/devis/modeles/{modele.pk}/supprimer/').status_code == 405
    assert QuoteTemplate.objects.filter(pk=modele.pk).exists()


# ── Le fichier déposé ──────────────────────────────────────────────────────

def test_un_fichier_qui_n_est_pas_un_pdf_est_refuse():
    """L'extension ne prouve rien : un .docx renommé passerait, et l'erreur
    n'apparaîtrait qu'à la première génération de devis."""
    from apps.sales.forms import QuoteTemplateForm

    faux = ContentFile(b'PK\x03\x04 ceci est un zip', name='piege.pdf')
    form = QuoteTemplateForm(
        data={'name': 'Piège', 'is_active': True},
        files={'pdf': faux},
    )
    assert not form.is_valid()
    assert 'pdf' in form.errors


def test_un_vrai_pdf_est_accepte():
    from apps.sales.forms import QuoteTemplateForm

    vrai = ContentFile(_pdf_vierge(), name='modele.pdf')
    form = QuoteTemplateForm(
        data={'name': 'Correct', 'is_active': True},
        files={'pdf': vrai},
    )
    assert form.is_valid(), form.errors
