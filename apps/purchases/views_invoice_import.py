"""
apps/purchases/views_invoice_import.py — Importer une facture fournisseur PDF

Deux temps, et jamais un seul : **déposer**, puis **relire et confirmer**.

Une facture crée une dette et part en comptabilité. Un import qui
enregistrerait directement ce qu'il croit avoir lu transformerait une
erreur d'extraction en écriture comptable, et personne ne s'en
apercevrait avant le rapprochement bancaire. L'extraction propose donc,
et c'est un humain qui valide — avec sous les yeux ce dont le détecteur
n'est pas sûr.

Le formulaire de confirmation est un formulaire ordinaire, pré-rempli. Ce
n'est pas un détail : tout ce que l'extraction a mal lu se corrige sur
place, et le champ vide qu'elle n'a pas su remplir se saisit comme
d'habitude.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .invoice_detection import FactureIllisible, detecter_facture
from .models import Supplier, SupplierInvoice

# Un PDF de facture pèse quelques centaines de kilo-octets. La borne est là
# contre l'envoi accidentel d'une archive ou d'un scan de 80 pages, qui
# ferait travailler le serveur plusieurs minutes pour rien.
TAILLE_MAX = 15 * 1024 * 1024


def _champs_pour_formulaire(detection):
    """Les valeurs extraites, dans la forme attendue par les champs HTML.

    Les dates en AAAA-MM-JJ (ce qu'attend `<input type="date">`) et les
    montants en texte simple : un Decimal rendu tel quel écrirait
    « 1234.56 » là où le champ attend un point, ce qui marche, mais
    « None » là où il faut du vide.
    """
    champs = detection.get('champs', {})
    sortie = {}
    for nom, valeur in champs.items():
        if valeur is None:
            sortie[nom] = ''
        elif hasattr(valeur, 'isoformat'):
            sortie[nom] = valeur.isoformat()
        else:
            sortie[nom] = str(valeur)
    return sortie


@login_required
def invoice_import(request):
    """Dépôt du PDF, puis relecture. Rien n'est enregistré à ce stade."""
    company = request.current_company

    if request.method != 'POST':
        return render(request, 'purchases/invoice_import.html', {
            'page_title': 'Importer une facture PDF',
            'active_module': 'purchases',
        })

    fichier = request.FILES.get('fichier')
    if fichier is None:
        messages.error(request, 'Aucun fichier reçu.')
        return redirect('purchases:invoice_import')

    if fichier.size > TAILLE_MAX:
        messages.error(request, (
            f'Fichier trop volumineux ({fichier.size // 1024 // 1024} Mo). '
            f'Une facture PDF dépasse rarement un mégaoctet ; au-delà de '
            f'{TAILLE_MAX // 1024 // 1024} Mo, il s\'agit souvent d\'un scan '
            f'en très haute résolution — dont le texte n\'est de toute façon '
            f'pas lisible.'))
        return redirect('purchases:invoice_import')

    octets = fichier.read()
    try:
        detection = detecter_facture(octets, company=company)
    except FactureIllisible as exc:
        messages.error(request, str(exc))
        return redirect('purchases:invoice_import')

    # Le fichier est remis à zéro pour pouvoir être relu et enregistré à
    # l'étape suivante : .read() a consommé le flux, et un FileField
    # enregistré après coup écrirait un fichier vide.
    fichier.seek(0)

    # Conservé en session sous forme d'identifiant du fichier temporaire.
    # Le PDF lui-même n'y est PAS mis : une session porte quelques
    # kilo-octets, et y glisser un fichier d'un mégaoctet gonflerait la
    # table des sessions à chaque import.
    from django.core.files.storage import default_storage
    chemin_provisoire = default_storage.save(
        f'supplier_invoices/_en_attente/{fichier.name}', fichier)

    request.session['facture_importee'] = {
        'chemin': chemin_provisoire,
        'nom': fichier.name,
    }

    return render(request, 'purchases/invoice_import_review.html', {
        'detection': detection,
        'valeurs': _champs_pour_formulaire(detection),
        'fournisseurs': Supplier.objects.filter(
            company=company, is_active=True).order_by('name'),
        'nom_fichier': fichier.name,
        'page_title': 'Vérifier la facture détectée',
        'active_module': 'purchases',
    })


@login_required
def invoice_import_confirm(request):
    """Enregistre la facture telle que l'utilisateur l'a validée.

    On repart des champs du FORMULAIRE, pas de l'extraction : c'est tout
    l'objet de l'écran de relecture. Relire la détection ici ferait
    silencieusement perdre les corrections.
    """
    company = request.current_company
    if request.method != 'POST':
        return redirect('purchases:invoice_import')

    from datetime import date as _date
    from decimal import Decimal, InvalidOperation

    def texte(nom):
        return (request.POST.get(nom) or '').strip()

    def montant(nom):
        brut = texte(nom)
        if not brut:
            return Decimal('0')
        try:
            return Decimal(brut.replace(',', '.'))
        except InvalidOperation:
            return Decimal('0')

    def jour(nom):
        brut = texte(nom)
        if not brut:
            return None
        try:
            annee, mois, numero = (int(part) for part in brut.split('-'))
            return _date(annee, mois, numero)
        except (TypeError, ValueError):
            return None

    # Le fournisseur est borné à l'entreprise : la liste déroulante l'était
    # déjà, mais un identifiant forgé dans le POST rattacherait la facture
    # au fournisseur d'une autre société.
    fournisseur = Supplier.objects.filter(
        pk=texte('supplier') or 0, company=company).first()
    if fournisseur is None:
        messages.error(request, (
            'Choisissez le fournisseur émetteur. Une facture sans '
            'fournisseur ne peut pas être rapprochée ni payée.'))
        return redirect('purchases:invoice_import')

    emission = jour('date_emission')
    if emission is None:
        messages.error(request, (
            'La date de facture est obligatoire : elle détermine '
            'l\'exercice comptable et l\'échéance.'))
        return redirect('purchases:invoice_import')

    facture = SupplierInvoice(
        company=company,
        supplier=fournisseur,
        number=texte('numero')[:30],
        supplier_ref=texte('numero')[:50],
        issue_date=emission,
        due_date=jour('date_echeance'),
        total_ht=montant('total_ht'),
        total_tva=montant('total_tva'),
        total_ttc=montant('total_ttc'),
        notes=texte('notes'),
    )

    # Le PDF déposé à l'étape précédente est rattaché à la facture : c'est
    # la pièce justificative, et la perdre ici viderait l'import de son
    # intérêt.
    depose = request.session.pop('facture_importee', None)
    if depose and depose.get('chemin'):
        from django.core.files.base import ContentFile
        from django.core.files.storage import default_storage
        try:
            with default_storage.open(depose['chemin'], 'rb') as flux:
                facture.fichier.save(depose['nom'], ContentFile(flux.read()),
                                     save=False)
            default_storage.delete(depose['chemin'])
        except Exception:
            # Le fichier perdu ne doit pas empêcher d'enregistrer la
            # facture : les montants sont ce qui compte, et le PDF peut
            # être rattaché à nouveau.
            messages.warning(request, (
                'La facture est enregistrée, mais le PDF n\'a pas pu être '
                'rattaché. Vous pouvez le joindre depuis sa fiche.'))

    facture.save()
    messages.success(request, (
        f'Facture « {facture.number or "sans numéro"} » de '
        f'{fournisseur.name} enregistrée.'))
    return redirect('purchases:supplier_invoice_detail', pk=facture.pk)


@login_required
def invoice_redetect(request, pk):
    """Relit le PDF déjà rattaché à une facture existante.

    Utile quand l'extraction s'est améliorée, ou pour vérifier un montant
    contesté sans ouvrir le PDF à la main. **Ne modifie rien** : elle
    affiche ce que le détecteur lit aujourd'hui, à côté de ce qui est
    enregistré.
    """
    company = request.current_company
    facture = get_object_or_404(SupplierInvoice, pk=pk, company=company)

    if not facture.fichier:
        messages.warning(request, (
            'Aucun PDF n\'est rattaché à cette facture : il n\'y a rien à '
            'relire.'))
        return redirect('purchases:supplier_invoice_detail', pk=facture.pk)

    try:
        with facture.fichier.open('rb') as flux:
            detection = detecter_facture(flux.read(), company=company)
    except FileNotFoundError:
        messages.error(request, (
            'Le PDF est référencé mais introuvable sur le serveur : il a '
            'été perdu, pas supprimé.'))
        return redirect('purchases:supplier_invoice_detail', pk=facture.pk)
    except FactureIllisible as exc:
        messages.error(request, str(exc))
        return redirect('purchases:supplier_invoice_detail', pk=facture.pk)

    return render(request, 'purchases/invoice_redetect.html', {
        'facture': facture,
        'detection': detection,
        'page_title': f'Relecture — {facture.number or "facture"}',
        'active_module': 'purchases',
    })
