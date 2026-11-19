"""La conformité fiscale portugaise : signature, ATCUD et code QR.

POURQUOI CES TESTS EMPLOIENT LES EXEMPLES DE L'ADMINISTRATION

La certification d'un logiciel de facturation au Portugal ne se discute
pas : l'AT recalcule les signatures et relit les codes QR. Un test écrit
d'après notre propre compréhension du texte validerait notre
compréhension, pas la conformité.

Les vecteurs viennent donc des documents officiels :

* Despacho n.º 8632/2014, point 7.1 — l'exemple de chaîne à signer
  « 2010-05-18;2010-05-18T11:22:19;FAC 001/14;3.12; » ;
* « Especificações Técnicas Código QR » de l'AT, figures 1, 5 et 6 — les
  messages complets, champ par champ.

CE QUE CES TESTS NE PROUVENT PAS

Qu'une signature produite ici serait acceptée par l'AT : cela dépend de
la clé privée que l'AT enregistre pour l'éditeur, et qu'on ne possède
pas. Ils prouvent que le MÉCANISME est conforme — format, longueur,
chaînage, ordre des champs — ce qui est la part vérifiable sans elle.
"""
from datetime import date, datetime
from decimal import Decimal

import pytest

from apps.fiscal_pt import assinatura, atcud, qr


# ── 1. La chaîne à signer ────────────────────────────────────────────────────

def test_le_message_reprend_l_exemple_officiel():
    """Despacho 8632/2014, point 7.1, premier enregistrement.

    Le document précédent est vide : la chaîne se termine donc par « ; ».
    C'est le cas qu'on rate le plus — on écrit volontiers quatre champs et
    on oublie le séparateur final.
    """
    message = assinatura.composer_le_message(
        date_document=date(2010, 5, 18),
        horodatage=datetime(2010, 5, 18, 11, 22, 19),
        numero='FAC 001/14',
        total=Decimal('3.12'),
        hash_precedent='',
    )

    assert message == '2010-05-18;2010-05-18T11:22:19;FAC 001/14;3.12;'


def test_le_montant_prend_toujours_deux_decimales():
    """« 3.1 » et « 3,12 » produiraient une signature que l’AT ne pourrait
    pas revérifier — et l’erreur n’apparaîtrait qu’au contrôle."""
    message = assinatura.composer_le_message(
        date(2024, 1, 2), datetime(2024, 1, 2, 9, 0, 0), 'FT 1/1', 3.1)

    assert ';3.10;' in message


def test_l_horodatage_perd_son_fuseau_et_ses_microsecondes():
    """L’exemple officiel écrit « 2010-05-18T11:22:19 ». Un suffixe
    « +00:00 » changerait la chaîne signée, donc la signature."""
    from django.utils import timezone

    message = assinatura.composer_le_message(
        date(2024, 1, 2),
        timezone.make_aware(datetime(2024, 1, 2, 9, 0, 0, 123456)),
        'FT 1/1', 10)

    assert '2024-01-02T09:00:00;' in message
    assert '+' not in message.split(';')[1]


def test_un_saut_de_ligne_est_refuse():
    """Le Despacho l’interdit explicitement. Un numéro de document collé
    depuis un tableur en emporte un sans qu’on le voie."""
    with pytest.raises(assinatura.ErreurDeSignature):
        assinatura.composer_le_message(
            date(2024, 1, 2), datetime(2024, 1, 2, 9, 0, 0),
            'FT 1/1\n', 10)


# ── 2. La signature elle-même ────────────────────────────────────────────────

@pytest.fixture(scope='module')
def paire_de_cles():
    return assinatura.generer_une_cle()


def test_la_cle_fait_bien_1024_bits(paire_de_cles):
    """RSA-1024 et SHA-1 sont faibles, et pourtant imposés par le texte.
    Une clé plus solide serait refusée à la certification : le test fige
    donc la valeur légale, pas la bonne pratique cryptographique."""
    from cryptography.hazmat.primitives import serialization

    privee, _ = paire_de_cles
    cle = serialization.load_pem_private_key(privee.encode(), password=None)

    assert cle.key_size == 1024


def test_la_signature_fait_exactement_172_caracteres(paire_de_cles):
    """« deve ser garantido que as assinaturas contêm 172 bytes, sem
    quaisquer carateres separadores de linhas »."""
    privee, _ = paire_de_cles
    message = assinatura.composer_le_message(
        date(2024, 1, 2), datetime(2024, 1, 2, 9, 0, 0), 'FT 1/1', 100)

    signature = assinatura.signer(message, privee)

    assert len(signature) == 172
    assert '\n' not in signature and '\r' not in signature


def test_une_signature_se_reverifie(paire_de_cles):
    """C’est ce que fait l’administration au contrôle : on doit pouvoir le
    faire soi-même, et bien avant elle."""
    privee, publique = paire_de_cles
    message = assinatura.composer_le_message(
        date(2024, 1, 2), datetime(2024, 1, 2, 9, 0, 0), 'FT 1/1', 100)
    signature = assinatura.signer(message, privee)

    assert assinatura.verifier(message, signature, publique) is True


def test_un_document_modifie_casse_sa_signature(paire_de_cles):
    """LA GARANTIE CENTRALE DU DISPOSITIF : changer un centime invalide la
    preuve."""
    privee, publique = paire_de_cles
    original = assinatura.composer_le_message(
        date(2024, 1, 2), datetime(2024, 1, 2, 9, 0, 0), 'FT 1/1', 100)
    signature = assinatura.signer(original, privee)

    falsifie = assinatura.composer_le_message(
        date(2024, 1, 2), datetime(2024, 1, 2, 9, 0, 0), 'FT 1/1', 100.01)

    assert assinatura.verifier(falsifie, signature, publique) is False


def test_une_cle_trop_solide_est_refusee():
    """Refuser 2048 bits paraît absurde — c’est pourtant la règle, et un
    éditeur qui « améliore » la sécurité échoue à la certification."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    forte = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = forte.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption()).decode()

    with pytest.raises(assinatura.ErreurDeSignature, match='1024'):
        assinatura.signer('x;y;z;1.00;', pem)


# ── 3. Le chaînage, qui est le cœur du dispositif ────────────────────────────

def test_la_chaine_relie_les_documents(paire_de_cles):
    """Chaque document signe la signature du précédent. Retirer le
    deuxième d’une série de trois rend le troisième invérifiable — c’est
    exactement ce que l’administration cherche."""
    privee, publique = paire_de_cles

    premier = assinatura.composer_le_message(
        date(2024, 1, 2), datetime(2024, 1, 2, 9, 0, 0), 'FT A/1', 100)
    sig1 = assinatura.signer(premier, privee)

    second = assinatura.composer_le_message(
        date(2024, 1, 3), datetime(2024, 1, 3, 9, 0, 0), 'FT A/2', 200,
        hash_precedent=sig1)
    sig2 = assinatura.signer(second, privee)

    assert second.endswith(';' + sig1)
    assert assinatura.verifier(second, sig2, publique) is True

    # Le deuxième document rejoué sans son prédécesseur ne tient plus.
    orphelin = assinatura.composer_le_message(
        date(2024, 1, 3), datetime(2024, 1, 3, 9, 0, 0), 'FT A/2', 200)
    assert assinatura.verifier(orphelin, sig2, publique) is False


# ── 4. Ce qui s'imprime sur le document ──────────────────────────────────────

def test_les_caracteres_imprimes_sont_aux_positions_1_11_21_31():
    """Despacho 2.2.2. Les positions sont données en base 1 dans le texte ;
    une conversion ratée donne quatre caractères faux, et personne ne s’en
    aperçoit — ils ressemblent à n’importe quels autres."""
    signature = ''.join(str(i % 10) for i in range(1, 173))

    assert assinatura.caracteres_imprimes(signature) == '1111'

    alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz' * 4
    assert assinatura.caracteres_imprimes(alphabet) == 'AKUe'


def test_la_mention_legale_suit_l_exemple_officiel():
    """« AxAx-Processado por programa certificado n.º 0000/AT »."""
    signature = 'A' + 'x' * 9 + 'x' + 'A' * 9 + 'A' + 'x' * 9 + 'x' + 'y' * 141

    mention = assinatura.mention_legale(signature, '0000')

    assert mention.endswith('-Processado por programa certificado n.º 0000/AT')
    assert len(mention.split('-')[0]) == 4


def test_les_documents_non_signes_portent_tout_de_meme_la_mention():
    """Despacho 2.2.3, et le VERBE n'est pas celui de 2.2.2.

    Les reçus ne sont pas signés — le point 1.1 les exclut expressément de
    l'obligation — mais doivent annoncer le programme certifié. Le texte
    emploie alors « EMITIDO por programa certificado n.º 0000/AT », là où
    les documents signés portent « Processado por », précédé de quatre
    caractères de signature (2.2.2). Chacune des deux expressions figure
    une seule fois dans le Despacho, et pas au même endroit.

    CE TEST AFFIRMAIT L'INVERSE, ET C'EST INSTRUCTIF.

    Il comparait la sortie de la fonction au code de la fonction — donc il
    passait, et il figeait la faute. La mention légale imprimée au pied de
    chaque reçu aurait été celle des documents signés, sans que rien ne le
    signale : le reçu s'imprime, le fichier passe, et seule une lecture du
    texte officiel relève l'écart.

    Un test n'est utile que s'il compare à autre chose qu'à ce qu'il teste.
    """
    assert assinatura.mention_sans_signature('1234') == (
        'Emitido por programa certificado n.º 1234/AT')


@pytest.mark.parametrize('valeur', ['', 'ABCD', '12345', '0', None])
def test_le_numero_de_certificat_est_valide_a_la_saisie(valeur):
    if valeur == '0':
        assert assinatura.valider_numero_de_certificat(valeur) == '0'
        return
    with pytest.raises(assinatura.ErreurDeSignature):
        assinatura.valider_numero_de_certificat(valeur)


# ── 5. L'ATCUD ───────────────────────────────────────────────────────────────

def test_l_atcud_suit_l_exemple_officiel():
    """La spécification du code QR donne « CSDF7T5H-0035 »."""
    assert atcud.composer('CSDF7T5H', '0035') == 'CSDF7T5H-0035'


def test_un_code_de_validation_invente_est_refuse():
    """Le code vient de l’AT, par webservice. Un code fabriqué localement
    produirait des documents d’apparence correcte et juridiquement nuls —
    sur des mois de facturation, avant que quiconque s’en aperçoive."""
    for faux in ('abc', 'TROP-COURT', '1234567', 'AVEC ESPACE', 'PONCTU@TION'):
        with pytest.raises(atcud.ErreurATCUD):
            atcud.composer(faux, '1')


def test_un_code_saisi_en_minuscules_est_mis_en_forme():
    """Le code se recopie à la main depuis le portail de l’AT, où il est en
    majuscules. Le mettre en forme ne peut pas transformer un code juste en
    code faux ; le refuser, en revanche, bloquerait une saisie correcte.
    La normalisation est donc voulue — ce test est là pour qu’on ne la
    prenne pas plus tard pour un trou dans la validation."""
    assert atcud.composer('csdf7t5h', '35') == 'CSDF7T5H-35'


def test_une_serie_non_communiquee_se_declare_par_zero():
    """La Portaria le prévoit. Mieux vaut la marque explicite d’une série
    non déclarée qu’un ATCUD inventé pour faire bonne figure."""
    assert atcud.composer('0', '1') == '0-1'


def test_separer_rend_les_deux_moities():
    assert atcud.separer('CSDF7T5H-0035') == ('CSDF7T5H', '0035')


# ── 6. Le code QR, contre les exemples publiés par l'AT ──────────────────────

def test_le_code_qr_reprend_l_exemple_officiel_figure_5():
    """« Especificações Técnicas Código QR », figure 5 — facture émise à un
    acquéreur français, TVA au taux normal.

    Le champ G est fourni tel quel : l’extraction du PDF ne permet pas de
    trancher son espacement interne, mais le test n’en dépend pas — on le
    passe en entrée et on l’attend en sortie, à l’identique.
    """
    message = qr.composer(
        nif_emetteur='123456789',
        nif_acquereur='4443332215',
        pays_acquereur='FR',
        type_document='FT',
        etat_document='N',
        date_document=date(2019, 5, 26),
        numero_document='ABC BNH/4561',
        atcud='DK5ZJ2HN-4561',
        espaces_fiscaux=[{'regiao': 'FR',
                          'base_normal': '100.00',
                          'iva_normal': '20.00'}],
        total_impostos='20.00',
        total_documento='120.00',
        caracteres_hash='YJRE',
        numero_certificat='9999',
    )

    assert message == (
        'A:123456789*B:4443332215*C:FR*D:FT*E:N*F:20190526'
        '*G:ABC BNH/4561*H:DK5ZJ2HN-4561*I1:FR*I7:100.00*I8:20.00'
        '*N:20.00*O:120.00*Q:YJRE*R:9999')


def test_le_code_qr_reprend_l_exemple_officiel_figure_6():
    """Figure 6 — note de débit rectificative, Madère, taux intermédiaire.

    Elle vérifie deux choses que la figure 5 ne montre pas : une région
    composée (« PT-MA ») et un bloc où seul le taux intermédiaire est
    rempli — les autres champs doivent être ABSENTS, pas à zéro.
    """
    message = qr.composer(
        nif_emetteur='123456789',
        nif_acquereur='500000000',
        pays_acquereur='PT',
        type_document='ND',
        etat_document='N',
        date_document=date(2019, 2, 16),
        numero_document='M1F KLG/6145',
        atcud='RQD8L6DG-6145',
        espaces_fiscaux=[{'regiao': 'PT-MA', 'iva_intermedia': '26.50'}],
        total_impostos='26.50',
        total_documento='26.50',
        caracteres_hash='h1rB',
        numero_certificat='9999',
    )

    assert message == (
        'A:123456789*B:500000000*C:PT*D:ND*E:N*F:20190216'
        '*G:M1F KLG/6145*H:RQD8L6DG-6145*I1:PT-MA*I6:26.50'
        '*N:26.50*O:26.50*Q:h1rB*R:9999')


def test_les_trois_espaces_fiscaux_prennent_I_puis_J_puis_K():
    """Ce ne sont pas des lettres attribuées à des régions : c’est l’ORDRE
    d’apparition qui décide. L’erreur la plus courante est de réserver J
    aux Açores et K à Madère — un document qui ne facture qu’à Madère
    emploie alors J, et le code devient faux."""
    message = qr.composer(
        nif_emetteur='123456789', nif_acquereur='999999990',
        pays_acquereur='PT', type_document='FT', etat_document='N',
        date_document=date(2019, 12, 31), numero_document='FT A/1',
        atcud='CSDF7T5H-1',
        espaces_fiscaux=[
            {'regiao': 'PT', 'base_normal': '100.00', 'iva_normal': '23.00'},
            {'regiao': 'PT-AC', 'base_normal': '50.00', 'iva_normal': '8.00'},
            {'regiao': 'PT-MA', 'base_normal': '10.00', 'iva_normal': '2.20'},
        ],
        total_impostos='33.20', total_documento='193.20',
        caracteres_hash='ABCD', numero_certificat='1',
    )

    assert '*I1:PT*' in message
    assert '*J1:PT-AC*' in message
    assert '*K1:PT-MA*' in message
    assert message.index('I1:') < message.index('J1:') < message.index('K1:')


def test_un_montant_absent_n_est_pas_un_montant_nul():
    """« I3: » n’est pas « rien » : c’est une base déclarée à zéro, ce qui
    n’a pas le même sens fiscal qu’un champ absent."""
    message = qr.composer(
        nif_emetteur='1', nif_acquereur='2', pays_acquereur='PT',
        type_document='FT', etat_document='N', date_document=date(2024, 1, 1),
        numero_document='FT A/1', atcud='CSDF7T5H-1',
        espaces_fiscaux=[{'regiao': 'PT', 'iva_normal': '23.00'}],
        total_impostos='23.00', total_documento='123.00',
        caracteres_hash='ABCD', numero_certificat='1')

    assert 'I3:' not in message
    assert 'I8:23.00' in message


def test_le_consommateur_final_prend_le_nif_conventionnel():
    """La spécification impose « 999999990 » et non un champ vide."""
    message = qr.composer(
        nif_emetteur='123456789', nif_acquereur=None, pays_acquereur='PT',
        type_document='FS', etat_document='N', date_document=date(2024, 1, 1),
        numero_document='FS A/1', atcud='CSDF7T5H-1',
        espaces_fiscaux=[{'regiao': 'PT', 'iva_normal': '2.30'}],
        total_impostos='2.30', total_documento='12.30',
        caracteres_hash='ABCD', numero_certificat='1')

    assert '*B:999999990*' in message


def test_la_date_du_qr_n_a_pas_de_tirets():
    """Deux formats cohabitent dans la même facture : « AAAA-MM-JJ » dans
    la chaîne signée, « AAAAMMJJ » dans le code QR. Les confondre casse
    l’un ou l’autre, et chacun se vérifie séparément."""
    message = qr.composer(
        nif_emetteur='1', nif_acquereur='2', pays_acquereur='PT',
        type_document='FT', etat_document='N', date_document=date(2026, 3, 7),
        numero_document='FT A/1', atcud='CSDF7T5H-1',
        espaces_fiscaux=[{'regiao': 'PT'}], total_impostos='0.00',
        total_documento='0.00', caracteres_hash='ABCD', numero_certificat='1')

    assert '*F:20260307*' in message


def test_un_champ_obligatoire_vide_est_refuse():
    with pytest.raises(qr.ErreurQR, match='A'):
        qr.composer(
            nif_emetteur='', nif_acquereur='2', pays_acquereur='PT',
            type_document='FT', etat_document='N',
            date_document=date(2024, 1, 1), numero_document='FT A/1',
            atcud='CSDF7T5H-1', espaces_fiscaux=[{'regiao': 'PT'}],
            total_impostos='0.00', total_documento='0.00',
            caracteres_hash='ABCD', numero_certificat='1')


def test_un_asterisque_dans_un_champ_est_refuse():
    """Il sépare les champs : un numéro de document qui en contient un
    rendrait le code illisible, et le lecteur verrait deux champs là où il
    n’y en a qu’un."""
    with pytest.raises(qr.ErreurQR, match=r'\*'):
        qr.composer(
            nif_emetteur='1', nif_acquereur='2', pays_acquereur='PT',
            type_document='FT', etat_document='N',
            date_document=date(2024, 1, 1), numero_document='FT*A/1',
            atcud='CSDF7T5H-1', espaces_fiscaux=[{'regiao': 'PT'}],
            total_impostos='0.00', total_documento='0.00',
            caracteres_hash='ABCD', numero_certificat='1')


def test_le_champ_Q_attend_exactement_quatre_caracteres():
    with pytest.raises(qr.ErreurQR, match='4'):
        qr.composer(
            nif_emetteur='1', nif_acquereur='2', pays_acquereur='PT',
            type_document='FT', etat_document='N',
            date_document=date(2024, 1, 1), numero_document='FT A/1',
            atcud='CSDF7T5H-1', espaces_fiscaux=[{'regiao': 'PT'}],
            total_impostos='0.00', total_documento='0.00',
            caracteres_hash='AB', numero_certificat='1')


def test_le_qr_et_la_signature_s_accordent(paire_de_cles):
    """LE LIEN ENTRE LES DEUX MÉCANISMES.

    Le champ Q du code QR reprend les quatre caractères imprimés en pied
    de page, qui viennent eux-mêmes de la signature. Les calculer deux
    fois par deux chemins différents est le meilleur moyen de les voir
    diverger.
    """
    privee, _ = paire_de_cles
    message = assinatura.composer_le_message(
        date(2024, 1, 2), datetime(2024, 1, 2, 9, 0, 0), 'FT A/1', 123)
    signature = assinatura.signer(message, privee)
    quatre = assinatura.caracteres_imprimes(signature)

    contenu = qr.composer(
        nif_emetteur='123456789', nif_acquereur='999999990',
        pays_acquereur='PT', type_document='FT', etat_document='N',
        date_document=date(2024, 1, 2), numero_document='FT A/1',
        atcud='CSDF7T5H-1',
        espaces_fiscaux=[{'regiao': 'PT', 'base_normal': '100.00',
                          'iva_normal': '23.00'}],
        total_impostos='23.00', total_documento='123.00',
        caracteres_hash=quatre, numero_certificat='1')

    assert f'*Q:{quatre}*' in contenu
    assert assinatura.mention_legale(signature, '1').startswith(quatre)
