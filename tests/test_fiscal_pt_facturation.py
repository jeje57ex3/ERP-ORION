"""Le pont entre une facture de l'ERP et sa preuve légale.

CE QUE CES TESTS DÉFENDENT

1. Qu'une installation qui ne facture pas au Portugal ne voit AUCUNE
   différence. C'est la condition pour que ce module puisse exister dans
   un ERP généraliste.

2. Qu'une facture ne puisse pas partir sans sa signature. Si la signature
   échoue, la facture doit rester en brouillon — l'inverse paraît plus
   accommodant et laisserait sortir des mois de factures sans preuve,
   sans que rien le signale.

3. Qu'un double appel ne consomme pas deux numéros. Un bouton cliqué deux
   fois laisserait un document orphelin au milieu de la chaîne, et aucune
   correction ne rattrape cela ensuite.
"""
from datetime import date
from decimal import Decimal

import pytest
from cryptography.fernet import Fernet
from django.core.exceptions import ValidationError
from django.urls import reverse

from apps.core.models import Company
from apps.crm.models import Customer
from apps.fiscal_pt import facturation
from apps.fiscal_pt.models import (CleDeSignature, DocumentFiscal,
                                   ParametresFiscauxPT, SerieFiscale)
from apps.sales.models import Invoice, InvoiceLine


@pytest.fixture
def chiffrement(settings):
    settings.ORION_SECRET_ENCRYPTION_KEY = Fernet.generate_key().decode()


@pytest.fixture
def entreprise(db):
    return Company.objects.create(name='Orion Lusitana', slug='orion-pt-fact')


@pytest.fixture
def cliente(entreprise):
    return Customer.objects.create(company=entreprise, name='Cliente Lda',
                                   nif='500000000', country='Portugal')


@pytest.fixture
def facture(entreprise, cliente):
    facture = Invoice.objects.create(
        company=entreprise, customer=cliente, number='FAC-2026-0042',
        issue_date=date(2026, 3, 7), status='draft')
    InvoiceLine.objects.create(
        invoice=facture, description='Instalação elétrica',
        quantity=Decimal('1'), unit_price=Decimal('100.00'),
        vat_rate=Decimal('23'))
    facture.refresh_from_db()
    return facture


@pytest.fixture
def conformite(entreprise, chiffrement):
    """L'entreprise prête à émettre au Portugal."""
    parametres = ParametresFiscauxPT.de(entreprise)
    parametres.est_actif = True
    parametres.nif = '123456789'
    parametres.save()
    cle = CleDeSignature.creer(entreprise)
    return SerieFiscale.objects.create(
        company=entreprise, type_document='FT', nom='A',
        code_de_validation='CSDF7T5H', cle=cle)


# ── Rien ne change hors du Portugal ──────────────────────────────────────────

def test_sans_conformite_activee_rien_n_est_signe(facture):
    """La condition pour que ce module puisse exister dans un ERP
    généraliste : une installation française ne voit aucune différence."""
    with pytest.raises(facturation.ConformiteInactive):
        facturation.emettre_pour_facture(facture)

    assert DocumentFiscal.objects.count() == 0
    assert facturation.document_pour(facture) is None
    assert facturation.est_active(facture.company) is False


def _envoyer(facture, django_user_model):
    """Appelle la vue d'envoi de facture avec une requête fabriquée.

    On appelle la VUE et non un service : ce qui est à vérifier est
    l'ordre des deux opérations — signer, puis changer le statut — et cet
    ordre n'existe que dans la vue. `current_company` est posé à la main
    parce que l'intergiciel qui s'en charge a ses propres tests.
    """
    from django.contrib.messages.storage.fallback import FallbackStorage
    from django.test import RequestFactory

    from apps.sales.views import invoice_send

    requete = RequestFactory().post(
        reverse('sales:invoice_send', args=[facture.pk]))
    requete.user = django_user_model.objects.create_user(
        username=f'agent{facture.pk}', password='mot-de-passe-de-test')
    requete.current_company = facture.company
    requete.session = {}
    requete._messages = FallbackStorage(requete)

    reponse = invoice_send(requete, facture.pk)
    facture.refresh_from_db()
    return reponse, [str(m) for m in requete._messages]


def test_l_envoi_d_une_facture_francaise_reste_inchange(facture,
                                                        django_user_model):
    """Hors conformité portugaise, le comportement doit être EXACTEMENT
    celui d'avant : statut envoyé, numéro inchangé, aucune signature."""
    reponse, messages = _envoyer(facture, django_user_model)

    assert reponse.status_code == 302
    assert facture.status == 'sent'
    assert facture.number == 'FAC-2026-0042'
    assert DocumentFiscal.objects.count() == 0
    assert any('marquée comme envoyée' in m for m in messages)


def test_l_envoi_signe_la_facture_quand_la_conformite_est_active(
        facture, conformite, django_user_model):
    reponse, messages = _envoyer(facture, django_user_model)

    assert reponse.status_code == 302
    assert facture.status == 'sent'
    assert facture.number == 'FT A/1'
    document = DocumentFiscal.objects.get()
    assert document.verifier() is True
    assert any('signée' in m and document.atcud in m for m in messages)


def test_une_signature_qui_echoue_laisse_la_facture_en_brouillon(
        facture, entreprise, chiffrement, django_user_model):
    """LA GARANTIE LA PLUS IMPORTANTE DE CE FICHIER.

    Aucune série n'est déclarée : la signature échoue. La facture doit
    rester en BROUILLON. L'inverse paraît plus accommodant et serait bien
    pire — la facture partirait sans preuve, l'anomalie ne se verrait
    nulle part, et des mois de facturation sortiraient hors la loi.
    """
    parametres = ParametresFiscauxPT.de(entreprise)
    parametres.est_actif = True
    parametres.nif = '123456789'
    parametres.save()
    CleDeSignature.creer(entreprise)

    reponse, messages = _envoyer(facture, django_user_model)

    assert reponse.status_code == 302
    assert facture.status == 'draft'          # pas envoyée
    assert facture.number == 'FAC-2026-0042'  # pas renumérotée
    assert DocumentFiscal.objects.count() == 0
    assert any('non envoyée' in m for m in messages)
    assert any('série active' in m for m in messages)


# ── L'émission ───────────────────────────────────────────────────────────────

def test_une_facture_est_signee_et_renumerotee(facture, conformite):
    """Le numéro légal portugais REMPLACE celui de l'ERP.

    Les deux ne peuvent pas coexister : c'est le numéro imprimé qui est
    signé, et c'est lui que le SAF-T exporte. En laisser deux donnerait
    deux documents différents portant la même signature.
    """
    document = facturation.emettre_pour_facture(facture)

    assert document.numero == 'FT A/1'
    assert document.atcud == 'CSDF7T5H-1'
    assert document.verifier() is True

    facture.refresh_from_db()
    assert facture.number == 'FT A/1'


def test_les_montants_de_la_facture_sont_reportes(facture, conformite):
    document = facturation.emettre_pour_facture(facture)

    assert document.total_base == Decimal('100.00')
    assert document.total_taxes == Decimal('23.00')
    assert document.total == Decimal('123.00')


def test_le_nif_du_client_passe_dans_le_code_qr(facture, conformite):
    document = facturation.emettre_pour_facture(facture)

    assert document.nif_acquereur == '500000000'
    assert '*B:500000000*' in document.contenu_qr
    assert '*C:PT*' in document.contenu_qr


def test_un_client_sans_nif_devient_consommateur_final(facture, conformite):
    facture.customer.nif = ''
    facture.customer.save()

    document = facturation.emettre_pour_facture(facture)

    assert '*B:999999990*' in document.contenu_qr


def test_le_lien_vers_la_facture_est_conserve(facture, conformite):
    document = facturation.emettre_pour_facture(facture)

    assert facturation.document_pour(facture) == document
    assert document.source_app == 'sales'
    assert document.source_id == facture.pk


# ── L'idempotence ────────────────────────────────────────────────────────────

def test_un_double_appel_ne_consomme_pas_deux_numeros(facture, conformite):
    """LE CAS QU'AUCUNE CORRECTION NE RATTRAPE.

    Un bouton cliqué deux fois, une requête rejouée : deux documents pour
    une facture laisseraient un orphelin au milieu de la chaîne, et le
    numéro consommé ne peut pas être rendu.
    """
    premier = facturation.emettre_pour_facture(facture)
    second = facturation.emettre_pour_facture(facture)

    assert premier.pk == second.pk
    assert DocumentFiscal.objects.count() == 1
    conformite.refresh_from_db()
    assert conformite.prochain_numero == 2


# ── Les échecs, et ce qu'ils doivent laisser derrière eux ────────────────────

def test_sans_serie_active_l_emission_echoue_clairement(facture, entreprise,
                                                        chiffrement):
    parametres = ParametresFiscauxPT.de(entreprise)
    parametres.est_actif = True
    parametres.nif = '123456789'
    parametres.save()
    CleDeSignature.creer(entreprise)

    with pytest.raises(ValidationError, match='série active'):
        facturation.emettre_pour_facture(facture)


def test_sans_nif_l_emission_echoue_clairement(facture, entreprise,
                                               chiffrement):
    parametres = ParametresFiscauxPT.de(entreprise)
    parametres.est_actif = True
    parametres.save()

    with pytest.raises(ValidationError, match='NIF'):
        facturation.emettre_pour_facture(facture)


def test_une_facture_sans_ligne_est_refusee(entreprise, cliente, conformite):
    vide = Invoice.objects.create(company=entreprise, customer=cliente,
                                  number='FAC-2026-0043',
                                  issue_date=date(2026, 3, 7))

    with pytest.raises(ValidationError, match='aucune ligne'):
        facturation.emettre_pour_facture(vide)


def test_un_taux_francais_sur_une_facture_portugaise_est_refuse(
        facture, conformite):
    """Un taux de 20 % n'existe pas au Portugal. Le ranger dans le palier
    voisin laisserait le total juste et le code QR faux."""
    from apps.fiscal_pt.taxas import TauxInconnu

    ligne = facture.lines.first()
    ligne.vat_rate = Decimal('20')
    ligne.save()

    with pytest.raises(TauxInconnu, match='20'):
        facturation.emettre_pour_facture(facture)

    assert DocumentFiscal.objects.count() == 0
    conformite.refresh_from_db()
    assert conformite.prochain_numero == 1   # aucun numéro brûlé


# ── Le pays de l'acquéreur ───────────────────────────────────────────────────

@pytest.mark.parametrize('saisi, attendu', [
    ('Portugal', 'PT'),
    ('France', 'FR'),
    ('', 'PT'),
    ('FR', 'FR'),
    ('fr', 'FR'),
    ('Ruritanie', 'Desconhecido'),
])
def test_le_pays_est_traduit_en_deux_lettres(saisi, attendu, entreprise):
    """Le champ « pays » de l'ERP est un texte libre et le code QR attend
    deux lettres. Recopier « Portugal » tel quel produirait un code QR que
    l'application de l'AT ne sait pas lire."""
    client = Customer(company=entreprise, name='X', country=saisi)

    assert facturation._pays_de(client) == attendu


def test_un_pays_inconnu_est_declare_inconnu_et_non_devine(facture,
                                                           conformite):
    """« Desconhecido » est la valeur que le SAF-T prévoit, et elle se
    corrige après coup. Un code à deux lettres inventé passerait
    inaperçu."""
    facture.customer.country = 'Ruritanie'
    facture.customer.save()

    document = facturation.emettre_pour_facture(facture)

    assert '*C:Desconhecido*' in document.contenu_qr
