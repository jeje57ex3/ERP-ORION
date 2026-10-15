"""Remplissage d'un modèle de devis fourni en PDF.

Le principe : la mise en page du devis — en-tête, logo, conditions générales,
mentions légales — est fournie par l'exploitant sous forme de PDF, et Orion
n'en redessine rien. Il écrit par-dessus les seules valeurs qui changent d'un
devis à l'autre.

C'est délibérément l'inverse d'un générateur. Redessiner la mise en page
supposerait de reproduire une charte dans du code, de la maintenir à chaque
changement de papier à en-tête, et d'expliquer pourquoi le rendu diffère de
l'original. La superposition laisse le document tel que son auteur l'a voulu.

Deux outils, et chacun fait ce que l'autre ne sait pas faire : reportlab écrit
un PDF mais ne sait pas en relire un, pypdf relit et fusionne mais ne dessine
pas. D'où la combinaison -- une page de texte transparente, fusionnée sur la
page d'origine.
"""

import io
from decimal import Decimal

from django.utils import timezone


# ─── Les valeurs disponibles ─────────────────────────────────────────────────

def _format_montant(valeur):
    """Format français : espace comme séparateur de milliers, virgule décimale.

    « 12 400,00 » et non « 12400.00 » : un devis est un document commercial
    français, et un montant mal formaté y est lu comme une erreur de saisie.

    Le séparateur est l'espace INSÉCABLE U+00A0, et non l'espace fine U+202F
    que la typographie française préférerait. Vérifié : les polices standard
    du PDF (Helvetica et ses soeurs) utilisent l'encodage WinAnsi, qui ne
    contient pas U+202F — reportlab y substitue alors un carré noir, et le
    devis envoyé au client afficherait « 12■400,00 ». U+00A0 appartient à
    WinAnsi et empêche de la même façon la coupure en fin de ligne.
    """
    if valeur is None:
        return ''
    montant = Decimal(str(valeur)).quantize(Decimal('0.01'))
    entier, _, decimales = f'{montant:.2f}'.partition('.')
    negatif = entier.startswith('-')
    entier = entier.lstrip('-')
    tranches = []
    while len(entier) > 3:
        tranches.insert(0, entier[-3:])
        entier = entier[:-3]
    tranches.insert(0, entier)
    return ('-' if negatif else '') + ' '.join(tranches) + ',' + decimales


def _format_date(valeur):
    return valeur.strftime('%d/%m/%Y') if valeur else ''


def valeurs_du_devis(quote):
    """Les valeurs injectables, prêtes à écrire.

    Un devis sans client est impossible (la clé étrangère est obligatoire),
    mais un client sans code, sans contact ou sans email est courant : chaque
    valeur absente devient une chaîne vide plutôt qu'un « None » imprimé sur
    le document.
    """
    client = quote.customer
    adresse = ', '.join(
        part for part in (
            getattr(client, 'address', '') or '',
            getattr(client, 'zip_code', '') or '',
            getattr(client, 'city', '') or '',
        ) if part
    )

    commercial = quote.salesperson or quote.created_by
    nom_commercial = ''
    if commercial is not None:
        nom_commercial = (
            commercial.get_full_name() or commercial.get_username()
        )

    return {
        'numero_devis': quote.number or '',
        'date': _format_date(quote.issue_date),
        'validite': _format_date(quote.validity_date),
        'numero_client': getattr(client, 'code', '') or '',
        'nom_client': client.name or '',
        'contact_client': getattr(client, 'contact_name', '') or '',
        'adresse_client': adresse,
        'email_client': getattr(client, 'email', '') or '',
        'telephone_client': (
            getattr(client, 'phone', '') or getattr(client, 'mobile', '') or ''
        ),
        'objet': quote.subject or '',
        'total_ht': _format_montant(quote.total_ht),
        'total_tva': _format_montant(quote.total_tva),
        'total_ttc': _format_montant(quote.total_ttc),
        'delai_paiement': str(quote.payment_terms or ''),
        'commercial': nom_commercial,
    }


# ─── Le remplissage ──────────────────────────────────────────────────────────

class ModeleDevisError(Exception):
    pass


def _octets_du_modele(template):
    """Le PDF du modèle, en mémoire.

    Les trois fonctions de ce module lisaient le fichier chacune à leur
    façon, avec un `close()` en `finally`. Conséquence : une FieldFile fermée
    ne se réouvre pas toujours (« The file cannot be reopened »), et deux
    opérations successives sur le même modèle échouaient — générer un devis
    puis sa grille, ou générer deux devis d'affilée.

    Un modèle pèse quelques kilo-octets. Le lire entièrement une fois évite
    toute gestion de poignée de fichier, et rend ces fonctions utilisables
    en boucle.
    """
    if not template.pdf:
        raise ModeleDevisError(
            f'Le modèle « {template.name} » n’a pas de fichier PDF.')
    fichier = template.pdf
    try:
        fichier.open('rb')
    except Exception:
        # Deja ouvert, ou flux non reouvrable : on repart de sa position.
        pass
    try:
        fichier.seek(0)
    except Exception:
        pass
    octets = fichier.read()
    if not octets:
        raise ModeleDevisError(
            f'Le modèle « {template.name} » est vide ou illisible.')
    return octets


def _texte_du_champ(champ, valeurs):
    """Ce que ce champ écrira, ou une chaîne vide.

    Un champ sans valeur n'imprime rien -- pas même son préfixe : « Client : »
    suivi du vide ferait croire à une donnée perdue.
    """
    valeur = valeurs.get(champ.cle, '')
    if not valeur:
        return ''
    return f'{champ.prefixe}{valeur}{champ.suffixe}'


def _page_de_texte(champs, valeurs, largeur, hauteur):
    """Une page transparente ne portant que le texte à superposer."""
    from reportlab.pdfgen import canvas

    tampon = io.BytesIO()
    feuille = canvas.Canvas(tampon, pagesize=(largeur, hauteur))

    for champ in champs:
        texte = _texte_du_champ(champ, valeurs)
        if not texte:
            continue

        police = 'Helvetica-Bold' if champ.gras else 'Helvetica'
        feuille.setFont(police, champ.taille)

        x = float(champ.x)
        y = float(champ.y)
        if champ.alignement == 'right':
            feuille.drawRightString(x, y, texte)
        elif champ.alignement == 'center':
            feuille.drawCentredString(x, y, texte)
        else:
            feuille.drawString(x, y, texte)

    feuille.save()
    tampon.seek(0)
    return tampon


def remplir_modele(quote, template, champs=None):
    """Rend le PDF du devis : le modèle, avec les valeurs écrites dessus.

    Retourne un tampon, comme le reste des générateurs de ce dépôt : la vue le
    passe tel quel à la réponse HTTP, sans matérialiser le fichier deux fois.

    `champs` permet de passer une liste explicite au lieu de la lire sur le
    modèle. C'est ce qui rend la fonction éprouvable sans base de données --
    et, accessoirement, ce qui permettra de prévisualiser un placement avant
    de l'enregistrer.
    """
    from pypdf import PdfReader, PdfWriter

    valeurs = valeurs_du_devis(quote)
    if champs is None:
        champs = list(template.fields.all())
    else:
        champs = list(champs)

    lecteur = PdfReader(io.BytesIO(_octets_du_modele(template)))
    nombre_pages = len(lecteur.pages)

    # Un champ place sur une page qui n'existe pas serait perdu en silence :
    # on le dit AVANT de produire le document, plutot que de livrer un devis
    # auquel il manque une valeur sans explication.
    hors_limites = sorted({c.page for c in champs if c.page > nombre_pages})
    if hors_limites:
        raise ModeleDevisError(
            'Le modèle « %s » n’a que %s page(s), mais des champs sont placés '
            'en page %s.' % (
                template.name, nombre_pages,
                ', '.join(str(p) for p in hors_limites),
            )
        )

    ecrivain = PdfWriter()
    for index, page in enumerate(lecteur.pages, start=1):
        # Les champs PORTEURS DE VALEUR, et non tous ceux de la page.
        # Verifie : un canvas reportlab sur lequel rien n'est dessine produit
        # un document de ZERO page, et « pages[0] » levait alors IndexError --
        # toute la generation echouait pour un client sans code ni email.
        champs_de_la_page = [
            c for c in champs
            if c.page == index and _texte_du_champ(c, valeurs)
        ]
        if champs_de_la_page:
            boite = page.mediabox
            texte = _page_de_texte(
                champs_de_la_page, valeurs,
                float(boite.width), float(boite.height),
            )
            page.merge_page(PdfReader(texte).pages[0])
        ecrivain.add_page(page)

    sortie = io.BytesIO()
    ecrivain.write(sortie)
    sortie.seek(0)
    return sortie


# ─── La grille de calage ─────────────────────────────────────────────────────

def generer_grille_de_calage(template, pas=20):
    """Le modèle, avec un quadrillage coté imprimé dessus.

    Placer un champ demande des coordonnées en points PDF comptées depuis le
    BAS de la page. Personne ne les devine, et les chercher par essais
    successifs -- modifier, regénérer, regarder -- prend un temps
    déraisonnable pour une quinzaine de champs.

    Cette grille supprime le problème : on l'imprime ou on l'ouvre, on lit les
    deux nombres à l'endroit voulu, on les saisit. Une fois.
    """
    from pypdf import PdfReader, PdfWriter
    from reportlab.pdfgen import canvas

    lecteur = PdfReader(io.BytesIO(_octets_du_modele(template)))
    ecrivain = PdfWriter()

    for page in lecteur.pages:
        boite = page.mediabox
        largeur, hauteur = float(boite.width), float(boite.height)

        tampon = io.BytesIO()
        feuille = canvas.Canvas(tampon, pagesize=(largeur, hauteur))
        feuille.setLineWidth(0.25)

        # Lignes fines tous les `pas` points, plus marquées tous les 100 :
        # un quadrillage uniforme devient illisible sur un document charge.
        x = 0
        while x <= largeur:
            fort = int(x) % 100 == 0
            feuille.setStrokeColorRGB(0.85, 0.2, 0.2) if fort \
                else feuille.setStrokeColorRGB(0.6, 0.75, 0.9)
            feuille.setLineWidth(0.5 if fort else 0.2)
            feuille.line(x, 0, x, hauteur)
            if fort:
                feuille.setFont('Helvetica', 6)
                feuille.setFillColorRGB(0.85, 0.2, 0.2)
                feuille.drawString(x + 1, 4, str(int(x)))
            x += pas

        y = 0
        while y <= hauteur:
            fort = int(y) % 100 == 0
            feuille.setStrokeColorRGB(0.85, 0.2, 0.2) if fort \
                else feuille.setStrokeColorRGB(0.6, 0.75, 0.9)
            feuille.setLineWidth(0.5 if fort else 0.2)
            feuille.line(0, y, largeur, y)
            if fort:
                feuille.setFont('Helvetica', 6)
                feuille.setFillColorRGB(0.85, 0.2, 0.2)
                feuille.drawString(2, y + 2, str(int(y)))
            y += pas

        feuille.setFont('Helvetica-Bold', 7)
        feuille.setFillColorRGB(0.85, 0.2, 0.2)
        feuille.drawString(
            12, hauteur - 12,
            'Grille de calage — X vers la droite, Y vers le HAUT '
            '(origine en bas à gauche), en points'
        )
        feuille.save()
        tampon.seek(0)

        page.merge_page(PdfReader(tampon).pages[0])
        ecrivain.add_page(page)

    sortie = io.BytesIO()
    ecrivain.write(sortie)
    sortie.seek(0)
    return sortie


def champs_de_formulaire_detectes(template):
    """Noms des champs de formulaire du PDF, s'il en a.

    Un PDF exporté depuis un traitement de texte est le plus souvent « plat » :
    il n'a aucun champ, et seules des coordonnées permettent d'y écrire. Mais
    un PDF préparé comme formulaire en porte, et les relever permet alors de
    proposer un placement automatique plutôt que de faire saisir des
    coordonnées pour rien.

    Renvoie une liste, vide si le PDF est plat.
    """
    from pypdf import PdfReader

    try:
        lecteur = PdfReader(io.BytesIO(_octets_du_modele(template)))
        return sorted((lecteur.get_fields() or {}).keys())
    except Exception:
        # Un PDF illisible ne doit pas empêcher l'écran de s'afficher : le
        # placement par coordonnées reste disponible.
        return []


def nombre_de_pages(template):
    from pypdf import PdfReader

    try:
        return len(PdfReader(io.BytesIO(_octets_du_modele(template))).pages)
    except Exception:
        return 0


def devis_exemple(company):
    """Un devis non enregistré, pour prévisualiser un modèle.

    Prévisualiser avec de vraies valeurs supposerait d'avoir déjà un devis et
    un client — or on règle un modèle AVANT d'en créer. Cet exemple sert à
    vérifier le placement, pas les montants.
    """
    from apps.crm.models import Customer
    from apps.sales.models import Quote

    client = Customer(
        company=company,
        code='CLI-0042',
        name='Entreprise Exemple SARL',
        contact_name='Jean Dupont',
        address='12 rue des Artisans',
        zip_code='57000',
        city='Metz',
        email='contact@exemple.fr',
        phone='03 87 00 00 00',
    )
    quote = Quote(
        company=company,
        number='DEV-%s-0042' % timezone.now().year,
        customer=client,
        issue_date=timezone.now().date(),
        subject='Exemple de placement des champs',
        payment_terms=30,
        total_ht=Decimal('12400.00'),
        total_tva=Decimal('2480.00'),
        total_ttc=Decimal('14880.00'),
    )
    return quote
