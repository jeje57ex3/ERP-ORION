"""apps/fiscal_pt/atcud.py — L'ATCUD, code unique de document.

CE QUE C'EST

Portaria n.º 195/2020. Avant d'émettre le moindre document d'une série,
l'entreprise déclare cette série à l'AT, qui lui rend un « código de
validação ». L'ATCUD d'un document est ensuite :

    <code de validation de la série>-<numéro séquentiel>

Exemple officiel : « CSDF7T5H-0035 ».

CE QUE CE MODULE NE FAIT PAS, ET POURQUOI C'EST IMPORTANT

Il ne FABRIQUE pas le code de validation. Celui-ci est attribué par
l'AT, par webservice, et lui seul fait foi. Un code inventé localement
produirait des documents d'apparence correcte et juridiquement nuls —
l'erreur ne se verrait qu'au premier contrôle, sur des mois de
facturation.

Ce module compose, valide le format, et refuse ce qui ne vient
manifestement pas de l'AT.
"""

import re

#: Le code rendu par l'AT : 8 caractères au moins, alphanumériques
#: majuscules. La Portaria ne fixe pas de longueur maximale ; on accepte
#: donc jusqu'à 70 caractères, taille du champ ATCUD du SAF-T (PT).
MOTIF_CODE_DE_VALIDATION = re.compile(r'^[0-9A-Z]{8,60}$')

#: Les séries non communiquées — un document émis en situation de secours,
#: par exemple — portent cette valeur. Elle est prévue par la Portaria :
#: mieux vaut la marque explicite d'une série non déclarée qu'un ATCUD
#: fabriqué pour faire bonne figure.
SANS_CODE = '0'


class ErreurATCUD(Exception):
    """Ce qui a empêché la composition, dit dans des termes exploitables."""


def valider_code_de_validation(code):
    """Le code rendu par l'AT, ou « 0 » pour une série non communiquée."""
    texte = str(code or '').strip().upper()

    if texte == SANS_CODE:
        return texte

    if not MOTIF_CODE_DE_VALIDATION.fullmatch(texte):
        raise ErreurATCUD(
            f'Code de validation invalide : « {texte} ». Il est attribué '
            'par l’AT lors de la communication de la série et ne peut pas '
            'être inventé. Employez « 0 » pour une série non communiquée.')

    return texte


def composer(code_de_validation, numero_sequentiel):
    """L'ATCUD d'un document.

    Le numéro est celui de la SÉRIE, pas le numéro complet du document :
    pour « FT AB2019/0035 », c'est « 0035 ». Confondre les deux donne un
    ATCUD qui ne correspond pas au document imprimé à côté, et le code QR
    le répète — l'incohérence serait donc visible deux fois.
    """
    code = valider_code_de_validation(code_de_validation)

    numero = str(numero_sequentiel or '').strip()
    if not numero.isdigit() or int(numero) < 1:
        raise ErreurATCUD(
            f'Numéro séquentiel invalide : « {numero} ». Il doit être un '
            'entier positif, sans la série ni le type de document.')

    return f'{code}-{numero}'


def separer(atcud):
    """L'opération inverse : rend (code de validation, numéro).

    Sert à revérifier un document déjà émis, et aux tests.
    """
    texte = str(atcud or '').strip()
    if texte.count('-') != 1:
        raise ErreurATCUD(
            f'ATCUD malformé : « {texte} ». Il s’écrit « code-numéro ».')
    code, numero = texte.split('-')
    return valider_code_de_validation(code), numero
