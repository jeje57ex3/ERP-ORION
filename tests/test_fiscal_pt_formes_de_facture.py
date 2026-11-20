"""Les quatre autres formes de facture : FS, FR, ND — et ce qu'elles exigent.

POURQUOI CES TESTS PASSENT PAR LA BASE

`tests/test_fiscal_pt_tipos.py` mesure les règles elles-mêmes, sans
Django. Ce fichier-ci mesure autre chose : que le chemin RÉEL — un
formulaire, une série, une transaction, une signature, un export —
applique bien ces règles, et qu'il les applique AVANT que le document
devienne immuable.

La distinction n'est pas théorique. Une règle juste dans un module qui
n'est pas appelé au bon moment laisse émettre le document, et un document
émis ne se corrige plus que par un autre document.
"""
from datetime import date
from decimal import Decimal
from xml.etree import ElementTree as ET

import pytest
from cryptography.fernet import Fernet
from django.core.exceptions import ValidationError

from apps.core.models import Company
from apps.crm.models import Customer
from apps.fiscal_pt import export, facturation, tipos
from apps.fiscal_pt.models import (CleDeSignature, DocumentFiscal,
                                   ParametresFiscauxPT, SerieFiscale)
from apps.sales.models import Invoice, InvoiceLine

ESPACE = '{urn:OECD:StandardAuditFile-Tax:PT_1.04_01}'


@pytest.fixture
def chiffrement(settings):
    settings.ORION_SECRET_ENCRYPTION_KEY = Fernet.generate_key().decode()


@pytest.fixture
def entreprise(db):
    return Company.objects.create(name='Orion Lusitana', slug='orion-formes')


@pytest.fixture
def cliente(entreprise):
    return Customer.objects.create(company=entreprise, name='Cliente Lda',
                                   nif='500000000', country='Portugal')


def _facture(entreprise, cliente, numero, prix, quantite=Decimal('1')):
    facture = Invoice.objects.create(
        company=entreprise, customer=cliente, number=numero,
        issue_date=date(2026, 3, 7), status='draft')
    InvoiceLine.objects.create(
        invoice=facture, description='Instalação elétrica',
        quantity=quantite, unit_price=prix, vat_rate=Decimal('23'))
    facture.refresh_from_db()
    return facture


@pytest.fixture
def petite_facture(entreprise, cliente):
    """80 € hors taxe, 98,40 € à payer : sous le plafond dans les deux
    lectures."""
    return _facture(entreprise, cliente, 'FAC-0001', Decimal('80.00'))


@pytest.fixture
def grosse_facture(entreprise, cliente):
    """1 000 € hors taxe : hors plafond dans les deux lectures."""
    return _facture(entreprise, cliente, 'FAC-0002', Decimal('1000.00'))


@pytest.fixture
def facture_limite(entreprise, cliente):
    """95 € hors taxe, 116,85 € à payer : la bande de divergence."""
    return _facture(entreprise, cliente, 'FAC-0003', Decimal('95.00'))


@pytest.fixture
def conformite(entreprise, chiffrement):
    """L'entreprise prête à émettre, avec les CINQ séries."""
    parametres = ParametresFiscauxPT.de(entreprise)
    parametres.est_actif = True
    parametres.nif = '123456789'
    parametres.save()
    cle = CleDeSignature.creer(entreprise)

    codes = {'FT': 'CSDF7T5H', 'FS': 'JFFNVTC7', 'FR': 'RQD8L6DG',
             'ND': 'HMPTDQ4R', 'NC': 'KSMLFPQZ'}
    return {type_document: SerieFiscale.objects.create(
                company=entreprise, type_document=type_document, nom='A',
                code_de_validation=code, cle=cle)
            for type_document, code in codes.items()}


UN_PAIEMENT = [{'mecanisme': 'TB', 'montant': Decimal('98.40'),
                'date': date(2026, 3, 7)}]


# ── La facture simplifiée et son plafond ─────────────────────────────────────

def test_une_facture_simplifiee_sous_le_plafond_s_emet(petite_facture,
                                                       conformite):
    document = facturation.emettre_pour_facture(petite_facture, 'FS')

    assert document.numero == 'FS A/1'
    assert document.total == Decimal('98.40')
    assert document.verifier() is True
    assert document.avertissements == []


def test_la_forme_legale_remplace_le_numero_de_l_erp(petite_facture,
                                                     conformite):
    """« FS » est écrit DANS le numéro et signé avec lui. C'est pourquoi la
    forme ne se change plus après l'émission."""
    facturation.emettre_pour_facture(petite_facture, 'FS')
    petite_facture.refresh_from_db()

    assert petite_facture.number == 'FS A/1'


def test_une_facture_simplifiee_hors_plafond_est_refusee(grosse_facture,
                                                         conformite):
    with pytest.raises(ValidationError) as erreur:
        facturation.emettre_pour_facture(grosse_facture, 'FS')

    assert 'plafond' in str(erreur.value)


def test_le_refus_ne_consomme_pas_de_numero(grosse_facture, conformite):
    """CE QUE CE TEST DÉFEND VRAIMENT.

    Un refus qui aurait déjà incrémenté le compteur laisserait un TROU
    permanent dans la série. Un trou ne se comble pas : il faudra
    l'expliquer à chaque contrôle, pour toujours. La transaction doit donc
    rendre le numéro, et c'est seulement mesurable ici.
    """
    serie = conformite['FS']

    with pytest.raises(ValidationError):
        facturation.emettre_pour_facture(grosse_facture, 'FS')

    serie.refresh_from_db()
    assert serie.prochain_numero == 1
    assert DocumentFiscal.objects.filter(serie=serie).count() == 0


def test_la_bande_de_divergence_emet_et_avertit(facture_limite, conformite):
    """95 € hors taxe, 116,85 € à payer.

    L'article 40.º plafonne « o montante da fatura » ; l'Ofício-Circulado
    n.º 30141/2013 dit que ce montant s'entend hors TVA. Le document
    s'émet — c'est la doctrine de l'administration — et l'avertissement
    remonte jusqu'à l'écran.
    """
    document = facturation.emettre_pour_facture(facture_limite, 'FS')

    assert document.numero == 'FS A/1'
    assert len(document.avertissements) == 1
    assert '30141' in document.avertissements[0]


def test_le_regime_de_l_entreprise_deplace_le_plafond(grosse_facture,
                                                      conformite,
                                                      entreprise):
    """Le plafond dépend de l'ACTIVITÉ et non du document : un détaillant
    simplifie jusqu'à mille euros. Le réglage est donc dans les paramètres
    de l'entreprise, une fois — pas à choisir sur chaque facture, où il
    finirait par être mis au plus large."""
    parametres = ParametresFiscauxPT.de(entreprise)
    parametres.regime_simplifiee = 'a'
    parametres.save()

    document = facturation.emettre_pour_facture(grosse_facture, 'FS')

    assert document.numero == 'FS A/1'


def test_une_facture_ordinaire_ignore_le_plafond(grosse_facture, conformite):
    """C'est la FORME simplifiée qui est plafonnée, pas le montant qu'on
    peut facturer."""
    document = facturation.emettre_pour_facture(grosse_facture, 'FT')

    assert document.numero == 'FT A/1'
    assert document.total == Decimal('1230.00')


# ── La facture-reçu et son encaissement ──────────────────────────────────────

def test_une_facture_recu_porte_son_encaissement(petite_facture, conformite):
    document = facturation.emettre_pour_facture(
        petite_facture, 'FR', paiements=UN_PAIEMENT)

    assert document.numero == 'FR A/1'
    assert document.paiements == [{'mecanisme': 'TB', 'montant': '98.40',
                                   'date': '2026-03-07'}]
    assert document.verifier() is True


def test_le_montant_est_stocke_en_texte_et_non_en_flottant(petite_facture,
                                                           conformite):
    """Un `float` perd des centimes sur de gros totaux, et la signature
    porte sur le total : l'écart rendrait le fichier incohérent avec sa
    propre preuve."""
    document = facturation.emettre_pour_facture(
        petite_facture, 'FR', paiements=UN_PAIEMENT)
    document.refresh_from_db()

    assert isinstance(document.paiements[0]['montant'], str)
    assert Decimal(document.paiements[0]['montant']) == document.total


def test_le_montant_vient_du_document_et_non_du_cumul_de_la_facture(
        petite_facture, conformite):
    """LE DÉFAUT QUE CE TEST FERME, trouvé en mesurant.

    L'écran prenait d'abord le montant de la quittance dans
    `invoice.total_ttc` — un cumul tenu à part des lignes. Le total du
    DOCUMENT, lui, est recalculé à l'émission depuis les lignes figées.

    Les deux ne diffèrent jamais que d'un centime, après une suppression
    de ligne. Au Portugal ce centime est signé : la quittance cesserait
    de correspondre à la preuve qui l'accompagne. Et c'est tout le
    propos de ce module de ne jamais faire confiance à un cumul.

    La facture de ce test a justement un `total_ttc` à zéro, puisque rien
    ne l'a recalculé : seule la bonne source donne 98,40 €.
    """
    assert petite_facture.total_ttc == Decimal('0')

    document = facturation.emettre_pour_facture(
        petite_facture, 'FR',
        paiements=[{'mecanisme': 'TB', 'date': date(2026, 3, 7)}])

    assert document.total == Decimal('98.40')
    assert document.paiements[0]['montant'] == '98.40'


def test_une_facture_recu_sans_encaissement_est_refusee(petite_facture,
                                                        conformite):
    with pytest.raises(ValidationError) as erreur:
        facturation.emettre_pour_facture(petite_facture, 'FR')

    assert 'quittance' in str(erreur.value)


def test_un_encaissement_partiel_est_refuse(petite_facture, conformite):
    """Le cas le plus traître : le document s'imprime « fatura-recibo »
    comme les autres, et atteste un solde payé qui ne l'est pas."""
    with pytest.raises(ValidationError) as erreur:
        facturation.emettre_pour_facture(
            petite_facture, 'FR',
            paiements=[dict(UN_PAIEMENT[0], montant=Decimal('50.00'))])

    assert 'inférieure' in str(erreur.value)


def test_une_facture_ordinaire_refuse_un_encaissement(petite_facture,
                                                      conformite):
    with pytest.raises(ValidationError) as erreur:
        facturation.emettre_pour_facture(petite_facture, 'FT',
                                         paiements=UN_PAIEMENT)

    assert 'FR' in str(erreur.value)


def test_le_paiement_fige_ne_suit_plus_la_tresorerie(petite_facture,
                                                     conformite):
    """Le document est immuable, et son paiement avec lui.

    Un règlement annulé plus tard ne doit pas faire disparaître du fichier
    l'encaissement que le document atteste et que sa signature couvre.
    """
    document = facturation.emettre_pour_facture(
        petite_facture, 'FR', paiements=UN_PAIEMENT)

    document.paiements = []
    with pytest.raises(ValidationError):
        document.save()


# ── La note de débit ─────────────────────────────────────────────────────────

LIGNES_EN_PLUS = [{'description': 'Revisão de preços',
                   'quantite': Decimal('1'),
                   'prix_unitaire': Decimal('20.00'),
                   'base': Decimal('20.00'),
                   'taux': Decimal('23'),
                   'tva': Decimal('4.60')}]


@pytest.fixture
def signee(petite_facture, conformite):
    return facturation.emettre_pour_facture(petite_facture)


def test_une_note_de_debit_rectifie_la_facture_signee(petite_facture, signee):
    note = facturation.emettre_une_note_de_debit(
        petite_facture, 'Acerto de medição', LIGNES_EN_PLUS)

    assert note.numero == 'ND A/1'
    assert note.document_rectifie == signee
    assert note.total == Decimal('24.60')
    assert note.verifier() is True


def test_la_note_de_debit_ne_reprend_pas_la_facture(petite_facture, signee):
    """CE QUE CE TEST DÉFEND.

    Reprendre les lignes d'origine facturerait la même prestation une
    seconde fois, et le client recevrait un document parfaitement signé
    lui réclamant le double. Le défaut serait irréversible : une note de
    débit ne se retire que par un avoir.
    """
    note = facturation.emettre_une_note_de_debit(
        petite_facture, 'Acerto', LIGNES_EN_PLUS)

    assert note.total != signee.total
    assert len(note.lignes) == 1
    assert note.lignes[0]['description'] == 'Revisão de preços'


def test_une_note_de_debit_sans_ligne_est_refusee(petite_facture, signee):
    with pytest.raises(ValidationError) as erreur:
        facturation.emettre_une_note_de_debit(petite_facture, 'Acerto', [])

    assert 'seconde fois' in str(erreur.value)


def test_une_note_de_debit_sans_motif_est_refusee(petite_facture, signee):
    with pytest.raises(ValidationError) as erreur:
        facturation.emettre_une_note_de_debit(petite_facture, '  ',
                                              LIGNES_EN_PLUS)

    assert 'motif' in str(erreur.value)


def test_une_note_de_debit_sur_une_facture_non_signee_est_refusee(
        petite_facture, conformite):
    with pytest.raises(ValidationError) as erreur:
        facturation.emettre_une_note_de_debit(petite_facture, 'Acerto',
                                              LIGNES_EN_PLUS)

    assert 'brouillon' in str(erreur.value)


def test_la_note_de_debit_a_sa_propre_chaine(petite_facture, signee):
    """Une chaîne par série : la note de débit ouvre celle de « ND »."""
    note = facturation.emettre_une_note_de_debit(
        petite_facture, 'Acerto', LIGNES_EN_PLUS)

    assert note.signature_precedente == ''


def test_plusieurs_notes_de_debit_sont_possibles(petite_facture, signee):
    """Contrairement à l'avoir d'annulation, il n'y a pas de doublon
    possible : chaque note de débit facture une chose différente, et deux
    révisions de prix successives sont légitimes."""
    une = facturation.emettre_une_note_de_debit(petite_facture, 'Revisão 1',
                                                LIGNES_EN_PLUS)
    deux = facturation.emettre_une_note_de_debit(petite_facture, 'Revisão 2',
                                                 LIGNES_EN_PLUS)

    assert une.numero == 'ND A/1'
    assert deux.numero == 'ND A/2'
    assert deux.signature_precedente == une.signature


def test_les_deux_sens_de_rectification_ne_se_melangent_pas(petite_facture,
                                                            signee):
    """Un avoir diminue ce qui est dû, une note de débit l'augmente. Les
    afficher ensemble sous le mot « avoirs » ferait lire une hausse comme
    une baisse — le contresens exact que ces deux documents permettent."""
    facturation.emettre_une_note_de_debit(petite_facture, 'Revisão',
                                          LIGNES_EN_PLUS)
    facturation.emettre_une_note_de_credit(petite_facture, 'Devolução')

    avoirs = list(facturation.rectifications_de(petite_facture, 'NC'))
    notes = list(facturation.rectifications_de(petite_facture, 'ND'))

    assert [d.numero for d in avoirs] == ['NC A/1']
    assert [d.numero for d in notes] == ['ND A/1']
    assert facturation.rectifications_de(petite_facture).count() == 2


# ── Les formes réellement disponibles ────────────────────────────────────────

def test_seules_les_formes_a_serie_active_sont_offertes(entreprise,
                                                        conformite):
    """POURQUOI LA LISTE EST CALCULÉE.

    Une forme sans série active ne peut pas être numérotée. L'offrir au
    choix donnerait un écran qui propose « facture simplifiée » et un
    refus à l'envoi, alors que la seule chose à faire est de déclarer la
    série.
    """
    codes = [code for code, _ in
             facturation.formes_legales_disponibles(entreprise)]

    assert codes == ['FT', 'FS', 'FR']


def test_une_serie_desactivee_retire_la_forme(entreprise, conformite):
    conformite['FS'].est_active = False
    conformite['FS'].save()

    codes = [code for code, _ in
             facturation.formes_legales_disponibles(entreprise)]

    assert codes == ['FT', 'FR']


def test_les_rectificatifs_ne_sont_pas_offerts_comme_forme_de_facture(
        entreprise, conformite):
    """« NC » et « ND » ont des séries actives, et ne sont pourtant pas
    des formes de facture : ils s'émettent depuis une facture DÉJÀ signée,
    jamais à sa place."""
    codes = [code for code, _ in
             facturation.formes_legales_disponibles(entreprise)]

    assert 'NC' not in codes and 'ND' not in codes


# ── Le fichier remis à l'administration ──────────────────────────────────────

def test_le_saft_porte_les_quatre_formes_et_reste_conforme(
        entreprise, cliente, conformite):
    """LA PREUVE DE BOUT EN BOUT.

    Quatre documents émis par le chemin réel, exportés, puis mesurés
    contre le schéma de l'AT et contre le contrôle de cohérence. C'est la
    seule mesure qui engage tout le trajet : formulaire, série, signature,
    gel des lignes, composition du fichier.
    """
    from apps.fiscal_pt import coherence, schema

    ordinaire = _facture(entreprise, cliente, 'FAC-1', Decimal('80.00'))
    simplifiee = _facture(entreprise, cliente, 'FAC-2', Decimal('80.00'))
    recu = _facture(entreprise, cliente, 'FAC-3', Decimal('80.00'))

    facturation.emettre_pour_facture(ordinaire, 'FT')
    facturation.emettre_pour_facture(simplifiee, 'FS')
    facturation.emettre_pour_facture(recu, 'FR', paiements=UN_PAIEMENT)
    facturation.emettre_une_note_de_debit(ordinaire, 'Acerto',
                                          LIGNES_EN_PLUS)

    octets = export.composer(entreprise, date(2026, 1, 1),
                             date(2026, 12, 31))
    racine = ET.fromstring(octets)

    assert schema.valider(racine) == []
    assert coherence.verifier(racine) == []

    types = [element.text for element in
             racine.iter(f'{ESPACE}InvoiceType')]
    assert sorted(types) == ['FR', 'FS', 'FT', 'ND']


def test_le_saft_porte_le_paiement_de_la_facture_recu(entreprise, cliente,
                                                      conformite):
    recu = _facture(entreprise, cliente, 'FAC-9', Decimal('80.00'))
    facturation.emettre_pour_facture(recu, 'FR', paiements=UN_PAIEMENT)

    racine = ET.fromstring(export.composer(entreprise, date(2026, 1, 1),
                                           date(2026, 12, 31)))
    paiement = racine.find(f'.//{ESPACE}Payment')

    assert paiement.find(f'{ESPACE}PaymentMechanism').text == 'TB'
    assert paiement.find(f'{ESPACE}PaymentAmount').text == '98.40'
    assert paiement.find(f'{ESPACE}PaymentDate').text == '2026-03-07'


def test_la_note_de_debit_designe_sa_facture_dans_le_fichier(petite_facture,
                                                             signee,
                                                             entreprise):
    """L'article 36.º n.º 6 exige « a referência à fatura a que
    respeitam ». Le schéma, lui, rend `References` optionnel : sans ce
    test, une note de débit orpheline passerait les deux contrôles."""
    facturation.emettre_une_note_de_debit(petite_facture, 'Acerto',
                                          LIGNES_EN_PLUS)

    racine = ET.fromstring(export.composer(entreprise, date(2026, 1, 1),
                                           date(2026, 12, 31)))
    renvois = [element.text for element in racine.iter(f'{ESPACE}Reference')]

    assert signee.numero in renvois


def test_la_note_de_debit_est_portee_au_credit_dans_le_fichier(
        petite_facture, signee, entreprise):
    """Elle rectifie comme un avoir et se compte comme une facture : elle
    AUGMENTE ce que le client doit. La porter au débit avec les avoirs
    donnerait un fichier qui s'équilibre à l'envers, et le validateur de
    l'AT ne le dit pas."""
    facturation.emettre_une_note_de_debit(petite_facture, 'Acerto',
                                          LIGNES_EN_PLUS)

    racine = ET.fromstring(export.composer(entreprise, date(2026, 1, 1),
                                           date(2026, 12, 31)))
    ventes = racine.find(f'{ESPACE}SourceDocuments/{ESPACE}SalesInvoices')

    # 80 € de la facture + 20 € de la note de débit, tous deux au crédit.
    assert ventes.find(f'{ESPACE}TotalCredit').text == '100.00'
    assert ventes.find(f'{ESPACE}TotalDebit').text == '0.00'


def test_le_code_qr_porte_la_forme_du_document(petite_facture, conformite):
    """Le champ D du code QR est le type du document. Un lecteur de QR le
    rend tel quel : « FS » doit y figurer, pas « FT »."""
    document = facturation.emettre_pour_facture(petite_facture, 'FS')

    champs = dict(partie.split(':', 1)
                  for partie in document.contenu_qr.split('*'))
    assert champs['D'] == 'FS'


# ── L'écran de la facture, réellement rendu ──────────────────────────────────
#
# POURQUOI CES TESTS SONT LES PLUS UTILES DU FICHIER
#
# Tout ce qui précède mesure des modules. Un gabarit, lui, échoue
# autrement : une variable que la vue oublie de passer rend une chaîne
# vide sans rien dire, et un bouton placé dans `page_actions` ne
# s'affiche pas du tout si la vue ne passe pas `page_title`. Dix écrans
# de ce paquet ont déjà été livrés avec un bouton invisible pour cette
# raison exacte.
#
# Ces tests rendent donc le HTML et le lisent.

from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory


def _afficher(facture, entreprise, utilisateur):
    """Rend l'écran de détail d'une facture et renvoie son HTML."""
    from apps.sales.views import invoice_detail

    requete = RequestFactory().get(f'/ventes/factures/{facture.pk}/')
    requete.user = utilisateur
    requete.current_company = entreprise
    requete.session = {}
    requete._messages = FallbackStorage(requete)
    # `django.shortcuts.render` rend la reponse IMMEDIATEMENT : elle
    # arrive donc deja rendue, et il n'y a pas de `render()` a appeler.
    # Un defaut du gabarit -- balise inconnue, filtre absent -- aurait
    # fait lever l'appel a la vue lui-meme, avec le fichier et la ligne.
    return invoice_detail(requete, facture.pk).content.decode()


def _envoyer(facture, entreprise, utilisateur, **champs):
    """Poste le formulaire d'envoi et renvoie les messages affichés."""
    from apps.sales.views import invoice_send

    requete = RequestFactory().post(f'/ventes/factures/{facture.pk}/envoyer/',
                                    champs)
    requete.user = utilisateur
    requete.current_company = entreprise
    requete.session = {}
    requete._messages = FallbackStorage(requete)
    invoice_send(requete, facture.pk)
    return [str(message) for message in requete._messages]


@pytest.fixture
def utilisateur(db, django_user_model):
    return django_user_model.objects.create_user(
        username='pedro-formes', password='mot-de-passe-de-test')


def test_l_ecran_offre_les_trois_formes_de_facture(petite_facture,
                                                   conformite, entreprise,
                                                   utilisateur):
    html = _afficher(petite_facture, entreprise, utilisateur)

    assert 'name="type_document"' in html
    for code in ('FT', 'FS', 'FR'):
        assert f'value="{code}"' in html
    # Un rectificatif n'est pas une forme de facture : il s'émet depuis
    # une facture DÉJÀ signée, jamais à sa place.
    assert 'value="NC"' not in html
    assert 'value="ND"' not in html


def test_l_ecran_n_offre_pas_une_forme_sans_serie(petite_facture, conformite,
                                                  entreprise, utilisateur):
    conformite['FS'].delete()

    html = _afficher(petite_facture, entreprise, utilisateur)

    assert 'value="FT"' in html
    assert 'value="FS"' not in html


def test_sans_conformite_le_bouton_d_envoi_reste_celui_d_avant(
        petite_facture, entreprise, utilisateur):
    """Une installation française ne doit voir AUCUNE différence."""
    html = _afficher(petite_facture, entreprise, utilisateur)

    assert 'name="type_document"' not in html
    assert 'invoice_send' in html or 'envoyer' in html.lower()


def test_la_forme_choisie_a_l_ecran_est_celle_qui_est_emise(petite_facture,
                                                            conformite,
                                                            entreprise,
                                                            utilisateur):
    messages = _envoyer(petite_facture, entreprise, utilisateur,
                        type_document='FS')

    petite_facture.refresh_from_db()
    assert petite_facture.number == 'FS A/1'
    assert petite_facture.status == 'sent'
    assert any('FS A/1' in message for message in messages)


def test_l_envoi_d_une_facture_recu_enregistre_l_encaissement(petite_facture,
                                                              conformite,
                                                              entreprise,
                                                              utilisateur):
    """Le MONTANT n'est pas posté : c'est le total.

    Une facture-reçu vaut quittance du total ; toute autre somme en
    ferait un document qui atteste un paiement partiel. Demander le
    montant n'offrirait que l'occasion de se tromper.
    """
    _envoyer(petite_facture, entreprise, utilisateur, type_document='FR',
             mecanisme='CC', date_encaissement='2026-03-07')

    document = DocumentFiscal.objects.get(serie__type_document='FR')
    assert document.paiements == [{'mecanisme': 'CC', 'montant': '98.40',
                                   'date': '2026-03-07'}]


def test_l_avertissement_de_plafond_remonte_jusqu_a_l_ecran(facture_limite,
                                                            conformite,
                                                            entreprise,
                                                            utilisateur):
    """La mise en garde est montrée APRÈS le succès, et non à sa place :
    le document est émis, et c'est un avertissement, pas un échec."""
    messages = _envoyer(facture_limite, entreprise, utilisateur,
                        type_document='FS')

    assert any('FS A/1' in message for message in messages)
    assert any('30141' in message for message in messages)


def test_un_envoi_refuse_laisse_la_facture_en_brouillon(grosse_facture,
                                                        conformite,
                                                        entreprise,
                                                        utilisateur):
    """L'ORDRE DES DEUX OPÉRATIONS.

    La signature est produite avant le changement de statut, dans la même
    transaction. Si elle échoue, la facture reste en brouillon et rien
    n'est remis au client. L'inverse paraît plus accommodant et serait
    bien pire : la facture partirait sans preuve.
    """
    messages = _envoyer(grosse_facture, entreprise, utilisateur,
                        type_document='FS')

    grosse_facture.refresh_from_db()
    assert grosse_facture.status == 'draft'
    assert grosse_facture.number == 'FAC-0002'
    assert any('plafond' in message for message in messages)


def test_un_type_qui_n_est_pas_une_forme_de_facture_est_refuse(
        petite_facture, conformite, entreprise, utilisateur):
    """« NC » posté à la main dans le formulaire d'envoi.

    Sans ce garde-fou, une facture s'émettrait comme note de crédit :
    elle serait portée au débit dans le SAF-T, le fichier s'équilibrerait
    à l'envers, et le validateur de l'AT ne le dirait pas.
    """
    messages = _envoyer(petite_facture, entreprise, utilisateur,
                        type_document='NC')

    petite_facture.refresh_from_db()
    assert petite_facture.status == 'draft'
    assert not DocumentFiscal.objects.exists()
    assert any('note de crédit' in message for message in messages)


def test_un_moyen_de_paiement_invente_est_refuse(petite_facture, conformite,
                                                 entreprise, utilisateur):
    messages = _envoyer(petite_facture, entreprise, utilisateur,
                        type_document='FR', mecanisme='XX',
                        date_encaissement='2026-03-07')

    petite_facture.refresh_from_db()
    assert petite_facture.status == 'draft'
    assert any('moyen de paiement' in message for message in messages)


def test_l_ecran_separe_les_avoirs_des_notes_de_debit(petite_facture, signee,
                                                      entreprise,
                                                      utilisateur):
    """Les deux sens ne se mélangent pas.

    Un avoir diminue ce qui est dû, une note de débit l'augmente. Les
    afficher ensemble sous le mot « avoirs » ferait lire une hausse comme
    une baisse — le contresens exact que ces deux documents permettent.
    """
    facturation.emettre_une_note_de_debit(petite_facture, 'Revisao',
                                          LIGNES_EN_PLUS)
    facturation.emettre_une_note_de_credit(petite_facture, 'Devolucao')

    html = _afficher(petite_facture, entreprise, utilisateur)

    assert 'NC A/1' in html and 'ND A/1' in html
    avant_avoirs = html.index('Avoirs emis')
    avant_notes = html.index('Notes de debit emises')
    assert html.index('NC A/1') > avant_avoirs
    assert html.index('ND A/1') > avant_notes


def test_l_ecran_montre_l_encaissement_en_clair(petite_facture, conformite,
                                                entreprise, utilisateur):
    """Le document ne garde que le CODE du moyen de paiement — « CC » —,
    parce que c'est lui que le SAF-T transporte. Afficher « CC » au client
    n'apprend rien à personne."""
    facturation.emettre_pour_facture(
        petite_facture, 'FR',
        paiements=[dict(UN_PAIEMENT[0], mecanisme='CC')])

    html = _afficher(petite_facture, entreprise, utilisateur)

    assert tipos.libelle_de_mecanisme('CC') in html


def test_l_ecran_montre_la_forme_legale_du_document(petite_facture,
                                                    conformite, entreprise,
                                                    utilisateur):
    """« FS A/1 » seul ne dit pas au lecteur que c'est une facture
    simplifiée : il faut connaître la nomenclature de l'AT."""
    facturation.emettre_pour_facture(petite_facture, 'FS')

    html = _afficher(petite_facture, entreprise, utilisateur)

    assert 'Fatura simplificada' in html
