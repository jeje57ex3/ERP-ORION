"""
{% load permissions_tags %}

Usage:
  {% has_module_access request.user current_company 'sales' as can_sales %}
  {% if can_sales %}...{% endif %}

  {% can_view request.user current_company 'invoices' as can_view_invoices %}
  {% can_action request.user current_company 'sales' 'create' as can_create_invoice %}

  {% module_accessible 'crm' as crm_ok %}   (uses request/company from context)
  {% if crm_ok %}...{% endif %}
"""
from django import template
from apps.access_control.services import (
    user_has_module_access,
    user_has_view_access,
    user_has_action_access,
)

register = template.Library()


@register.simple_tag
def has_module_access(user, company, module_code):
    """Returns True if user can access the module."""
    if not user or not user.is_authenticated:
        return False
    if not company:
        return user.is_superuser
    return user_has_module_access(user, company, module_code)


@register.simple_tag
def can_view(user, company, view_code):
    """Returns True if user can access a specific view (by view_code)."""
    if not user or not user.is_authenticated:
        return False
    if not company:
        return user.is_superuser
    return user_has_view_access(user, company, view_code)


@register.simple_tag
def can_action(user, company, module_code, action_code):
    """Returns True if user can perform a specific action in a module."""
    if not user or not user.is_authenticated:
        return False
    if not company:
        return user.is_superuser
    return user_has_action_access(user, company, module_code, action_code)


@register.simple_tag(takes_context=True)
def can_create(context, module_code):
    """Shorthand: check 'create' permission using request/company from context."""
    request = context.get('request')
    company = context.get('current_company')
    if not request or not request.user.is_authenticated:
        return False
    if request.user.is_superuser:
        return True
    return user_has_action_access(request.user, company, module_code, 'create')


@register.simple_tag(takes_context=True)
def can_edit(context, module_code):
    """Shorthand: check 'update' permission using request/company from context."""
    request = context.get('request')
    company = context.get('current_company')
    if not request or not request.user.is_authenticated:
        return False
    if request.user.is_superuser:
        return True
    return user_has_action_access(request.user, company, module_code, 'update')


@register.simple_tag(takes_context=True)
def can_delete(context, module_code):
    """Shorthand: check 'delete' permission using request/company from context."""
    request = context.get('request')
    company = context.get('current_company')
    if not request or not request.user.is_authenticated:
        return False
    if request.user.is_superuser:
        return True
    return user_has_action_access(request.user, company, module_code, 'delete')


@register.simple_tag(takes_context=True)
def module_accessible(context, module_code):
    """Shorthand: check module access using request/company from context."""
    request = context.get('request')
    company = context.get('current_company')
    if not request or not request.user.is_authenticated:
        return False
    if request.user.is_superuser:
        return True
    return user_has_module_access(request.user, company, module_code)


@register.inclusion_tag('components/action_buttons.html', takes_context=True)
def action_buttons_tag(context, module_code, obj=None, edit_url=None, delete_url=None):
    """Renders edit/delete buttons based on user permissions."""
    request = context.get('request')
    company = context.get('current_company')
    user = request.user if request else None
    return {
        'can_edit': user and user_has_action_access(user, company, module_code, 'update'),
        'can_delete': user and user_has_action_access(user, company, module_code, 'delete'),
        'obj': obj,
        'edit_url': edit_url,
        'delete_url': delete_url,
    }


# ─── Simple tags d'action supplémentaires ────────────────────────────────────

@register.simple_tag(takes_context=True)
def can_export(context, module_code):
    """Raccourci : vérifie la permission 'export' depuis le contexte."""
    request = context.get('request')
    company = context.get('current_company')
    if not request or not request.user.is_authenticated:
        return False
    if request.user.is_superuser:
        return True
    return user_has_action_access(request.user, company, module_code, 'export')


@register.simple_tag(takes_context=True)
def can_import(context, module_code):
    """Raccourci : vérifie la permission 'import' depuis le contexte."""
    request = context.get('request')
    company = context.get('current_company')
    if not request or not request.user.is_authenticated:
        return False
    if request.user.is_superuser:
        return True
    return user_has_action_access(request.user, company, module_code, 'import')


@register.simple_tag(takes_context=True)
def can_validate(context, module_code):
    """Raccourci : vérifie la permission 'validate' depuis le contexte."""
    request = context.get('request')
    company = context.get('current_company')
    if not request or not request.user.is_authenticated:
        return False
    if request.user.is_superuser:
        return True
    return user_has_action_access(request.user, company, module_code, 'validate')


@register.simple_tag(takes_context=True)
def can_archive(context, module_code):
    """Raccourci : vérifie la permission 'archive' depuis le contexte."""
    request = context.get('request')
    company = context.get('current_company')
    if not request or not request.user.is_authenticated:
        return False
    if request.user.is_superuser:
        return True
    return user_has_action_access(request.user, company, module_code, 'archive')


# ─── Block tag {% if_user_can %} ──────────────────────────────────────────────

class IfUserCanNode(template.Node):
    """
    Nœud de template pour le block tag {% if_user_can "module.action" %}.

    Rend le contenu du bloc uniquement si l'utilisateur dispose
    de la permission demandée sur le module et l'action indiqués.
    """

    def __init__(self, permission: str, nodelist):
        self.permission = permission
        self.nodelist = nodelist

    def render(self, context):
        request = context.get('request')
        company = context.get('current_company')

        # Utilisateur non authentifié → bloc masqué
        if not request or not request.user.is_authenticated:
            return ''

        # Superuser → accès total sans vérification
        if request.user.is_superuser:
            return self.nodelist.render(context)

        # Décomposition "module_code.action_code"
        parts = self.permission.split('.', 1)
        module_code = parts[0]
        action_code = parts[1] if len(parts) > 1 else 'view'

        if user_has_action_access(request.user, company, module_code, action_code):
            return self.nodelist.render(context)

        return ''


@register.tag('if_user_can')
def if_user_can_tag(parser, token):
    """
    Block tag de permission pour les templates Orion ERP.

    Syntaxe :
        {% if_user_can "sales.create" %}
            <button>Créer une facture</button>
        {% endif_user_can %}

        {% if_user_can "btp.validate" %}
            <button>Valider le chantier</button>
        {% endif_user_can %}

    Format de permission : "module_code.action_code"
        module_code  → ex: 'sales', 'crm', 'btp', 'inventory'
        action_code  → ex: 'view', 'create', 'update', 'delete',
                           'validate', 'export', 'import', 'archive'

    Requiert que 'request' et 'current_company' soient dans le contexte
    (RequestContext ou django.template.context_processors.request activé).
    """
    bits = token.split_contents()
    if len(bits) != 2:
        raise template.TemplateSyntaxError(
            f"Le tag '{bits[0]}' requiert exactement un argument : "
            "{% if_user_can \"module.action\" %}"
        )
    permission = bits[1].strip('"\'')
    nodelist = parser.parse(('endif_user_can',))
    parser.delete_first_token()
    return IfUserCanNode(permission, nodelist)
