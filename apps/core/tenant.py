"""
apps/core/tenant.py — Utilitaires multi-tenant Orion ERP

Fonctions de bas niveau pour gérer le contexte d'entreprise active.
Ces fonctions sont utilisées par le middleware, les vues et les services.

Exemples :
    from apps.core.tenant import get_active_company, require_company, run_in_company_context
"""
from apps.core.exceptions import CompanyAccessDenied


# ─── Accès à l'entreprise active ─────────────────────────────────────────────

def get_active_company(request):
    """
    Retourne l'instance Company active pour la requête courante, ou None.
    L'entreprise est injectée par CompanyMiddleware dans request.current_company.
    """
    return getattr(request, 'current_company', None)


def set_active_company(request, company):
    """
    Définit l'entreprise active pour la requête en cours.
    Met à jour request.current_company et la session utilisateur.
    """
    request.current_company = company
    if company is not None:
        request.session['current_company_id'] = company.pk
        try:
            profile = request.user.profile
            profile.current_company = company
            profile.save(update_fields=['current_company'])
        except Exception:
            pass
    else:
        request.session.pop('current_company_id', None)


# ─── Vérification d'accès ─────────────────────────────────────────────────────

def user_has_company_access(user, company) -> bool:
    """
    Vérifie si un utilisateur a accès à une entreprise.

    Retourne True si :
    - L'utilisateur est superuser (accès total)
    - L'entreprise fait partie des entreprises actives de son profil

    Ne lève pas d'exception : retourne un booléen.
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if company is None:
        return False
    try:
        return user.profile.companies.filter(pk=company.pk, is_active=True).exists()
    except Exception:
        return False


def require_company(request):
    """
    Vérifie qu'une entreprise active est définie sur la requête.
    Lève CompanyAccessDenied si aucune entreprise n'est disponible.

    Utilisation dans les vues fonctionnelles :
        def ma_vue(request):
            require_company(request)
            ...
    """
    company = get_active_company(request)
    if company is None:
        raise CompanyAccessDenied(
            "Aucune entreprise active. Veuillez sélectionner une entreprise."
        )
    return company


# ─── Alias de base de données ─────────────────────────────────────────────────

def get_company_database_alias(company) -> str:
    """
    Retourne l'alias de base de données Django pour une entreprise.

    Si la base dédiée de l'entreprise est créée, retourne 'company_{pk}'.
    Sinon, retourne 'default' (base centrale partagée).
    """
    if company is None:
        return 'default'
    if getattr(company, 'database_created', False):
        return f'company_{company.pk}'
    return 'default'


# ─── Exécution dans un contexte d'entreprise ─────────────────────────────────

def run_in_company_context(company, func, *args, **kwargs):
    """
    Exécute func(*args, **kwargs) en activant le contexte DB de l'entreprise.

    Le routage DB thread-local est défini avant l'appel et restauré
    à la valeur précédente après (même en cas d'exception).

    Utilisation :
        result = run_in_company_context(company, Invoice.objects.all)
        run_in_company_context(company, sync_products, catalog_id=42)
    """
    from apps.core.db_router import set_company_db, get_company_db

    # Sauvegarde du contexte DB précédent
    previous_alias = get_company_db()
    # Activation du contexte DB de l'entreprise cible
    alias = get_company_database_alias(company)
    set_company_db(alias if alias != 'default' else None)

    try:
        return func(*args, **kwargs)
    finally:
        # Restauration du contexte DB précédent (toujours exécuté)
        set_company_db(previous_alias)
