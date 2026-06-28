"""
python manage.py seed_permissions
Crée tous les modules ERP, vues, actions, rôles et permissions par défaut.
"""
from django.core.management.base import BaseCommand
from apps.access_control.models import ERPModule, ERPView, ERPAction, Role, RolePermission


MODULES = [
    ('Dashboard', 'dashboard', 'speedometer2', '#6366F1', 1),
    ('CRM', 'crm', 'people', '#3B82F6', 2),
    ('Ventes', 'sales', 'receipt', '#10B981', 3),
    ('Facturation', 'facturation', 'file-earmark-text', '#F59E0B', 4),
    ('Comptabilité', 'accounting', 'calculator', '#8B5CF6', 5),
    ('Achats', 'purchases', 'cart3', '#EF4444', 6),
    ('Stocks', 'inventory', 'box-seam', '#F97316', 7),
    ('BTP', 'btp', 'building', '#0EA5E9', 8),
    ('E-commerce', 'ecommerce', 'shop', '#EC4899', 9),
    ('Commerce', 'commerce', 'bag', '#84CC16', 10),
    ('Production', 'production', 'gear', '#64748B', 11),
    ('Audio', 'audio', 'music-note', '#A855F7', 12),
    ('RH', 'hr', 'person-badge', '#06B6D4', 13),
    ('Paie', 'payroll', 'cash-coin', '#22C55E', 14),
    ('Documents', 'documents', 'folder2', '#F59E0B', 15),
    ('Support', 'support', 'headset', '#EF4444', 16),
    ('Sites web', 'websites', 'globe', '#0EA5E9', 17),
    ('Portail client', 'client_portal', 'person-circle', '#6366F1', 18),
    ('Reporting', 'reporting', 'bar-chart', '#8B5CF6', 19),
    ('Paramètres', 'settings', 'gear-wide', '#64748B', 20),
    ('Gestion accès', 'access_control', 'shield-lock', '#DC2626', 21),
]

ACTIONS = [
    ('Voir', 'view'), ('Créer', 'create'), ('Modifier', 'edit'), ('Supprimer', 'delete'),
    ('Valider', 'validate'), ('Refuser', 'refuse'), ('Exporter', 'export'), ('Importer', 'import'),
    ('Imprimer', 'print'), ('Télécharger', 'download'), ('Uploader', 'upload'),
    ('Archiver', 'archive'), ('Restaurer', 'restore'), ('Publier', 'publish'),
    ('Dépublier', 'unpublish'), ('Envoyer', 'send'), ('Approuver', 'approve'),
    ('Assigner', 'assign'), ('Configurer', 'configure'), ('Administrer', 'admin'),
]

ROLES = [
    ('Superadmin', 'superadmin', True),
    ('Admin société', 'admin', True),
    ('Direction', 'direction', True),
    ('Responsable administratif', 'admin_rh', False),
    ('Comptable', 'comptable', True),
    ('Responsable RH', 'rh_manager', True),
    ('Responsable commercial', 'sales_manager', False),
    ('Commercial', 'commercial', True),
    ('Responsable chantier', 'site_manager', True),
    ('Chef d\'équipe', 'team_leader', False),
    ('Salarié terrain', 'field_worker', True),
    ('Technicien', 'technician', False),
    ('Magasinier', 'warehouse', False),
    ('Responsable e-commerce', 'ecom_manager', False),
    ('Support client', 'support', False),
    ('Lecture seule', 'readonly', True),
]

# Modules accessibles par rôle (module_code, [action_codes])
ROLE_PERMISSIONS = {
    'superadmin': {mod[1]: ['view', 'create', 'edit', 'delete', 'validate', 'export', 'import', 'admin'] for mod in MODULES},
    'admin': {mod[1]: ['view', 'create', 'edit', 'delete', 'validate', 'export', 'import', 'admin'] for mod in MODULES},
    'direction': {
        'dashboard': ['view'], 'crm': ['view', 'export'], 'sales': ['view', 'validate', 'export'],
        'facturation': ['view', 'validate', 'export'], 'accounting': ['view', 'validate', 'export'],
        'purchases': ['view', 'validate'], 'hr': ['view', 'validate'], 'payroll': ['view'],
        'btp': ['view'], 'documents': ['view', 'export'], 'reporting': ['view', 'export'],
    },
    'comptable': {
        'dashboard': ['view'], 'accounting': ['view', 'create', 'edit', 'validate', 'export', 'import'],
        'facturation': ['view', 'create', 'edit', 'validate', 'export'],
        'purchases': ['view', 'create', 'edit'], 'documents': ['view', 'create', 'upload'],
        'crm': ['view'], 'sales': ['view'], 'inventory': ['view'], 'btp': ['view'],
        'reporting': ['view', 'export'],
    },
    'rh_manager': {
        'dashboard': ['view'], 'hr': ['view', 'create', 'edit', 'delete', 'export'],
        'payroll': ['view', 'create', 'edit', 'validate', 'export'],
        'documents': ['view', 'create', 'edit', 'upload', 'download', 'delete'],
    },
    'commercial': {
        'dashboard': ['view'], 'crm': ['view', 'create', 'edit', 'export'],
        'sales': ['view', 'create', 'edit', 'export'], 'facturation': ['view'],
        'inventory': ['view'], 'btp': ['view'], 'support': ['view'],
    },
    'site_manager': {
        'dashboard': ['view'], 'btp': ['view', 'create', 'edit', 'export'],
        'crm': ['view'], 'hr': ['view'], 'documents': ['view', 'upload'],
        'support': ['view', 'create'],
    },
    'field_worker': {
        'dashboard': ['view'], 'btp': ['view'], 'documents': ['view'],
    },
    'support': {
        'dashboard': ['view'], 'support': ['view', 'create', 'edit'],
        'crm': ['view'], 'sales': ['view'], 'btp': ['view'],
    },
    'readonly': {mod[1]: ['view'] for mod in MODULES},
}


class Command(BaseCommand):
    help = 'Crée les modules ERP, actions, rôles et permissions par défaut.'

    def handle(self, *args, **options):
        self.stdout.write('=== Seed permissions ERP ===\n')

        # Modules
        self.stdout.write('Création des modules...')
        module_objs = {}
        for name, code, icon, color, order in MODULES:
            obj, created = ERPModule.objects.update_or_create(
                code=code,
                defaults={'name': name, 'icon': icon, 'color': color, 'order': order, 'is_active': True}
            )
            module_objs[code] = obj
            if created:
                self.stdout.write(f'  + Module {name}')

        # Actions
        self.stdout.write('Création des actions...')
        action_objs = {}
        for name, code in ACTIONS:
            obj, _ = ERPAction.objects.update_or_create(code=code, defaults={'name': name})
            action_objs[code] = obj

        # Rôles (sans company = rôles globaux/système)
        self.stdout.write('Création des rôles...')
        role_objs = {}
        for name, code, is_system in ROLES:
            obj, created = Role.objects.update_or_create(
                code=code, company=None,
                defaults={'name': name, 'is_system_role': is_system, 'is_active': True}
            )
            role_objs[code] = obj
            if created:
                self.stdout.write(f'  + Rôle {name}')

        # Permissions
        self.stdout.write('Création des permissions...')
        total = 0
        for role_code, perms in ROLE_PERMISSIONS.items():
            role = role_objs.get(role_code)
            if not role:
                continue
            for module_code, actions in perms.items():
                module = module_objs.get(module_code)
                if not module:
                    continue
                for action_code in actions:
                    action = action_objs.get(action_code)
                    if not action:
                        continue
                    _, created = RolePermission.objects.get_or_create(
                        role=role, module=module, view=None, action=action,
                        defaults={'allowed': True}
                    )
                    if created:
                        total += 1

        self.stdout.write(self.style.SUCCESS(
            f'\n✓ Seed terminé : {len(module_objs)} modules, {len(action_objs)} actions, '
            f'{len(role_objs)} rôles, {total} permissions créées.'
        ))
