"""apps/fiscal_pt/coherence.py — Ce qu'un schéma ne sait pas dire.

POURQUOI CE MODULE EXISTE

Un XSD décrit une FORME : quels éléments, dans quel ordre, avec quelles
valeurs admises. Il ne sait pas dire que `GrossTotal` doit égaler
`NetTotal` plus `TaxPayable`, ni qu'un `ProductCode` employé sur une
ligne doit figurer dans le référentiel.

Le validateur de l'AT, lui, vérifie ces deux choses. Un fichier qui
passe le schéma et échoue ici est rejeté tout autant — et le motif du
rejet est alors bien plus difficile à comprendre, parce qu'il parle de
cohérence et non de structure.

LES DEUX FAMILLES DE CONTRÔLES

1. L'ARITHMÉTIQUE. Les totaux d'un document contre ses lignes, et les
   totaux du fichier contre ses documents. Un centime d'écart suffit à
   faire rejeter l'ensemble, et c'est l'erreur la plus courante : elle
   vient d'un cumul tenu à part qui a dérivé.

2. LE RÉFÉRENTIEL. Chaque `ProductCode`, chaque `CustomerID`, chaque
   couple (`TaxCode`, `TaxCountryRegion`) employé dans un document doit
   exister dans `MasterFiles`. C'est l'oubli le plus fréquent : les
   documents sont justes, le référentiel est incomplet, et le fichier est
   rejeté en entier.

LA TOLÉRANCE, ET POURQUOI ELLE N'EST PAS ZÉRO

La TVA d'un document se calcule ligne par ligne, et chaque ligne est
arrondie au centime. La somme des TVA arrondies diffère donc parfois
d'un centime de la TVA calculée sur le total — c'est de l'arithmétique,
pas une erreur. On tolère un centime PAR LIGNE, ce qui est la marge
qu'un arrondi peut réellement produire, et rien de plus : une tolérance
large laisserait passer une vraie incohérence.
"""

from decimal import Decimal, InvalidOperation

from . import tipos
from .saft import (ESPACE_DE_NOMS, ETATS_DE_RECU_HORS_TOTAUX,
                   ETATS_HORS_TOTAUX, TYPES_AU_DEBIT)
from .schema import Anomalie

#: La tolérance d'arrondi, par ligne de document.
TOLERANCE_PAR_LIGNE = Decimal('0.01')

ZERO = Decimal('0.00')


def _etiquette(nom):
    return f'{{{ESPACE_DE_NOMS}}}{nom}'


def _texte(element, nom):
    if element is None:
        return None
    trouve = element.find(_etiquette(nom))
    return trouve.text if trouve is not None else None


def _renseigne(element, nom):
    """Le texte d'un sous-élément, vide s'il n'apporte rien.

    POURQUOI LE `strip()` N'EST PAS UNE COQUETTERIE

    Les champs texte du SAF-T ont une longueur MINIMALE de 1. Une seule
    espace la respecte : « <OriginatingON> </OriginatingON> » passe le
    schéma, et un contrôle qui testerait seulement la présence le
    laisserait passer aussi. Une référence faite d'espaces est pourtant
    aussi inutile qu'une référence absente — c'est même le cas réel, un
    champ recopié vide.
    """
    return (_texte(element, nom) or '').strip()


def _montant(element, nom):
    """Un montant, ou None s'il est absent ou illisible.

    On rend None plutôt que zéro : un champ absent et un champ à zéro ne
    disent pas la même chose, et les confondre ferait passer un total
    manquant pour un total nul — donc équilibré.
    """
    brut = _texte(element, nom)
    if brut is None:
        return None
    try:
        return Decimal(brut.strip())
    except (InvalidOperation, AttributeError):
        return None


def _documents(racine):
    return racine.findall(
        f'{_etiquette("SourceDocuments")}/{_etiquette("SalesInvoices")}/'
        f'{_etiquette("Invoice")}')


def _recus(racine):
    return racine.findall(
        f'{_etiquette("SourceDocuments")}/{_etiquette("Payments")}/'
        f'{_etiquette("Payment")}')


def _referentiels(racine):
    """Les codes déclarés dans `MasterFiles`, pour vérifier les renvois."""
    referentiels = racine.find(_etiquette('MasterFiles'))
    if referentiels is None:
        return set(), set(), set()

    clients = {_texte(c, 'CustomerID')
               for c in referentiels.findall(_etiquette('Customer'))}
    produits = {_texte(p, 'ProductCode')
                for p in referentiels.findall(_etiquette('Product'))}
    taux = {(_texte(t, 'TaxCode'), _texte(t, 'TaxCountryRegion'))
            for t in referentiels.findall(
                f'{_etiquette("TaxTable")}/{_etiquette("TaxTableEntry")}')}

    return clients, produits, taux


# ── L'arithmétique d'un document ─────────────────────────────────────────────

def _verifier_un_document(document, anomalies):
    numero = _texte(document, 'InvoiceNo') or '(sans numéro)'
    type_document = _texte(document, 'InvoiceType') or ''
    au_debit = type_document in TYPES_AU_DEBIT

    totaux = document.find(_etiquette('DocumentTotals'))
    net = _montant(totaux, 'NetTotal')
    taxe = _montant(totaux, 'TaxPayable')
    brut = _montant(totaux, 'GrossTotal')

    if None in (net, taxe, brut):
        anomalies.append(Anomalie(
            numero, 'Un total du document est absent ou illisible : '
                    'la cohérence ne peut pas être vérifiée.'))
        return

    # 1. GrossTotal = NetTotal + TaxPayable. Exactement.
    #
    # Aucune tolérance ici : les trois nombres sont écrits par nous, et un
    # écart signifie que l'un des trois a été calculé autrement que les
    # autres.
    if brut != net + taxe:
        anomalies.append(Anomalie(
            numero,
            f'GrossTotal ({brut}) ne vaut pas NetTotal + TaxPayable '
            f'({net} + {taxe} = {net + taxe}).'))

    lignes = document.findall(_etiquette('Line'))
    if not lignes:
        anomalies.append(Anomalie(numero, 'Document sans ligne.'))
        return

    champ = 'DebitAmount' if au_debit else 'CreditAmount'
    somme = ZERO
    taxe_attendue = ZERO
    manquants = 0

    for rang, ligne in enumerate(lignes, start=1):
        montant = _montant(ligne, champ)
        if montant is None:
            manquants += 1
            # Le montant est peut-être du mauvais côté : c'est une erreur
            # bien plus parlante que « total incohérent ».
            autre = 'CreditAmount' if au_debit else 'DebitAmount'
            if _montant(ligne, autre) is not None:
                anomalies.append(Anomalie(
                    f'{numero} ligne {rang}',
                    f'Montant porté en {autre} alors qu’un document '
                    f'« {type_document} » l’attend en {champ}. Le fichier '
                    's’équilibrerait à l’envers, et le validateur de l’AT '
                    'ne le dit pas : seul le contrôle le relève.'))
            continue

        somme += montant

        taux = _montant(ligne.find(_etiquette('Tax')), 'TaxPercentage')
        if taux is not None:
            taxe_attendue += (montant * taux / Decimal('100')).quantize(
                Decimal('0.01'))

    if manquants:
        return

    # 2. NetTotal = somme des montants de lignes. Exactement, là encore.
    if somme != net:
        anomalies.append(Anomalie(
            numero,
            f'NetTotal ({net}) ne vaut pas la somme des {len(lignes)} '
            f'ligne(s) ({somme}). Un cumul tenu à part a dérivé.'))

    # 3. TaxPayable contre la TVA recalculée, à l'arrondi près.
    tolerance = TOLERANCE_PAR_LIGNE * len(lignes)
    if abs(taxe - taxe_attendue) > tolerance:
        anomalies.append(Anomalie(
            numero,
            f'TaxPayable ({taxe}) s’écarte de la TVA recalculée depuis les '
            f'lignes ({taxe_attendue}) de plus que l’arrondi ne permet '
            f'({tolerance}).'))


# ── Ce que le type du document impose ────────────────────────────────────────

def _verifier_le_type(document, anomalies):
    """Les règles du CIVA que le schéma laisse passer sans rien dire.

    Les trois éléments en jeu — `References` d'une ligne, `Payment` des
    totaux — sont tous OPTIONNELS au schéma, parce qu'ils ne le sont pas
    pour tous les types. Le XSD ne sait pas écrire « obligatoire quand
    InvoiceType vaut ND », alors il n'exige rien, et un document
    irrégulier passe.

    Les contrôles sont refaits ICI, sur le fichier, alors qu'ils sont déjà
    tenus à l'émission. Ce n'est pas une redondance inutile : un document
    importé d'un autre logiciel, ou émis avant que la règle existe, n'est
    jamais passé par notre émission. Le fichier remis est ce que l'AT
    regarde, et c'est donc lui qu'il faut mesurer.
    """
    numero = _texte(document, 'InvoiceNo') or '(sans numéro)'
    type_document = _texte(document, 'InvoiceType') or ''

    # 1. Un rectificatif doit désigner la facture qu'il corrige.
    if tipos.exige_une_rectification(type_document):
        lignes = document.findall(_etiquette('Line'))
        sans_reference = [
            rang for rang, ligne in enumerate(lignes, start=1)
            if not _renseigne(ligne.find(_etiquette('References')),
                              'Reference')
        ]
        if sans_reference:
            rangs = ', '.join(str(r) for r in sans_reference)
            anomalies.append(Anomalie(
                numero,
                f'Document « {type_document} » : la ou les ligne(s) {rangs} '
                'ne désignent aucune facture rectifiée. L’article 36.º n.º 6 '
                'du CIVA exige la référence à la facture corrigée ; le '
                'schéma, lui, rend « References » optionnel et accepte le '
                'document.'))

    # 2. Une facture-reçu atteste un encaissement, et pour son total.
    paiements = document.findall(
        f'{_etiquette("DocumentTotals")}/{_etiquette("Payment")}')

    if not tipos.atteste_un_paiement(type_document):
        if paiements:
            anomalies.append(Anomalie(
                numero,
                f'Document « {type_document} » : {len(paiements)} '
                'paiement(s) déclaré(s) alors que ce type n’atteste aucun '
                'encaissement. Une facture payée à l’émission s’émet en '
                '« FR ».'))
        return

    brut = _montant(document.find(_etiquette('DocumentTotals')), 'GrossTotal')
    if not paiements:
        anomalies.append(Anomalie(
            numero,
            'Facture-reçu sans aucun paiement : le document vaut quittance '
            'd’un encaissement dont le fichier ne garde aucune trace.'))
        return

    encaisse = ZERO
    for rang, paiement in enumerate(paiements, start=1):
        montant = _montant(paiement, 'PaymentAmount')
        if montant is None:
            anomalies.append(Anomalie(
                f'{numero} paiement {rang}',
                'Montant du paiement absent ou illisible.'))
            return
        encaisse += montant

    if brut is not None and encaisse != brut:
        sens = 'inférieure' if encaisse < brut else 'supérieure'
        anomalies.append(Anomalie(
            numero,
            f'Facture-reçu : la somme encaissée ({encaisse}) est {sens} au '
            f'total du document ({brut}). Une facture-reçu vaut quittance du '
            'total ; un écart en moins atteste un solde payé qui ne l’est '
            'pas, un écart en plus déclare un encaissement qui n’a pas eu '
            'lieu.'))


# ── Les reçus (table 4.4) ────────────────────────────────────────────────────

def _verifier_un_recu(recu, anomalies):
    """L'arithmétique et les renvois d'un reçu.

    CE QUE LE SCHÉMA DIT ET QUE NOTRE VALIDATEUR NE LIT PAS

    Le XSD de la table 4.4 porte quatre `xs:assert` — notamment « si
    PaymentType vaut RC, chaque ligne doit porter son bloc Tax ». Ce sont
    des assertions XSD 1.1 ; notre validateur, qui lit le modèle de
    contenu, ne les évalue pas. Celui de l'AT, si.

    Un fichier peut donc passer notre contrôle de schéma et échouer chez
    l'administration pour une règle qui était écrite noir sur blanc dans
    le fichier qu'on a lu. Les asserts sont donc vérifiés ici, où l'on
    sait les dire.
    """
    numero = _texte(recu, 'PaymentRefNo') or '(sans numéro)'
    type_recu = _texte(recu, 'PaymentType') or ''

    totaux = recu.find(_etiquette('DocumentTotals'))
    net = _montant(totaux, 'NetTotal')
    taxe = _montant(totaux, 'TaxPayable')
    brut = _montant(totaux, 'GrossTotal')

    if None in (net, taxe, brut):
        anomalies.append(Anomalie(
            numero, 'Un total du reçu est absent ou illisible : la '
                    'cohérence ne peut pas être vérifiée.'))
        return

    if brut != net + taxe:
        anomalies.append(Anomalie(
            numero,
            f'GrossTotal ({brut}) ne vaut pas NetTotal + TaxPayable '
            f'({net} + {taxe} = {net + taxe}).'))

    lignes = recu.findall(_etiquette('Line'))
    if not lignes:
        anomalies.append(Anomalie(numero, 'Reçu sans aucune affectation.'))
        return

    somme = ZERO
    sens_vus = set()

    for rang, ligne in enumerate(lignes, start=1):
        # 1. Chaque ligne doit nommer le document réglé.
        source = ligne.find(_etiquette('SourceDocumentID'))
        renvoi = _renseigne(source, 'OriginatingON')
        if not renvoi:
            anomalies.append(Anomalie(
                f'{numero} ligne {rang}',
                'L’affectation ne désigne aucun document. Un reçu est la '
                'quittance d’une créance ; sans « OriginatingON », '
                'l’administration ne peut rapprocher les deux tables.'))
        elif not _renseigne(source, 'InvoiceDate'):
            anomalies.append(Anomalie(
                f'{numero} ligne {rang}',
                f'L’affectation désigne « {renvoi} » sans sa date. Le '
                'rapprochement suppose alors que la numérotation soit '
                'chronologique, ce que rien ne garantit.'))

        # 2. Le montant, et son sens.
        debit = _montant(ligne, 'DebitAmount')
        credit = _montant(ligne, 'CreditAmount')
        if debit is None and credit is None:
            anomalies.append(Anomalie(
                f'{numero} ligne {rang}',
                'L’affectation ne porte aucun montant, ni au débit ni au '
                'crédit.'))
            continue
        if debit is not None and credit is not None:
            anomalies.append(Anomalie(
                f'{numero} ligne {rang}',
                'L’affectation porte un montant au débit ET au crédit. Le '
                'schéma n’en autorise qu’un des deux ; les sommes de '
                'contrôle compteraient la somme deux fois.'))
            continue

        somme += debit if debit is not None else credit
        sens_vus.add(debit is not None)

        # 3. L'assert du schéma sur les reçus du régime de TVA de caisse.
        if type_recu == 'RC' and ligne.find(_etiquette('Tax')) is None:
            anomalies.append(Anomalie(
                f'{numero} ligne {rang}',
                'Un reçu « RC » relève du régime de TVA sur les '
                'encaissements : le schéma impose son bloc « Tax » à '
                'chaque ligne, par un « assert » que notre validateur de '
                'structure n’évalue pas et que celui de l’AT évalue.'))

    # 4. Un reçu ne mêle pas les deux sens.
    if len(sens_vus) > 1:
        anomalies.append(Anomalie(
            numero,
            'Ce reçu encaisse et rembourse à la fois. La table 4.4 tient ses '
            'sommes de contrôle séparément au débit et au crédit : son '
            'total unique ne correspond alors à aucun des deux mouvements.'))

    # 5. NetTotal = somme des affectations.
    if somme != net:
        anomalies.append(Anomalie(
            numero,
            f'NetTotal ({net}) ne vaut pas la somme des {len(lignes)} '
            f'affectation(s) ({somme}).'))

    # 6. Les moyens de paiement, et leur somme.
    #
    # `PaymentMethod` est l'élément du reçu — et non « Payment », qui est
    # son nom dans les totaux d'une facture. Le même type sous deux noms.
    encaissements = recu.findall(_etiquette('PaymentMethod'))
    if not encaissements:
        anomalies.append(Anomalie(
            numero,
            'Reçu sans aucun moyen de paiement : il n’atteste rien de '
            'vérifiable. Le schéma rend « PaymentMethod » optionnel ; un '
            'reçu, non.'))
        return

    encaisse = ZERO
    for rang, encaissement in enumerate(encaissements, start=1):
        montant = _montant(encaissement, 'PaymentAmount')
        if montant is None:
            anomalies.append(Anomalie(
                f'{numero} paiement {rang}',
                'Montant du paiement absent ou illisible.'))
            return
        encaisse += montant

    if encaisse != brut:
        sens = 'inférieure' if encaisse < brut else 'supérieure'
        anomalies.append(Anomalie(
            numero,
            f'La somme des moyens de paiement ({encaisse}) est {sens} au '
            f'total du reçu ({brut}). Un reçu est la quittance de ce qu’il '
            'déclare avoir reçu : l’écart dit que l’un des deux nombres est '
            'faux, et c’est le document remis au client qui tranche.'))


def _verifier_les_totaux_des_recus(racine, recus, anomalies):
    table = racine.find(
        f'{_etiquette("SourceDocuments")}/{_etiquette("Payments")}')
    if table is None:
        return

    annonce = _texte(table, 'NumberOfEntries')
    if annonce is not None and annonce.strip() != str(len(recus)):
        anomalies.append(Anomalie(
            'Payments',
            f'NumberOfEntries annonce {annonce.strip()} reçu(s) et le '
            f'fichier en contient {len(recus)}.'))

    debit = ZERO
    credit = ZERO
    for recu in recus:
        # Pour un reçu, seul « A » existe comme état exclu : `PaymentStatus`
        # n'énumère que « N » et « A », là où un document de facturation
        # exclut aussi « F ».
        etat = _texte(recu.find(_etiquette('DocumentStatus')), 'PaymentStatus')
        if etat in ETATS_DE_RECU_HORS_TOTAUX:
            continue
        for ligne in recu.findall(_etiquette('Line')):
            montant = _montant(ligne, 'DebitAmount')
            if montant is not None:
                debit += montant
                continue
            montant = _montant(ligne, 'CreditAmount')
            if montant is not None:
                credit += montant

    for nom, calcule in (('TotalCredit', credit), ('TotalDebit', debit)):
        annonce = _montant(table, nom)
        if annonce is None:
            anomalies.append(Anomalie('Payments',
                                      f'{nom} est absent ou illisible.'))
        elif annonce != calcule:
            anomalies.append(Anomalie(
                'Payments',
                f'{nom} annonce {annonce} et la somme des lignes des reçus '
                f'non annulés donne {calcule}.'))


# ── Les totaux du fichier ────────────────────────────────────────────────────

def _verifier_les_totaux_du_fichier(racine, documents, anomalies):
    ventes = racine.find(
        f'{_etiquette("SourceDocuments")}/{_etiquette("SalesInvoices")}')
    if ventes is None:
        return

    annonce = _texte(ventes, 'NumberOfEntries')
    if annonce is not None and annonce.strip() != str(len(documents)):
        anomalies.append(Anomalie(
            'SalesInvoices',
            f'NumberOfEntries annonce {annonce.strip()} document(s) et le '
            f'fichier en contient {len(documents)}.'))

    # LES TOTAUX EXCLUENT CE QUE `NumberOfEntries` COMPTE.
    #
    # Portaria n.º 302/2016, champs 4.1.1 à 4.1.3 : le nombre de registres
    # compte TOUS les documents, « incluindo os documentos cujo valor do
    # campo Estado atual (InvoiceStatus) seja do tipo "A" ou "F" », et les
    # deux sommes de contrôle les EXCLUENT.
    #
    # Ce contrôle appliquait la même règle que le composeur, et la même
    # erreur : il sommait tous les documents, annulés compris. Un défaut
    # qu'on vérifie avec la méthode qui l'a produit n'apparaît jamais —
    # le fichier était déclaré cohérent et l'AT le refusait.
    credit = ZERO
    debit = ZERO
    for document in documents:
        etat = _texte(document.find(_etiquette('DocumentStatus')),
                      'InvoiceStatus')
        if etat in ETATS_HORS_TOTAUX:
            continue

        au_debit = (_texte(document, 'InvoiceType') or '') in TYPES_AU_DEBIT
        champ = 'DebitAmount' if au_debit else 'CreditAmount'

        # On somme les MONTANTS DE LIGNES, qui sont ce que le texte nomme
        # (« a soma de controlo do campo Valor a crédito (CreditAmount) »)
        # et non le total du document. Les deux coïncident sur un document
        # cohérent ; sur un document qui ne l'est pas, c'est la ligne que
        # l'AT recompte.
        for ligne in document.findall(_etiquette('Line')):
            montant = _montant(ligne, champ)
            if montant is None:
                continue
            if au_debit:
                debit += montant
            else:
                credit += montant

    for nom, calcule in (('TotalCredit', credit), ('TotalDebit', debit)):
        annonce = _montant(ventes, nom)
        if annonce is None:
            anomalies.append(Anomalie('SalesInvoices',
                                      f'{nom} est absent ou illisible.'))
        elif annonce != calcule:
            anomalies.append(Anomalie(
                'SalesInvoices',
                f'{nom} annonce {annonce} et la somme des lignes des '
                f'documents non annulés donne {calcule}.'))


# ── Le référentiel ───────────────────────────────────────────────────────────

def _verifier_les_renvois(racine, documents, anomalies, recus=()):
    clients, produits, taux = _referentiels(racine)

    # Un reçu porte aussi un `CustomerID`, et il doit figurer dans
    # `MasterFiles` comme celui d'une facture. Le reçu n'ajoute pourtant
    # jamais de client au référentiel : il règle un document qui en a déjà
    # un. Un reçu dont le client manque signale donc que le rassemblement
    # a perdu un document, pas qu'il a oublié un client.
    for recu in recus:
        client = _texte(recu, 'CustomerID')
        if client and client not in clients:
            anomalies.append(Anomalie(
                _texte(recu, 'PaymentRefNo') or '(sans numéro)',
                f'Le client « {client} » du reçu n’est pas déclaré dans '
                'MasterFiles.'))

    for document in documents:
        numero = _texte(document, 'InvoiceNo') or '(sans numéro)'

        client = _texte(document, 'CustomerID')
        if client and client not in clients:
            anomalies.append(Anomalie(
                numero,
                f'Le client « {client} » n’est pas déclaré dans '
                'MasterFiles. Les documents sont justes, le référentiel est '
                'incomplet, et le fichier est rejeté en entier.'))

        for rang, ligne in enumerate(document.findall(_etiquette('Line')),
                                     start=1):
            produit = _texte(ligne, 'ProductCode')
            if produit and produit not in produits:
                anomalies.append(Anomalie(
                    f'{numero} ligne {rang}',
                    f'Le produit « {produit} » n’est pas déclaré dans '
                    'MasterFiles.'))

            taxe = ligne.find(_etiquette('Tax'))
            couple = (_texte(taxe, 'TaxCode'), _texte(taxe, 'TaxCountryRegion'))
            if couple[0] and couple not in taux:
                anomalies.append(Anomalie(
                    f'{numero} ligne {rang}',
                    f'Le taux « {couple[0]} » en région « {couple[1]} » '
                    'n’est pas déclaré dans la table des taux.'))


# ── Les dates et la période ──────────────────────────────────────────────────

def _verifier_les_dates(racine, documents, anomalies):
    entete = racine.find(_etiquette('Header'))
    debut = _texte(entete, 'StartDate')
    fin = _texte(entete, 'EndDate')

    for document in documents:
        numero = _texte(document, 'InvoiceNo') or '(sans numéro)'
        date_document = _texte(document, 'InvoiceDate')

        if not date_document:
            continue

        # Les dates ISO se comparent correctement comme du texte.
        if debut and date_document < debut:
            anomalies.append(Anomalie(
                numero, f'Daté du {date_document}, avant le début de la '
                        f'période ({debut}).'))
        if fin and date_document > fin:
            anomalies.append(Anomalie(
                numero, f'Daté du {date_document}, après la fin de la '
                        f'période ({fin}).'))

        # La PÉRIODE est le mois du document.
        #
        # Une période fausse ne casse ni le schéma ni l'arithmétique :
        # elle range le document dans le mauvais mois, et l'écart
        # n'apparaît qu'au rapprochement des déclarations de TVA.
        periode = _texte(document, 'Period')
        attendue = date_document[5:7].lstrip('0')
        if periode and periode.strip().lstrip('0') != attendue:
            anomalies.append(Anomalie(
                numero,
                f'Period vaut {periode.strip()} alors que le document est '
                f'daté du {date_document} (mois {attendue}).'))

        # L'horodatage d'enregistrement ne peut pas précéder la date du
        # document : un document enregistré avant d'exister est le signe
        # d'une antidate, et c'est ce que la chaîne de signatures sert à
        # empêcher.
        horodatage = _texte(document, 'SystemEntryDate')
        if horodatage and horodatage[:10] < date_document:
            anomalies.append(Anomalie(
                numero,
                f'Enregistré le {horodatage[:10]}, avant sa propre date '
                f'({date_document}).'))


# ── L'entrée publique ────────────────────────────────────────────────────────

def verifier(racine):
    """Les incohérences d'un fichier déjà conforme au schéma.

    `racine` est un `Element` déjà analysé. On ne reprend pas l'analyse du
    XML ici : ce module s'emploie APRÈS `schema.valider`, qui a déjà dit
    si le fichier était lisible et bien formé. Le rappeler donnerait deux
    messages pour un seul défaut.
    """
    anomalies = []
    documents = _documents(racine)
    recus = _recus(racine)

    for document in documents:
        _verifier_un_document(document, anomalies)
        _verifier_le_type(document, anomalies)

    for recu in recus:
        _verifier_un_recu(recu, anomalies)

    _verifier_les_totaux_du_fichier(racine, documents, anomalies)
    _verifier_les_totaux_des_recus(racine, recus, anomalies)
    _verifier_les_renvois(racine, documents, anomalies, recus)
    _verifier_les_dates(racine, documents, anomalies)

    return anomalies


def resume(anomalies):
    if not anomalies:
        return ('Cohérence vérifiée : totaux, référentiel, dates et '
                'périodes s’accordent.')
    nombre = len(anomalies)
    return (f'{nombre} incohérence{"s" if nombre > 1 else ""}. Un fichier '
            'conforme au schéma mais incohérent est rejeté tout autant, et '
            'le motif du rejet est plus difficile à comprendre.')
