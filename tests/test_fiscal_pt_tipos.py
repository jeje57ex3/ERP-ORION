"""Les règles propres à chaque type de document.

CE QUE CES TESTS MESURENT, ET POURQUOI C'EST LE SEUL MOYEN

Les trois documents que ce module interdit — une note de débit sans
référence, une facture-reçu sans paiement, une facture simplifiée hors
plafond — passent TOUS LES TROIS le schéma de l'AT et le contrôle de
cohérence arithmétique. Rien dans le fichier ne les signale. Un test qui
se contenterait de vérifier qu'un document régulier est accepté passerait
donc aussi avec un module entièrement vide.

Chaque test part donc d'un cas RÉGULIER et le casse d'une seule façon.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.fiscal_pt import tipos


# ── Rectificatif n'est pas « porté au débit » ────────────────────────────────

def test_les_deux_listes_ne_sont_pas_la_meme():
    """Le défaut d'origine, gardé sous test.

    Une seule liste servait aux deux usages — le sens débit/crédit ET
    l'obligation de désigner la facture rectifiée. Tant que seule la note
    de crédit existait, les deux coïncidaient. La note de débit les
    sépare : elle rectifie, et son montant va au crédit.

    Si quelqu'un réunifie les deux constantes, ce test tombe avant que la
    première note de débit irrégulière ne soit émise.
    """
    from apps.fiscal_pt.saft import TYPES_AU_DEBIT

    assert 'ND' in tipos.TYPES_RECTIFICATIFS
    assert 'ND' not in TYPES_AU_DEBIT
    assert set(tipos.TYPES_RECTIFICATIFS) != set(TYPES_AU_DEBIT)


@pytest.mark.parametrize('type_document', ['NC', 'ND'])
def test_un_rectificatif_sans_facture_designee_est_refuse(type_document):
    with pytest.raises(tipos.RegleDeType) as erreur:
        tipos.verifier(type_document, Decimal('100'), Decimal('123'))

    assert '36' in str(erreur.value)


@pytest.mark.parametrize('type_document', ['NC', 'ND'])
def test_un_rectificatif_qui_designe_sa_facture_passe(type_document):
    assert tipos.verifier(type_document, Decimal('100'), Decimal('123'),
                          document_rectifie=object()) == []


@pytest.mark.parametrize('type_document', ['FT', 'FS', 'FR'])
def test_un_type_qui_ne_rectifie_rien_refuse_une_facture_designee(
        type_document):
    paiements = ([{'mecanisme': 'NU', 'montant': Decimal('123'),
                   'date': date(2026, 11, 19)}]
                 if type_document == 'FR' else None)

    with pytest.raises(tipos.RegleDeType) as erreur:
        tipos.verifier(type_document, Decimal('100'), Decimal('123'),
                       document_rectifie=object(), paiements=paiements)

    assert 'ne rectifie rien' in str(erreur.value)


def test_le_message_nomme_les_deux_sens():
    """Un message qui dirait seulement « employez NC » enverrait émettre un
    avoir là où il faut une note de débit — l'inverse exact du besoin."""
    with pytest.raises(tipos.RegleDeType) as erreur:
        tipos.verifier('FT', Decimal('100'), Decimal('123'),
                       document_rectifie=object())

    message = str(erreur.value)
    assert 'NC' in message and 'ND' in message


# ── La facture simplifiée et son plafond ─────────────────────────────────────

def test_le_plafond_ordinaire_est_de_cent_euros():
    """Article 40.º n.º 1 b) du CIVA, cas d'une entreprise de travaux."""
    assert tipos.plafond_simplifiee('b') == Decimal('100')


def test_le_plafond_du_detaillant_est_de_mille_euros():
    """Article 40.º n.º 1 a) : détaillants et marchands ambulants."""
    assert tipos.plafond_simplifiee('a') == Decimal('1000')


def test_le_regime_de_l_article_53_n_a_pas_de_plafond():
    """Article 40.º n.º 1 c), ajouté par le Decreto-Lei n.º 35/2025."""
    assert tipos.plafond_simplifiee('c') is None


def test_un_regime_inconnu_est_refuse():
    with pytest.raises(tipos.RegleDeType):
        tipos.plafond_simplifiee('z')


def test_une_facture_simplifiee_sous_le_plafond_passe_sans_un_mot():
    assert tipos.verifier('FS', Decimal('80'), Decimal('98.40')) == []


def test_une_facture_simplifiee_hors_plafond_hors_taxe_est_refusee():
    with pytest.raises(tipos.RegleDeType) as erreur:
        tipos.verifier('FS', Decimal('120'), Decimal('147.60'))

    message = str(erreur.value)
    assert '120' in message and '100' in message
    assert 'déduire la TVA' in message


def test_la_bande_de_divergence_avertit_sans_bloquer():
    """Les deux lectures du plafond, et ce qu'on en fait.

    L'article 40.º plafonne « o montante da fatura » — le total à payer.
    L'Ofício-Circulado n.º 30141/2013 dit que le montant s'entend hors
    TVA. Les deux divergent entre 100 € hors taxe et 100 € à payer.

    Bloquer serait refuser ce que l'administration accepte ; se taire
    serait laisser signer un document qu'un contrôle peut reprendre. On
    avertit, et la facture s'émet.
    """
    avertissements = tipos.verifier('FS', Decimal('95'), Decimal('116.85'))

    assert len(avertissements) == 1
    assert '30141' in avertissements[0]
    assert 'comptable' in avertissements[0]


def test_l_avertissement_ne_parle_pas_en_notation_exponentielle():
    """`Decimal.normalize()` rend « 1E+3 » pour 1000.

    Le piège se referme au moment précis où le message sert à quelque
    chose : sur un plafond rond.
    """
    avertissements = tipos.verifier('FS', Decimal('900'), Decimal('1107'),
                                    regime='a')

    assert '1000' in avertissements[0]
    assert 'E+' not in avertissements[0]


def test_le_regime_sans_plafond_accepte_n_importe_quel_montant():
    assert tipos.verifier('FS', Decimal('12000'), Decimal('14760'),
                          regime='c') == []


def test_le_plafond_ne_s_applique_qu_a_la_facture_simplifiee():
    """Une facture ordinaire de douze mille euros est parfaitement
    régulière : c'est la FORME simplifiée qui est plafonnée, pas le
    montant qu'on peut facturer."""
    assert tipos.verifier('FT', Decimal('12000'), Decimal('14760')) == []


# ── La facture-reçu et son encaissement ──────────────────────────────────────

UN_PAIEMENT = {'mecanisme': 'NU', 'montant': Decimal('123.00'),
               'date': date(2026, 11, 19)}


def test_une_facture_recu_sans_paiement_est_refusee():
    with pytest.raises(tipos.RegleDeType) as erreur:
        tipos.verifier('FR', Decimal('100'), Decimal('123'))

    assert 'quittance' in str(erreur.value)


def test_une_facture_recu_soldee_passe():
    assert tipos.verifier('FR', Decimal('100'), Decimal('123.00'),
                          paiements=[UN_PAIEMENT]) == []


def test_plusieurs_moyens_de_paiement_qui_soldent_le_total_passent():
    """Moitié espèces, moitié carte : le schéma accepte plusieurs
    « Payment », et c'est un cas courant au comptoir."""
    paiements = [
        dict(UN_PAIEMENT, mecanisme='NU', montant=Decimal('23.00')),
        dict(UN_PAIEMENT, mecanisme='CC', montant=Decimal('100.00')),
    ]

    assert tipos.verifier('FR', Decimal('100'), Decimal('123.00'),
                          paiements=paiements) == []


def test_un_encaissement_partiel_est_refuse():
    """Le cas le plus traître : le document s'imprime « fatura-recibo »
    comme les autres, et atteste un solde payé qui ne l'est pas."""
    with pytest.raises(tipos.RegleDeType) as erreur:
        tipos.verifier('FR', Decimal('100'), Decimal('123.00'),
                       paiements=[dict(UN_PAIEMENT,
                                       montant=Decimal('100.00'))])

    assert 'inférieure' in str(erreur.value)


def test_un_encaissement_excedentaire_est_refuse():
    with pytest.raises(tipos.RegleDeType) as erreur:
        tipos.verifier('FR', Decimal('100'), Decimal('123.00'),
                       paiements=[dict(UN_PAIEMENT,
                                       montant=Decimal('200.00'))])

    assert 'supérieure' in str(erreur.value)


def test_un_centime_d_ecart_est_refuse():
    """Aucune tolérance ici, contrairement à la TVA.

    Un centime de TVA peut venir d'un arrondi par ligne. Un centime
    d'encaissement ne vient de nulle part : c'est une somme qui a
    réellement changé de main.
    """
    with pytest.raises(tipos.RegleDeType):
        tipos.verifier('FR', Decimal('100'), Decimal('123.00'),
                       paiements=[dict(UN_PAIEMENT,
                                       montant=Decimal('122.99'))])


def test_un_type_qui_n_atteste_rien_refuse_un_paiement():
    with pytest.raises(tipos.RegleDeType) as erreur:
        tipos.verifier('FT', Decimal('100'), Decimal('123'),
                       paiements=[UN_PAIEMENT])

    assert 'FR' in str(erreur.value)


def test_un_seul_paiement_sans_montant_vaut_le_total():
    """CE QUE CE COMPORTEMENT ÉVITE, ET QUI N'EST PAS UNE COMMODITÉ.

    Le total est la seule somme légale pour une facture-reçu. Le faire
    porter par l'appelant l'obligerait à le connaître d'avance — or le
    total du document est calculé À L'ÉMISSION depuis les lignes figées,
    tandis que le cumul qu'un écran a sous la main est un autre nombre,
    tenu à part, qui dérive d'un centime après une suppression de ligne.

    Au Portugal ce centime est signé : laisser l'écran fournir le montant
    ferait entrer cette dérive dans une quittance.
    """
    paiements = [{'mecanisme': 'NU', 'date': date(2026, 11, 19)}]

    assert tipos.verifier('FR', Decimal('100'), Decimal('123.45'),
                          paiements=paiements) == []
    assert paiements[0]['montant'] == Decimal('123.45')


def test_plusieurs_paiements_exigent_chacun_leur_montant():
    """« Le total » réparti sur plusieurs moyens n'a pas de valeur par
    défaut : le remplir au total donnerait deux fois la somme."""
    with pytest.raises(tipos.RegleDeType) as erreur:
        tipos.verifier('FR', Decimal('100'), Decimal('123'),
                       paiements=[{'mecanisme': 'NU',
                                   'date': date(2026, 11, 19)},
                                  {'mecanisme': 'CC',
                                   'date': date(2026, 11, 19)}])

    assert 'PaymentAmount' in str(erreur.value)
    assert 'plusieurs' in str(erreur.value)


def test_un_montant_explicite_n_est_pas_ecrase():
    """Celui qui donne un montant le donne pour une raison ; s'il est
    faux, il doit être REFUSÉ et non corrigé en silence — une quittance
    rectifiée à l'insu de son émetteur est pire qu'une quittance
    refusée."""
    with pytest.raises(tipos.RegleDeType) as erreur:
        tipos.verifier('FR', Decimal('100'), Decimal('123'),
                       paiements=[{'mecanisme': 'NU',
                                   'montant': Decimal('50'),
                                   'date': date(2026, 11, 19)}])

    assert 'inférieure' in str(erreur.value)


def test_un_paiement_sans_date_est_refuse():
    with pytest.raises(tipos.RegleDeType) as erreur:
        tipos.verifier('FR', Decimal('100'), Decimal('123'),
                       paiements=[{'mecanisme': 'NU',
                                   'montant': Decimal('123'), 'date': None}])

    assert 'PaymentDate' in str(erreur.value)


def test_un_montant_a_zero_n_est_pas_un_montant_absent():
    """Zéro est un montant, absent n'en est pas un.

    Les confondre ferait passer un paiement explicitement nul pour un
    paiement à compléter. Ici le montant est écrit à zéro face à un total
    de 123 € : il doit être refusé comme un écart, et non comblé.
    """
    with pytest.raises(tipos.RegleDeType) as erreur:
        tipos.verifier('FR', Decimal('100'), Decimal('123'),
                       paiements=[{'mecanisme': 'NU',
                                   'montant': Decimal('0'),
                                   'date': date(2026, 11, 19)}])

    assert 'inférieure' in str(erreur.value)


# ── Les moyens de paiement ───────────────────────────────────────────────────

def test_les_quatorze_mecanismes_sont_ceux_du_schema():
    """Relevés un par un dans l'énumération « PaymentMechanism » du XSD
    de l'AT, et non dans une documentation qui la reproduit.

    Le test relit le schéma vendu avec le logiciel : si l'AT en publie une
    version qui ajoute un code, c'est ici qu'on l'apprend.
    """
    import re
    from pathlib import Path

    from apps.fiscal_pt import schema

    texte = Path(schema.FICHIER_XSD).read_text(encoding='latin-1')
    debut = texte.index('name="PaymentMechanism"')
    fin = texte.index('</xs:element>', debut)
    du_schema = set(re.findall(r'enumeration value="([A-Z]{2})"',
                               texte[debut:fin]))

    assert du_schema == set(tipos.CODES_DE_MECANISME)
    assert len(tipos.CODES_DE_MECANISME) == 14


def test_un_mecanisme_hors_enumeration_est_refuse():
    with pytest.raises(tipos.RegleDeType) as erreur:
        tipos.valider_le_mecanisme('XX')

    # Le message doit lister les codes possibles : « code invalide » tout
    # court laisserait chercher dans le schéma.
    assert 'NU' in str(erreur.value)


def test_un_mecanisme_absent_est_accepte():
    """`PaymentMechanism` est optionnel au schéma. On le réclame à la
    saisie, mais le valideur ne doit pas refuser son absence : un document
    importé d'ailleurs peut légitimement ne pas le porter."""
    assert tipos.valider_le_mecanisme('') == ''
    assert tipos.valider_le_mecanisme(None) is None


def test_chaque_mecanisme_a_un_libelle_lisible():
    for code, libelle in tipos.MECANISMES_DE_PAIEMENT:
        assert libelle and libelle != code
        assert tipos.libelle_de_mecanisme(code) == libelle


def test_un_code_inconnu_rend_le_code_plutot_que_rien():
    """Un libellé vide ferait disparaître l'information de l'écran. Rendre
    le code brut est moins beau et dit la vérité."""
    assert tipos.libelle_de_mecanisme('ZZ') == 'ZZ'
    assert tipos.libelle_de_mecanisme(None) == ''


# ── La date de l'encaissement ────────────────────────────────────────────────

@pytest.mark.parametrize('valeur', [
    'pas-une-date',
    '07/03/2026',      # le format français, qui n'est pas celui du SAF-T
    '2026-13-01',      # un mois qui n'existe pas
    '2026-02-30',      # un jour qui n'existe pas dans ce mois
])
def test_une_date_d_encaissement_illisible_est_refusee(valeur):
    """LE DÉFAUT QUE CE TEST FERME, mesuré avant d'être corrigé.

    `PaymentDate` n'était vérifié que non vide. Une saisie malformée était
    donc acceptée, SIGNÉE et figée dans le document ; le composeur du
    SAF-T écrit `str(valeur)[:10]` sans rien vérifier, et le fichier
    portait « <PaymentDate>pas-une-da</PaymentDate> ».

    Le défaut ne se découvrait qu'à l'export, des semaines plus tard, sur
    un document immuable que seul un avoir peut reprendre. C'est la forme
    la plus coûteuse d'erreur de saisie : celle dont le coût arrive après
    le point de non-retour.
    """
    with pytest.raises(tipos.RegleDeType) as erreur:
        tipos.verifier('FR', Decimal('100'), Decimal('123'),
                       paiements=[{'mecanisme': 'NU',
                                   'montant': Decimal('123'),
                                   'date': valeur}])

    assert 'AAAA-MM-JJ' in str(erreur.value)


@pytest.mark.parametrize('valeur, attendu', [
    (date(2026, 3, 7), date(2026, 3, 7)),
    ('2026-03-07', date(2026, 3, 7)),
    ('2026-03-07T10:30:00', date(2026, 3, 7)),
])
def test_une_date_lisible_est_normalisee(valeur, attendu):
    """La chaîne du formulaire et l'objet date doivent aboutir au même
    document : c'est le même encaissement, saisi par deux chemins."""
    paiements = [{'mecanisme': 'NU', 'montant': Decimal('123'),
                  'date': valeur}]

    assert tipos.verifier('FR', Decimal('100'), Decimal('123'),
                          paiements=paiements) == []
    assert paiements[0]['date'] == attendu


def test_un_horodatage_complet_est_ramene_au_jour():
    """Le schéma attend `SAFdateType` — un jour, pas un instant. Laisser
    passer un horodatage ferait rejeter le fichier."""
    from datetime import datetime

    paiements = [{'mecanisme': 'NU', 'montant': Decimal('123'),
                  'date': datetime(2026, 3, 7, 14, 32, 11)}]
    tipos.verifier('FR', Decimal('100'), Decimal('123'), paiements=paiements)

    assert paiements[0]['date'] == date(2026, 3, 7)


def test_le_message_nomme_le_vrai_probleme_et_pas_le_premier_trouve():
    """L'ORDRE DES CONTRÔLES, et ce qu'il change pour le lecteur.

    Une facture ordinaire portant un encaissement mal saisi a DEUX
    défauts. Signaler le moyen de paiement enverrait corriger le code ;
    la vérité est que ce document ne devrait porter aucun paiement.

    Un validateur qui désigne le premier défaut rencontré plutôt que le
    plus explicatif se fait ignorer — ce qui le rend inutile sans le
    casser.
    """
    with pytest.raises(tipos.RegleDeType) as erreur:
        tipos.verifier('FT', Decimal('100'), Decimal('123'),
                       paiements=[{'mecanisme': 'XX', 'montant': None,
                                   'date': 'pas-une-date'}])

    message = str(erreur.value)
    assert 'n’atteste aucun paiement' in message
    assert 'XX' not in message


# ── Le type lui-même ─────────────────────────────────────────────────────────

def test_les_cinq_types_emis_sont_dans_l_enumeration_du_schema():
    """Chacun doit être accepté par « InvoiceType » du XSD de l'AT.

    Le schéma en accepte d'autres — VD, TV, TD, AA, DA pour les données
    antérieures à 2013, et cinq types propres à l'assurance. On ne les
    offre pas : une série déclarée dans un type qu'on ne sait pas remplir
    produirait des documents que l'export refuserait, trop tard pour les
    reprendre.
    """
    import re
    from pathlib import Path

    from apps.fiscal_pt import schema

    texte = Path(schema.FICHIER_XSD).read_text(encoding='latin-1')
    debut = texte.index('<xs:element name="InvoiceType">')
    fin = texte.index('</xs:element>', debut)
    du_schema = set(re.findall(r'enumeration value="([A-Z]{2})"',
                               texte[debut:fin]))

    assert set(tipos.CODES_DE_TYPE) <= du_schema
    assert len(tipos.CODES_DE_TYPE) == 5


def test_la_liste_des_types_n_existe_qu_une_fois():
    """`models` l'importe plutôt que de la recopier : deux listes jumelles
    finissent toujours par diverger, et celle-ci borne ce que l'export
    acceptera."""
    from apps.fiscal_pt.models import TYPES_DE_DOCUMENT

    assert TYPES_DE_DOCUMENT is tipos.TYPES_DE_DOCUMENT


@pytest.mark.parametrize('type_document', ['VD', 'TV', 'ZZ', '', 'ft'])
def test_un_type_hors_liste_est_refuse_a_l_emission(type_document):
    """LE DÉFAUT QUE CE TEST FERME.

    `SerieFiscale.type_document` porte des `choices`, que Django ne
    vérifie qu'au `full_clean()` d'un formulaire. Une série créée
    autrement — un script, un import, la base en direct — pouvait porter
    n'importe quoi : les documents s'émettaient et se signaient, et c'est
    l'EXPORT qui les refusait, parce que « InvoiceType » est une
    énumération du schéma. À ce moment-là le document est immuable et le
    fichier entier est bloqué, pour un défaut de configuration.
    """
    with pytest.raises(tipos.RegleDeType) as erreur:
        tipos.verifier(type_document, Decimal('100'), Decimal('123'))

    assert 'FT' in str(erreur.value)
