"""Les garanties structurelles de la conformité portugaise.

Les tests de `test_fiscal_pt.py` vérifient les CALCULS contre les exemples
publiés par l'AT. Ceux-ci vérifient ce que la base de données garantit :
une série qui ne saute aucun numéro, un document qui ne change plus, une
chaîne de signatures continue.

Ce sont les trois points qu'un auditeur de certification met à l'épreuve,
et aucun ne se prouve en lisant le code — il faut l'exécuter.
"""
from datetime import date
from decimal import Decimal

import pytest
from cryptography.fernet import Fernet
from django.core.exceptions import ValidationError

from apps.core.models import Company
from apps.fiscal_pt import assinatura, taxas
from apps.fiscal_pt.models import CleDeSignature, DocumentFiscal, SerieFiscale


@pytest.fixture
def chiffrement(settings):
    """Une clé Fernet pour le test.

    Elle est générée à chaque fois : une clé en dur dans les tests finirait
    par servir de clé par défaut en production, et le dépôt deviendrait le
    secret.
    """
    settings.ORION_SECRET_ENCRYPTION_KEY = Fernet.generate_key().decode()
    return settings.ORION_SECRET_ENCRYPTION_KEY


@pytest.fixture
def entreprise(db):
    return Company.objects.create(name='Orion Lusitana', slug='orion-pt')


@pytest.fixture
def serie(entreprise, chiffrement):
    cle = CleDeSignature.creer(entreprise, commentaire='test')
    return SerieFiscale.objects.create(
        company=entreprise, type_document='FT', nom='A',
        code_de_validation='CSDF7T5H', cle=cle, region=taxas.CONTINENT)


def ligne(taux='23', base='100.00', tva='23.00', description='Servico'):
    """Une ligne de facture au format qu'attend `emettre`.

    Les lignes sont FIGEES dans le document a l'emission : le SAF-T exige
    le detail, et le relire plus tard depuis la facture d'origine
    laisserait l'export diverger de la signature.
    """
    return {'description': description, 'taux': Decimal(taux),
            'base': Decimal(base), 'tva': Decimal(tva),
            'quantite': Decimal('1'), 'prix_unitaire': Decimal(base)}


LIGNES = [ligne()]


# ── La clé ───────────────────────────────────────────────────────────────────

def test_la_cle_privee_n_est_pas_lisible_en_base(entreprise, chiffrement):
    """Une clé de signature en clair dans une sauvegarde de base permettrait
    de fabriquer des factures au nom de l’entreprise."""
    cle = CleDeSignature.creer(entreprise)

    assert 'PRIVATE KEY' not in cle.pem_privee_chiffree
    assert 'PRIVATE KEY' in cle.privee()


def test_une_nouvelle_cle_desactive_la_precedente(entreprise, chiffrement):
    """Deux clés actives feraient porter à des documents voisins des
    versions différentes sans raison, et la relecture choisirait au hasard."""
    premiere = CleDeSignature.creer(entreprise)
    seconde = CleDeSignature.creer(entreprise)

    premiere.refresh_from_db()
    assert premiere.est_active is False
    assert seconde.version == premiere.version + 1
    assert CleDeSignature.active_de(entreprise).pk == seconde.pk


def test_une_cle_illisible_le_dit_au_lieu_de_rendre_le_vide(
        entreprise, chiffrement, settings):
    """LE PIÈGE QUE CE TEST FERME.

    Le helper `decrypt_secret` du dépôt rend une chaîne VIDE quand le
    déchiffrement échoue. Avec lui, une clé Fernet changée donnerait une
    erreur « clé privée illisible » venue de la cryptographie, et on
    chercherait le défaut à des lieues de sa cause — la configuration.
    """
    cle = CleDeSignature.creer(entreprise)
    settings.ORION_SECRET_ENCRYPTION_KEY = Fernet.generate_key().decode()

    with pytest.raises(ValidationError, match='ORION_SECRET_ENCRYPTION_KEY'):
        cle.privee()


def test_emettre_sans_cle_active_le_dit_clairement(entreprise, chiffrement):
    sans_cle = SerieFiscale.objects.create(
        company=entreprise, type_document='FS', nom='B')

    with pytest.raises(ValidationError, match='Aucune clé de signature'):
        DocumentFiscal.emettre(
            serie=sans_cle, date_document=date(2026, 1, 2), lignes=LIGNES,
            nif_emetteur='123456789')


# ── La série et sa numérotation ──────────────────────────────────────────────

def test_le_numero_a_la_forme_exigee_par_le_saft(serie):
    """« FT A/1 ». Le schéma de l’AT valide InvoiceNo contre
    « [^ ]+ [^/^ ]+/[0-9]+ » : un export entier serait rejeté pour un
    numéro mal formé, et le numéro, lui, aurait l’air normal."""
    document = DocumentFiscal.emettre(
        serie=serie, date_document=date(2026, 1, 2), lignes=LIGNES,
        nif_emetteur='123456789')

    assert document.numero == 'FT A/1'


def test_une_serie_ne_saute_aucun_numero(serie):
    """La numérotation doit être séquentielle et sans trou."""
    numeros = [
        DocumentFiscal.emettre(serie=serie, date_document=date(2026, 1, 2),
                               lignes=LIGNES, nif_emetteur='123456789').numero
        for _ in range(5)]

    assert numeros == ['FT A/1', 'FT A/2', 'FT A/3', 'FT A/4', 'FT A/5']


def test_un_echec_d_emission_ne_brule_pas_le_numero(serie):
    """CE QUE CE TEST PROTÈGE.

    La numérotation de l’ERP pour les factures françaises attribuait le
    numéro AVANT d’enregistrer : un document qui échouait laissait un trou
    permanent. Ici tout est dans une transaction — un échec rend le
    numéro, et la série reste continue sans qu’on ait à combler quoi que
    ce soit.
    """
    DocumentFiscal.emettre(serie=serie, date_document=date(2026, 1, 2),
                           lignes=LIGNES, nif_emetteur='123456789')

    # Un taux qui n'existe pas au Portugal : l'émission doit échouer.
    with pytest.raises(taxas.TauxInconnu):
        DocumentFiscal.emettre(
            serie=serie, date_document=date(2026, 1, 3),
            lignes=[ligne(taux='20', tva='20.00')],
            nif_emetteur='123456789')

    suivant = DocumentFiscal.emettre(
        serie=serie, date_document=date(2026, 1, 4), lignes=LIGNES,
        nif_emetteur='123456789')

    assert suivant.numero == 'FT A/2'
    serie.refresh_from_db()
    assert serie.prochain_numero == 3


def test_une_serie_refuse_un_nom_avec_espace_ou_barre(entreprise):
    for mauvais in ('A B', 'A/B'):
        serie = SerieFiscale(company=entreprise, type_document='FT',
                             nom=mauvais)
        with pytest.raises(ValidationError):
            serie.clean()


def test_une_serie_non_communiquee_porte_un_atcud_a_zero(entreprise,
                                                         chiffrement):
    """Mieux vaut la marque explicite d’une série non déclarée qu’un ATCUD
    inventé : le premier se corrige, le second produit des mois de
    documents juridiquement nuls."""
    CleDeSignature.creer(entreprise)
    brute = SerieFiscale.objects.create(
        company=entreprise, type_document='FT', nom='Z')

    document = DocumentFiscal.emettre(
        serie=brute, date_document=date(2026, 1, 2), lignes=LIGNES,
        nif_emetteur='123456789')

    assert document.atcud == '0-1'


# ── L'immuabilité ────────────────────────────────────────────────────────────

def test_un_document_emis_ne_peut_plus_etre_modifie(serie):
    """LA GARANTIE CENTRALE. Modifier un document ne casse pas seulement sa
    preuve : il rend invérifiables tous ceux qui l’ont suivi."""
    document = DocumentFiscal.emettre(
        serie=serie, date_document=date(2026, 1, 2), lignes=LIGNES,
        nif_emetteur='123456789')

    document.total = Decimal('1.00')
    with pytest.raises(ValidationError, match='déjà émis'):
        document.save()

    document.refresh_from_db()
    assert document.total == Decimal('123.00')


def test_un_document_rechargé_puis_modifie_est_refuse_aussi(serie):
    """Le contrôle porte sur l’existence EN BASE, pas sur `self.pk`. Un
    objet rechargé a bien un pk, et c’est exactement le cas à arrêter —
    un contrôle sur `self.pk is None` laisserait passer celui-là."""
    DocumentFiscal.emettre(serie=serie, date_document=date(2026, 1, 2),
                           lignes=LIGNES, nif_emetteur='123456789')

    recharge = DocumentFiscal.objects.get(numero='FT A/1')
    recharge.signature = 'x' * 172

    with pytest.raises(ValidationError):
        recharge.save()


def test_un_document_emis_ne_peut_pas_etre_supprime(serie):
    document = DocumentFiscal.emettre(
        serie=serie, date_document=date(2026, 1, 2), lignes=LIGNES,
        nif_emetteur='123456789')

    with pytest.raises(ValidationError, match='chaîne'):
        document.delete()

    assert DocumentFiscal.objects.filter(pk=document.pk).exists()


# ── La chaîne ────────────────────────────────────────────────────────────────

def test_chaque_document_signe_le_precedent_de_sa_serie(serie):
    premier = DocumentFiscal.emettre(
        serie=serie, date_document=date(2026, 1, 2), lignes=LIGNES,
        nif_emetteur='123456789')
    second = DocumentFiscal.emettre(
        serie=serie, date_document=date(2026, 1, 3), lignes=LIGNES,
        nif_emetteur='123456789')

    assert premier.signature_precedente == ''
    assert second.signature_precedente == premier.signature
    assert second.message_signe.endswith(';' + premier.signature)


def test_deux_series_ont_deux_chaines_independantes(entreprise, chiffrement):
    """Une chaîne par série, et c’est ce que le texte demande. Les mélanger
    rendrait l’ordre d’émission entre séries significatif, ce qu’il n’est
    pas."""
    cle = CleDeSignature.creer(entreprise)
    a = SerieFiscale.objects.create(company=entreprise, type_document='FT',
                                    nom='A', cle=cle)
    b = SerieFiscale.objects.create(company=entreprise, type_document='FT',
                                    nom='B', cle=cle)

    DocumentFiscal.emettre(serie=a, date_document=date(2026, 1, 2),
                           lignes=LIGNES, nif_emetteur='123456789')
    premier_de_b = DocumentFiscal.emettre(
        serie=b, date_document=date(2026, 1, 3), lignes=LIGNES,
        nif_emetteur='123456789')

    assert premier_de_b.numero == 'FT B/1'
    assert premier_de_b.signature_precedente == ''


def test_toute_la_chaine_se_reverifie(serie):
    """C’est l’opération que fait l’administration au contrôle. Une chaîne
    cassée se découvre bien mieux chez soi."""
    for jour in range(2, 7):
        DocumentFiscal.emettre(serie=serie, date_document=date(2026, 1, jour),
                               lignes=LIGNES, nif_emetteur='123456789')

    documents = DocumentFiscal.objects.filter(serie=serie).order_by(
        'numero_sequentiel')
    assert documents.count() == 5
    assert all(document.verifier() for document in documents)


def test_une_signature_falsifiee_en_base_est_detectee(serie):
    """Le refus de `save()` protège le chemin applicatif. Un UPDATE SQL
    direct, lui, passe — et c’est précisément pour cela que la
    revérification existe."""
    document = DocumentFiscal.emettre(
        serie=serie, date_document=date(2026, 1, 2), lignes=LIGNES,
        nif_emetteur='123456789')

    DocumentFiscal.objects.filter(pk=document.pk).update(
        message_signe=document.message_signe.replace('123.00', '1.00'))

    assert DocumentFiscal.objects.get(pk=document.pk).verifier() is False


def test_la_version_de_la_cle_est_conservee(entreprise, chiffrement):
    """Sans elle, une rotation de clé rendrait invérifiable tout
    l’historique : on ne saurait plus quelle clé publique employer."""
    premiere = CleDeSignature.creer(entreprise)
    serie = SerieFiscale.objects.create(company=entreprise,
                                        type_document='FT', nom='A')
    ancien = DocumentFiscal.emettre(
        serie=serie, date_document=date(2026, 1, 2), lignes=LIGNES,
        nif_emetteur='123456789')

    CleDeSignature.creer(entreprise)  # rotation
    recent = DocumentFiscal.emettre(
        serie=serie, date_document=date(2026, 1, 3), lignes=LIGNES,
        nif_emetteur='123456789')

    assert ancien.version_cle == premiere.version
    assert recent.version_cle == premiere.version + 1
    # Les deux restent vérifiables, chacun avec SA clé.
    assert ancien.verifier() is True
    assert recent.verifier() is True


# ── Les montants et le code QR ───────────────────────────────────────────────

def test_les_totaux_se_calculent_depuis_les_lignes(serie):
    document = DocumentFiscal.emettre(
        serie=serie, date_document=date(2026, 1, 2),
        lignes=[ligne(), ligne(taux='6', base='50.00', tva='3.00'),
                ligne(taux='0', base='10.00', tva='0.00')],
        nif_emetteur='123456789')

    assert document.total_base == Decimal('160.00')
    assert document.total_taxes == Decimal('26.00')
    assert document.total == Decimal('186.00')


def test_le_qr_ventile_par_palier_et_non_par_taux(serie):
    """Le code QR ne demande pas « 23 % » mais la base et la TVA du palier
    NORMAL. La traduction dépend de la région — un taux de 22 % est normal
    à Madère et n’existe pas sur le continent."""
    document = DocumentFiscal.emettre(
        serie=serie, date_document=date(2026, 1, 2),
        lignes=[ligne(), ligne(taux='6', base='50.00', tva='3.00')],
        nif_emetteur='123456789')

    assert '*I1:PT*' in document.contenu_qr
    assert '*I7:100.00*' in document.contenu_qr   # base normale
    assert '*I8:23.00*' in document.contenu_qr    # TVA normale
    assert '*I3:50.00*' in document.contenu_qr    # base réduite
    assert '*I4:3.00*' in document.contenu_qr     # TVA réduite


def test_madere_classe_22_pourcent_en_taux_normal(entreprise, chiffrement):
    CleDeSignature.creer(entreprise)
    madere = SerieFiscale.objects.create(
        company=entreprise, type_document='FT', nom='M',
        region=taxas.MADERE)

    document = DocumentFiscal.emettre(
        serie=madere, date_document=date(2026, 1, 2),
        lignes=[ligne(taux='22', tva='22.00')],
        nif_emetteur='123456789')

    assert '*I1:PT-MA*' in document.contenu_qr
    assert '*I7:100.00*' in document.contenu_qr


def test_un_taux_etranger_arrete_l_emission(serie):
    """Un taux français de 20 % sur une facture portugaise doit arrêter
    l’émission, pas se faire ranger dans le palier le plus proche."""
    with pytest.raises(taxas.TauxInconnu, match='20'):
        DocumentFiscal.emettre(
            serie=serie, date_document=date(2026, 1, 2),
            lignes=[ligne(taux='20', tva='20.00')],
            nif_emetteur='123456789')


def test_sans_acquereur_le_qr_porte_le_nif_conventionnel(serie):
    document = DocumentFiscal.emettre(
        serie=serie, date_document=date(2026, 1, 2), lignes=LIGNES,
        nif_emetteur='123456789')

    assert '*B:999999990*' in document.contenu_qr


def test_le_qr_et_la_mention_imprimee_s_accordent(serie):
    """Les quatre caractères du pied de page et le champ Q du code QR
    viennent de la même signature. Les calculer deux fois par deux chemins
    est le meilleur moyen de les voir diverger."""
    document = DocumentFiscal.emettre(
        serie=serie, date_document=date(2026, 1, 2), lignes=LIGNES,
        nif_emetteur='123456789')

    quatre = assinatura.caracteres_imprimes(document.signature)
    assert f'*Q:{quatre}*' in document.contenu_qr
    assert document.mention_legale('1234').startswith(quatre)
    assert document.mention_legale('1234').endswith('n.º 1234/AT')


# ── Le lien avec le document d'origine ───────────────────────────────────────

def test_le_document_source_est_tracable(serie, entreprise):
    """Sans ce lien, on ne saurait pas quelle facture de l’ERP correspond à
    quel document fiscal — et le rapprochement se ferait à la main."""
    from apps.crm.models import Customer
    from apps.sales.models import Invoice

    client = Customer.objects.create(company=entreprise, name='Cliente Lda')
    facture = Invoice.objects.create(company=entreprise, customer=client,
                                     number='provisoire')

    document = DocumentFiscal.emettre(
        serie=serie, date_document=date(2026, 1, 2), lignes=LIGNES,
        nif_emetteur='123456789', source=facture)

    assert document.source_app == 'sales'
    assert document.source_modele == 'invoice'
    assert document.source_id == facture.pk


def test_les_lignes_sont_figees_dans_le_document(serie):
    """Le SAF-T exige le detail ligne par ligne. Le relire a l'export
    depuis la facture d'origine ouvrirait une divergence silencieuse : la
    facture peut avoir change, la signature non."""
    document = DocumentFiscal.emettre(
        serie=serie, date_document=date(2026, 1, 2),
        lignes=[ligne(description='Instalacao eletrica')],
        nif_emetteur='123456789')

    document.refresh_from_db()
    assert len(document.lignes) == 1
    figee = document.lignes[0]
    assert figee['description'] == 'Instalacao eletrica'
    assert figee['code_de_taux'] == 'NOR'
    # Les montants sont du TEXTE, jamais des flottants : un float perd des
    # centimes sur de gros totaux, et la signature porte sur le total.
    assert figee['base'] == '100.00'
    assert isinstance(figee['base'], str)


def test_une_ligne_sans_description_est_refusee(serie):
    """Le SAF-T exige « ProductDescription » sur chaque ligne."""
    with pytest.raises(ValidationError, match='description'):
        DocumentFiscal.emettre(
            serie=serie, date_document=date(2026, 1, 2),
            lignes=[{'base': Decimal('10'), 'taux': Decimal('23')}],
            nif_emetteur='123456789')


def test_un_document_sans_ligne_est_refuse(serie):
    with pytest.raises(ValidationError, match='sans ligne'):
        DocumentFiscal.emettre(
            serie=serie, date_document=date(2026, 1, 2), lignes=[],
            nif_emetteur='123456789')


def test_un_code_produit_est_deduit_et_reste_stable(serie):
    """Le SAF-T exige un « ProductCode » sur chaque ligne, et chaque code
    employe doit figurer dans le referentiel. Un code deduit de la
    description, stable pour une meme description, permet de construire un
    referentiel coherent sans rien demander a l'utilisateur."""
    premier = DocumentFiscal.emettre(
        serie=serie, date_document=date(2026, 1, 2),
        lignes=[ligne(description='Mesmo servico')],
        nif_emetteur='123456789')
    second = DocumentFiscal.emettre(
        serie=serie, date_document=date(2026, 1, 3),
        lignes=[ligne(description='Mesmo servico')],
        nif_emetteur='123456789')

    assert premier.lignes[0]['code_produit'] == second.lignes[0]['code_produit']
    assert premier.lignes[0]['code_produit'].startswith('SRV')
