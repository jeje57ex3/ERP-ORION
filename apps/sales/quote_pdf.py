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


def _format_taux(valeur):
    """« 20 % », « 5,5 % » : sans décimale inutile, virgule française.

    « 20,00 % » sur un devis se lit comme une précision affectée, et
    « 20.0 % » comme un montant anglais.
    """
    nombre = Decimal(str(valeur or 0)).normalize()
    texte = format(nombre, 'f')
    # Le rognage ne vaut QUE pour la partie decimale. Applique sans
    # condition, il transformait « 20 » en « 2 » et « 10 » en « 1 » :
    # un taux faux imprime sur un devis. Attrape a la verification.
    if '.' in texte:
        texte = texte.rstrip('0').rstrip('.')
    texte = texte or '0'
    return texte.replace('.', ',') + '\u00a0%'


def _taux_tva_appliques(quote):
    """Le ou les taux de TVA réellement appliqués par les lignes.

    Lu sur les lignes, et non saisi : c'est le taux APPLIQUÉ qui est
    demandé, et seules les lignes le portent (QuoteLine.vat_rate). Un champ
    saisi à part pourrait contredire le calcul, et c'est le document remis
    au client qui mentirait.

    Plusieurs taux sur un même devis sont courants en BTP — 10 % en
    rénovation, 20 % en neuf. Ils sont alors tous nommés : n'en afficher
    qu'un ferait du devis une pièce inexacte.

    Les lignes de sous-total et de texte sont exclues : elles ne portent pas
    de TVA, leur taux par défaut ferait apparaître un 20 % imaginaire.
    """
    if quote.pk:
        taux = sorted({
            Decimal(str(ligne.vat_rate or 0))
            for ligne in quote.lines.all()
            if ligne.line_type not in ('subtotal', 'text')
        })
        if taux:
            return ' / '.join(_format_taux(t) for t in taux)

    # Repli : le taux effectif, deduit des totaux.
    #
    # Deux cas l'empruntent. Le devis d'EXEMPLE de l'apercu de modele n'est
    # pas enregistre : interroger ses lignes leve « instance needs to have a
    # primary key » et fait tomber l'ecran qui sert justement a regler les
    # cadres -- constate avant livraison. Et un devis reel sans ligne mais
    # avec des totaux saisis ailleurs doit afficher quelque chose.
    #
    # Le melange de taux n'est pas un risque ici : s'il y avait des lignes,
    # le chemin ci-dessus les aurait nommees une a une.
    total_ht = Decimal(str(quote.total_ht or 0))
    total_tva = Decimal(str(quote.total_tva or 0))
    if total_ht <= 0 or total_tva <= 0:
        return ''
    return _format_taux(
        (total_tva / total_ht * 100).quantize(Decimal('0.01')))


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
        'taux_tva': _taux_tva_appliques(quote),
        'total_ttc': _format_montant(quote.total_ttc),
        # Les trois couts a zero n'impriment rien : un cadre sans valeur
        # reste vide (voir _texte_du_champ). « 0,00 EUR » de materiel sur un
        # devis de maconnerie serait lu comme une erreur, pas comme un
        # champ non renseigne.
        'cout_materiels': (
            _format_montant(quote.cout_materiels)
            if quote.cout_materiels else ''),
        'cout_fournitures': (
            _format_montant(quote.cout_fournitures)
            if quote.cout_fournitures else ''),
        'cout_main_oeuvre': (
            _format_montant(quote.cout_main_oeuvre)
            if quote.cout_main_oeuvre else ''),
        'taches_principales': (quote.taches_principales or '').strip(),
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


def _police(champ):
    return 'Helvetica-Bold' if champ.gras else 'Helvetica'


def _couleur(champ):
    """La couleur du texte, en composantes 0–1 pour reportlab.

    Tolère une valeur absente ou mal formée en retombant sur le noir : un
    réglage douteux ne doit pas faire échouer la génération d'un devis.
    """
    brut = (getattr(champ, 'couleur', '') or '#000000').lstrip('#')
    if len(brut) != 6:
        brut = '000000'
    try:
        rouge, vert, bleu = (int(brut[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        rouge = vert = bleu = 0
    return rouge / 255.0, vert / 255.0, bleu / 255.0


def _lignes_du_cadre(feuille, champ, texte, taille):
    """Découpe le texte en lignes qui tiennent dans la largeur du cadre.

    Les retours à la ligne saisis sont respectés — une liste de tâches est
    écrite une par ligne, et les recoller en un paragraphe perdrait
    l'information. Chaque paragraphe est ensuite coupé aux espaces.

    Un mot plus long que le cadre est laissé sur sa ligne et dépassera : le
    couper au milieu rendrait une référence illisible, et le débordement se
    voit — donc se corrige.
    """
    police = _police(champ)
    largeur = float(champ.largeur or 0)
    lignes = []

    for paragraphe in texte.splitlines():
        paragraphe = paragraphe.strip()
        if not paragraphe:
            lignes.append('')
            continue
        if largeur <= 0:
            lignes.append(paragraphe)
            continue

        courante = ''
        for mot in paragraphe.split():
            essai = f'{courante} {mot}'.strip()
            if feuille.stringWidth(essai, police, taille) <= largeur:
                courante = essai
            else:
                if courante:
                    lignes.append(courante)
                courante = mot
        if courante:
            lignes.append(courante)

    return lignes


def _taille_qui_tient(feuille, champ, texte):
    """La plus grande taille qui tient dans la largeur du cadre.

    Un nom de client long dépassait du cadre et chevauchait ce qui se trouve à
    côté — sur un devis, la colonne voisine. Réduire est préférable à
    déborder : le texte reste lisible et reste chez lui.

    La réduction s'arrête à 5 points. En dessous, le texte serait illisible et
    mieux vaut un débordement visible qu'une ligne qu'on ne peut pas lire :
    l'exploitant doit pouvoir constater que son cadre est trop petit.
    """
    largeur_cadre = float(champ.largeur or 0)
    taille = int(champ.taille or 10)
    if largeur_cadre <= 0:
        return taille

    police = _police(champ)
    while taille > 5:
        if feuille.stringWidth(texte, police, taille) <= largeur_cadre:
            return taille
        taille -= 1
    return taille


INTERLIGNE = 1.22
"""Hauteur d'une ligne, en multiples de la taille du texte.

1,0 collerait les lignes jambages contre accents ; au-dela de 1,3 une liste
de taches se disperse et ne se lit plus comme un bloc.
"""


def _ecrire_ligne(feuille, champ, texte, gauche, ligne_de_base, largeur):
    """Une ligne, posee selon l'alignement du cadre."""
    if champ.alignement == 'right':
        feuille.drawRightString(gauche + largeur, ligne_de_base, texte)
    elif champ.alignement == 'center':
        feuille.drawCentredString(gauche + largeur / 2, ligne_de_base, texte)
    else:
        feuille.drawString(gauche, ligne_de_base, texte)


def _ecrire_multiligne(feuille, champ, texte, gauche, bas, largeur, hauteur):
    """Un bloc de texte, rempli du HAUT du cadre vers le bas.

    Du haut, et non centre : une liste de taches doit commencer sous le
    coût de main-d'oeuvre, a un endroit previsible. Centree verticalement,
    elle se deplacerait a chaque tache ajoutee.

    La taille est reduite tant que le bloc depasse la hauteur du cadre,
    jusqu'a 5 points. En dessous, on laisse deborder : un debordement se
    voit et se corrige, un texte de 3 points ne se lit pas.
    """
    taille = int(champ.taille or 10)
    while True:
        lignes = _lignes_du_cadre(feuille, champ, texte, taille)
        besoin = len(lignes) * taille * INTERLIGNE
        if taille <= 5 or hauteur <= 0 or besoin <= hauteur:
            break
        taille -= 1

    feuille.setFont(_police(champ), taille)

    # La premiere ligne de base est sous le haut du cadre, de la hauteur
    # d'une majuscule : la poser SUR le haut ferait sortir le texte du
    # cadre dessine a l'ecran.
    haut = bas + hauteur if hauteur > 0 else bas
    ligne_de_base = haut - taille
    for ligne in lignes:
        if ligne:
            _ecrire_ligne(feuille, champ, ligne, gauche, ligne_de_base,
                          largeur)
        ligne_de_base -= taille * INTERLIGNE


def _page_de_texte(champs, valeurs, largeur, hauteur):
    """Une page transparente ne portant que le texte à superposer."""
    from reportlab.pdfgen import canvas

    tampon = io.BytesIO()
    feuille = canvas.Canvas(tampon, pagesize=(largeur, hauteur))

    for champ in champs:
        texte = _texte_du_champ(champ, valeurs)
        if not texte:
            continue

        gauche = float(champ.x)
        bas = float(champ.y)
        largeur_cadre = float(champ.largeur or 0)
        hauteur_cadre = float(champ.hauteur or 0)

        feuille.setFillColorRGB(*_couleur(champ))

        if getattr(champ, 'multiligne', False):
            _ecrire_multiligne(feuille, champ, texte, gauche, bas,
                               largeur_cadre, hauteur_cadre)
            continue

        taille = _taille_qui_tient(feuille, champ, texte)
        feuille.setFont(_police(champ), taille)

        # La ligne de base, et non le bord du cadre : poser le texte sur « bas »
        # le ferait reposer sur le bord inferieur, jambages compris, et il
        # paraitrait decale vers le bas par rapport au cadre dessine a l'ecran.
        # On le centre verticalement, en tenant compte de la descente.
        if hauteur_cadre > 0:
            ligne_de_base = bas + (hauteur_cadre - taille) / 2 + taille * 0.22
        else:
            ligne_de_base = bas

        _ecrire_ligne(feuille, champ, texte, gauche, ligne_de_base,
                      largeur_cadre)

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
        # Renseignes, sinon les cadres de la decomposition resteraient
        # vides a l'apercu -- et l'on ne pourrait pas verifier leur
        # placement, qui est la seule raison d'etre de cet ecran.
        cout_materiels=Decimal('5200.00'),
        cout_fournitures=Decimal('1450.00'),
        cout_main_oeuvre=Decimal('5750.00'),
        taches_principales=(
            'Depose de l’ancien revetement de sol\n'
            'Ragreage et preparation du support\n'
            'Pose du carrelage grand format\n'
            'Joints et finitions, evacuation des gravats'
        ),
    )
    return quote


# ─── Rendu d'une page en image, pour l'éditeur visuel ────────────────────────

ECHELLE_EDITEUR = 2.0
"""Pixels par point PDF dans l'éditeur.

2.0 donne 144 dpi : net à l'écran, et une page A4 tient en ~1191x1684 pixels,
soit une trentaine de kilo-octets en PNG. Un rapport entier simplifie aussi la
conversion que fait l'éditeur — et une conversion simple est une conversion
qu'on peut vérifier de tête.
"""


def rendre_page_en_png(template, numero_page=1, echelle=ECHELLE_EDITEUR):
    """Une page du modèle, en PNG, pour servir de fond à l'éditeur.

    Rendu côté serveur plutôt que par un visionneur JavaScript embarqué :
    pypdfium2 est une roue pure, sans dépendance système, donc installable sur
    une appliance hors ligne — là où embarquer pdf.js ajouterait un mégaoctet
    de JavaScript à maintenir. Et l'échelle est connue exactement, ce qui rend
    la conversion pixels → points exacte plutôt qu'approchée.
    """
    import pypdfium2 as pdfium

    octets = _octets_du_modele(template)
    try:
        document = pdfium.PdfDocument(io.BytesIO(octets))
    except Exception as exc:
        # pypdfium2 leve PdfiumError, pas ModeleDevisError : sans cette
        # traduction, un fichier corrompu faisait repondre 500 a l'ecran de
        # placement au lieu de dire ce qui n'allait pas.
        raise ModeleDevisError(
            'Le modèle « %s » n’est pas un PDF lisible (%s).'
            % (template.name, exc)
        ) from exc
    try:
        if numero_page < 1 or numero_page > len(document):
            raise ModeleDevisError(
                'Le modèle « %s » n’a pas de page %s.'
                % (template.name, numero_page)
            )
        page = document[numero_page - 1]
        image = page.render(scale=echelle).to_pil()
        sortie = io.BytesIO()
        image.save(sortie, format='PNG')
        sortie.seek(0)
        return sortie, float(page.get_width()), float(page.get_height())
    finally:
        document.close()


def dimensions_des_pages(template):
    """Largeur et hauteur de chaque page, en points.

    L'éditeur en a besoin pour convertir : il travaille en pixels depuis le
    HAUT, le PDF compte en points depuis le BAS.
    """
    import pypdfium2 as pdfium

    # Toute defaillance rend une liste VIDE, et l'ecran l'interprete comme
    # « ce PDF n'est pas lisible » -- un fichier corrompu ne doit pas faire
    # echouer la page, mais le dire.
    try:
        octets = _octets_du_modele(template)
        document = pdfium.PdfDocument(io.BytesIO(octets))
    except Exception:
        return []

    try:
        return [
            {
                'numero': index + 1,
                'largeur': float(document[index].get_width()),
                'hauteur': float(document[index].get_height()),
            }
            for index in range(len(document))
        ]
    finally:
        document.close()
