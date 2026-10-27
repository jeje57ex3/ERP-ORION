from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from apps.domain_manager.forms import CustomDomainForm
from apps.domain_manager.models import CustomDomain
from apps.domain_manager.services import create_custom_domain, make_primary_domain, verify_custom_domain
# « require_active_company » etait importe ici et n'existe nulle part dans
# le projet : apps/private_saas/decorators.py n'expose que
# super_admin_required et require_company_module. L'application n'etant pas
# declaree, cet import n'avait jamais ete execute -- il levait un
# ImportError des la premiere tentative de chargement. Il n'etait de plus
# utilise par aucune vue de ce fichier, d'ou son retrait plutot que
# l'invention d'un decorateur que rien n'appelle.
from apps.private_saas.decorators import require_company_module


@login_required
@require_company_module('domains')
def domain_list_view(request):
    company = getattr(request, 'current_company', None)
    domains = CustomDomain.objects.filter(company=company)
    return render(request, 'domain_manager/domain_list.html', {
        'page_title': 'Domaines connectés',
        'page_subtitle': 'Gérez les domaines personnalisés rattachés à cette entreprise.',
        'domains': domains,
    })


@login_required
@require_company_module('domains')
def domain_create_view(request):
    company = getattr(request, 'current_company', None)

    if request.method == 'POST':
        form = CustomDomainForm(request.POST)
        if form.is_valid():
            domain = create_custom_domain(
                company=company,
                user=request.user,
                domain=form.cleaned_data['domain'],
                brand_key=form.cleaned_data.get('brand_key', ''),
                target_type=form.cleaned_data.get('target_type', 'shop'),
            )
            messages.success(request, 'Domaine ajouté. Configurez maintenant les DNS.')
            return redirect('domain_manager:detail', pk=domain.id)
    else:
        form = CustomDomainForm()

    return render(request, 'domain_manager/domain_form.html', {
        'page_title': 'Ajouter un domaine',
        'page_subtitle': 'Entrez le domaine à connecter à Orion.',
        'form': form,
    })


@login_required
@require_company_module('domains')
def domain_detail_view(request, pk):
    company = getattr(request, 'current_company', None)
    domain = get_object_or_404(CustomDomain, pk=pk, company=company)
    return render(request, 'domain_manager/domain_detail.html', {
        'page_title': domain.domain,
        'domain': domain,
    })


@login_required
@require_company_module('domains')
def domain_verify_view(request, pk):
    company = getattr(request, 'current_company', None)
    domain = get_object_or_404(CustomDomain, pk=pk, company=company)

    result = verify_custom_domain(domain)
    dns_result = result.get('dns', {})

    if dns_result.get('manual'):
        messages.info(request, 'Vérification automatique non disponible. Configurez les DNS manuellement puis revenez vérifier.')
    elif domain.status in ['dns_valid', 'active']:
        messages.success(request, 'DNS valides. Domaine vérifié avec succès.')
    else:
        messages.warning(request, domain.last_error or 'DNS pas encore propagés. Réessayez dans quelques minutes.')

    return redirect('domain_manager:detail', pk=domain.id)


@login_required
@require_company_module('domains')
def domain_make_primary_view(request, pk):
    company = getattr(request, 'current_company', None)
    domain = get_object_or_404(CustomDomain, pk=pk, company=company)

    if not domain.dns_is_valid:
        messages.error(request, 'Le domaine doit avoir des DNS valides avant de devenir principal.')
        return redirect('domain_manager:detail', pk=domain.id)

    make_primary_domain(domain)
    messages.success(request, f'« {domain.domain} » est maintenant le domaine principal.')
    return redirect('domain_manager:detail', pk=domain.id)


@login_required
@require_company_module('domains')
def domain_delete_view(request, pk):
    company = getattr(request, 'current_company', None)
    domain = get_object_or_404(CustomDomain, pk=pk, company=company)

    if request.method == 'POST':
        name = domain.domain
        domain.delete()
        messages.success(request, f'Domaine « {name} » supprimé.')
        return redirect('domain_manager:list')

    return render(request, 'domain_manager/domain_confirm_delete.html', {
        'page_title': f'Supprimer {domain.domain}',
        'domain': domain,
    })
