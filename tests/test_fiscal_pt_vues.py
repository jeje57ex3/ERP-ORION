"""Les écrans de conformité portugaise.

POURQUOI DES TESTS D'ÉCRAN ICI

Une obligation fiscale qui demanderait un accès au serveur est une
obligation qu'on n'honore pas le jour où il le faut. Ces tests vérifient
donc que chaque geste — créer une clé, déclarer une série, saisir le code
de l'AT, vérifier la chaîne, produire le SAF-T — se fait réellement à
l'écran, et qu'un bouton annoncé est bien présent dans le HTML rendu.

Le dernier point n'est pas théorique : un bouton de diagnostic ajouté
plus tôt dans ce dépôt se trouvait enfermé dans une condition qui le
masquait précisément quand il servait. Il avait l'air écrit, et il
n'apparaissait pas.
"""
from datetime import date
from decimal import Decimal
from xml.etree import ElementTree as ET

import pytest
from cryptography.fernet import Fernet
from django.urls import reverse

from apps.core.models import Company
from apps.fiscal_pt.models import (CleDeSignature, DocumentFiscal,
                                   ParametresFiscauxPT, SerieFiscale)


@pytest.fixture
def chiffrement(settings):
    settings.ORION_SECRET_ENCRYPTION_KEY = Fernet.generate_key().decode()


@pytest.fixture
def entreprise(db):
    return Company.objects.create(name='Orion Lusitana', slug='orion-pt-vues')


@pytest.fixture
def utilisateur(db, django_user_model, entreprise):
    return django_user_model.objects.create_user(
        username='pedro', password='mot-de-passe-de-test', is_staff=True)


@pytest.fixture
def navigateur(client, utilisateur, entreprise, monkeypatch):
    """Un client authentifié dont l'entreprise courante est fixée.

    `request.current_company` est posé par un middleware qui dépend du
    rattachement de l'utilisateur. On le force ici pour tester les écrans
    et non le middleware, qui a ses propres tests.
    """
    client.force_login(utilisateur)

    from apps.fiscal_pt import views
    monkeypatch.setattr(views, '_company', lambda request: entreprise)
    return client


def ligne(taux='23', base='100.00', tva='23.00'):
    return {'description': 'Servico', 'taux': Decimal(taux),
            'base': Decimal(base), 'tva': Decimal(tva),
            'quantite': Decimal('1'), 'prix_unitaire': Decimal(base)}


# ── L'écran d'état ───────────────────────────────────────────────────────────

def test_l_etat_de_conformite_s_affiche_sans_rien_de_configure(navigateur,
                                                               entreprise):
    """L'écran doit fonctionner AVANT que quoi que ce soit soit en place :
    c'est précisément là qu'on en a besoin."""
    reponse = navigateur.get(reverse('fiscal_pt:index'))

    assert reponse.status_code == 200
    assert reponse.context['prets'] == 0
    assert reponse.context['total_etapes'] == 5


def test_l_etat_compte_les_etapes_franchies(navigateur, entreprise,
                                            chiffrement):
    parametres = ParametresFiscauxPT.de(entreprise)
    parametres.nif = '123456789'
    parametres.save()
    CleDeSignature.creer(entreprise)
    SerieFiscale.objects.create(company=entreprise, type_document='FT',
                                nom='A', code_de_validation='CSDF7T5H')

    reponse = navigateur.get(reverse('fiscal_pt:index'))

    # NIF, clé, séries, codes de validation — mais pas le n° de certificat,
    # qui dépend de l'AT et non de nous.
    assert reponse.context['prets'] == 4


def test_chaque_etape_pointe_vers_un_ecran_existant(navigateur):
    """Une étape dont le lien casse est une étape qu'on ne peut pas
    franchir. Le gabarit appelle `{% url %}` sur chaque nom : un nom
    inexistant lèverait au rendu, et ce test le verrait."""
    reponse = navigateur.get(reverse('fiscal_pt:index'))

    assert reponse.status_code == 200
    for etape in reponse.context['etapes']:
        assert reverse(etape['lien'])


def test_les_boutons_annonces_sont_dans_le_html(navigateur):
    """Les deux actions principales doivent être ATTEINTES, pas seulement
    écrites dans le code de la vue."""
    html = navigateur.get(reverse('fiscal_pt:index')).content.decode()

    assert reverse('fiscal_pt:verification') in html
    assert reverse('fiscal_pt:export_saft') in html
    assert reverse('fiscal_pt:serie_creer') in html


# ── Les clés ─────────────────────────────────────────────────────────────────

def test_une_cle_se_cree_depuis_l_ecran(navigateur, entreprise, chiffrement):
    reponse = navigateur.post(reverse('fiscal_pt:cle_creer'),
                              {'commentaire': 'première clé'}, follow=True)

    assert reponse.status_code == 200
    cle = CleDeSignature.objects.get(company=entreprise)
    assert cle.version == 1
    assert cle.est_active is True
    assert 'PRIVATE KEY' not in cle.pem_privee_chiffree


def test_une_creation_de_cle_sans_chiffrement_configure_le_dit(navigateur,
                                                               settings):
    """Sans clé Fernet, la création doit ÉCHOUER AVEC UN MESSAGE — pas
    enregistrer une clé privée vide qui ne signerait rien et ne se
    découvrirait qu'à la première facture."""
    settings.ORION_SECRET_ENCRYPTION_KEY = ''

    reponse = navigateur.post(reverse('fiscal_pt:cle_creer'), follow=True)

    assert reponse.status_code == 200
    assert CleDeSignature.objects.count() == 0
    messages = [str(m) for m in reponse.context['messages']]
    assert any('ORION_SECRET_ENCRYPTION_KEY' in m for m in messages)


def test_l_ecran_des_cles_s_affiche(navigateur, entreprise, chiffrement):
    CleDeSignature.creer(entreprise)
    reponse = navigateur.get(reverse('fiscal_pt:cles'))

    assert reponse.status_code == 200
    assert b'1024' in reponse.content  # la contrainte légale est annoncée


# ── Les séries ───────────────────────────────────────────────────────────────

def test_une_serie_se_cree_depuis_l_ecran(navigateur, entreprise,
                                          chiffrement):
    CleDeSignature.creer(entreprise)
    reponse = navigateur.post(reverse('fiscal_pt:serie_creer'), {
        'type_document': 'FT', 'nom': 'A', 'region': 'PT',
        'code_de_validation': 'CSDF7T5H', 'cle': '', 'est_active': 'on',
    }, follow=True)

    assert reponse.status_code == 200
    serie = SerieFiscale.objects.get(company=entreprise)
    assert serie.nom == 'A'
    assert serie.code_de_validation == 'CSDF7T5H'


def test_un_code_de_validation_invente_est_refuse_a_l_ecran(navigateur,
                                                            entreprise):
    reponse = navigateur.post(reverse('fiscal_pt:serie_creer'), {
        'type_document': 'FT', 'nom': 'A', 'region': 'PT',
        'code_de_validation': 'court', 'cle': '', 'est_active': 'on',
    })

    assert reponse.status_code == 200
    assert SerieFiscale.objects.count() == 0
    assert 'code_de_validation' in reponse.context['form'].errors


def test_le_choix_de_cle_ne_propose_que_celles_de_l_entreprise(
        navigateur, entreprise, chiffrement):
    """LA FUITE QUE CE TEST FERME.

    Un `ModelChoiceField` non filtré propose TOUTES les clés de
    l'installation. Une entreprise pourrait signer ses factures avec la
    clé d'une autre, et rien à l'écran ne le signalerait.
    """
    autre = Company.objects.create(name='Autre SA', slug='autre-pt')
    CleDeSignature.creer(entreprise)
    cle_etrangere = CleDeSignature.creer(autre)

    reponse = navigateur.get(reverse('fiscal_pt:serie_creer'))
    propositions = reponse.context['form'].fields['cle'].queryset

    assert cle_etrangere not in propositions
    assert propositions.count() == 1


def test_le_prochain_numero_n_est_pas_modifiable_a_l_ecran(navigateur,
                                                           entreprise):
    """Le reculer produirait des doublons, l'avancer un trou permanent."""
    serie = SerieFiscale.objects.create(company=entreprise,
                                        type_document='FT', nom='A')
    reponse = navigateur.get(
        reverse('fiscal_pt:serie_modifier', args=[serie.pk]))

    assert 'prochain_numero' not in reponse.context['form'].fields


def test_une_serie_d_une_autre_entreprise_est_introuvable(navigateur,
                                                          entreprise):
    autre = Company.objects.create(name='Autre SA', slug='autre-pt-2')
    etrangere = SerieFiscale.objects.create(company=autre,
                                            type_document='FT', nom='A')

    reponse = navigateur.get(
        reverse('fiscal_pt:serie_modifier', args=[etrangere.pk]))

    assert reponse.status_code == 404


# ── Les documents ────────────────────────────────────────────────────────────

@pytest.fixture
def document(entreprise, chiffrement):
    cle = CleDeSignature.creer(entreprise)
    serie = SerieFiscale.objects.create(
        company=entreprise, type_document='FT', nom='A',
        code_de_validation='CSDF7T5H', cle=cle)
    parametres = ParametresFiscauxPT.de(entreprise)
    parametres.nif = '123456789'
    parametres.save()
    return DocumentFiscal.emettre(
        serie=serie, date_document=date(2026, 3, 7), lignes=[ligne()],
        nif_emetteur='123456789')


def test_le_detail_d_un_document_montre_la_preuve(navigateur, document):
    reponse = navigateur.get(
        reverse('fiscal_pt:document_detail', args=[document.pk]))

    assert reponse.status_code == 200
    assert reponse.context['verifie'] is True
    contenu = reponse.content.decode()
    assert document.signature in contenu
    assert document.message_signe in contenu
    assert document.atcud in contenu


def test_le_code_qr_se_sert_en_png(navigateur, document):
    reponse = navigateur.get(
        reverse('fiscal_pt:document_qr', args=[document.pk]))

    assert reponse.status_code == 200
    assert reponse['Content-Type'] == 'image/png'
    octets = b''.join(reponse.streaming_content)
    assert octets.startswith(b'\x89PNG\r\n\x1a\n')


def test_un_document_d_une_autre_entreprise_est_introuvable(navigateur,
                                                            document):
    autre = Company.objects.create(name='Autre SA', slug='autre-pt-3')
    cle = CleDeSignature.creer(autre)
    serie = SerieFiscale.objects.create(company=autre, type_document='FT',
                                        nom='A', cle=cle)
    etranger = DocumentFiscal.emettre(
        serie=serie, date_document=date(2026, 3, 7), lignes=[ligne()],
        nif_emetteur='500000000')

    reponse = navigateur.get(
        reverse('fiscal_pt:document_detail', args=[etranger.pk]))

    assert reponse.status_code == 404


# ── La vérification ──────────────────────────────────────────────────────────

def test_la_verification_annonce_une_chaine_intacte(navigateur, document):
    reponse = navigateur.get(reverse('fiscal_pt:verification'))

    assert reponse.status_code == 200
    assert reponse.context['tout_intact'] is True


def test_la_verification_detecte_une_signature_falsifiee(navigateur,
                                                         document):
    """Un UPDATE direct contourne le refus de `save()`. C'est précisément
    pour cela que la revérification existe."""
    DocumentFiscal.objects.filter(pk=document.pk).update(
        message_signe='falsifie')

    reponse = navigateur.get(reverse('fiscal_pt:verification'))

    assert reponse.context['tout_intact'] is False
    rapport = reponse.context['rapport'][0]
    assert any('signature invalide' in r for r in rapport['ruptures'])


def test_la_verification_detecte_un_document_retire_du_milieu(navigateur,
                                                              document):
    """LE CAS QUE LA SEULE VÉRIFICATION DE SIGNATURE NE VOIT PAS.

    Les signatures restantes sont toutes valides ; c'est la CHAÎNE qui est
    rompue. Deux contrôles distincts sont donc nécessaires, et c'est ce
    qu'un auditeur cherche.
    """
    serie = document.serie
    for jour in (8, 9):
        DocumentFiscal.emettre(serie=serie, date_document=date(2026, 3, jour),
                               lignes=[ligne()], nif_emetteur='123456789')

    # On retire le deuxième par la base, puisque le modèle l'interdit.
    DocumentFiscal.objects.filter(serie=serie, numero_sequentiel=2).delete()

    reponse = navigateur.get(reverse('fiscal_pt:verification'))
    rapport = reponse.context['rapport'][0]

    assert reponse.context['tout_intact'] is False
    assert any('ne suit pas' in r for r in rapport['ruptures'])


# ── Le SAF-T ─────────────────────────────────────────────────────────────────

def test_le_saft_se_telecharge_depuis_l_ecran(navigateur, document):
    reponse = navigateur.post(reverse('fiscal_pt:export_saft'),
                              {'debut': '2026-01-01', 'fin': '2026-12-31'})

    assert reponse.status_code == 200
    assert reponse['Content-Type'] == 'application/xml'
    assert 'attachment' in reponse['Content-Disposition']
    assert '123456789' in reponse['Content-Disposition']

    racine = ET.fromstring(reponse.content)
    espace = '{urn:OECD:StandardAuditFile-Tax:PT_1.04_01}'
    numeros = [e.text for e in racine.iter(f'{espace}InvoiceNo')]
    assert numeros == ['FT A/1']


def test_le_saft_porte_la_signature_et_la_version_de_cle(navigateur,
                                                          document):
    reponse = navigateur.post(reverse('fiscal_pt:export_saft'),
                              {'debut': '2026-01-01', 'fin': '2026-12-31'})
    racine = ET.fromstring(reponse.content)
    espace = '{urn:OECD:StandardAuditFile-Tax:PT_1.04_01}'

    assert next(racine.iter(f'{espace}Hash')).text == document.signature
    assert next(racine.iter(f'{espace}HashControl')).text == '1'
    assert next(racine.iter(f'{espace}ATCUD')).text == document.atcud


def test_le_saft_exporte_les_lignes_figees_et_non_la_facture_vivante(
        navigateur, document):
    """LA DIVERGENCE QUE CE TEST FERME.

    Si l'export relisait la facture d'origine, modifier celle-ci
    changerait le fichier remis à l'administration alors que la signature,
    elle, resterait celle du contenu d'origine. Le fichier ne
    correspondrait plus à sa propre preuve, et rien ne le signalerait.
    """
    reponse = navigateur.post(reverse('fiscal_pt:export_saft'),
                              {'debut': '2026-01-01', 'fin': '2026-12-31'})
    racine = ET.fromstring(reponse.content)
    espace = '{urn:OECD:StandardAuditFile-Tax:PT_1.04_01}'

    assert next(racine.iter(f'{espace}CreditAmount')).text == '100.00'
    assert next(racine.iter(f'{espace}GrossTotal')).text == '123.00'


def test_une_periode_a_l_envers_est_refusee(navigateur, document):
    reponse = navigateur.post(reverse('fiscal_pt:export_saft'),
                              {'debut': '2026-12-31', 'fin': '2026-01-01'})

    assert reponse.status_code == 200
    assert reponse.context['form'].errors


def test_un_export_sans_nif_le_dit_au_lieu_d_echouer(navigateur, entreprise,
                                                     chiffrement):
    """Un fichier sans NIF est rejeté en entier par l'AT. Autant le dire
    ici, où l'information existe encore."""
    reponse = navigateur.post(reverse('fiscal_pt:export_saft'),
                              {'debut': '2026-01-01', 'fin': '2026-12-31'},
                              follow=True)

    messages = [str(m) for m in reponse.context['messages']]
    assert any('NIF' in m for m in messages)


# ── Les paramètres ───────────────────────────────────────────────────────────

def test_les_parametres_s_enregistrent_depuis_l_ecran(navigateur, entreprise):
    reponse = navigateur.post(reverse('fiscal_pt:parametres'), {
        'est_actif': 'on', 'nif': '123456789', 'numero_de_certificat': '1234',
        'region_par_defaut': 'PT', 'nom_editeur': 'Orion',
        'nif_editeur': '500000000', 'version_produit': '1.0',
    }, follow=True)

    assert reponse.status_code == 200
    parametres = ParametresFiscauxPT.de(entreprise)
    assert parametres.nif == '123456789'
    assert parametres.numero_de_certificat == '1234'
    assert parametres.est_actif is True


def test_activer_sans_nif_est_refuse(navigateur, entreprise):
    """Le NIF figure dans le code QR et dans le SAF-T : activer sans lui
    produirait des documents inexploitables."""
    reponse = navigateur.post(reverse('fiscal_pt:parametres'), {
        'est_actif': 'on', 'nif': '', 'numero_de_certificat': '0',
        'region_par_defaut': 'PT', 'nom_editeur': 'Orion',
        'nif_editeur': '', 'version_produit': '1.0',
    })

    assert reponse.status_code == 200
    assert 'nif' in reponse.context['form'].errors
    assert ParametresFiscauxPT.de(entreprise).est_actif is False


def test_un_numero_de_certificat_fantaisiste_est_refuse(navigateur):
    reponse = navigateur.post(reverse('fiscal_pt:parametres'), {
        'est_actif': '', 'nif': '123456789',
        'numero_de_certificat': 'ABCD', 'region_par_defaut': 'PT',
        'nom_editeur': 'Orion', 'nif_editeur': '', 'version_produit': '1.0',
    })

    assert 'numero_de_certificat' in reponse.context['form'].errors
