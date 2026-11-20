"""apps/fiscal_pt/taxas.py — Classer un taux de TVA dans le bon palier.

POURQUOI CE MODULE EXISTE

Le code QR ne demande pas « 23 % » : il demande la base et la TVA du
palier NORMAL, du palier INTERMÉDIAIRE, du palier RÉDUIT et de
l'exonéré. Il faut donc traduire un taux en palier — et la traduction
dépend de la région, ce qui est l'erreur qu'on ne voit pas venir.

    Palier          Continent   Açores   Madère
    ────────────────────────────────────────────
    Normal              23 %     16 %     22 %
    Intermédiaire       13 %      9 %     12 %
    Réduit               6 %      4 %      5 %
    Exonéré              0 %      0 %      0 %

Un taux de 22 % est le taux NORMAL à Madère et n'existe pas sur le
continent. Classer les taux avec une table unique mettrait donc les
ventes de Madère dans le mauvais champ du code QR, et le total du
document resterait juste — c'est pourquoi personne ne s'en apercevrait
avant un contrôle.
"""

from decimal import Decimal

#: Les régions, telles qu'elles s'écrivent dans le champ « TaxCountryRegion »
#: du SAF-T (PT) et dans le champ I1 du code QR.
CONTINENT = 'PT'
ACORES = 'PT-AC'
MADERE = 'PT-MA'

REGIONS = (
    (CONTINENT, 'Continent'),
    (ACORES, 'Açores'),
    (MADERE, 'Madère'),
)

#: Les taux en vigueur par région. Chaque entrée associe un taux au palier
#: correspondant. Les taux ont changé dans le passé et changeront encore :
#: cette table est le seul endroit à corriger.
PALIERS_PAR_REGION = {
    CONTINENT: {
        Decimal('23'): 'normal',
        Decimal('13'): 'intermedia',
        Decimal('6'): 'reduzida',
        Decimal('0'): 'isenta',
    },
    ACORES: {
        Decimal('16'): 'normal',
        Decimal('9'): 'intermedia',
        Decimal('4'): 'reduzida',
        Decimal('0'): 'isenta',
    },
    MADERE: {
        Decimal('22'): 'normal',
        Decimal('12'): 'intermedia',
        Decimal('5'): 'reduzida',
        Decimal('0'): 'isenta',
    },
}


class TauxInconnu(Exception):
    """Un taux qui n'appartient à aucun palier de la région.

    On lève plutôt que de deviner : un taux français de 20 % saisi sur une
    facture portugaise doit arrêter l'émission, pas se faire ranger dans le
    palier le plus proche.
    """


def _lisible(valeur):
    """Un taux écrit comme un humain l'écrit : « 20 », « 6 », « 23 ».

    `Decimal.normalize()` ne sert QU'À COMPARER, jamais à afficher : il
    rend « 2E+1 » pour 20, parce qu'il retire le zéro final. Le message
    d'erreur devenait « Le taux de 2E+1 % n'existe pas » — illisible
    précisément au moment où l'utilisateur a besoin de comprendre quel
    taux corriger.
    """
    return format(Decimal(str(valeur or 0)).normalize(), 'f')


def palier(taux, region=CONTINENT):
    """Le palier d'un taux dans une région : normal, intermedia, reduzida
    ou isenta."""
    table = PALIERS_PAR_REGION.get(region)
    if table is None:
        raise TauxInconnu(
            f'Région fiscale inconnue : « {region} ». Les trois régions '
            f'portugaises sont {CONTINENT}, {ACORES} et {MADERE}.')

    valeur = Decimal(str(taux or 0)).normalize()
    for connu, nom in table.items():
        if connu.normalize() == valeur:
            return nom

    attendus = ', '.join(f'{_lisible(t)} %' for t in table)
    raise TauxInconnu(
        f'Le taux de {_lisible(valeur)} % n’existe pas en région {region}. '
        f'Taux admis : {attendus}. Vérifiez le taux de la ligne plutôt que de '
        'le ranger dans le palier voisin : le total du document resterait '
        'juste et l’erreur ne se verrait qu’au contrôle.')


def code_saft(taux, region=CONTINENT):
    """Le code de taux du SAF-T : NOR, INT, RED ou ISE.

    La table vit dans `saft`, parce que ces codes appartiennent au format
    SAF-T et non au barème fiscal. On l'importe ici au lieu de la
    recopier : deux tables finiraient par diverger, et l'export serait
    faux pour un palier sans que l'émission, elle, signale quoi que ce
    soit.
    """
    from . import saft

    nom = palier(taux, region)
    try:
        return saft.CODES_DE_TAUX[nom]
    except KeyError:
        raise TauxInconnu(
            f'Le palier « {nom} » n’a pas de code SAF-T. Complétez '
            'saft.CODES_DE_TAUX : sans lui, l’export serait rejeté des mois '
            'après l’émission des factures.')


def ventiler(lignes, region=CONTINENT):
    """Regroupe des lignes de facture en un bloc d'espace fiscal.

    `lignes` est un itérable de triplets (taux, base, tva). Le résultat est
    le dictionnaire attendu par `qr.composer` : « regiao », et seulement
    les paliers réellement employés.

    LES PALIERS ABSENTS SONT ABSENTS, pas à zéro. « I3:0.00 » déclare une
    base réduite nulle, ce qui n'a pas le même sens fiscal qu'une facture
    sans ligne au taux réduit.
    """
    cumul = {}

    for taux, base, tva in lignes:
        nom = palier(taux, region)
        poste = cumul.setdefault(nom, [Decimal('0'), Decimal('0')])
        poste[0] += Decimal(str(base or 0))
        poste[1] += Decimal(str(tva or 0))

    bloc = {'regiao': region}

    for nom, (base, tva) in cumul.items():
        if nom == 'isenta':
            # L'exonéré n'a qu'une base : il n'y a pas de TVA à déclarer.
            bloc['base_isenta'] = base
        else:
            bloc[f'base_{nom}'] = base
            bloc[f'iva_{nom}'] = tva

    return bloc
