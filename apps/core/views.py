"""
apps/core/views.py — Dashboard global et vues core
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Count, Sum, Q
from django.utils import timezone
from datetime import timedelta

from .models import Company, AuditLog, Notification


@login_required
def dashboard(request):
    """Dashboard principal multi-sociétés."""
    company = request.current_company
    ctx = {'page_title': 'Tableau de bord'}

    if company:
        ctx.update(_get_company_stats(company, request.user))
    else:
        ctx.update(_get_global_stats(request.user))

    # Activité récente
    audit_qs = AuditLog.objects.select_related('user', 'company')
    if not request.user.is_superuser and company:
        audit_qs = audit_qs.filter(company=company)
    ctx['recent_activity'] = audit_qs.order_by('-created_at')[:10]

    return render(request, 'core/dashboard.html', ctx)


def _get_global_stats(user):
    """Stats globales pour superadmin sans entreprise sélectionnée."""
    companies = Company.objects.filter(is_active=True)
    return {
        'total_companies': companies.count(),
        'companies_by_sector': companies.values('sector').annotate(count=Count('id')).order_by('-count'),
        'show_global_view': True,
    }


def _get_company_stats(company, user):
    """Stats pour une entreprise spécifique."""
    stats = {'show_global_view': False}

    # Import lazy pour éviter les imports circulaires
    try:
        from apps.crm.models import Customer, Prospect
        stats['total_customers'] = Customer.objects.filter(company=company, is_active=True).count()
        stats['total_prospects'] = Prospect.objects.filter(company=company, is_active=True).count()
    except Exception:
        stats['total_customers'] = 0
        stats['total_prospects'] = 0

    try:
        from apps.sales.models import Invoice, Quote
        from decimal import Decimal
        import datetime

        current_month = timezone.now().replace(day=1)
        stats['monthly_revenue'] = Invoice.objects.filter(
            company=company,
            issue_date__gte=current_month,
            status__in=['sent', 'partial', 'paid'],
        ).aggregate(total=Sum('total_ttc'))['total'] or Decimal('0')

        stats['unpaid_invoices'] = Invoice.objects.filter(
            company=company,
            status__in=['sent', 'partial', 'overdue'],
        ).count()

        stats['pending_quotes'] = Quote.objects.filter(
            company=company,
            status__in=['draft', 'sent'],
        ).count()
    except Exception:
        stats['monthly_revenue'] = 0
        stats['unpaid_invoices'] = 0
        stats['pending_quotes'] = 0

    try:
        from apps.support.models import Ticket
        stats['open_tickets'] = Ticket.objects.filter(
            company=company,
            status__in=['open', 'in_progress'],
        ).count()
    except Exception:
        stats['open_tickets'] = 0

    try:
        from apps.inventory.models import Product
        from django.db.models import F
        stats['low_stock_products'] = Product.objects.filter(
            company=company,
            track_inventory=True,
            stock_quantity__lte=F('min_stock_quantity'),
        ).count()
    except Exception:
        stats['low_stock_products'] = 0

    return stats


@login_required
def switch_company(request, company_id):
    """Changer l'entreprise courante."""
    try:
        if request.user.is_superuser:
            company = Company.objects.get(pk=company_id, is_active=True)
        else:
            company = request.user.profile.companies.get(pk=company_id, is_active=True)

        request.session['current_company_id'] = company.pk
        messages.success(request, f'Vous travaillez maintenant sur : {company.name}')
    except Company.DoesNotExist:
        messages.error(request, 'Entreprise non trouvée ou accès refusé.')

    next_url = request.GET.get('next', 'core:dashboard')
    return redirect(next_url)


@login_required
def company_list(request):
    """Liste des entreprises accessibles."""
    if request.user.is_superuser:
        companies = Company.objects.filter(is_active=True).order_by('name')
    else:
        companies = request.user.profile.companies.filter(is_active=True).order_by('name')

    return render(request, 'core/company_list.html', {
        'companies': companies,
        'page_title': 'Mes entreprises',
    })


@login_required
def company_detail(request, pk):
    """Détail d'une entreprise."""
    if request.user.is_superuser:
        company = get_object_or_404(Company, pk=pk)
    else:
        company = get_object_or_404(request.user.profile.companies, pk=pk)

    return render(request, 'core/company_detail.html', {
        'company': company,
        'page_title': company.name,
    })


@login_required
def company_create(request):
    """Créer une entreprise (superadmin seulement)."""
    if not request.user.is_superuser:
        messages.error(request, 'Accès refusé.')
        return redirect('core:dashboard')

    from .forms import CompanyForm
    form = CompanyForm(request.POST or None, request.FILES or None)

    if form.is_valid():
        company = form.save()
        AuditLog.objects.create(
            user=request.user,
            company=company,
            action='create',
            model_name='Company',
            object_id=str(company.pk),
            object_repr=str(company),
            description=f'Création entreprise : {company.name}',
        )
        messages.success(request, f'Entreprise "{company.name}" créée avec succès.')
        return redirect('core:company_detail', pk=company.pk)

    return render(request, 'core/company_form.html', {
        'form': form,
        'page_title': 'Nouvelle entreprise',
    })


@login_required
def company_edit(request, pk):
    """Modifier une entreprise."""
    if request.user.is_superuser:
        company = get_object_or_404(Company, pk=pk)
    else:
        company = get_object_or_404(request.user.profile.companies, pk=pk)
        profile = request.user.profile
        if profile.role not in ['admin', 'superadmin']:
            messages.error(request, 'Accès refusé.')
            return redirect('core:dashboard')

    from .forms import CompanyForm
    form = CompanyForm(request.POST or None, request.FILES or None, instance=company)

    if form.is_valid():
        form.save()
        messages.success(request, 'Entreprise modifiée avec succès.')
        return redirect('core:company_detail', pk=company.pk)

    return render(request, 'core/company_form.html', {
        'form': form,
        'company': company,
        'page_title': f'Modifier — {company.name}',
    })


# ─── Gestion bases de données entreprises ─────────────────────────────────────

@login_required
def company_database(request, pk):
    """Page de gestion de la base de données d'une entreprise."""
    if not request.user.is_superuser:
        messages.error(request, 'Accès refusé. Réservé aux administrateurs.')
        return redirect('core:company_list')

    company = get_object_or_404(Company, pk=pk)

    try:
        db_record = company.company_database
    except Exception:
        db_record = None

    logs = AuditLog.objects.filter(
        model_name='CompanyDatabase', object_repr__contains=company.database_name or company.name
    ).order_by('-created_at')[:20]

    return render(request, 'core/company_database.html', {
        'company': company,
        'db_record': db_record,
        'audit_logs': logs,
        'page_title': f'Base de données — {company.name}',
    })


@login_required
def company_database_create(request, pk):
    """Crée la base de données MySQL de l'entreprise."""
    if not request.user.is_superuser:
        messages.error(request, 'Accès refusé.')
        return redirect('core:company_list')

    company = get_object_or_404(Company, pk=pk)
    if request.method == 'POST':
        from .company_database_service import create_company_database
        success, msg = create_company_database(company)
        if success:
            messages.success(request, msg)
        else:
            messages.error(request, msg)
    return redirect('core:company_database', pk=pk)


@login_required
def company_database_test(request, pk):
    """Teste la connexion à la base de données de l'entreprise."""
    if not request.user.is_superuser:
        return JsonResponse({'ok': False, 'message': 'Accès refusé.'})

    company = get_object_or_404(Company, pk=pk)
    from .company_database_service import test_company_database_connection
    success, msg = test_company_database_connection(company)
    return JsonResponse({'ok': success, 'message': msg})


@login_required
def company_database_migrate(request, pk):
    """Lance les migrations sur la base de données de l'entreprise."""
    if not request.user.is_superuser:
        messages.error(request, 'Accès refusé.')
        return redirect('core:company_list')

    company = get_object_or_404(Company, pk=pk)
    if request.method == 'POST':
        from .company_database_service import run_company_migrations
        success, msg = run_company_migrations(company)
        if success:
            messages.success(request, 'Migrations appliquées avec succès.')
        else:
            messages.error(request, msg)
    return redirect('core:company_database', pk=pk)


@login_required
def company_database_backup(request, pk):
    """Sauvegarde la base de données de l'entreprise."""
    if not request.user.is_superuser:
        messages.error(request, 'Accès refusé.')
        return redirect('core:company_list')

    company = get_object_or_404(Company, pk=pk)
    if request.method == 'POST':
        from .company_database_service import backup_company_database
        success, msg = backup_company_database(company)
        if success:
            messages.success(request, msg)
        else:
            messages.error(request, msg)
    return redirect('core:company_database', pk=pk)


@login_required
def company_database_archive(request, pk):
    """Archive la base de données de l'entreprise."""
    if not request.user.is_superuser:
        messages.error(request, 'Accès refusé.')
        return redirect('core:company_list')

    company = get_object_or_404(Company, pk=pk)
    if request.method == 'POST':
        from .company_database_service import archive_company_database
        success, msg = archive_company_database(company)
        if success:
            messages.success(request, msg)
        else:
            messages.error(request, msg)
    return redirect('core:company_database', pk=pk)


@login_required
def company_database_delete(request, pk):
    """Suppression définitive et sécurisée de la base de données."""
    if not request.user.is_superuser:
        messages.error(request, 'Accès refusé.')
        return redirect('core:company_list')

    company = get_object_or_404(Company, pk=pk)

    if request.method == 'POST':
        confirmation = request.POST.get('confirmation_text', '')
        from .company_database_service import delete_company_database
        success, msg = delete_company_database(company, confirmation, request.user)
        if success:
            messages.success(request, msg)
            return redirect('core:company_list')
        else:
            messages.error(request, msg)

    from .company_database_service import DELETION_CONFIRMATION_TEXT
    return render(request, 'core/company_database_delete.html', {
        'company': company,
        'confirmation_text': DELETION_CONFIRMATION_TEXT,
        'page_title': f'Suppression base — {company.name}',
    })


@login_required
def notifications_read(request, pk):
    """Marquer une notification comme lue."""
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.is_read = True
    notification.save()
    return JsonResponse({'status': 'ok'})


@login_required
def notifications_read_all(request):
    """Marquer toutes les notifications comme lues."""
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return JsonResponse({'status': 'ok'})


@login_required
def notifications_list(request):
    """Liste complète des notifications de l'utilisateur."""
    from django.core.paginator import Paginator
    filter_type = request.GET.get('filter', 'all')
    qs = Notification.objects.filter(user=request.user)
    if filter_type == 'unread':
        qs = qs.filter(is_read=False)
    elif filter_type == 'read':
        qs = qs.filter(is_read=True)
    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'core/notifications.html', {
        'page_obj': page_obj,
        'filter_type': filter_type,
        'page_title': 'Notifications',
        'active_module': 'dashboard',
    })
