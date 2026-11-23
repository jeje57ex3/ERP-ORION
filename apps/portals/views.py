from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages

@login_required
def index(request):
    from .models import ClientPortalAccount, ClientPortalSignupRequest

    company = request.current_company
    pending_signups = 0
    total_accounts = 0
    active_accounts = 0
    if company:
        pending_signups = ClientPortalSignupRequest.objects.filter(
            company=company,
            status__in=[
                ClientPortalSignupRequest.STATUS_PENDING_EMAIL,
                ClientPortalSignupRequest.STATUS_PENDING_APPROVAL,
            ],
        ).count()
        accounts = ClientPortalAccount.objects.filter(company=company)
        total_accounts = accounts.count()
        active_accounts = accounts.filter(is_active=True).count()

    return render(request, 'portals/index.html', {
        'page_title': 'Portails',
        'company': company,
        'pending_signups': pending_signups,
        'total_accounts': total_accounts,
        'active_accounts': active_accounts,
    })


def _is_hr_admin(request):
    return request.user.is_superuser or (
        hasattr(request.user, 'profile') and request.user.profile.role in ('admin', 'superadmin')
    )


@login_required
def create_customer_portal_account(request, customer_id):
    from apps.crm.models import Customer
    from .services import signup_service

    company = request.current_company
    customer = get_object_or_404(Customer, pk=customer_id, company=company)

    if not _is_hr_admin(request):
        messages.error(request, 'Action réservée aux administrateurs.')
        return redirect('crm:customer_detail', pk=customer_id)

    if request.method == 'POST':
        try:
            # LA LANGUE VIENT DU SELECTEUR DE LA FICHE CLIENT. Elle gouverne
            # l'interface de l'espace client ET le courriel qu'il recoit :
            # un seul champ pour les deux, sinon ils se contrediraient un
            # jour, et un client qui lit son courriel en portugais puis
            # trouve une interface en francais y verrait une erreur.
            #
            # Vide -> la langue du compte n'est pas touchee. C'est ce qui
            # permet de renvoyer un code sans reinitialiser la langue.
            account, created = signup_service.create_portal_account_for_customer(
                customer, created_by=request.user,
                base_url=request.build_absolute_uri('/').rstrip('/'),
                langue=(request.POST.get('langue') or '').strip(),
            )
            # L'ENVOI EST RAPPORTÉ TEL QU'IL S'EST PASSÉ.
            #
            # Le message disait « Un email d'activation a été envoyé » quoi
            # qu'il arrive, parce que `signup_service._send_email` passe
            # `fail_silently=True` et rattrape toute exception : l'appelant
            # ne pouvait pas savoir. `creer_et_envoyer` rend désormais
            # (envoyé, motif), posé sur `account.envoi_du_code`.
            envoye, motif = getattr(account, 'envoi_du_code', (True, ''))

            if created and envoye:
                messages.success(request, f'Compte espace client créé pour {account.full_name}. Un code provisoire a été envoyé à {account.email} ; il devra le changer à sa première connexion.')
            elif created:
                messages.error(request, f'Compte créé pour {account.full_name}, mais le code provisoire n\'a PAS pu être envoyé à {account.email} ({motif}). Personne ne peut donc s\'y connecter : corrigez les réglages de courriel dans /orion-admin/courriels/, puis relancez cette action pour renvoyer un code.')
            elif envoye:
                messages.success(request, f'Un compte existait déjà pour {account.email} : un NOUVEAU code provisoire vient d\'être envoyé. Le précédent ne vaut plus.')
            else:
                messages.error(request, f'Un compte existe déjà pour {account.email}, et le nouveau code n\'a PAS pu être envoyé ({motif}). L\'ancien ne vaut plus non plus : le compte est fermé jusqu\'au prochain envoi réussi.')
        except ValueError as exc:
            messages.error(request, str(exc))

    return redirect('crm:customer_detail', pk=customer_id)


