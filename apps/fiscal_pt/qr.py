"""apps/fiscal_pt/qr.py — Le code QR des documents, au Portugal.

CE QUE LA LOI EXIGE

Portaria n.º 195/2020, et les « Especificações Técnicas Código de Barras
Bidimensional (Código QR) » publiées par l'AT. Chaque document porte un
code QR dont le contenu est une suite de champs « lettre:valeur »
concaténés par « * ».

Exemple officiel, tiré de la spécification (figure 5) :

    A:123456789*B:4443332215*C:FR*D:FT*E:N*F:20190526*G:ABC BNH/4561
    *H:DK5ZJ2HN-4561*I1:FR*I7:100.00*I8:20.00*N:20.00*O:120.00
    *Q:YJRE*R:9999

TROIS RÈGLES QUI SE PERDENT FACILEMENT

1. L'ORDRE EST FIXE. Les champs se suivent dans l'ordre du tableau, pas
   dans celui où le code les calcule. Un lecteur conforme accepterait
   peut-être un autre ordre ; le contrôle, lui, compare au tableau.

2. UN CHAMP OPTIONNEL VIDE EST OMIS, pas rendu vide. « I3: » n'est pas
   « rien » : c'est un champ déclaré à zéro, ce qui n'a pas le même sens
   fiscal qu'un champ absent.

3. LES MONTANTS ONT DEUX DÉCIMALES, point décimal, sans séparateur de
   milliers. « 1 000,00 » et « 1000.0 » sont tous deux faux.

LES ESPACES FISCAUX

Le continent (PT), les Açores (PT-AC) et Madère (PT-MA) ont chacun leur
bloc de huit champs : I pour le premier espace du document, J pour le
deuxième, K pour le troisième. Ce ne sont pas des lettres attribuées à
des régions — c'est l'ORDRE d'apparition qui décide, et c'est l'erreur
la plus courante.
"""

from decimal import Decimal

SEPARATEUR = '*'

#: Les trois blocs d'espace fiscal, dans l'ordre où ils se remplissent.
PREFIXES_ESPACE = ('I', 'J', 'K')

#: Les huit lignes d'un bloc : région, puis bases et TVA par taux.
LIGNES_ESPACE = (
    'regiao',          # n1 — ex. « PT », « PT-AC », « PT-MA », ou « 0 »
    'base_isenta',     # n2
    'base_reduzida',   # n3
    'iva_reduzida',    # n4
    'base_intermedia',  # n5
    'iva_intermedia',  # n6
    'base_normal',     # n7
    'iva_normal',      # n8
)

#: Le NIF conventionnel du consommateur final, imposé par la
#: spécification pour le champ B.
NIF_CONSOMMATEUR_FINAL = '999999990'


class ErreurQR(Exception):
    """Ce qui a empêché la composition, dit dans des termes exploitables."""


def _montant(valeur):
    """Deux décimales, point décimal, pas de séparateur de milliers."""
    return f'{Decimal(str(valeur)):.2f}'


def _date(valeur):
    """AAAAMMJJ — sans tirets, contrairement à la signature.

    Les deux formats coexistent dans la même facture : AAAA-MM-JJ dans la
    chaîne signée, AAAAMMJJ dans le code QR. Les confondre casse l'un ou
    l'autre, et chacun se vérifie séparément.
    """
    texte = str(valeur)[:10]
    return texte.replace('-', '')


def composer(*, nif_emetteur, nif_acquereur, pays_acquereur, type_document,
             etat_document, date_document, numero_document, atcud,
             espaces_fiscaux, total_impostos, total_documento,
             caracteres_hash, numero_certificat,
             nao_sujeito=None, imposto_selo=None, retencoes=None,
             outras_informacoes=''):
    """Le contenu du code QR, prêt à encoder.

    Les paramètres sont tous NOMMÉS, et c'est délibéré : dix-huit champs
    positionnels s'interverticraient tôt ou tard, et une base de TVA
    passée en total d'impôt ne se verrait pas à la lecture du code.
    """
    champs = []

    def ajouter(code, valeur):
        champs.append(f'{code}:{valeur}')

    # ── Les champs obligatoires, dans l'ordre du tableau ────────────────
    for code, valeur, nom in (
        ('A', nif_emetteur, 'NIF de l’émetteur'),
        ('B', nif_acquereur or NIF_CONSOMMATEUR_FINAL, 'NIF de l’acquéreur'),
        ('C', pays_acquereur, 'pays de l’acquéreur'),
        ('D', type_document, 'type de document'),
        ('E', etat_document, 'état du document'),
        ('G', numero_document, 'numéro du document'),
        ('H', atcud, 'ATCUD'),
    ):
        texte = str(valeur or '').strip()
        if not texte:
            raise ErreurQR(f'Le champ obligatoire {code} ({nom}) est vide.')
        if SEPARATEUR in texte:
            raise ErreurQR(
                f'Le champ {code} contient « {SEPARATEUR} », qui sépare les '
                'champs : le code serait illisible.')

    ajouter('A', str(nif_emetteur).strip())
    ajouter('B', str(nif_acquereur or NIF_CONSOMMATEUR_FINAL).strip())
    ajouter('C', str(pays_acquereur).strip())
    ajouter('D', str(type_document).strip())
    ajouter('E', str(etat_document).strip())
    ajouter('F', _date(date_document))
    ajouter('G', str(numero_document).strip())
    ajouter('H', str(atcud).strip())

    # ── Les espaces fiscaux : I, puis J, puis K ─────────────────────────
    if not espaces_fiscaux:
        raise ErreurQR(
            'Aucun espace fiscal. Le champ I1 est obligatoire ; un document '
            'sans taux de TVA se déclare avec la région « 0 ».')
    if len(espaces_fiscaux) > len(PREFIXES_ESPACE):
        raise ErreurQR(
            f'{len(espaces_fiscaux)} espaces fiscaux : la spécification en '
            f'prévoit {len(PREFIXES_ESPACE)} au plus (I, J, K).')

    for prefixe, espace in zip(PREFIXES_ESPACE, espaces_fiscaux):
        region = str(espace.get('regiao') or '').strip()
        if not region:
            raise ErreurQR(f'L’espace fiscal {prefixe}1 n’a pas de région.')
        ajouter(f'{prefixe}1', region)

        # Les sept montants ne sont écrits que s'ils existent : un champ
        # à zéro et un champ absent ne disent pas la même chose au fisc.
        for rang, nom in enumerate(LIGNES_ESPACE[1:], start=2):
            valeur = espace.get(nom)
            if valeur is not None:
                ajouter(f'{prefixe}{rang}', _montant(valeur))

    # ── Les totaux et les champs finaux ─────────────────────────────────
    if nao_sujeito is not None:
        ajouter('L', _montant(nao_sujeito))
    if imposto_selo is not None:
        ajouter('M', _montant(imposto_selo))

    ajouter('N', _montant(total_impostos))
    ajouter('O', _montant(total_documento))

    if retencoes is not None:
        ajouter('P', _montant(retencoes))

    hash4 = str(caracteres_hash or '').strip()
    if len(hash4) != 4:
        raise ErreurQR(
            f'Le champ Q attend les 4 caractères de la signature, reçu '
            f'« {hash4} » ({len(hash4)}).')
    ajouter('Q', hash4)

    ajouter('R', str(numero_certificat).strip())

    if outras_informacoes:
        texte = str(outras_informacoes).strip()
        if SEPARATEUR in texte:
            raise ErreurQR(
                'Le champ S ne peut pas contenir « * » : ses éléments se '
                'concatènent avec « ; ».')
        ajouter('S', texte)

    return SEPARATEUR.join(champs)


def image(contenu, taille_module=4, marge=2):
    """L'image du code QR, en PNG.

    La spécification demande une correction d'erreur de niveau M et une
    marge de 2 modules ; le reste (taille du module) dépend du support
    d'impression.
    """
    try:
        import qrcode
    except ImportError:
        raise ErreurQR('Le paquet « qrcode » n’est pas installé.')

    code = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=taille_module,
        border=marge,
    )
    code.add_data(contenu)
    code.make(fit=True)
    return code.make_image(fill_color='black', back_color='white')
