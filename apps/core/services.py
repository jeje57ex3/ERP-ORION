"""
apps/core/services.py — Services de base Orion ERP

La couche service concentre la logique métier et découple les vues des modèles.
Toutes les opérations importantes (création, modification, suppression) doivent
passer par un service qui hérite de BaseService.

Exemples :
    from apps.core.services import BaseService, CompanyService

    class InvoiceService(BaseService):
        def create_invoice(self, data):
            self.log_action('create', 'Invoice', description='Création facture')
            ...
"""
import logging

logger = logging.getLogger('orion.services')


class BaseService:
    """
    Service de base pour la logique métier Orion ERP.

    Chaque service métier doit hériter de cette classe et lui fournir
    l'entreprise active (et optionnellement l'utilisateur courant).

    Attributs :
        company : instance Company active
        user    : instance User (optionnel, pour l'audit)
    """

    def __init__(self, company, user=None):
        self.company = company
        self.user = user

    # ── Audit ──────────────────────────────────────────────────────────────────

    def log_action(
        self,
        action: str,
        model_name: str,
        object_id=None,
        object_repr: str = '',
        description: str = '',
        module: str = '',
        old_values=None,
        new_values=None,
        ip_address: str = '',
    ):
        """
        Enregistre une entrée dans le journal d'audit (AuditLog).

        Paramètres :
            action      : code action ('create', 'update', 'delete', etc.)
            model_name  : nom du modèle concerné (ex: 'Invoice')
            object_id   : identifiant de l'objet (str ou int)
            object_repr : représentation textuelle de l'objet
            description : description libre de l'action
            module      : code du module ERP (ex: 'sales', 'crm')
            old_values  : dict des anciennes valeurs (avant modification)
            new_values  : dict des nouvelles valeurs (après modification)
            ip_address  : adresse IP du demandeur (si disponible)
        """
        from apps.core.models import AuditLog

        try:
            AuditLog.objects.create(
                user=self.user,
                company=self.company,
                action=action,
                module=module or getattr(self, 'module_code', ''),
                model_name=model_name,
                object_id=str(object_id) if object_id is not None else '',
                object_repr=object_repr[:200] if object_repr else '',
                description=description,
                old_values=old_values,
                new_values=new_values,
                ip_address=ip_address or None,
            )
        except Exception as exc:
            # L'audit ne doit jamais faire échouer l'opération principale
            logger.warning('Échec enregistrement audit : %s', exc)

    # ── QuerySet filtré par entreprise ─────────────────────────────────────────

    def get_queryset(self, model_class):
        """
        Retourne le QuerySet du modèle filtré par l'entreprise courante.
        Utilise la méthode for_company() si disponible (CompanyManager),
        sinon filtre directement sur le champ company.

        Exemple :
            qs = self.get_queryset(Invoice)
        """
        manager = model_class.objects
        if hasattr(manager, 'for_company'):
            return manager.for_company(self.company)
        return manager.filter(company=self.company)

    # ── Méthode utilitaire ─────────────────────────────────────────────────────

    def get_object_or_404(self, model_class, **kwargs):
        """
        Récupère un objet filtré par entreprise, lève NotFound si absent.

        Exemple :
            invoice = self.get_object_or_404(Invoice, pk=42)
        """
        from apps.core.exceptions import NotFound

        try:
            return self.get_queryset(model_class).get(**kwargs)
        except model_class.DoesNotExist:
            pk = kwargs.get('pk') or kwargs.get('id')
            raise NotFound(model=model_class.__name__, pk=pk)


class CompanyService(BaseService):
    """
    Service utilitaire pour les opérations sur les entreprises.
    Fournit des méthodes pour récupérer et mettre à jour les paramètres.
    """

    # ── Récupération ───────────────────────────────────────────────────────────

    def get_company_settings(self):
        """
        Retourne (ou crée) les paramètres étendus de l'entreprise.
        """
        from apps.core.models import CompanySettings

        settings_obj, created = CompanySettings.objects.get_or_create(
            company=self.company
        )
        if created:
            logger.info('Paramètres entreprise créés pour %s', self.company)
        return settings_obj

    def get_active_connectors(self):
        """Retourne les connecteurs actifs de l'entreprise."""
        from apps.core.models import Connector

        return Connector.objects.filter(company=self.company, is_active=True)

    def get_connector(self, connector_type: str):
        """
        Retourne le connecteur d'un type donné, ou None s'il n'existe pas.

        Exemple :
            stripe = service.get_connector('stripe')
        """
        from apps.core.models import Connector

        try:
            return Connector.objects.get(
                company=self.company,
                connector_type=connector_type,
                is_active=True,
            )
        except Connector.DoesNotExist:
            return None

    # ── Actions ────────────────────────────────────────────────────────────────

    def update_settings(self, **kwargs):
        """
        Met à jour les paramètres de l'entreprise.

        Exemple :
            service.update_settings(payment_terms_days=45, invoice_footer='...')
        """
        settings_obj = self.get_company_settings()
        for attr, value in kwargs.items():
            if hasattr(settings_obj, attr):
                setattr(settings_obj, attr, value)
        settings_obj.save()
        self.log_action(
            action='update',
            model_name='CompanySettings',
            object_id=settings_obj.pk,
            object_repr=str(settings_obj),
            description='Mise à jour des paramètres entreprise',
        )
        return settings_obj


class AuditService(BaseService):
    """
    Service dédié à la consultation et gestion du journal d'audit.
    """

    def get_recent_logs(self, limit: int = 50):
        """Retourne les dernières entrées d'audit de l'entreprise."""
        from apps.core.models import AuditLog

        return AuditLog.objects.filter(company=self.company).order_by('-created_at')[:limit]

    def get_logs_for_object(self, model_name: str, object_id):
        """Retourne l'historique d'audit d'un objet précis."""
        from apps.core.models import AuditLog

        return AuditLog.objects.filter(
            company=self.company,
            model_name=model_name,
            object_id=str(object_id),
        ).order_by('-created_at')

    def get_logs_for_user(self, user, limit: int = 100):
        """Retourne les actions d'un utilisateur donné."""
        from apps.core.models import AuditLog

        return AuditLog.objects.filter(
            company=self.company,
            user=user,
        ).order_by('-created_at')[:limit]

    def get_logs_by_action(self, action: str, limit: int = 100):
        """Retourne les entrées d'audit filtrées par type d'action."""
        from apps.core.models import AuditLog

        return AuditLog.objects.filter(
            company=self.company,
            action=action,
        ).order_by('-created_at')[:limit]
