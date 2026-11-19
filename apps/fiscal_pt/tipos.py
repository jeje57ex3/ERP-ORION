"""Ce que chaque type de document exige, et que le schéma ne dit pas.

POURQUOI UN MODULE À PART

Le SAF-T accepte les cinq types de documents de facturation — FT, FS, FR,
ND, NC — avec exactement les mêmes éléments obligatoires. Le schéma ne
distingue rien : une note de débit sans référence à la facture qu'elle
corrige, une facture-reçu qui n'atteste aucun paiement, une facture
simplifiée de douze mille euros passent toutes les trois le contrôle du
schéma et toutes les trois le contrôle de cohérence arithmétique.

Ce sont pourtant trois documents illégaux. Les règles qui les interdisent
sont dans le Code de l'IVA, pas dans le XSD, et c'est au logiciel de les
tenir : c'est précisément ce qu'une certification vérifie.

Le module ne touche ni la base ni Django : les règles se mesurent sur des
montants et des chaînes, donc elles se testent sans migration et sans
transaction.
"""

from datetime import date as Date, datetime
from decimal import Decimal


class RegleDeType(Exception):
    """Une règle propre au type du document, dite en termes exploitables."""


# ── Les types eux-mêmes ──────────────────────────────────────────────────────

#: Les types de documents de facturation que ce logiciel émet, tels que
#: l'AT les nomme. Ce sont les valeurs du champ D du code QR et de
#: « InvoiceType » du SAF-T.
#:
#: POURQUOI LA LISTE VIT ICI ET NON DANS `models`
#:
#: C'est un fait légal, pas une liste de choix d'interface : le code QR
#: la cite, le SAF-T la cite, et l'énumération du XSD la borne. `models`
#: l'importe pour ses `choices`, de sorte qu'il n'y ait qu'une source.
#:
#: Le schéma de l'AT en accepte d'autres — VD, TV, TD, AA, DA pour les
#: données antérieures à 2013, et cinq types propres au secteur de
#: l'assurance. On ne les offre pas : une série déclarée dans un type
#: qu'on ne sait pas remplir produirait des documents que l'export
#: refuserait, et il serait trop tard pour les reprendre.
TYPES_DE_DOCUMENT = (
    ('FT', 'Fatura'),
    ('FS', 'Fatura simplificada'),
    ('FR', 'Fatura-recibo'),
    ('ND', 'Nota de débito'),
    ('NC', 'Nota de crédito'),
)

CODES_DE_TYPE = tuple(code for code, _ in TYPES_DE_DOCUMENT)


def valider_le_type(type_document):
    """Refuse un type hors liste, AVANT la signature.

    LE DÉFAUT QUE CE CONTRÔLE FERME

    `SerieFiscale.type_document` porte des `choices`, que Django ne
    vérifie qu'au `full_clean()` d'un formulaire. Une série créée
    autrement — un script, un import, la base en direct — pouvait porter
    n'importe quoi. Les documents s'émettaient et se signaient ; c'est
    l'EXPORT qui les refusait, parce que « InvoiceType » est une
    énumération du schéma. À ce moment-là le document est immuable et le
    fichier entier est bloqué, pour un défaut de configuration.
    """
    if type_document not in CODES_DE_TYPE:
        raise RegleDeType(
            f'« {type_document} » n’est pas un type de document émis par ce '
            f'logiciel. Les types possibles sont : '
            f'{", ".join(CODES_DE_TYPE)}. Un type hors liste serait signé '
            'sans protester et ferait refuser l’export, alors que le '
            'document ne serait plus modifiable.')
    return type_document


# ── Les documents rectificatifs ──────────────────────────────────────────────

#: Les types qui RECTIFIENT un autre document, et doivent le désigner.
#:
#: POURQUOI CETTE LISTE N'EST PAS CELLE DU SENS DÉBIT/CRÉDIT
#:
#: Les deux notions se confondent tant qu'on ne connaît que la note de
#: crédit, qui est à la fois rectificative et portée au débit. La note de
#: DÉBIT sépare les deux : elle rectifie une facture — l'article 29.º n.º 7
#: du CIVA la nomme « documento retificativo » au même titre que l'avoir,
#: et l'article 36.º n.º 6 lui impose « a referência à fatura a que
#: respeitam » — mais elle AUGMENTE ce que le client doit, donc son montant
#: va au crédit comme celui d'une facture.
#:
#: Une seule liste pour les deux usages donnait donc, mécaniquement, une
#: note de débit à laquelle le logiciel REFUSAIT de rattacher une facture.
#: Chaque note de débit émise était illégale, et rien ne le signalait : le
#: schéma rend `References` optionnel.
TYPES_RECTIFICATIFS = ('NC', 'ND')

#: Les types qui attestent un encaissement au moment de leur émission.
#:
#: Une facture-reçu vaut quittance : le client peut l'opposer comme preuve
#: de paiement. En émettre une sans enregistrer le paiement produit un
#: document qui atteste un encaissement dont le fichier ne porte pas trace.
TYPES_QUI_ATTESTENT_UN_PAIEMENT = ('FR',)


def exige_une_rectification(type_document):
    """Ce type doit-il désigner le document qu'il corrige ?"""
    return type_document in TYPES_RECTIFICATIFS


def atteste_un_paiement(type_document):
    """Ce type vaut-il quittance ?"""
    return type_document in TYPES_QUI_ATTESTENT_UN_PAIEMENT


# ── Les moyens de paiement ───────────────────────────────────────────────────

#: Les quatorze mécanismes de paiement du SAF-T, relevés un par un dans
#: l'énumération « PaymentMechanism » du schéma 1.04_01 et non dans une
#: documentation qui la reproduit. Un code hors de cette liste fait rejeter
#: le fichier entier, et le message de l'AT ne nomme pas le document fautif.
MECANISMES_DE_PAIEMENT = (
    ('NU', 'Numéraire'),
    ('CC', 'Carte de crédit'),
    ('CD', 'Carte de débit'),
    ('CH', 'Chèque bancaire'),
    ('TB', 'Virement ou prélèvement autorisé'),
    ('MB', 'Référence de paiement Multibanco'),
    ('CI', 'Crédit documentaire international'),
    ('CO', 'Chèque ou carte cadeau'),
    ('CS', 'Compensation de soldes en compte courant'),
    ('DE', 'Monnaie électronique'),
    ('LC', 'Lettre de change'),
    ('PR', 'Échange de biens'),
    ('TR', 'Titres de compensation extrasalariale'),
    ('OU', 'Autres moyens'),
)

CODES_DE_MECANISME = tuple(code for code, _ in MECANISMES_DE_PAIEMENT)


def libelle_de_mecanisme(code):
    """Le libellé lisible d'un mécanisme, ou le code s'il est inconnu."""
    for connu, libelle in MECANISMES_DE_PAIEMENT:
        if connu == code:
            return libelle
    return code or ''


def valider_le_mecanisme(code):
    """Refuse un mécanisme hors énumération, en nommant les possibles."""
    if code and code not in CODES_DE_MECANISME:
        raise RegleDeType(
            f'« {code} » n’est pas un moyen de paiement du SAF-T. Le schéma '
            f'n’en accepte que quatorze : {", ".join(CODES_DE_MECANISME)}. '
            'Un code hors liste fait rejeter le fichier entier, et le motif '
            'rendu par l’AT ne désigne pas le document fautif.')
    return code


# ── La facture simplifiée ────────────────────────────────────────────────────

#: Article 40.º n.º 1 a) du CIVA : ventes de biens par des détaillants ou
#: des marchands ambulants à des non-assujettis.
PLAFOND_DETAILLANT = Decimal('1000')

#: Article 40.º n.º 1 b) : toutes les autres livraisons de biens et
#: prestations de services. C'est le cas d'une entreprise de travaux.
PLAFOND_ORDINAIRE = Decimal('100')

#: Les trois cas de l'article 40.º n.º 1, dans sa rédaction en vigueur
#: depuis le 25 mars 2025 (Decreto-Lei n.º 35/2025, qui a ajouté le c)).
REGIMES_SIMPLIFIEE = (
    ('b', 'Autres livraisons et prestations — plafond 100 € (art. 40.º/1 b)'),
    ('a', 'Détaillant ou marchand ambulant — plafond 1 000 € (art. 40.º/1 a)'),
    ('c', 'Régime d’exonération de l’article 53.º — sans plafond '
          '(art. 40.º/1 c)'),
)

REGIME_SIMPLIFIEE_PAR_DEFAUT = 'b'

PLAFONDS = {'a': PLAFOND_DETAILLANT, 'b': PLAFOND_ORDINAIRE, 'c': None}


def plafond_simplifiee(regime=REGIME_SIMPLIFIEE_PAR_DEFAUT):
    """Le plafond du régime, ou None quand il n'y en a pas."""
    if regime not in PLAFONDS:
        raise RegleDeType(
            f'« {regime} » n’est pas un cas de l’article 40.º n.º 1. Les '
            'trois cas sont a), b) et c).')
    return PLAFONDS[regime]


def verifier_le_plafond(total_base, total,
                        regime=REGIME_SIMPLIFIEE_PAR_DEFAUT):
    """Le plafond de la facture simplifiée, et la contradiction qu'il porte.

    DEUX LECTURES, ET CE QU'ON EN FAIT

    L'article 40.º plafonne « o montante da fatura », ce qui se lit comme
    le total à payer. L'Ofício-Circulado n.º 30141 du 4 janvier 2013
    précise, lui, que « para determinação dos montantes referidos,
    considera-se o valor da fatura sem o IVA ».

    Les deux lectures ne divergent que dans une bande étroite : un total
    hors taxe au-dessous du plafond et un total à payer au-dessus. Choisir
    l'une et se taire reviendrait soit à refuser des factures que
    l'administration accepte, soit à en laisser passer qu'un contrôle
    pourrait reprendre.

    On refuse donc là où les deux lectures s'accordent — hors taxe
    au-dessus du plafond, illégal dans les deux cas — et on AVERTIT dans
    la bande de divergence, sans bloquer : le choix revient à l'entreprise
    et à son comptable, pas au logiciel, mais il doit être fait en
    connaissance de cause.

    Rend la liste des avertissements. Lève `RegleDeType` sur un refus.
    """
    plafond = plafond_simplifiee(regime)
    if plafond is None:
        return []

    base = Decimal(str(total_base or 0))
    brut = Decimal(str(total or 0))

    if base > plafond:
        raise RegleDeType(
            f'Une facture simplifiée ne peut pas dépasser '
            f'{_lisible(plafond)} € : celle-ci porte '
            f'{_lisible(base)} € hors taxe, au-dessus du plafond quelle que '
            'soit la lecture retenue (article 40.º n.º 1 du CIVA). Émettez '
            'une facture complète — une facture simplifiée hors plafond est '
            'irrégulière, et le client ne peut pas y déduire la TVA.')

    if brut > plafond:
        return [
            f'Le total à payer ({_lisible(brut)} €) dépasse le plafond de '
            f'{_lisible(plafond)} €, mais le total hors taxe '
            f'({_lisible(base)} €) le respecte. L’article 40.º plafonne « o '
            'montante da fatura » ; l’Ofício-Circulado n.º 30141/2013 précise '
            'qu’il s’entend hors TVA. La facture est régulière selon la '
            'doctrine de l’administration, et contestable selon la lettre du '
            'texte. À vérifier avec votre comptable.'
        ]

    return []


# ── Le paiement d'une facture-reçu ───────────────────────────────────────────

def valider_les_paiements(paiements, total, type_document):
    """Ce qu'une facture-reçu doit porter, et ce qu'aucun type ne peut porter.

    POURQUOI LA SOMME EST EXIGÉE EXACTE

    Une facture-reçu est une quittance. Si la somme encaissée est
    inférieure au total, le document atteste un paiement qui n'a pas
    soldé la facture, et aucun écran ne le dira : il s'imprime
    « fatura-recibo » comme les autres. Si elle est supérieure, le fichier
    déclare un encaissement qui n'a pas eu lieu.

    Les montants sont des `Decimal` au centime : la tolérance d'un centime
    admise ailleurs sur la TVA n'a pas lieu d'être ici, parce qu'un
    encaissement n'est pas le résultat d'un arrondi — c'est une somme qui
    a réellement changé de main.

    LA FONCTION MODIFIE LES DICTIONNAIRES REÇUS, et c'est voulu : la date
    normalisée doit atteindre le document figé. Vérifier sans normaliser
    laisserait la chaîne du formulaire filer jusqu'au fichier, où elle
    serait écrite telle quelle — c'est exactement le défaut que
    `_date_certaine` ferme.

    Rend la liste des avertissements. Lève `RegleDeType` sur un refus.
    """
    paiements = list(paiements or [])

    # L'ORDRE DES DEUX CONTRÔLES, et ce qu'il change pour le lecteur.
    #
    # On refuse d'abord le paiement sur un type qui n'atteste rien, AVANT
    # de valider le paiement lui-même. L'inverse donnerait, sur une
    # facture ordinaire portant un encaissement mal saisi, un message sur
    # le moyen de paiement — qui enverrait corriger le code au lieu de
    # dire la vérité : ce document ne devrait porter aucun paiement.
    if not atteste_un_paiement(type_document):
        if paiements:
            raise RegleDeType(
                f'Un document de type « {type_document} » n’atteste aucun '
                'paiement. Pour une facture payée à l’émission, employez une '
                'série de type « FR » (fatura-recibo) : c’est elle qui vaut '
                'quittance.')
        return []

    # UN SEUL PAIEMENT SANS MONTANT VAUT « LE TOTAL ».
    #
    # Ce n'est pas une commodité : c'est la seule valeur légale, et la
    # faire porter par l'appelant l'obligerait à la connaître d'avance.
    # Or le total du document est calculé À L'ÉMISSION depuis les lignes
    # figées ; le cumul qu'un écran a sous la main est un autre nombre,
    # tenu à part, qui dérive d'un centime après une suppression de
    # ligne. Laisser l'appelant le fournir ferait entrer cette dérive
    # dans une quittance — et au Portugal ce centime est signé.
    #
    # Au-delà d'un paiement, les montants sont exigés : « le total »
    # réparti sur plusieurs moyens n'a pas de sens par défaut.
    if len(paiements) == 1 and paiements[0].get('montant') is None:
        paiements[0]['montant'] = Decimal(str(total or 0))

    for rang, paiement in enumerate(paiements, start=1):
        valider_le_mecanisme(paiement.get('mecanisme'))
        if paiement.get('montant') is None:
            raise RegleDeType(
                f'Le paiement {rang} n’a pas de montant. Avec plusieurs '
                'moyens de paiement, chacun doit porter le sien : « le '
                'total » réparti sur plusieurs n’a pas de valeur par '
                'défaut. Le schéma rend « PaymentAmount » obligatoire.')
        paiement['date'] = _date_certaine(paiement.get('date'), rang)

    if not paiements:
        raise RegleDeType(
            'Une facture-reçu atteste un encaissement : elle doit porter au '
            'moins un paiement. Sans cela le document vaut quittance pour un '
            'paiement dont le fichier ne garde aucune trace. Pour une facture '
            'à régler plus tard, employez une série de type « FT ».')

    encaisse = sum((Decimal(str(p.get('montant') or 0)) for p in paiements),
                   Decimal('0'))
    attendu = Decimal(str(total or 0))

    if encaisse != attendu:
        sens = 'inférieure' if encaisse < attendu else 'supérieure'
        raise RegleDeType(
            f'La somme encaissée ({_lisible(encaisse)} €) est {sens} au '
            f'total de la facture-reçu ({_lisible(attendu)} €). Une '
            'facture-reçu vaut quittance du total : un écart en moins '
            'atteste un solde payé qui ne l’est pas, un écart en plus '
            'déclare un encaissement qui n’a pas eu lieu. Pour un acompte, '
            'émettez une facture « FT » et un reçu séparé.')

    return []


# ── Le tout ──────────────────────────────────────────────────────────────────

def verifier(type_document, total_base, total, document_rectifie=None,
             paiements=None, regime=REGIME_SIMPLIFIEE_PAR_DEFAUT):
    """Toutes les règles du type, en un appel, avant que le document soit figé.

    Rend la liste des avertissements. Lève `RegleDeType` au premier refus.

    L'ordre compte : on vérifie d'abord ce qui rend le document ILLÉGAL,
    puis ce qui le rend seulement discutable. Une facture simplifiée de
    douze mille euros a un problème plus pressant que l'ambiguïté du
    plafond.
    """
    avertissements = []

    valider_le_type(type_document)

    if exige_une_rectification(type_document):
        if document_rectifie is None:
            raise RegleDeType(
                f'Un document de type « {type_document} » rectifie une '
                'facture et doit la désigner : l’article 36.º n.º 6 du CIVA '
                'exige « a referência à fatura a que respeitam », et '
                'l’administration rapproche les deux. Le schéma, lui, '
                'accepterait le document sans référence — le fichier serait '
                'valide et le document irrégulier.')
    elif document_rectifie is not None:
        raise RegleDeType(
            f'Un document de type « {type_document} » ne rectifie rien. '
            'Employez une série de type « NC » pour diminuer le montant dû, '
            '« ND » pour l’augmenter.')

    avertissements += valider_les_paiements(paiements, total, type_document)

    if type_document == 'FS':
        avertissements += verifier_le_plafond(total_base, total, regime)

    return avertissements


def _date_certaine(valeur, rang):
    """Une vraie date, ou un refus — jamais une chaîne qu'on espère juste.

    LE DÉFAUT QUE CETTE FONCTION FERME

    `PaymentDate` était seulement vérifié non vide. Une saisie malformée
    arrivant du formulaire — un champ date d'un navigateur qui n'en a pas,
    une valeur postée à la main — était donc acceptée, SIGNÉE, et figée
    dans le document. Le composeur du SAF-T, lui, écrit `str(valeur)[:10]`
    sans rien vérifier : le fichier portait
    `<PaymentDate>pas-une-da</PaymentDate>`.

    Le défaut ne se découvrait qu'à l'export, c'est-à-dire des semaines
    plus tard, sur un document immuable que seul un avoir peut reprendre.
    C'est la forme la plus coûteuse d'erreur de saisie : celle dont le
    coût arrive après le point de non-retour.
    """
    if isinstance(valeur, datetime):
        return valeur.date()
    if isinstance(valeur, Date):
        return valeur
    if valeur:
        try:
            return Date.fromisoformat(str(valeur)[:10])
        except ValueError:
            raise RegleDeType(
                f'« {valeur} » n’est pas une date d’encaissement lisible '
                f'(paiement {rang}). Le SAF-T attend AAAA-MM-JJ. Une valeur '
                'illisible serait signée telle quelle, et ne se découvrirait '
                'qu’à l’export — sur un document que plus rien ne corrige.')
    raise RegleDeType(
        f'Le paiement {rang} n’a pas de date. Le schéma rend '
        '« PaymentDate » obligatoire.')


def _lisible(valeur):
    """`Decimal.normalize()` ne sert QU'À COMPARER, jamais à afficher : il
    rend « 1E+3 » pour 1000, et le message devient illisible au moment
    précis où on en a besoin."""
    return format(Decimal(str(valeur or 0)).normalize(), 'f')
