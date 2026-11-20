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
#:
#: Le reçu « RG » y figure pour la même raison, et c'est même sa seule
#: raison d'être : un reçu qui ne dit pas ce qu'il a reçu n'est rien.
TYPES_QUI_ATTESTENT_UN_PAIEMENT = ('FR', 'RG')


def exige_une_rectification(type_document):
    """Ce type doit-il désigner le document qu'il corrige ?"""
    return type_document in TYPES_RECTIFICATIFS


def atteste_un_paiement(type_document):
    """Ce type vaut-il quittance ?"""
    return type_document in TYPES_QUI_ATTESTENT_UN_PAIEMENT


# ── Les états d'un document ──────────────────────────────────────────────────

#: Les cinq états d'un document de FACTURATION, relevés dans l'énumération
#: « InvoiceStatus » du schéma, avec le sens que sa documentation leur
#: donne — « R » est un document de RÉSUMÉ d'autres documents créés dans
#: une autre application, et non un « autre » état fourre-tout.
ETATS_DE_FACTURATION = (
    ('N', 'Normal'),
    ('S', 'Autofacturation'),
    ('A', 'Annulé'),
    ('R', 'Résumé d’autres documents'),
    ('F', 'Facturé'),
)

CODES_D_ETAT_DE_FACTURATION = tuple(code for code, _ in ETATS_DE_FACTURATION)

#: Les états d'un REÇU. Le schéma n'en accepte que DEUX : « PaymentStatus »
#: vaut « N » ou « A », là où un document de facturation en accepte cinq.
#:
#: LES DEUX LISTES SE RESSEMBLENT ASSEZ POUR QU'ON SOIT TENTÉ DE N'EN
#: TENIR QU'UNE. Un reçu marqué « F » passerait alors de notre côté et
#: serait refusé par le schéma de l'AT — sur un document déjà figé, et en
#: bloquant le fichier entier. C'est le même piège que les deux listes de
#: types rectificatifs, à un endroit différent.
ETATS_DE_RECU = (
    ('N', 'Normal'),
    ('A', 'Annulé'),
)

CODES_D_ETAT_DE_RECU = tuple(code for code, _ in ETATS_DE_RECU)


def valider_l_etat(etat, type_document):
    """Refuse un état hors énumération, AVANT la signature.

    LE DÉFAUT QUE CE CONTRÔLE FERME, ET C'EST LE TROISIÈME DE SA FAMILLE

    `etat` arrivait jusqu'au document sans contrôle : les `choices` du
    modèle ne sont vérifiés qu'au `full_clean()` d'un formulaire, et
    l'émission n'en fait pas. Un état hors liste était donc signé,
    inscrit dans le champ E du code QR et dans « InvoiceStatus » — où le
    schéma, lui, l'énumère. Le document s'émettait, et c'est l'EXPORT du
    fichier ENTIER qui échouait, sur un document que plus rien ne
    modifie.

    Exactement le même défaut que le type de série hors liste, et au même
    endroit du chemin. Un défaut de cette famille ne se corrige pas une
    fois : il se cherche partout où une énumération du schéma entre dans
    le logiciel sans passer par un formulaire.
    """
    # QUATRE FAMILLES, QUATRE LISTES. Elles se ressemblent assez pour
    # qu'on soit tente de n'en tenir qu'une, et le « T » de la table 4.2
    # n'existe dans aucune autre. Voir les listes plus bas dans ce
    # module, relevees une par une dans le XSD.
    if est_un_recu(type_document):
        admis = CODES_D_ETAT_DE_RECU
    elif est_un_mouvement(type_document):
        admis = CODES_D_ETAT_DE_MOUVEMENT
    elif est_un_document_de_travail(type_document):
        admis = CODES_D_ETAT_DE_TRAVAIL
    else:
        admis = CODES_D_ETAT_DE_FACTURATION

    if etat not in admis:
        raise RegleDeType(
            f'« {etat} » n’est pas un état possible pour un document de '
            f'type « {type_document} ». Le schéma n’en accepte que '
            f'{len(admis)} : {", ".join(admis)}. Un état hors liste serait '
            'signé sans protester et ferait refuser l’export entier, alors '
            'que le document ne serait plus modifiable.')
    return etat


# ── Les reçus, qui ne sont pas des documents de facturation ──────────────────

#: Les types de reçus, relevés dans l'énumération « SAFTPTPaymentType » du
#: schéma : elle n'en accepte que DEUX. « RC » est le reçu du régime de
#: TVA sur les encaissements (regime de IVA de caixa), « RG » tout autre
#: reçu émis.
#:
#: CE LOGICIEL N'ÉMET QUE « RG », ET LE REFUS DE « RC » EST EXPLICITE.
#:
#: Le schéma impose à CHAQUE ligne d'un « RC » de porter son bloc `Tax` —
#: il l'écrit dans un `xs:assert`, et notre validateur ne lit pas les
#: asserts. Un « RC » composé comme un « RG » passerait donc notre
#: contrôle et serait refusé par celui de l'AT. Offrir un type qu'on ne
#: sait pas remplir est le piège que `valider_le_type` a déjà fermé une
#: fois : la série se déclare, les documents se signent, et l'export les
#: refuse quand il est trop tard pour les reprendre.
TYPES_DE_RECU = (
    ('RG', 'Recibo'),
)

#: Le type que le schéma connaît et que ce logiciel n'émet pas.
TYPE_DE_RECU_NON_COUVERT = 'RC'

CODES_DE_RECU = tuple(code for code, _ in TYPES_DE_RECU)

#: Les types qu'une SÉRIE peut porter. Un reçu se numérote dans une série
#: déclarée à l'AT comme n'importe quel document, avec son propre code de
#: validation et son propre compteur : c'est la même table.
#: Defini a la FIN de ce module, apres les quatre familles qu'il reunit.
#: Une affectation de module s'evalue a l'import : ecrite ici, elle levait
#: « NameError: name 'TYPES_DE_MOUVEMENT' is not defined » et empechait
#: Django de charger l'application. Les CORPS de fonction, eux, resolvent
#: leurs noms a l'appel et peuvent donc citer ce qui vient plus bas.
TYPES_DE_SERIE = ()  # complete en fin de module

#: Les types de documents dont le RÈGLEMENT fait SORTIR l'argent, donc
#: dont la ligne de reçu va au débit.
#:
#: Régler une facture fait entrer de l'argent — ligne au crédit.
#: Rembourser un avoir en fait sortir — ligne au débit.
#:
#: CETTE LISTE COÏNCIDE AUJOURD'HUI AVEC `saft.TYPES_AU_DEBIT`, POUR UNE
#: AUTRE RAISON. Là-bas, « NC » va au débit parce que l'avoir diminue le
#: chiffre d'affaires ; ici, parce que l'argent part. Les deux
#: raisonnements se rejoignent sur « NC » et rien ne garantit qu'ils se
#: rejoignent sur le type suivant — c'est mot pour mot la confusion qui
#: rendait illégale toute note de débit. Deux listes, donc, et un test
#: qui échoue si quelqu'un les réunit.
TYPES_REGLES_AU_DEBIT = ('NC',)


def est_un_recu(type_document):
    """Ce type relève-t-il de la table 4.4 du SAF-T, et non de la 4.1 ?"""
    return type_document in CODES_DE_RECU


def valider_le_type_de_recu(type_recu):
    """Refuse un type de reçu que ce logiciel ne sait pas composer."""
    if type_recu == TYPE_DE_RECU_NON_COUVERT:
        raise RegleDeType(
            f'Le reçu « {TYPE_DE_RECU_NON_COUVERT} » relève du régime de TVA '
            'sur les encaissements (regime de IVA de caixa), que ce logiciel '
            'ne couvre pas : le schéma exige que chacune de ses lignes porte '
            'sa TVA, et ce reçu serait refusé par l’AT après avoir été émis. '
            'Employez une série de type « RG ».')
    if type_recu not in CODES_DE_RECU:
        raise RegleDeType(
            f'« {type_recu} » n’est pas un type de reçu. Le schéma n’en '
            f'accepte que deux — « RG » et « {TYPE_DE_RECU_NON_COUVERT} » — '
            f'et ce logiciel émet « {", ".join(CODES_DE_RECU)} ».')
    return type_recu


def regle_au_debit(type_du_document):
    """Le règlement de ce document fait-il sortir l'argent ?

    `type_du_document` est le type du document RÉGLÉ, pas celui du reçu.
    Absent, on répond « non » : un reçu règle une facture dans
    l'immense majorité des cas, et c'est la seule valeur par défaut qui
    ne crée pas de mouvement imaginaire. Fourni, il est validé — un type
    inconnu serait silencieusement traité comme une facture, et un
    remboursement compterait comme une recette.
    """
    if not type_du_document:
        return False
    valider_le_type(type_du_document)
    return type_du_document in TYPES_REGLES_AU_DEBIT


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
            f'Un document de type « {type_document} » atteste un '
            'encaissement : il doit porter au moins un paiement. Sans cela '
            'il vaut quittance pour un règlement dont le fichier ne garde '
            'aucune trace. Pour une facture à régler plus tard, employez une '
            'série de type « FT ».')

    encaisse = sum((Decimal(str(p.get('montant') or 0)) for p in paiements),
                   Decimal('0'))
    attendu = Decimal(str(total or 0))

    if encaisse != attendu:
        sens = 'inférieure' if encaisse < attendu else 'supérieure'
        raise RegleDeType(
            f'La somme encaissée ({_lisible(encaisse)} €) est {sens} au '
            f'total du document « {type_document} » '
            f'({_lisible(attendu)} €). Ce document vaut quittance de son '
            'total : un écart en moins atteste un solde payé qui ne l’est '
            'pas, un écart en plus déclare un encaissement qui n’a pas eu '
            'lieu. Pour un acompte, émettez une facture « FT » et un reçu '
            '« RG » du montant reçu.')

    return []


# ── Ce qu'un reçu affecte ────────────────────────────────────────────────────

#: La longueur du champ `OriginatingON` du SAF-T, qui porte le numéro du
#: document réglé.
LONGUEUR_DU_RENVOI = 60


def valider_les_affectations(affectations):
    """Les documents qu'un reçu solde, et le montant affecté à chacun.

    POURQUOI UN REÇU NE PEUT PAS ÊTRE ORPHELIN

    Le schéma impose à chaque ligne un `SourceDocumentID` — le numéro du
    document réglé et sa date. Ce n'est pas une formalité : un reçu qui ne
    dit pas ce qu'il solde ne solde rien de vérifiable, et
    l'administration rapproche les deux tables. La loi dit la même chose
    autrement : un reçu est la quittance D'UNE créance.

    POURQUOI UN REÇU NE MÉLANGE PAS LES DEUX SENS

    Encaisser le règlement d'une facture et rembourser un avoir sont deux
    mouvements opposés. Un reçu qui porterait les deux n'aurait pas de
    total : la table 4.4 tient ses sommes de contrôle SÉPARÉMENT au débit
    et au crédit, et `GrossTotal` est un nombre unique. Le document
    s'imprimerait avec un total net qui ne correspondrait à aucun des
    deux mouvements.

    LA FONCTION MODIFIE LES DICTIONNAIRES REÇUS, comme
    `valider_les_paiements` : la date normalisée et le sens calculé
    doivent atteindre le document figé.

    Rend (liste normalisée, total, au_debit). Lève `RegleDeType`.
    """
    affectations = list(affectations or [])

    if not affectations:
        raise RegleDeType(
            'Un reçu doit dire ce qu’il règle : au moins un document et le '
            'montant affecté. Le schéma exige « SourceDocumentID » sur '
            'chaque ligne, et un reçu sans affectation ne solde rien que '
            'l’administration puisse rapprocher.')

    total = Decimal('0')
    sens_vus = set()

    for rang, affectation in enumerate(affectations, start=1):
        renvoi = str(affectation.get('document') or '').strip()
        if not renvoi:
            raise RegleDeType(
                f'L’affectation {rang} ne désigne aucun document. Un reçu '
                'est la quittance d’une créance : il doit nommer le document '
                'qu’il solde, et le SAF-T le porte dans « OriginatingON ».')
        if len(renvoi) > LONGUEUR_DU_RENVOI:
            raise RegleDeType(
                f'Le numéro « {renvoi[:20]}… » dépasse '
                f'{LONGUEUR_DU_RENVOI} caractères, la taille du champ '
                '« OriginatingON ». Le fichier entier serait refusé.')
        affectation['document'] = renvoi

        affectation['date'] = _date_certaine(affectation.get('date'), rang)

        montant = Decimal(str(affectation.get('montant') or 0))
        if montant <= 0:
            raise RegleDeType(
                f'L’affectation {rang} porte {_lisible(montant)} €. Un reçu '
                'atteste une somme reçue ou rendue : zéro n’atteste rien, et '
                'un montant négatif ne peut pas être imprimé — le Despacho '
                '8632/2014 (2.2.6) l’interdit sur les documents émis, et '
                'c’est à un avoir qu’il revient d’inverser un mouvement.')
        affectation['montant'] = montant
        total += montant

        au_debit = regle_au_debit(affectation.get('type_du_document'))
        affectation['au_debit'] = au_debit
        sens_vus.add(au_debit)

    if len(sens_vus) > 1:
        raise RegleDeType(
            'Ce reçu encaisse et rembourse à la fois. Les deux mouvements '
            'sont opposés et la table 4.4 du SAF-T tient ses sommes de '
            'contrôle séparément au débit et au crédit : un reçu mixte '
            'n’aurait pas de total, et s’imprimerait avec un net qui ne '
            'correspond à aucun des deux. Émettez deux reçus.')

    return affectations, total, sens_vus.pop()


def verifier_un_recu(type_recu, affectations, paiements, etat='N'):
    """Toutes les règles d'un reçu, avant qu'il soit figé.

    Rend (affectations normalisées, total, au_debit, avertissements).
    Lève `RegleDeType` au premier refus.

    Le total n'est pas un paramètre : il EST la somme des affectations, et
    le calculer ici plutôt que de le recevoir ferme la porte qu'a déjà
    ouverte la facture-reçu — un cumul tenu ailleurs, qui dérive d'un
    centime, et qui se retrouve signé dans une quittance.
    """
    avertissements = []

    valider_le_type_de_recu(type_recu)
    valider_l_etat(etat, type_recu)

    affectations, total, au_debit = valider_les_affectations(affectations)
    avertissements += valider_les_paiements(paiements, total, type_recu)

    return affectations, total, au_debit, avertissements


# ── Le tout ──────────────────────────────────────────────────────────────────

def verifier(type_document, total_base, total, document_rectifie=None,
             paiements=None, regime=REGIME_SIMPLIFIEE_PAR_DEFAUT, etat='N'):
    """Toutes les règles du type, en un appel, avant que le document soit figé.

    Rend la liste des avertissements. Lève `RegleDeType` au premier refus.

    L'ordre compte : on vérifie d'abord ce qui rend le document ILLÉGAL,
    puis ce qui le rend seulement discutable. Une facture simplifiée de
    douze mille euros a un problème plus pressant que l'ambiguïté du
    plafond.
    """
    avertissements = []

    valider_le_type(type_document)
    valider_l_etat(etat, type_document)

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
    """Un montant, pour un message adressé à quelqu'un.

    DEUX DÉCIMALES, TOUJOURS, ET UNE VIRGULE.

    `Decimal.normalize()` était employé ici, et la docstring disait
    elle-même qu'il « ne sert QU'À COMPARER, jamais à afficher ». Le
    `'f'` qui suivait fermait bien le piège de « 1E+3 » pour 1000, mais
    pas celui des zéros de queue : 98,40 s'écrivait « 98.4 ».

    Sur de l'argent, ce n'est pas un détail de présentation. « La somme
    encaissée (90 €) est inférieure au total (98.4 €) » laisse chercher
    un écart de quarante centimes là où il est de huit euros quarante —
    et ces messages servent précisément à retrouver un écart.

    Les huit appels sont tous des montants, chacun suivi d'un « € » dans
    une phrase française. La virgule est donc la bonne séparation.
    """
    montant = Decimal(str(valeur or 0)).quantize(Decimal('0.01'))
    return f'{montant:.2f}'.replace('.', ',')


# ── Les mouvements de marchandises et les documents de travail ───────────────
#
# DEUX TABLES DE PLUS, ET QUATRE LISTES D'ÉTATS QUI NE SE RESSEMBLENT QUE
# DE LOIN.
#
# Le schéma de l'AT énumère un état par table, et les quatre listes
# diffèrent — relevées une par une dans `SAFTPT1.04_01.xsd` :
#
#     InvoiceStatus   (4.1)  N  S  A  R  F
#     MovementStatus  (4.2)  N  T  A  F  R
#     WorkStatus      (4.3)  N  A  F
#     PaymentStatus   (4.4)  N  A
#
# Le « T » de la table 4.2 n'existe dans aucune autre : c'est le document
# de transport dont les biens sont en cours d'acheminement. Tenir une
# seule liste pour les quatre ferait passer de notre côté un état que le
# schéma refuse — sur un document déjà signé, et en bloquant le fichier
# entier. C'est le même piège que les deux listes de types rectificatifs,
# à deux endroits de plus.

#: Les types de mouvement, relevés dans l'énumération « MovementType ».
#:
#: Les cinq sont offerts, et c'est un choix MOTIVÉ par le schéma : il les
#: compose à l'identique — même séquence, mêmes cardinalités — et AUCUN de
#: ses deux `xs:assert` ne les distingue. C'est la différence matérielle
#: avec le reçu « RC », refusé plus haut : là, un assert impose à chaque
#: ligne un bloc `Tax` que nous ne produisons pas, donc le type serait
#: accepté chez nous et refusé par l'AT. Ici, rien de tel. Refuser un type
#: que nous savons composer reviendrait à décider à la place de
#: l'exploitant QUAND chacun est légal, ce qui n'est pas notre rôle.
TYPES_DE_MOUVEMENT = (
    ('GR', 'Guia de remessa'),
    ('GT', 'Guia de transporte'),
    ('GA', 'Guia de movimentação de ativos próprios'),
    ('GC', 'Guia de consignação'),
    ('GD', 'Guia ou nota de devolução'),
)

CODES_DE_MOUVEMENT = tuple(code for code, _ in TYPES_DE_MOUVEMENT)

#: Les types de documents de travail, relevés dans « WorkType ». Quatorze,
#: et la même raison de les offrir tous : le schéma les compose à
#: l'identique et aucun de ses cinq `xs:assert` ne les distingue.
#:
#: « OR » est le devis, « FO » la fiche de chantier, « NE » le bon de
#: commande : les trois que cet ERP produit déjà sous un autre nom.
TYPES_DE_TRAVAIL = (
    ('CM', 'Consultas de mesa'),
    ('CC', 'Crédito de consignação'),
    ('FC', 'Fatura de consignação (art. 38.º CIVA)'),
    ('FO', 'Folhas de obra'),
    ('NE', 'Nota de encomenda'),
    ('OU', 'Outros'),
    ('OR', 'Orçamentos'),
    ('PF', 'Pró-forma'),
    ('DC', 'Documentos de conferência'),
    ('RP', 'Prémio ou recibo de prémio'),
    ('RE', 'Estorno ou recibo de estorno'),
    ('CS', 'Imputação a co-seguradoras'),
    ('LD', 'Imputação a co-seguradora líder'),
    ('RA', 'Resseguro aceite'),
)

CODES_DE_TRAVAIL = tuple(code for code, _ in TYPES_DE_TRAVAIL)

#: Les états d'un MOUVEMENT. Cinq, dont un « T » unique au schéma.
ETATS_DE_MOUVEMENT = (
    ('N', 'Normal'),
    ('T', 'Biens en cours d’acheminement'),
    ('A', 'Annulé'),
    ('F', 'Facturé'),
    ('R', 'Résumé d’autres documents'),
)

CODES_D_ETAT_DE_MOUVEMENT = tuple(code for code, _ in ETATS_DE_MOUVEMENT)

#: Les états d'un DOCUMENT DE TRAVAIL. Trois seulement : ni « S », ni « R ».
ETATS_DE_TRAVAIL = (
    ('N', 'Normal'),
    ('A', 'Annulé'),
    ('F', 'Facturé'),
)

CODES_D_ETAT_DE_TRAVAIL = tuple(code for code, _ in ETATS_DE_TRAVAIL)


def est_un_mouvement(type_document):
    """Ce type relève-t-il de la table 4.2 du SAF-T ?"""
    return type_document in CODES_DE_MOUVEMENT


def est_un_document_de_travail(type_document):
    """Ce type relève-t-il de la table 4.3 du SAF-T ?"""
    return type_document in CODES_DE_TRAVAIL


def table_du_type(type_document):
    """La table du SAF-T où ce type se déclare, pour les messages.

    Quatre tables, quatre jeux de règles. Nommer la table dans un refus
    fait gagner le temps qu'on passerait à chercher laquelle s'applique.
    """
    if est_un_recu(type_document):
        return '4.4 (Payments)'
    if est_un_mouvement(type_document):
        return '4.2 (MovementOfGoods)'
    if est_un_document_de_travail(type_document):
        return '4.3 (WorkingDocuments)'
    return '4.1 (SalesInvoices)'


def valider_le_type_de_mouvement(type_mouvement):
    """Refuse un type de mouvement hors énumération, AVANT la signature."""
    if type_mouvement not in CODES_DE_MOUVEMENT:
        raise RegleDeType(
            f'« {type_mouvement} » n’est pas un type de mouvement de '
            f'marchandises. Le schéma en énumère '
            f'{len(CODES_DE_MOUVEMENT)} : {", ".join(CODES_DE_MOUVEMENT)}.')
    return type_mouvement


def valider_le_type_de_travail(type_travail):
    """Refuse un type de document de travail hors énumération."""
    if type_travail not in CODES_DE_TRAVAIL:
        raise RegleDeType(
            f'« {type_travail} » n’est pas un type de document de travail. '
            f'Le schéma en énumère {len(CODES_DE_TRAVAIL)} : '
            f'{", ".join(CODES_DE_TRAVAIL)}.')
    return type_travail


#: Les types de mouvement dont la ligne va au DÉBIT.
#:
#: Un retour fait rentrer la marchandise : la ligne va au débit. Tout
#: autre mouvement la fait sortir, donc au crédit.
#:
#: TROISIÈME LISTE DE SENS DE CE MODULE, et pour une troisième raison.
#: `saft.TYPES_AU_DEBIT` classe les documents de facturation d'après leur
#: effet sur le chiffre d'affaires ; `TYPES_REGLES_AU_DEBIT` classe les
#: règlements d'après le sens de l'argent ; celle-ci classe les mouvements
#: d'après le sens de la MARCHANDISE. Les trois se ressemblent et ne
#: parlent pas de la même chose. Un test échoue si quelqu'un les réunit.
MOUVEMENTS_AU_DEBIT = ('GD',)


def mouvement_au_debit(type_mouvement):
    """La ligne de ce mouvement va-t-elle au débit ?"""
    if not type_mouvement:
        return False
    valider_le_type_de_mouvement(type_mouvement)
    return type_mouvement in MOUVEMENTS_AU_DEBIT


#: Les types qu'une SERIE peut porter, les quatre familles reunies.
#:
#: Defini ICI et non plus haut : une affectation de module s'evalue a
#: l'import, et les tuples de mouvement et de travail sont declares
#: au-dessus de cette ligne mais SOUS la premiere definition. Ecrite
#: plus haut, elle levait une NameError au chargement de l'application.
TYPES_DE_SERIE = (TYPES_DE_DOCUMENT + TYPES_DE_RECU
                  + TYPES_DE_MOUVEMENT + TYPES_DE_TRAVAIL)

CODES_DE_SERIE = tuple(code for code, _ in TYPES_DE_SERIE)
