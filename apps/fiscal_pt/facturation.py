"""apps/fiscal_pt/facturation.py — Le pont entre une facture et sa preuve.

CE QUE CE MODULE DÉCIDE

À quel moment une facture de l'ERP devient un document fiscal signé, et
avec quelles valeurs. Tout le reste du paquet calcule et conserve ; ici
on traduit le modèle de l'ERP vers celui de l'administration
portugaise.

LA RÈGLE QUI GOUVERNE TOUT

Une facture ne peut pas être remise au client avant d'être signée. Si la
signature échoue — clé absente, série non déclarée, taux étranger — alors
l'ÉMISSION ÉCHOUE AUSSI. Un programme certifié qui remettrait un
document non signé en cas d'incident serait pire qu'un programme non
certifié : l'anomalie serait invisible, et des mois de factures
sortiraient sans preuve.

RIEN NE CHANGE TANT QUE LA CONFORMITÉ N'EST PAS ACTIVÉE

`ParametresFiscauxPT.est_actif` commande tout. Une installation française
ne voit aucune différence : `document_pour` rend None et la facturation
suit son cours habituel.
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import DocumentFiscal, ParametresFiscauxPT, SerieFiscale

#: Le type de document d'une facture de vente ordinaire.
TYPE_PAR_DEFAUT = 'FT'


class ConformiteInactive(Exception):
    """La conformité portugaise n'est pas activée pour cette entreprise.

    Ce n'est pas une erreur : c'est le cas normal d'une installation qui
    ne facture pas au Portugal. On lève tout de même, plutôt que de rendre
    None, pour que l'appelant choisisse explicitement ce qu'il en fait.
    """


def est_active(company):
    return ParametresFiscauxPT.objects.filter(
        company=company, est_actif=True).exists()


def document_pour(invoice):
    """Le document fiscal d'une facture, s'il existe.

    Sert à l'affichage : une facture déjà signée doit montrer son ATCUD,
    son code QR et sa mention légale, et ne doit surtout pas être signée
    une seconde fois.

    `document_rectifie__isnull=True` N'EST PAS UN DÉTAIL.

    Les avoirs portent le MÊME lien source que la facture qu'ils
    rectifient — c'est voulu, pour la traçabilité. Sans ce filtre, la
    requête rendait le plus récent, donc l'avoir : le deuxième appel
    rectifiait alors l'AVOIR au lieu de la facture, et l'écran de la
    facture affichait l'avoir comme sa propre preuve.

    Mesure : un deuxième avoir sur la même facture donnait « NC A/2 »
    rectifiant « NC A/1 », au lieu de rendre le premier. Les deux
    documents étaient parfaitement signés, et le client était crédité
    deux fois.

    Le document propre d'une facture est celui qui ne rectifie rien.
    """
    return DocumentFiscal.objects.filter(
        company_id=invoice.company_id,
        source_app='sales', source_modele='invoice',
        source_id=invoice.pk,
        document_rectifie__isnull=True).first()


def rectifications_de(invoice, type_document=None):
    """Les documents rectificatifs d'une facture, du plus ancien au plus récent.

    `type_document` sépare les avoirs des notes de débit. Les mélanger
    dans une même liste intitulée « avoirs » donnerait à lire une note de
    débit comme un crédit : le lecteur en déduirait que la facture a été
    diminuée alors qu'elle a été augmentée, et c'est le contresens exact
    que ces deux documents permettent.
    """
    documents = (DocumentFiscal.objects
                 .filter(company_id=invoice.company_id,
                         source_app='sales', source_modele='invoice',
                         source_id=invoice.pk,
                         document_rectifie__isnull=False)
                 .order_by('date_document', 'numero_sequentiel'))
    if type_document:
        documents = documents.filter(serie__type_document=type_document)
    return documents


def formes_legales_disponibles(company):
    """Les formes de facture qu'on peut réellement émettre aujourd'hui.

    POURQUOI LA LISTE EST CALCULÉE ET NON ÉCRITE EN DUR

    Une forme sans série active ne peut pas être numérotée. L'offrir au
    choix donnerait un écran qui propose « facture simplifiée » et un
    refus à l'envoi — alors que la seule chose à faire est de déclarer la
    série. On n'offre donc que ce qui marche, et l'absence d'une forme
    renvoie au bon endroit : Conformité Portugal → Séries.
    """
    from .models import TYPES_DE_DOCUMENT

    actives = set(SerieFiscale.objects
                  .filter(company=company, est_active=True)
                  .values_list('type_document', flat=True))

    return [(code, libelle) for code, libelle in TYPES_DE_DOCUMENT
            if code in ('FT', 'FS', 'FR') and code in actives]


def serie_pour(company, type_document=TYPE_PAR_DEFAUT):
    """La série active de ce type de document, ou une erreur explicite."""
    serie = SerieFiscale.objects.filter(
        company=company, type_document=type_document,
        est_active=True).order_by('nom').first()

    if serie is None:
        raise ValidationError(
            f'Aucune série active de type « {type_document} » pour cette '
            'entreprise. Déclarez-en une dans Conformité Portugal → Séries '
            'avant d’émettre une facture : un document émis hors série ne '
            'peut pas être numéroté légalement.')
    return serie


def lignes_de_la_facture(invoice):
    """Les lignes de la facture, dans la forme qu'attend `emettre`.

    On relit `total_ht` et `total_tva` tels qu'ils sont enregistrés plutôt
    que de les recalculer. Recalculer donnerait parfois un centime d'écart
    avec le total de la facture — et c'est le total qui est signé, donc
    l'écart rendrait la preuve incohérente avec le document imprimé.
    """
    lignes = []

    for ligne in invoice.lines.all().order_by('order', 'pk'):
        lignes.append({
            'description': ligne.description or ligne.reference or 'Serviço',
            'code_produit': ligne.reference or '',
            'quantite': Decimal(str(ligne.quantity or 1)),
            'unite': ligne.unit or 'UN',
            'prix_unitaire': Decimal(str(ligne.unit_price or 0)),
            'base': Decimal(str(ligne.total_ht or 0)),
            'taux': Decimal(str(ligne.vat_rate or 0)),
            'tva': Decimal(str(ligne.total_tva or 0)),
            'code_exoneration': ligne.code_exoneration or '',
        })

    return lignes


def emettre_pour_facture(invoice, type_document=TYPE_PAR_DEFAUT,
                         paiements=None):
    """Signe une facture de l'ERP et rend son document fiscal.

    IDEMPOTENT. Une facture déjà signée rend son document existant sans en
    créer un second : un double appel — un bouton cliqué deux fois, une
    requête rejouée — consommerait sinon deux numéros de série et laisserait
    un document orphelin dans la chaîne, ce qu'aucune correction ne rattrape
    ensuite.

    `type_document` choisit la forme légale : « FT » pour la facture
    ordinaire, « FS » pour la facture simplifiée — dont le plafond de
    l'article 40.º est alors vérifié —, « FR » pour la facture-reçu, qui
    exige `paiements` puisqu'elle vaut quittance.

    `paiements` est une liste de dictionnaires portant « mecanisme »,
    « montant » et « date ».
    """
    company = invoice.company
    parametres = ParametresFiscauxPT.de(company)

    if not parametres.est_actif:
        raise ConformiteInactive(
            'La conformité portugaise n’est pas activée pour cette '
            'entreprise.')

    if not parametres.nif:
        raise ValidationError(
            'Le NIF de l’entreprise est absent : il figure dans le code QR '
            'et dans le SAF-T. Renseignez-le dans Conformité Portugal → '
            'Paramètres.')

    with transaction.atomic():
        existant = document_pour(invoice)
        if existant is not None:
            return existant

        lignes = lignes_de_la_facture(invoice)
        if not lignes:
            raise ValidationError(
                f'La facture {invoice.number} n’a aucune ligne. Un document '
                'sans ligne ne peut pas être émis : le SAF-T en exige au '
                'moins une, et le fichier entier serait rejeté.')

        document = DocumentFiscal.emettre(
            serie=serie_pour(company, type_document),
            date_document=invoice.issue_date,
            lignes=lignes,
            nif_emetteur=parametres.nif,
            nif_acquereur=getattr(invoice.customer, 'nif', '') or '',
            pays_acquereur=_pays_de(invoice.customer),
            source=invoice,
            numero_de_certificat=parametres.numero_de_certificat or '0',
            paiements=paiements,
            regime_simplifiee=parametres.regime_simplifiee,
        )

        # Le numéro légal portugais REMPLACE celui de l'ERP.
        #
        # Les deux ne peuvent pas coexister sur un même document : c'est le
        # numéro imprimé qui est signé, et c'est lui que le SAF-T exporte.
        # Laisser « FAC-2026-0042 » sur la facture et « FT A/42 » dans la
        # preuve donnerait deux documents différents portant la même
        # signature.
        if invoice.number != document.numero:
            type(invoice).objects.filter(pk=invoice.pk).update(
                number=document.numero)
            invoice.number = document.numero

        return document


def emettre_une_note_de_credit(invoice, motif, lignes=None):
    """Émet l'avoir qui rectifie une facture déjà signée.

    POURQUOI CETTE FONCTION DOIT EXISTER

    `DocumentFiscal.save()` refuse de modifier un document émis, et son
    message dit « Émettez une note de crédit pour le corriger ». Sans
    cette fonction, ce message désignerait quelque chose qui n'existe
    pas — et la seule voie légale de correction serait fermée.

    `lignes` permet un avoir PARTIEL. Omis, l'avoir reprend toutes les
    lignes de la facture : c'est l'annulation complète, le cas courant.
    """
    company = invoice.company
    parametres = ParametresFiscauxPT.de(company)

    if not parametres.est_actif:
        raise ConformiteInactive(
            'La conformité portugaise n’est pas activée pour cette '
            'entreprise.')

    origine = document_pour(invoice)
    if origine is None:
        raise ValidationError(
            f'La facture {invoice.number} n’a pas été signée : il n’y a '
            'rien à rectifier. Une facture encore en brouillon se modifie '
            'directement.')

    motif = (motif or '').strip()
    if not motif:
        raise ValidationError(
            'Un avoir doit porter son motif. C’est lui qui distingue un '
            'geste commercial d’une erreur de facturation, et le SAF-T le '
            'transporte dans le champ « Reason ».')

    with transaction.atomic():
        # Un seul avoir d'annulation par facture.
        #
        # Deux avoirs complets créditeraient deux fois le client, et rien
        # dans la chaîne de signatures ne le signalerait : les deux
        # documents sont parfaitement valides pris séparément.
        if lignes is None:
            deja = DocumentFiscal.objects.filter(
                document_rectifie=origine,
                total=origine.total).first()
            if deja is not None:
                return deja

        return DocumentFiscal.emettre(
            serie=serie_pour(company, 'NC'),
            date_document=timezone.now().date(),
            lignes=lignes if lignes is not None else _lignes_figees(origine),
            nif_emetteur=parametres.nif,
            nif_acquereur=origine.nif_acquereur,
            pays_acquereur=origine.pays_acquereur,
            source=invoice,
            numero_de_certificat=parametres.numero_de_certificat or '0',
            document_rectifie=origine,
            motif_rectification=motif,
        )


def emettre_une_note_de_debit(invoice, motif, lignes):
    """Émet la note de débit qui AUGMENTE ce que le client doit.

    POURQUOI `lignes` EST OBLIGATOIRE ICI, ALORS QU'IL EST FACULTATIF POUR
    UN AVOIR

    Un avoir omis de lignes annule la facture entière : c'est le cas
    courant, et le raccourci est sûr. Une note de débit omise de lignes
    n'aurait, elle, aucun sens par défaut : reprendre les lignes de la
    facture facturerait la même prestation une seconde fois, et le client
    recevrait un document parfaitement signé lui réclamant le double. Le
    défaut silencieux serait une erreur de facturation irréversible — une
    note de débit ne se retire que par un avoir.

    On exige donc de dire ce qui est facturé en plus. `lignes` prend la
    même forme que celles d'une facture : description, quantité, prix
    unitaire, taux.
    """
    company = invoice.company
    parametres = ParametresFiscauxPT.de(company)

    if not parametres.est_actif:
        raise ConformiteInactive(
            'La conformité portugaise n’est pas activée pour cette '
            'entreprise.')

    origine = document_pour(invoice)
    if origine is None:
        raise ValidationError(
            f'La facture {invoice.number} n’a pas été signée : il n’y a '
            'rien à rectifier. Une facture encore en brouillon se modifie '
            'directement.')

    motif = (motif or '').strip()
    if not motif:
        raise ValidationError(
            'Une note de débit doit porter son motif. C’est lui qui '
            'justifie la somme réclamée en plus, et le SAF-T le transporte '
            'dans le champ « Reason ».')

    lignes = list(lignes or [])
    if not lignes:
        raise ValidationError(
            'Une note de débit doit dire ce qu’elle facture en plus. Sans '
            'ligne, il n’y a pas de montant à réclamer — et reprendre les '
            'lignes de la facture facturerait la prestation une seconde '
            'fois.')

    with transaction.atomic():
        return DocumentFiscal.emettre(
            serie=serie_pour(company, 'ND'),
            date_document=timezone.now().date(),
            lignes=lignes,
            nif_emetteur=parametres.nif,
            nif_acquereur=origine.nif_acquereur,
            pays_acquereur=origine.pays_acquereur,
            source=invoice,
            numero_de_certificat=parametres.numero_de_certificat or '0',
            document_rectifie=origine,
            motif_rectification=motif,
            regime_simplifiee=parametres.regime_simplifiee,
        )


def _lignes_figees(document):
    """Les lignes d'un document émis, remises en forme pour une réémission.

    On repart des lignes FIGÉES du document fiscal, et non de la facture
    de l'ERP : la facture a pu changer depuis, et un avoir doit créditer
    ce qui a réellement été facturé, pas l'état actuel du dossier.
    """
    return [{
        'description': figee['description'],
        'code_produit': figee['code_produit'],
        'quantite': Decimal(figee['quantite']),
        'unite': figee['unite'],
        'prix_unitaire': Decimal(figee['prix_unitaire']),
        'base': Decimal(figee['base']),
        'taux': Decimal(figee['taux']),
        'tva': Decimal(figee['tva']),
        'code_exoneration': figee.get('code_exoneration') or '',
    } for figee in document.lignes]


def _pays_de(customer):
    """Le code pays à deux lettres de l'acquéreur.

    Le champ « pays » de l'ERP est un texte libre (« Portugal », « France »),
    et le code QR attend deux lettres. Un texte libre recopié tel quel
    produirait un code QR illisible par l'application de l'AT.
    """
    brut = (getattr(customer, 'country', '') or '').strip()

    if not brut:
        return 'PT'
    if len(brut) == 2:
        return brut.upper()

    connus = {
        'portugal': 'PT', 'france': 'FR', 'espagne': 'ES', 'espanha': 'ES',
        'allemagne': 'DE', 'alemanha': 'DE', 'italie': 'IT', 'itália': 'IT',
        'belgique': 'BE', 'bélgica': 'BE', 'pays-bas': 'NL',
        'luxembourg': 'LU', 'royaume-uni': 'GB', 'suisse': 'CH',
        'brésil': 'BR', 'brasil': 'BR', 'angola': 'AO',
        'moçambique': 'MZ', 'mozambique': 'MZ',
    }

    code = connus.get(brut.lower())
    if code:
        return code

    # Plutôt que de deviner, on le dit : « Desconhecido » est la valeur que
    # le SAF-T prévoit pour un pays inconnu, et elle se corrige après coup.
    # Un code à deux lettres inventé, lui, passerait inaperçu.
    return 'Desconhecido'
