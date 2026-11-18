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
    """
    return DocumentFiscal.objects.filter(
        company_id=invoice.company_id,
        source_app='sales', source_modele='invoice',
        source_id=invoice.pk).first()


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
        })

    return lignes


def emettre_pour_facture(invoice, type_document=TYPE_PAR_DEFAUT):
    """Signe une facture de l'ERP et rend son document fiscal.

    IDEMPOTENT. Une facture déjà signée rend son document existant sans en
    créer un second : un double appel — un bouton cliqué deux fois, une
    requête rejouée — consommerait sinon deux numéros de série et laisserait
    un document orphelin dans la chaîne, ce qu'aucune correction ne rattrape
    ensuite.
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
