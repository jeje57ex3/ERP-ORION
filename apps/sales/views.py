"""apps/sales/views.py — Vues CRUD Ventes"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum
from django.utils import timezone
from .models import Quote, SalesOrder, Invoice
from .forms import QuoteForm, SalesOrderForm, InvoiceForm
from apps.crm.models import Customer


@login_required
def index(request):
    return redirect('sales:quote_list')


# ─────────────────────────────────────────────────────────────
# DEVIS
# ─────────────────────────────────────────────────────────────

@login_required
def quote_list(request):
    company = request.current_company
    qs = Quote.objects.filter(company=company).select_related('customer', 'salesperson')

    q = request.GET.get('q', '')
    status = request.GET.get('status', '')

    if q:
        qs = qs.filter(Q(number__icontains=q) | Q(customer__name__icontains=q) | Q(subject__icontains=q))
    if status:
        qs = qs.filter(status=status)

    total_ht = qs.aggregate(t=Sum('total_ht'))['t'] or 0
    count_draft = Quote.objects.filter(company=company, status='draft').count()
    count_sent = Quote.objects.filter(company=company, status='sent').count()

    return render(request, 'sales/quote_list.html', {
        'page_title': 'Devis',
        'quotes': qs,
        'q': q,
        'status': status,
        'status_choices': Quote.STATUS_CHOICES,
        'total_ht': total_ht,
        'count_draft': count_draft,
        'count_sent': count_sent,
    })


@login_required
def quote_detail(request, pk):
    company = request.current_company
    quote = get_object_or_404(Quote, pk=pk, company=company)
    lines = quote.lines.all()
    # select_related sur l'article : sans lui, une requete par ligne part
    # chercher le nom du materiau pour l'afficher.
    detail = quote.detail_lines.select_related('material')
    return render(request, 'sales/quote_detail.html', {
        'page_title': f'Devis {quote.number or pk}',
        'quote': quote,
        'lines': lines,
        'detail_materiels': [d for d in detail if d.nature == 'materiel'],
        'detail_fournitures': [d for d in detail if d.nature == 'fourniture'],
        'detail_actions': [d for d in detail if d.nature == 'action'],
    })


@login_required
def quote_create(request):
    from django.db import transaction

    from apps.sales.forms import QuoteDetailLineFormSet

    company = request.current_company
    clients = Customer.objects.filter(company=company, is_active=True)

    if request.method == 'POST':
        form = QuoteForm(request.POST)
        # Le client doit etre borne a l'entreprise A LA VALIDATION aussi, et
        # pas seulement a l'affichage : sans cette ligne, un identifiant forge
        # dans la requete designait le client d'une AUTRE entreprise, et le
        # devis lui etait rattache. C'est la regle centrale de cet ERP.
        form.fields['customer'].queryset = clients

        # Le detail -- materiaux, fournitures, actions -- se saisit DES la
        # creation. Le formset est construit sans instance : il n'y a pas
        # encore de devis auquel rattacher ses lignes. Elles le sont juste
        # apres, en lui donnant l'instance enregistree : save_new() relit
        # `self.instance` au moment d'ecrire, pas a la construction.
        detail = QuoteDetailLineFormSet(
            request.POST, form_kwargs={'company': company})

        if form.is_valid() and detail.is_valid():
            # Tout ou rien : un devis enregistre dont le detail echouerait
            # ensuite partirait au client ampute de ce qui justifie son prix.
            with transaction.atomic():
                quote = form.save(commit=False)
                quote.company = company
                quote.created_by = request.user
                # Numerotation atomique (SELECT FOR UPDATE), et non un
                # comptage. « count() + 1 » donnait le meme numero a deux
                # devis crees en meme temps, et recyclait un numero deja
                # emis apres une suppression -- sur un document comptable,
                # c'est inacceptable.
                from apps.core.numbering import next_number
                quote.number = next_number(company, 'quote') or ''
                quote.save()

                detail.instance = quote
                detail.save()

            messages.success(request, f'Devis {quote.number} créé avec succès.')
            return redirect('sales:quote_detail', pk=quote.pk)
    else:
        form = QuoteForm()
        form.fields['customer'].queryset = clients
        customer_pk = request.GET.get('customer')
        if customer_pk:
            form.fields['customer'].initial = customer_pk
        detail = QuoteDetailLineFormSet(form_kwargs={'company': company})

    return render(request, 'sales/quote_form.html', {
        'page_title': 'Nouveau devis',
        'form': form,
        'detail': detail,
        'action': 'create',
    })


@login_required
def quote_edit(request, pk):
    from apps.sales.forms import QuoteDetailLineFormSet

    company = request.current_company
    quote = get_object_or_404(Quote, pk=pk, company=company)

    # Le detail des materiels et fournitures s'edite ICI, par un formset :
    # on ajoute, modifie et supprime en un seul envoi. Des vues separees
    # demanderaient trois chemins pour un tableau que l'on remplit d'un
    # trait.
    clients = Customer.objects.filter(company=company, is_active=True)

    if request.method == 'POST':
        form = QuoteForm(request.POST, instance=quote)
        # Borne A LA VALIDATION, et pas seulement a l'affichage. Cette ligne
        # manquait ici alors qu'elle existait a la creation : un identifiant
        # forge rattachait le devis au client d'une AUTRE entreprise.
        form.fields['customer'].queryset = clients
        detail = QuoteDetailLineFormSet(
            request.POST, instance=quote, form_kwargs={'company': company})
        if form.is_valid() and detail.is_valid():
            form.save()
            detail.save()
            messages.success(request, 'Devis mis à jour.')
            return redirect('sales:quote_detail', pk=quote.pk)
    else:
        form = QuoteForm(instance=quote)
        form.fields['customer'].queryset = clients
        detail = QuoteDetailLineFormSet(
            instance=quote, form_kwargs={'company': company})

    return render(request, 'sales/quote_form.html', {
        'page_title': f'Modifier devis {quote.number}',
        'form': form,
        'detail': detail,
        'quote': quote,
        'action': 'edit',
    })


@login_required
def quote_delete(request, pk):
    company = request.current_company
    quote = get_object_or_404(Quote, pk=pk, company=company)
    if request.method == 'POST':
        num = quote.number
        quote.delete()
        messages.success(request, f'Devis {num} supprimé.')
        return redirect('sales:quote_list')
    return render(request, 'sales/quote_confirm_delete.html', {
        'page_title': 'Supprimer le devis',
        'quote': quote,
    })


@login_required
def quote_send(request, pk):
    company = request.current_company
    quote = get_object_or_404(Quote, pk=pk, company=company)
    quote.status = 'sent'
    quote.save()
    messages.success(request, f'Devis {quote.number} marqué comme envoyé.')
    return redirect('sales:quote_detail', pk=quote.pk)


@login_required
def quote_accept(request, pk):
    company = request.current_company
    quote = get_object_or_404(Quote, pk=pk, company=company)
    quote.status = 'accepted'
    quote.save()
    messages.success(request, f'Devis {quote.number} accepté.')
    return redirect('sales:quote_detail', pk=quote.pk)


@login_required
def quote_convert_order(request, pk):
    """Convertit un devis en commande."""
    company = request.current_company
    quote = get_object_or_404(Quote, pk=pk, company=company)
    last = SalesOrder.objects.filter(company=company).count()
    order = SalesOrder.objects.create(
        company=company,
        customer=quote.customer,
        quote=quote,
        number=f'CMD-{str(last + 1).zfill(4)}',
        total_ht=quote.total_ht,
        total_ttc=quote.total_ttc,
        salesperson=quote.salesperson,
    )
    quote.status = 'accepted'
    quote.save()
    messages.success(request, f'Commande {order.number} créée depuis le devis.')
    return redirect('sales:order_detail', pk=order.pk)


# ─────────────────────────────────────────────────────────────
# COMMANDES
# ─────────────────────────────────────────────────────────────

@login_required
def order_list(request):
    company = request.current_company
    qs = SalesOrder.objects.filter(company=company).select_related('customer', 'salesperson')

    q = request.GET.get('q', '')
    status = request.GET.get('status', '')

    if q:
        qs = qs.filter(Q(number__icontains=q) | Q(customer__name__icontains=q))
    if status:
        qs = qs.filter(status=status)

    return render(request, 'sales/order_list.html', {
        'page_title': 'Commandes clients',
        'orders': qs,
        'q': q,
        'status': status,
        'status_choices': SalesOrder.STATUS_CHOICES,
    })


@login_required
def order_detail(request, pk):
    company = request.current_company
    order = get_object_or_404(SalesOrder, pk=pk, company=company)
    return render(request, 'sales/order_detail.html', {
        'page_title': f'Commande {order.number or pk}',
        'order': order,
    })


@login_required
def order_create(request):
    company = request.current_company
    if request.method == 'POST':
        form = SalesOrderForm(request.POST)
        if form.is_valid():
            order = form.save(commit=False)
            order.company = company
            last = SalesOrder.objects.filter(company=company).count()
            order.number = f'CMD-{str(last + 1).zfill(4)}'
            order.save()
            messages.success(request, f'Commande {order.number} créée.')
            return redirect('sales:order_detail', pk=order.pk)
    else:
        form = SalesOrderForm()
        form.fields['customer'].queryset = Customer.objects.filter(company=company, is_active=True)

    return render(request, 'sales/order_form.html', {
        'page_title': 'Nouvelle commande',
        'form': form,
        'action': 'create',
    })


@login_required
def order_update_status(request, pk, new_status):
    company = request.current_company
    order = get_object_or_404(SalesOrder, pk=pk, company=company)
    valid = dict(SalesOrder.STATUS_CHOICES)
    if new_status in valid:
        order.status = new_status
        order.save()
        messages.success(request, f'Commande {order.number} : statut mis à jour → {valid[new_status]}.')
    return redirect('sales:order_detail', pk=order.pk)


# ─────────────────────────────────────────────────────────────
# FACTURES
# ─────────────────────────────────────────────────────────────

@login_required
def invoice_list(request):
    company = request.current_company
    qs = Invoice.objects.filter(company=company).select_related('customer', 'salesperson')

    q = request.GET.get('q', '')
    status = request.GET.get('status', '')

    if q:
        qs = qs.filter(Q(number__icontains=q) | Q(customer__name__icontains=q) | Q(subject__icontains=q))
    if status:
        qs = qs.filter(status=status)

    total_ht = qs.aggregate(t=Sum('total_ht'))['t'] or 0
    total_ttc = qs.aggregate(t=Sum('total_ttc'))['t'] or 0
    total_paid = qs.aggregate(t=Sum('amount_paid'))['t'] or 0

    return render(request, 'sales/invoice_list.html', {
        'page_title': 'Factures',
        'invoices': qs,
        'q': q,
        'status': status,
        'status_choices': Invoice.STATUS_CHOICES,
        'total_ht': total_ht,
        'total_ttc': total_ttc,
        'total_paid': total_paid,
    })


@login_required
def invoice_detail(request, pk):
    company = request.current_company
    invoice = get_object_or_404(Invoice, pk=pk, company=company)
    lines = invoice.lines.all()

    # Les mentions légales portugaises, si la facture a été signée.
    #
    # Elles figurent SUR LE DOCUMENT, et pas seulement dans l'écran de
    # conformité : l'ATCUD, le code QR et la mention « Processado por
    # programa certificado » sont des mentions obligatoires de la facture
    # elle-même. Les tenir à l'écart dans un module d'administration
    # donnerait un logiciel conforme dont les factures ne le sont pas.
    from apps.fiscal_pt.facturation import document_pour, rectifications_de
    from apps.fiscal_pt.models import ParametresFiscauxPT

    document_fiscal = document_pour(invoice)
    # Les avoirs deja emis. Une facture rectifiee qui ne le dirait pas se
    # lirait comme une facture due : c'est l'information qui manque le
    # plus souvent sur un ecran de facture.
    rectifications = list(rectifications_de(invoice)) if document_fiscal else []
    mention_legale = ''
    mentions_d_exoneration = []
    if document_fiscal is not None:
        numero = (ParametresFiscauxPT.de(company).numero_de_certificat
                  or '0')
        mention_legale = document_fiscal.mention_legale(numero)

        # Les mentions d'exoneration, DISTINCTES et dans l'ordre.
        #
        # Elles doivent figurer sur la facture : la « menção que consta da
        # fatura » de la table de l'AT n'est pas une etiquette d'interface,
        # c'est une mention legale. Cinq lignes au meme motif ne doivent
        # pourtant l'afficher qu'une fois.
        for ligne_figee in document_fiscal.lignes:
            # La mention de la FACTURE, pas celle du fichier : elles ne
            # different que pour M15, et c'est celle-ci qui a valeur
            # legale sur le document imprime.
            motif = (ligne_figee.get('mention_facture')
                     or ligne_figee.get('motif_exoneration') or '')
            code = ligne_figee.get('code_exoneration') or ''
            if motif and (code, motif) not in mentions_d_exoneration:
                mentions_d_exoneration.append((code, motif))

    return render(request, 'sales/invoice_detail.html', {
        'page_title': f'Facture {invoice.number or pk}',
        'invoice': invoice,
        'lines': lines,
        'document_fiscal': document_fiscal,
        'mention_legale': mention_legale,
        'mentions_d_exoneration': mentions_d_exoneration,
        'rectifications': rectifications,
    })


@login_required
def invoice_create(request):
    from django.db import transaction

    from apps.sales.forms import InvoiceLineFormSet

    company = request.current_company
    clients = Customer.objects.filter(company=company, is_active=True)

    if request.method == 'POST':
        form = InvoiceForm(request.POST)

        # Le client doit etre borne a l'entreprise A LA VALIDATION aussi, et
        # pas seulement a l'affichage. Sans cette ligne, un identifiant forge
        # dans la requete designait le client d'une AUTRE entreprise, et la
        # facture lui etait rattachee. La vue des devis, juste au-dessus,
        # appelle cela « la regle centrale de cet ERP » -- elle manquait ici.
        form.fields['customer'].queryset = clients

        lignes = InvoiceLineFormSet(request.POST)

        if form.is_valid() and lignes.is_valid():
            # Tout ou rien : une facture enregistree dont les lignes
            # echoueraient ensuite serait une facture a zero euro, et son
            # ecran afficherait fidelement une liste vide.
            with transaction.atomic():
                invoice = form.save(commit=False)
                invoice.company = company
                invoice.created_by = request.user
                last = Invoice.objects.filter(company=company).count()
                prefix = getattr(company, 'invoice_prefix', 'FAC') or 'FAC'
                invoice.number = f'{prefix}-{str(last + 1).zfill(4)}'
                invoice.save()

                lignes.instance = invoice
                lignes.save()
                _recalculer_les_totaux(invoice)

            messages.success(request, f'Facture {invoice.number} créée.')
            return redirect('sales:invoice_detail', pk=invoice.pk)
    else:
        form = InvoiceForm()
        form.fields['customer'].queryset = clients
        customer_pk = request.GET.get('customer')
        if customer_pk:
            form.fields['customer'].initial = customer_pk
        lignes = InvoiceLineFormSet()

    return render(request, 'sales/invoice_form.html', {
        'page_title': 'Nouvelle facture',
        'lignes': lignes,
        'form': form,
        'action': 'create',
    })


@login_required
def invoice_edit(request, pk):
    from django.db import transaction

    from apps.sales.forms import InvoiceLineFormSet

    company = request.current_company
    invoice = get_object_or_404(Invoice, pk=pk, company=company)
    clients = Customer.objects.filter(company=company, is_active=True)

    if request.method == 'POST':
        form = InvoiceForm(request.POST, instance=invoice)
        form.fields['customer'].queryset = clients
        lignes = InvoiceLineFormSet(request.POST, instance=invoice)

        if form.is_valid() and lignes.is_valid():
            with transaction.atomic():
                form.save()
                lignes.save()
                _recalculer_les_totaux(invoice)

            messages.success(request, 'Facture mise à jour.')
            return redirect('sales:invoice_detail', pk=invoice.pk)
    else:
        form = InvoiceForm(instance=invoice)
        form.fields['customer'].queryset = clients
        lignes = InvoiceLineFormSet(instance=invoice)

    return render(request, 'sales/invoice_form.html', {
        'page_title': f'Modifier facture {invoice.number}',
        'form': form,
        'lignes': lignes,
        'invoice': invoice,
        'action': 'edit',
    })


def _recalculer_les_totaux(invoice):
    """Recalcule les totaux de la facture depuis ses lignes.

    POURQUOI DEPUIS LES LIGNES, ET A CHAQUE FOIS

    Les totaux etaient a zero sur toutes les factures, puisque rien ne
    creait de lignes. Maintenant qu'il y en a, les tenir a part dans un
    cumul mis a jour « au passage » finirait par deriver d'un centime apres
    une suppression de ligne. Au Portugal, ce centime est signe : la preuve
    cesserait de correspondre au document.

    `InvoiceLine.save()` calcule deja `total_ht` et `total_tva` par ligne ;
    on ne fait donc que les sommer, et on ecrit avec `update()` pour ne pas
    repasser par la garde d'immuabilite de `Invoice.save()` -- un
    recalcul de totaux n'est pas une modification de facture au sens ou
    cette garde l'entend.
    """
    from decimal import Decimal

    from django.db.models import Sum

    cumuls = invoice.lines.aggregate(
        ht=Sum('total_ht'), tva=Sum('total_tva'))
    total_ht = cumuls['ht'] or Decimal('0')
    total_tva = cumuls['tva'] or Decimal('0')

    Invoice.objects.filter(pk=invoice.pk).update(
        total_ht=total_ht,
        total_tva=total_tva,
        total_ttc=total_ht + total_tva,
    )
    invoice.refresh_from_db()


@login_required
def invoice_delete(request, pk):
    company = request.current_company
    invoice = get_object_or_404(Invoice, pk=pk, company=company)
    if request.method == 'POST':
        num = invoice.number
        invoice.delete()
        messages.success(request, f'Facture {num} supprimée.')
        return redirect('sales:invoice_list')
    return render(request, 'sales/invoice_confirm_delete.html', {
        'page_title': 'Supprimer la facture',
        'invoice': invoice,
    })


@login_required
def invoice_mark_paid(request, pk):
    company = request.current_company
    invoice = get_object_or_404(Invoice, pk=pk, company=company)
    invoice.status = 'paid'
    invoice.amount_paid = invoice.total_ttc
    invoice.save()
    messages.success(request, f'Facture {invoice.number} marquée comme payée.')
    return redirect('sales:invoice_detail', pk=invoice.pk)


@login_required
def invoice_send(request, pk):
    """Marque une facture comme envoyée — et la signe si la loi l'exige.

    L'ORDRE DES DEUX OPÉRATIONS EST LE POINT IMPORTANT.

    La signature est produite AVANT le changement de statut, et dans la
    même transaction. Si elle échoue — clé absente, série non déclarée,
    taux étranger sur une ligne — la facture reste en brouillon et rien
    n'est remis au client.

    L'inverse paraît plus accommodant et serait bien pire : la facture
    partirait sans preuve, l'anomalie ne se verrait nulle part, et des
    mois de facturation sortiraient hors la loi avant que quiconque s'en
    aperçoive.

    Hors conformité portugaise, `ConformiteInactive` est levée et le
    comportement reste exactement celui d'avant.
    """
    from django.db import transaction

    from apps.fiscal_pt import facturation

    company = request.current_company
    invoice = get_object_or_404(Invoice, pk=pk, company=company)

    # On interroge l'état AVANT d'ouvrir la transaction.
    #
    # Appeler l'émission pour la voir refuser créerait une ligne de
    # paramètres aussitôt annulée par l'exception — inoffensif, et inutile
    # à chaque envoi de facture d'une installation qui ne facture pas au
    # Portugal.
    document = None
    if not facturation.est_active(company):
        invoice.status = 'sent'
        invoice.save()
    else:
        try:
            with transaction.atomic():
                document = facturation.emettre_pour_facture(invoice)
                invoice.status = 'sent'
                invoice.save()
        except Exception as exc:
            messages.error(
                request,
                f'Facture non envoyée : la signature légale a échoué — {exc}')
            return redirect('sales:invoice_detail', pk=invoice.pk)

    if document is not None:
        messages.success(
            request,
            f'Facture {document.numero} envoyée et signée '
            f'(ATCUD {document.atcud}).')
    else:
        messages.success(
            request, f'Facture {invoice.number} marquée comme envoyée.')
    return redirect('sales:invoice_detail', pk=invoice.pk)
