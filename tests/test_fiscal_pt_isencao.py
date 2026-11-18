"""Les motifs d'exonération de TVA, contre la table officielle de l'AT.

D'OÙ VIENNENT CES VECTEURS

« Códigos de Motivo de Isenção — Manual de Integração de Software »,
version 4.0 du 18 juin 2026, lu dans le PDF publié par l'AT et non dans
une reproduction : plusieurs sites omettent M35, le plus récent, et une
table incomplète refuse des factures parfaitement légales.

CE QUE CES TESTS DÉFENDENT SURTOUT

Que les codes ne sont PAS contigus. M03, M08, M17, M18, M22 à M24,
M27 à M29 et M36 à M39 n'existent pas. Un code choisi par analogie — on
voit M07 et M09, on écrit M08 — fait rejeter le fichier entier tout en
ayant l'air aussi normal que les autres.
"""
from datetime import date

import pytest

from apps.fiscal_pt import isencao


# ── La table ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize('code, mencao', [
    ('M01', 'Artigo 16.º n.º 6 do CIVA'),
    ('M05', 'Isento artigo 14.º do CIVA'),
    ('M07', 'Isento artigo 9.º do CIVA'),
    ('M19', 'Outras isenções'),
    ('M31', 'IVA - autoliquidação'),
    ('M35', 'IVA - autoliquidação'),
    ('M44', 'IVA – Regras específicas - artigo 6.º'),
    ('M46', 'IVA – e-TaxFree'),
    ('M99', 'Não sujeito ou não tributado'),
])
def test_la_mention_est_celle_de_la_table_officielle(code, mencao):
    """La « menção » n’est pas une étiquette d’interface : c’est une
    mention LÉGALE du document. La relire dans la table plutôt que de la
    saisir à la main évite qu’elle soit fautive une fois sur dix."""
    assert isencao.mencao(code) == mencao


def test_la_table_contient_les_trente_trois_codes():
    """Ni plus ni moins. Un code en trop serait accepté à la saisie et
    rejeté à la remise ; un code en moins refuserait une facture légale."""
    assert len(isencao.CODES) == 33
    assert set(isencao.CODES) == {
        'M01', 'M02', 'M04', 'M05', 'M06', 'M07', 'M09', 'M10', 'M11',
        'M12', 'M13', 'M14', 'M15', 'M16', 'M19', 'M20', 'M21', 'M25',
        'M26', 'M30', 'M31', 'M32', 'M33', 'M34', 'M35', 'M40', 'M41',
        'M42', 'M43', 'M44', 'M45', 'M46', 'M99'}


@pytest.mark.parametrize('inexistant', [
    'M03', 'M08', 'M17', 'M18', 'M22', 'M23', 'M24', 'M27', 'M28', 'M29',
    'M36', 'M37', 'M38', 'M39', 'M47', 'M00', 'M50',
])
def test_les_codes_absents_de_la_table_sont_refuses(inexistant):
    """LE PIÈGE CENTRAL DE CE MODULE.

    On voit M07 et M09 dans la liste, on en déduit que M08 existe. Il
    n’existe pas. Le document émis aurait l’air normal et le fichier
    serait rejeté — des mois plus tard, à la remise.
    """
    with pytest.raises(isencao.MotifInvalide, match='contigu'):
        isencao.valider(inexistant)


def test_chaque_code_porte_une_mention_et_une_norme():
    """La norme sert à l’affichage, pour que celui qui facture puisse
    vérifier qu’il a choisi le bon article."""
    for code, (mencao, norma) in isencao.CODES.items():
        assert mencao.strip(), code
        assert norma.strip(), code


# ── La casse et les espaces ──────────────────────────────────────────────────

@pytest.mark.parametrize('saisi', ['m07', ' M07 ', 'm07 ', 'M07'])
def test_le_code_est_mis_en_forme(saisi):
    """Le code se recopie à la main depuis un document. Le mettre en forme
    ne peut pas transformer un code juste en code faux ; le refuser
    bloquerait une saisie correcte."""
    assert isencao.valider(saisi) == 'M07'


def test_un_code_absent_le_dit_sans_detour():
    with pytest.raises(isencao.MotifInvalide, match='Aucun motif'):
        isencao.valider('')


# ── La date d'entrée en vigueur ──────────────────────────────────────────────

def test_m35_est_refuse_avant_le_1er_juillet_2026():
    """M35 a été introduit par la version 4.0 de la table et ne
    s’applique qu’aux factures émises à partir du 1er juillet 2026.
    L’employer avant est un refus assuré, et rien dans le code ne le
    signalerait."""
    with pytest.raises(isencao.MotifInvalide, match='01/07/2026'):
        isencao.valider('M35', date(2026, 6, 30))

    assert isencao.valider('M35', date(2026, 7, 1)) == 'M35'
    assert isencao.valider('M35', date(2026, 12, 1)) == 'M35'


def test_sans_date_le_code_recent_passe():
    """Une validation hors contexte de document ne peut pas juger de la
    date. Elle laisse donc passer, plutôt que de refuser à tort."""
    assert isencao.valider('M35') == 'M35'


def test_un_code_ancien_passe_a_toute_date():
    assert isencao.valider('M07', date(2010, 1, 1)) == 'M07'


# ── La liste déroulante ──────────────────────────────────────────────────────

def test_les_codes_du_btp_viennent_en_tete():
    """Sur trente-trois entrées, celle qu’on cherche doit être trouvable.
    M31 et M35 sont ceux qu’un ERP de travaux emploie le plus souvent."""
    codes = [code for code, _ in isencao.choix()]

    assert codes[:2] == ['M31', 'M35']
    assert len(codes) == 33


def test_la_liste_masque_un_code_pas_encore_en_vigueur():
    codes = [code for code, _ in isencao.choix(date(2026, 1, 1))]

    assert 'M35' not in codes
    assert 'M31' in codes
    assert len(codes) == 32


def test_chaque_libelle_porte_son_code():
    """Le libellé seul ne suffit pas : cinq codes différents affichent
    « IVA - autoliquidação ». Sans le code devant, le choix est
    impossible."""
    for code, libelle in isencao.choix():
        assert libelle.startswith(f'{code} — ')


def test_cinq_codes_partagent_le_meme_libelle():
    """La preuve que le point précédent n’est pas théorique."""
    autoliquidation = [c for c, (m, _) in isencao.CODES.items()
                       if m == 'IVA - autoliquidação']

    assert len(autoliquidation) >= 5


# ── L'autoliquidation ────────────────────────────────────────────────────────

def test_l_autoliquidation_se_distingue_de_l_exoneration():
    """La nuance compte sur le document : en autoliquidation le client
    acquitte la TVA lui-même, l’opération n’est pas « exonérée »."""
    assert isencao.est_autoliquidation('M31') is True
    assert isencao.est_autoliquidation('M35') is True
    assert isencao.est_autoliquidation('M07') is False
    assert isencao.est_autoliquidation('M99') is False


def test_les_deux_codes_du_btp_sont_des_autoliquidations():
    for code in isencao.CODES_DU_BTP:
        assert code in isencao.CODES
        assert isencao.est_autoliquidation(code)


def test_m31_couvre_la_sous_traitance_de_construction():
    """C’est le cas courant d’un ERP de travaux : inversion du redevable
    sur les services de construction civile en sous-traitance."""
    assert isencao.norma('M31') == 'Artigo 2.º n.º 1 alínea j) do CIVA'


def test_m35_cible_les_chantiers_d_habitation():
    assert 'Verba 2.42 da Lista I' in isencao.norma('M35')
