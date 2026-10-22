"""
apps/purchases/invoice_detection.py — Lire une facture fournisseur en PDF

**Rien n'est jamais enregistré par ce module.** Il lit, il propose, il dit
ce dont il n'est pas sûr. Une facture crée une dette et part en
comptabilité : une extraction qui se tromperait en silence sur un montant
coûterait bien plus cher que dix minutes de saisie.

Deux contrôles font la différence entre « fiable » et « plausible ».

**La cohérence HT + TVA = TTC.** Trois montants extraits qui ne se
réconcilient pas prouvent qu'au moins un est faux — sans savoir lequel,
mais c'est déjà l'essentiel, et l'écran le dit. Quand deux seulement sont
trouvés, le troisième est *déduit* plutôt que laissé vide : une soustraction
est sûre, une case vide se remplit à la main et de travers.

**Les clés de contrôle du SIRET et du numéro de TVA.** Un SIRET est un
nombre à 14 chiffres qui vérifie Luhn ; une TVA intracommunautaire
française porte une clé calculable depuis le SIREN. Les valider écarte les
faux positifs — un numéro de commande à 14 chiffres, une référence qui
ressemble à une TVA — au lieu de rattacher la facture au mauvais
fournisseur. C'est la différence entre reconnaître l'émetteur et le
deviner.

**Ce que ce module ne peut pas faire.** Un PDF scanné ne contient qu'une
image : il n'y a aucun texte à lire, et aucune expression régulière n'y
changera rien. Le dire franchement, avec la raison, vaut mieux qu'un
résultat vide inexpliqué — c'est la seule réponse qui mène à une action
utile (demander le PDF d'origine, ou saisir à la main).
"""

import re
from decimal import Decimal

from apps.core.nombres import nombre_francais

CENTIME = Decimal('0.01')

# Taux de TVA français en vigueur. Sert à reconnaître un taux plausible, pas
# à l'imposer : un taux étranger ou historique reste accepté s'il est écrit
# noir sur blanc, simplement signalé comme inhabituel.
TAUX_USUELS = (Decimal('20'), Decimal('10'), Decimal('5.5'), Decimal('2.1'),
               Decimal('0'))

MOIS_FR = {
    'janvier': 1, 'fevrier': 2, 'février': 2, 'mars': 3, 'avril': 4,
    'mai': 5, 'juin': 6, 'juillet': 7, 'aout': 8, 'août': 8,
    'septembre': 9, 'octobre': 10, 'novembre': 11, 'decembre': 12,
    'décembre': 12,
}


class FactureIllisible(Exception):
    """Le PDF ne peut pas être ouvert du tout."""


# ─── Lecture du PDF ───────────────────────────────────────────────────────────

def extraire_texte(octets):
    """Le texte du PDF, et le nombre de pages. Rend (texte, pages).

    Une page illisible ne fait pas perdre les autres : une facture de trois
    pages dont la deuxième est une image reste exploitable pour le reste.
    """
    try:
        from pypdf import PdfReader
    except ImportError:
        raise FactureIllisible(
            'Lecture des PDF indisponible sur ce serveur.')

    import io

    try:
        lecteur = PdfReader(io.BytesIO(octets))
        pages = list(lecteur.pages)
    except Exception as exc:
        raise FactureIllisible(f'PDF illisible : {exc}')

    morceaux = []
    for page in pages:
        try:
            morceaux.append(page.extract_text() or '')
        except Exception:
            continue
    return '\n'.join(morceaux), len(pages)


# ─── Numéros d'identification, validés par leur clé ──────────────────────────

def luhn_valide(chiffres):
    """Le contrôle de Luhn, celui du SIRET et des cartes bancaires."""
    if not chiffres.isdigit():
        return False
    total = 0
    for position, caractere in enumerate(reversed(chiffres)):
        valeur = int(caractere)
        if position % 2 == 1:
            valeur *= 2
            if valeur > 9:
                valeur -= 9
        total += valeur
    return total % 10 == 0


MOTIF_SIRET = re.compile(r'(?<!\d)(\d[\d\s.]{12,20}\d)(?!\d)')


def chercher_siret(texte):
    """Le premier groupe de 14 chiffres qui vérifie Luhn.

    Sans ce contrôle, n'importe quel numéro de commande à 14 chiffres
    passerait pour un SIRET et rattacherait la facture au mauvais
    fournisseur — une erreur silencieuse, et qui se propage en
    comptabilité.
    """
    for trouve in MOTIF_SIRET.finditer(texte):
        chiffres = re.sub(r'\D', '', trouve.group(1))
        if len(chiffres) == 14 and luhn_valide(chiffres):
            return chiffres
    return None


MOTIF_TVA_FR = re.compile(r'\bFR\s?(\d{2})\s?(\d[\d\s]{8,12})', re.IGNORECASE)


def cle_tva_francaise(siren):
    """La clé attendue d'un numéro de TVA français : (12 + 3·(SIREN mod 97)) mod 97."""
    return (12 + 3 * (int(siren) % 97)) % 97


def chercher_numero_tva(texte):
    """Un numéro de TVA intracommunautaire français, clé vérifiée.

    La clé se recalcule depuis le SIREN : un numéro dont elle ne tombe pas
    juste est une faute de lecture ou une autre référence, pas une TVA.
    """
    for trouve in MOTIF_TVA_FR.finditer(texte):
        cle = trouve.group(1)
        siren = re.sub(r'\D', '', trouve.group(2))[:9]
        if len(siren) != 9:
            continue
        if int(cle) == cle_tva_francaise(siren):
            return f'FR{cle}{siren}'
    return None


# ─── Dates ────────────────────────────────────────────────────────────────────

MOTIF_DATE_CHIFFRES = re.compile(
    r'(?<!\d)(\d{1,2})\s*[/.\-]\s*(\d{1,2})\s*[/.\-]\s*(\d{2,4})(?!\d)')
MOTIF_DATE_TEXTE = re.compile(
    r'(?<!\d)(\d{1,2})(?:er)?\s+([a-zéû]{3,9})\.?\s+(\d{4})', re.IGNORECASE)


def _date_depuis(jour, mois, annee):
    from datetime import date
    try:
        annee = int(annee)
        if annee < 100:
            # Une facture est un document récent : « 24 » est 2024, jamais
            # 1924. Le pivot à 70 est la convention POSIX.
            annee += 2000 if annee < 70 else 1900
        return date(annee, int(mois), int(jour))
    except (TypeError, ValueError):
        return None


def dates_du_texte(texte):
    """Toutes les dates lisibles, dans l'ordre d'apparition.

    Le jour vient avant le mois : format français. Lire « 05/11 » comme le
    11 mai décalerait toutes les échéances de six mois, et l'erreur ne se
    verrait qu'au moment de payer.
    """
    trouvees = []
    for trouve in MOTIF_DATE_CHIFFRES.finditer(texte):
        valeur = _date_depuis(*trouve.groups())
        if valeur is not None:
            trouvees.append((trouve.start(), valeur))
    for trouve in MOTIF_DATE_TEXTE.finditer(texte):
        mois = MOIS_FR.get(trouve.group(2).lower().rstrip('.'))
        if mois is None:
            continue
        valeur = _date_depuis(trouve.group(1), mois, trouve.group(3))
        if valeur is not None:
            trouvees.append((trouve.start(), valeur))
    trouvees.sort()
    return [valeur for _position, valeur in trouvees]


MOTS_ECHEANCE = ('échéance', 'echeance', 'à payer avant', 'a payer avant',
                 'date limite', 'payable le', 'règlement au',
                 'reglement au', 'date de règlement', 'date de reglement')
MOTS_EMISSION = ('date de facture', 'date facture', "date d'émission",
                 "date d'emission", 'émise le', 'emise le', 'fait le',
                 'le ', 'date :')


def _date_pres_de(texte, mots, fenetre=90):
    """La première date trouvée juste après l'un de ces mots.

    La proximité plutôt que l'ordre d'apparition : une facture porte
    souvent trois ou quatre dates (émission, échéance, période, date de
    commande) et prendre « la première » revient à tirer au sort.
    """
    bas = texte.lower()
    for mot in mots:
        position = bas.find(mot)
        while position != -1:
            extrait = texte[position:position + fenetre]
            candidates = dates_du_texte(extrait)
            if candidates:
                return candidates[0]
            position = bas.find(mot, position + 1)
    return None


# ─── Montants ─────────────────────────────────────────────────────────────────

def texte_sans_identifiants(texte, siret=None, numero_tva=None):
    """Le texte privé de ses lignes d'identification.

    DÉFAUT MESURÉ, et sérieux. L'étiquette « TVA » mordait sur la ligne
    « TVA intracommunautaire : FR83404833048 » et en lisait le numéro comme
    un montant : la facture repartait avec 83 404 833 048 € de TVA. Une
    erreur de ce genre n'est pas une imprécision, c'est une écriture
    comptable absurde.

    Le filtre est EXACT, pas heuristique : on retire les lignes qui
    contiennent le SIRET ou le numéro de TVA déjà trouvés — et validés par
    leur clé de contrôle, donc certains. Le mot « intracom » couvre le cas
    où le numéro n'a pas pu être validé : la ligne est alors reconnue par
    son intitulé plutôt que par son contenu.
    """
    chiffres_tva = re.sub(r'\D', '', numero_tva or '')
    conserve = []
    for ligne in texte.splitlines():
        bas = ligne.lower()
        if 'intracom' in bas:
            continue
        chiffres = re.sub(r'\D', '', ligne)
        if siret and siret in chiffres:
            continue
        if chiffres_tva and len(chiffres_tva) >= 9 and chiffres_tva in chiffres:
            continue
        conserve.append(ligne)
    return '\n'.join(conserve)


def _montant_pres_de(texte, motifs):
    """Le montant qui suit l'une de ces étiquettes.

    Sur la même ligne d'abord, puis sur la suivante : dans un tableau de
    totaux, l'étiquette et le nombre sont parfois séparés par le retour à
    la ligne de l'extraction.
    """
    lignes = texte.splitlines()
    for index, ligne in enumerate(lignes):
        bas = ligne.lower()
        for motif in motifs:
            if not re.search(motif, bas):
                continue
            # Après l'étiquette sur la même ligne.
            reste = re.split(motif, bas, maxsplit=1)[-1]
            valeur = _dernier_nombre(reste)
            if valeur is not None:
                return valeur
            if index + 1 < len(lignes):
                valeur = _dernier_nombre(lignes[index + 1])
                if valeur is not None:
                    return valeur
    return None


MOTIF_NOMBRE = re.compile(r'-?\d[\d\s.,]*\d|-?\d')


def _dernier_nombre(fragment):
    """Le dernier nombre du fragment.

    Le dernier et non le premier : dans « Total HT 3 lignes 1 234,56 € »,
    le premier nombre est un compte de lignes.
    """
    trouves = MOTIF_NOMBRE.findall(fragment or '')
    for brut in reversed(trouves):
        valeur = nombre_francais(brut)
        if valeur is not None:
            return valeur
    return None


ETIQUETTES_HT = (r'total\s*h\.?\s*t\.?', r'montant\s*h\.?\s*t\.?',
                 r'base\s*h\.?\s*t\.?', r'total\s*hors\s*taxe')
ETIQUETTES_TVA = (r'(?<!sans\s)t\.?\s*v\.?\s*a\.?(?!\s*n)', r'montant\s*tva',
                  r'total\s*tva')
ETIQUETTES_TTC = (r'total\s*t\.?\s*t\.?\s*c\.?', r'montant\s*t\.?\s*t\.?\s*c\.?',
                  r'net\s*[àa]\s*payer', r'montant\s*d[ûu]',
                  r'total\s*[àa]\s*payer')

MOTIF_TAUX = re.compile(r'(\d{1,2}(?:[.,]\d{1,2})?)\s*%')


def taux_du_texte(texte):
    """Le taux de TVA le plus plausible parmi ceux écrits dans la page.

    Un taux usuel est préféré : une facture porte souvent d'autres
    pourcentages (remise, acompte, pénalité de retard) et prendre le
    premier venu donnerait « 2 % » pour une remise.
    """
    candidats = []
    for trouve in MOTIF_TAUX.finditer(texte):
        valeur = nombre_francais(trouve.group(1))
        if valeur is not None and Decimal('0') <= valeur <= Decimal('30'):
            candidats.append(valeur)
    if not candidats:
        return None
    usuels = [valeur for valeur in candidats if valeur in TAUX_USUELS]
    return usuels[0] if usuels else candidats[0]


# ─── Numéro de facture ────────────────────────────────────────────────────────

MOTIF_NUMERO = re.compile(
    r'(?:facture|invoice|fact\.?)\s*'
    r'(?:n\s*[°ºo]|num[eé]ro|no\.?|#)?\s*[:\-]?\s*'
    r'([A-Z0-9][A-Z0-9\-/_.]{2,24})',
    re.IGNORECASE)

# Mots qui suivent parfois « facture » sans en être le numéro.
FAUX_NUMEROS = {'du', 'de', 'date', 'no', 'num', 'numero', 'numéro', 'n',
                'acquittee', 'acquittée', 'proforma', 'avoir', 'client',
                'fournisseur', 'adresse', 'total'}


def chercher_numero(texte):
    for trouve in MOTIF_NUMERO.finditer(texte):
        candidat = trouve.group(1).strip(' .-/_')
        if not candidat or candidat.lower() in FAUX_NUMEROS:
            continue
        # Un numéro de facture porte au moins un chiffre : « Facture
        # Acquittée » ne doit pas devenir le numéro FA-ACQUITTEE.
        if any(caractere.isdigit() for caractere in candidat):
            return candidat
    return None


# ─── Cohérence des totaux ─────────────────────────────────────────────────────

def reconcilier(ht, tva, ttc, taux=None):
    """Complète ce qui manque et vérifie ce qui est là.

    Retourne (ht, tva, ttc, rapport). Le rapport dit si les trois montants
    se réconcilient, et de combien ils s'écartent sinon.

    Déduire le manquant plutôt que laisser une case vide : une
    soustraction est sûre, une case vide se remplit à la main et de
    travers. Mais on ne « corrige » JAMAIS trois montants incohérents —
    on ne sait pas lequel est faux, et en choisir un reviendrait à
    inventer un chiffre comptable.
    """
    deduits = []

    if ht is not None and tva is not None and ttc is None:
        ttc = (ht + tva).quantize(CENTIME)
        deduits.append('TTC')
    elif ht is not None and ttc is not None and tva is None:
        tva = (ttc - ht).quantize(CENTIME)
        deduits.append('TVA')
    elif tva is not None and ttc is not None and ht is None:
        ht = (ttc - tva).quantize(CENTIME)
        deduits.append('HT')
    elif ht is not None and tva is None and ttc is None and taux:
        tva = (ht * taux / Decimal('100')).quantize(CENTIME)
        ttc = (ht + tva).quantize(CENTIME)
        deduits.append('TVA et TTC (depuis le taux)')
    elif ttc is not None and ht is None and tva is None and taux:
        ht = (ttc / (Decimal('1') + taux / Decimal('100'))).quantize(CENTIME)
        tva = (ttc - ht).quantize(CENTIME)
        deduits.append('HT et TVA (depuis le taux)')

    rapport = {'coherent': None, 'ecart': None, 'deduits': deduits,
               'message': ''}

    if ht is None or tva is None or ttc is None:
        rapport['message'] = (
            'Montants incomplets : il en manque au moins un, et il ne peut '
            'pas être déduit sans le taux de TVA.')
        return ht, tva, ttc, rapport

    ecart = (ht + tva - ttc).quantize(CENTIME)
    rapport['ecart'] = ecart
    # Un centime de tolérance : les arrondis par ligne d'une facture ne
    # tombent pas toujours exactement sur le total.
    rapport['coherent'] = abs(ecart) <= CENTIME
    if rapport['coherent']:
        rapport['message'] = (
            'Les montants se réconcilient : HT + TVA = TTC.' if not deduits
            else f'Montant déduit : {", ".join(deduits)}. HT + TVA = TTC.')
    else:
        rapport['message'] = (
            f'HT + TVA ne donne pas le TTC : écart de {ecart} €. Au moins '
            f'un des trois montants a été mal lu — vérifiez les trois sur '
            f'le PDF avant d\'enregistrer.')
    return ht, tva, ttc, rapport


# ─── Rattachement au fournisseur ──────────────────────────────────────────────

def chercher_fournisseur(company, siret=None, numero_tva=None, texte=''):
    """Le fournisseur émetteur, et sur quoi il a été reconnu.

    Par ordre de certitude : SIRET, puis numéro de TVA, puis nom trouvé
    dans le texte. Le nom vient en dernier et n'est jamais présenté comme
    sûr : deux fournisseurs peuvent s'appeler « Martin », et rattacher une
    facture au mauvais fait payer la dette d'un autre.
    """
    from .models import Supplier

    base = Supplier.objects.filter(company=company, is_active=True)

    if siret:
        trouve = base.filter(siret=siret).first()
        if trouve is not None:
            return {'fournisseur': trouve, 'motif': 'siret',
                    'certitude': 'sure'}

    if numero_tva:
        normalise = numero_tva.replace(' ', '').upper()
        for candidat in base.exclude(vat_number=''):
            if candidat.vat_number.replace(' ', '').upper() == normalise:
                return {'fournisseur': candidat, 'motif': 'tva',
                        'certitude': 'sure'}

    # Recherche par nom : on exige le nom entier, pour éviter qu'un
    # fournisseur nommé « BTP » ne corresponde à toutes les factures.
    bas = (texte or '').lower()
    candidats = [candidat for candidat in base
                 if len(candidat.name) >= 4 and candidat.name.lower() in bas]
    if len(candidats) == 1:
        return {'fournisseur': candidats[0], 'motif': 'nom',
                'certitude': 'probable'}
    if len(candidats) > 1:
        return {'fournisseur': None, 'motif': 'nom_ambigu',
                'certitude': 'incertaine', 'candidats': candidats}

    return {'fournisseur': None, 'motif': 'aucun', 'certitude': 'aucune'}


# ─── Le détecteur complet ─────────────────────────────────────────────────────

def detecter_facture(octets, company=None):
    """Tout ce qu'on peut lire d'une facture PDF, avec ce qu'on en sait.

    Rend un dictionnaire. `texte_trouve` à False signifie qu'il n'y a
    simplement rien à lire — un scan — et le message le dit.
    """
    texte, pages = extraire_texte(octets)

    if not texte.strip():
        return {
            'texte_trouve': False, 'pages': pages, 'champs': {},
            'fournisseur': {'fournisseur': None, 'motif': 'aucun',
                            'certitude': 'aucune'},
            'totaux': {'coherent': None, 'message': ''},
            'message': (
                f'Ce PDF de {pages} page(s) ne contient aucun texte : c\'est '
                f'une image, comme tout document scanné ou photographié. '
                f'Aucune extraction n\'est possible — demandez au '
                f'fournisseur le PDF d\'origine, celui produit par son '
                f'logiciel de facturation.'),
        }

    siret = chercher_siret(texte)
    numero_tva = chercher_numero_tva(texte)
    taux = taux_du_texte(texte)

    # Les montants sont cherchés dans un texte PRIVÉ de ses lignes
    # d'identification : sinon « TVA intracommunautaire : FR83404833048 »
    # fournit un montant de TVA de 83 milliards. Voir
    # texte_sans_identifiants().
    texte_montants = texte_sans_identifiants(texte, siret, numero_tva)
    ht = _montant_pres_de(texte_montants, ETIQUETTES_HT)
    tva = _montant_pres_de(texte_montants, ETIQUETTES_TVA)
    ttc = _montant_pres_de(texte_montants, ETIQUETTES_TTC)
    ht, tva, ttc, rapport = reconcilier(ht, tva, ttc, taux)

    emission = _date_pres_de(texte, MOTS_EMISSION)
    echeance = _date_pres_de(texte, MOTS_ECHEANCE)
    if emission is None:
        # À défaut d'étiquette reconnue, la première date de la page est le
        # meilleur candidat — signalé comme incertain.
        toutes = dates_du_texte(texte)
        emission = toutes[0] if toutes else None

    # Une échéance antérieure à l'émission est une lecture fausse, pas une
    # facture étrange : on la retire plutôt que de proposer de payer avant
    # d'avoir reçu.
    if emission and echeance and echeance < emission:
        echeance = None

    fournisseur = (chercher_fournisseur(company, siret, numero_tva, texte)
                   if company is not None
                   else {'fournisseur': None, 'motif': 'aucun',
                         'certitude': 'aucune'})

    champs = {
        'numero': chercher_numero(texte),
        'date_emission': emission,
        'date_echeance': echeance,
        'total_ht': ht,
        'total_tva': tva,
        'total_ttc': ttc,
        'taux_tva': taux,
        'siret': siret,
        'numero_tva': numero_tva,
    }

    trouves = sum(1 for valeur in champs.values() if valeur is not None)
    return {
        'texte_trouve': True, 'pages': pages, 'champs': champs,
        'fournisseur': fournisseur, 'totaux': rapport,
        'message': (
            f'{trouves} information(s) extraite(s) de {pages} page(s). '
            f'Vérifiez-les avant d\'enregistrer : rien n\'est encore écrit.'),
    }
