"""apps/fiscal_pt/isencao.py — Les motifs d'exonération de TVA.

D'OÙ VIENT CETTE TABLE

« Códigos de Motivo de Isenção — Manual de Integração de Software »,
publié par l'AT, **version 4.0 du 18 juin 2026**. Elle complète les
notes techniques du champ `TaxExemptionCode` de l'annexe à la
Portaria n.º 302/2016.

Elle a été recopiée depuis le PDF officiel, et non d'après un site qui
la reproduit : plusieurs reproductions omettent M35, le plus récent, et
une table incomplète rejette des factures parfaitement légales.

POURQUOI CE N'EST PAS UNE SIMPLE LISTE DÉROULANTE

Trois raisons, et chacune a mordu quelqu'un :

1. **LES CODES NE SONT PAS CONTIGUS.** M03, M08, M17, M18, M22 à M24,
   M27 à M29 et M36 à M39 **n'existent pas**. Un code choisi « au
   milieu » par analogie fait rejeter le fichier entier, et il a l'air
   aussi normal que les autres.

2. **LA « MENÇÃO » DOIT ÊTRE IMPRIMÉE SUR LA FACTURE.** Ce n'est pas une
   étiquette d'interface : c'est une mention légale du document. La
   stocker ici, à côté du code, évite qu'elle soit saisie à la main et
   donc fautive une fois sur dix.

3. **M35 A UNE DATE D'ENTRÉE EN VIGUEUR.** Il ne s'applique qu'aux
   factures émises à partir du 1er juillet 2026. L'employer avant est un
   refus assuré, et rien dans le code ne le signalerait.

CE QUI CONCERNE DIRECTEMENT LE BTP

Deux codes servent à l'inversion du redevable sur les travaux :

* **M31** — autoliquidation sur les services de construction civile en
  régime d'entreprise ou de sous-traitance, entre assujettis établis au
  Portugal. C'est le cas courant de la sous-traitance de chantier.
* **M35** — chantiers de construction ou de réhabilitation d'immeubles
  destinés à l'habitation propre et permanente de l'acquéreur, ou à la
  location à usage d'habitation, dans les conditions du
  Decreto-Lei n.º 97/2026.
"""

from datetime import date

#: La table officielle. Pour chaque code : la mention à faire figurer sur
#: la facture, et la norme applicable.
CODES = {
    'M01': ('Artigo 16.º n.º 6 do CIVA',
            'Artigo 16.º n.º 6 alíneas a) a d) do CIVA'),
    'M02': ('Artigo 6.º do Decreto-Lei n.º 198/90, de 19 de junho',
            'Artigo 6.º do Decreto-Lei n.º 198/90, de 19 de junho'),
    'M04': ('Isento artigo 13.º do CIVA', 'Artigo 13.º do CIVA'),
    'M05': ('Isento artigo 14.º do CIVA', 'Artigo 14.º do CIVA'),
    'M06': ('Isento artigo 15.º do CIVA', 'Artigo 15.º do CIVA'),
    'M07': ('Isento artigo 9.º do CIVA', 'Artigo 9.º do CIVA'),
    'M09': ('IVA – não confere direito a dedução',
            'Artigo 62.º alínea b) do CIVA'),
    'M10': ('IVA – regime de isenção', 'Artigo 53.º n.º 1 do CIVA'),
    'M11': ('Regime particular do tabaco',
            'Decreto-Lei n.º 346/85, de 23 de agosto'),
    'M12': ('Regime da margem de lucro – Agências de viagens',
            'Decreto-Lei n.º 221/85, de 3 de julho'),
    'M13': ('Regime da margem de lucro – Bens em segunda mão',
            'Decreto-Lei n.º 199/96, de 18 de outubro'),
    'M14': ('Regime da margem de lucro – Objetos de arte',
            'Decreto-Lei n.º 199/96, de 18 de outubro'),
    'M15': ('Regime da margem de lucro – Objetos de coleção e antiguidades',
            'Decreto-Lei n.º 199/96, de 18 de outubro'),
    'M16': ('Isento artigo 14.º do RITI', 'Artigo 14.º do RITI'),
    'M19': ('Outras isenções',
            'Isenções temporárias determinadas em diploma próprio'),
    'M20': ('IVA – regime forfetário', 'Artigo 59.º-D n.º 2 do CIVA'),
    'M21': ('IVA – não confere direito à dedução (ou expressão similar)',
            'Artigo 72.º n.º 4 do CIVA'),
    'M25': ('Mercadorias à consignação',
            'Artigo 38.º n.º 1 alínea a) do CIVA'),
    'M26': ('Isenção de IVA com direito à dedução no cabaz alimentar',
            'Lei n.º 17/2023, de 14 de abril'),
    'M30': ('IVA - autoliquidação', 'Artigo 2.º n.º 1 alínea i) do CIVA'),
    'M31': ('IVA - autoliquidação', 'Artigo 2.º n.º 1 alínea j) do CIVA'),
    'M32': ('IVA - autoliquidação', 'Artigo 2.º n.º 1 alínea l) do CIVA'),
    'M33': ('IVA - autoliquidação', 'Artigo 2.º n.º 1 alínea m) do CIVA'),
    'M34': ('IVA - autoliquidação', 'Artigo 2.º n.º 1 alínea n) do CIVA'),
    'M35': ('IVA - autoliquidação',
            'Artigo 2.º n.º 1 alínea j) do CIVA – Verba 2.42 da Lista I'),
    'M40': ('IVA - autoliquidação',
            'Artigo 6.º n.º 6 alínea a) do CIVA, a contrário'),
    'M41': ('IVA - autoliquidação', 'Artigo 8.º n.º 3 do RITI'),
    'M42': ('IVA - autoliquidação',
            'Decreto-Lei n.º 21/2007, de 29 de janeiro'),
    'M43': ('IVA - autoliquidação',
            'Decreto-Lei n.º 362/99, de 16 de setembro'),
    'M44': ('IVA – Regras específicas - artigo 6.º',
            'Artigo 6.º do CIVA – Regras específicas'),
    'M45': ('IVA – regime transfronteiriço de isenção',
            'Artigo 58.º-A do CIVA'),
    'M46': ('IVA – e-TaxFree',
            'Decreto-Lei n.º 19/2017, de 14 de fevereiro'),
    'M99': ('Não sujeito ou não tributado',
            'Outras situações de não liquidação do imposto'),
}

#: Les codes qui n'existent qu'à partir d'une date. Les employer avant est
#: un refus assuré, et rien d'autre ne le signalerait.
EN_VIGUEUR_DEPUIS = {
    'M35': date(2026, 7, 1),
}

#: La longueur maximale du champ `TaxExemptionReason` du SAF-T, lue dans
#: le schéma de l'AT (`SAFPTPortugueseTaxExemptionReason` : de 6 à 60
#: caractères).
LONGUEUR_MAXIMALE_SAFT = 60

#: Les mentions trop longues pour le champ du SAF-T, et leur forme abrégée.
#:
#: DEUX DOCUMENTS OFFICIELS SE CONTREDISENT, ET IL FAUT TRANCHER.
#:
#: La table des motifs publie pour M15 « Regime da margem de lucro –
#: Objetos de coleção e antiguidades », qui fait 61 caractères. Le schéma
#: SAF-T, lui, plafonne `TaxExemptionReason` à 60. Une entreprise qui
#: facture des objets d'art sous le régime de la marge produirait donc un
#: fichier rejeté — en employant le texte publié par l'administration
#: elle-même.
#:
#: Tronquer au soixantième caractère couperait « antiguidade|s » au milieu
#: d'un mot, ce qui ressemble à un défaut du logiciel. On abrège donc
#: explicitement, en remplaçant « e » par « / » : tous les mots sont
#: conservés, et la forme reste reconnaissable.
#:
#: LA MENTION IMPRIMÉE SUR LA FACTURE RESTE CELLE DE LA TABLE. C'est elle
#: qui a valeur légale sur le document ; l'abrègement ne concerne que le
#: champ du fichier.
MENTION_SAFT_ABREGEE = {
    'M15': 'Regime da margem de lucro – Objetos de coleção/antiguidades',
}

#: Les codes qui désignent une autoliquidation (inversion du redevable) et
#: non une exonération au sens strict. La distinction compte à l'écran :
#: le client paie la TVA lui-même, l'opération n'est pas « exonérée ».
AUTOLIQUIDATION = ('M30', 'M31', 'M32', 'M33', 'M34', 'M35', 'M40', 'M41',
                   'M42', 'M43')

#: Les deux codes du BTP, mis en avant parce que ce sont ceux qu'un ERP de
#: travaux emploie le plus souvent.
CODES_DU_BTP = ('M31', 'M35')


class MotifInvalide(Exception):
    """Ce qui a empêché la validation, dit dans des termes exploitables."""


def choix(date_document=None):
    """Les couples (code, libellé) pour une liste déroulante.

    Les codes du BTP viennent en tête : sur trente-trois entrées, celle
    qu'on cherche doit être trouvable. Le reste suit dans l'ordre de la
    table officielle.
    """
    disponibles = [code for code in CODES
                   if _est_en_vigueur(code, date_document)]
    ordonnes = ([c for c in CODES_DU_BTP if c in disponibles]
                + [c for c in disponibles if c not in CODES_DU_BTP])

    return [(code, f'{code} — {CODES[code][0]}') for code in ordonnes]


def _est_en_vigueur(code, date_document=None):
    depuis = EN_VIGUEUR_DEPUIS.get(code)
    if depuis is None:
        return True
    if date_document is None:
        return True
    return date_document >= depuis


def mencao(code):
    """La mention à faire figurer sur la facture.

    C'est une mention LÉGALE du document, pas une étiquette d'interface.
    La lire ici plutôt que de la saisir à la main évite qu'elle soit
    fautive une fois sur dix.
    """
    return CODES[valider(code)][0]


def mencao_saft(code):
    """La mention telle qu'elle entre dans le champ du SAF-T.

    Identique à celle de la facture, sauf pour les rares mentions que le
    schéma ne peut pas contenir — voir `MENTION_SAFT_ABREGEE`.
    """
    texte = valider(code)
    return MENTION_SAFT_ABREGEE.get(texte, CODES[texte][0])


def norma(code):
    """La norme applicable, pour affichage à côté du choix."""
    return CODES[valider(code)][1]


def valider(code, date_document=None):
    """Le code en forme canonique, ou une erreur explicite."""
    texte = str(code or '').strip().upper()

    if not texte:
        raise MotifInvalide(
            'Aucun motif d’exonération. Une ligne sans TVA doit porter son '
            'motif : le SAF-T l’exige, et le fichier entier serait rejeté à '
            'la remise.')

    if texte not in CODES:
        raise MotifInvalide(
            f'Le motif d’exonération « {texte} » n’existe pas. Les codes ne '
            'sont PAS contigus — M03, M08, M17, M18, M22 à M24, M27 à M29 et '
            'M36 à M39 n’existent pas —, et un code choisi par analogie fait '
            'rejeter le fichier tout en ayant l’air normal. Table officielle '
            'de l’AT, version 4.0 du 18/06/2026.')

    depuis = EN_VIGUEUR_DEPUIS.get(texte)
    if depuis is not None and date_document is not None and date_document < depuis:
        raise MotifInvalide(
            f'Le motif « {texte} » ne s’applique qu’aux factures émises à '
            f'partir du {depuis:%d/%m/%Y}. Le document est daté du '
            f'{date_document:%d/%m/%Y}.')

    return texte


def est_autoliquidation(code):
    """Vrai si le client acquitte la TVA lui-même.

    L'opération n'est alors pas « exonérée » : elle est autoliquidée. La
    nuance compte sur le document, où la mention diffère.
    """
    return str(code or '').strip().upper() in AUTOLIQUIDATION
