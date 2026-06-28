"""
apps/core/exceptions.py — Exceptions métier Orion ERP

Hiérarchie :
    OrionException
    ├── CompanyAccessDenied
    ├── PermissionDenied
    ├── WorkflowError
    ├── ValidationError
    ├── NotFound
    ├── LockError
    ├── InsufficientStock
    ├── DuplicateReference
    └── IntegrationError

Utilisation :
    from apps.core.exceptions import LockError
    raise LockError("La facture FAC-00042 est validée et ne peut plus être modifiée.")
"""


class OrionException(Exception):
    """Exception de base pour toutes les exceptions métier Orion ERP."""

    code = 'orion_exception'
    default_message = "Une erreur s'est produite."

    def __init__(self, message=None, *args, **kwargs):
        self.message = message or self.default_message
        super().__init__(self.message, *args, **kwargs)

    def __str__(self):
        return f'[{self.code}] {self.message}'


class CompanyAccessDenied(OrionException):
    """L'utilisateur n'a pas accès à cette entreprise."""

    code = 'company_access_denied'
    default_message = "Accès à l'entreprise refusé."


class PermissionDenied(OrionException):
    """L'utilisateur n'a pas la permission d'effectuer cette action."""

    code = 'permission_denied'
    default_message = "Permission refusée."


class WorkflowError(OrionException):
    """Erreur dans le flux de traitement (transition d'état invalide, etc.)."""

    code = 'workflow_error'
    default_message = "Erreur de flux de traitement."


class ValidationError(OrionException):
    """Données invalides ou règle métier violée."""

    code = 'validation_error'
    default_message = "Erreur de validation."

    def __init__(self, message=None, field=None, *args, **kwargs):
        super().__init__(message, *args, **kwargs)
        # Champ concerné par l'erreur de validation (optionnel)
        self.field = field

    def __str__(self):
        if self.field:
            return f'[{self.code}] Champ « {self.field} » : {self.message}'
        return f'[{self.code}] {self.message}'


class NotFound(OrionException):
    """Ressource introuvable."""

    code = 'not_found'
    default_message = "Ressource introuvable."

    def __init__(self, message=None, model=None, pk=None, *args, **kwargs):
        if not message and model and pk:
            message = f"'{model}' avec l'identifiant {pk} introuvable."
        super().__init__(message, *args, **kwargs)
        self.model = model
        self.pk = pk


class LockError(OrionException):
    """
    Objet verrouillé : toute modification est interdite.
    Exemple : facture validée, commande expédiée.
    """

    code = 'lock_error'
    default_message = "Cet objet est verrouillé et ne peut pas être modifié."


class InsufficientStock(OrionException):
    """Stock insuffisant pour effectuer l'opération demandée."""

    code = 'insufficient_stock'
    default_message = "Stock insuffisant."

    def __init__(self, message=None, product=None, requested=None, available=None, *args, **kwargs):
        if not message and product:
            message = (
                f"Stock insuffisant pour « {product} » : "
                f"demandé {requested}, disponible {available}."
            )
        super().__init__(message, *args, **kwargs)
        self.product = product
        self.requested = requested
        self.available = available


class DuplicateReference(OrionException):
    """Référence déjà utilisée (numéro de facture, référence produit, etc.)."""

    code = 'duplicate_reference'
    default_message = "Cette référence existe déjà."

    def __init__(self, message=None, reference=None, *args, **kwargs):
        if not message and reference:
            message = f"La référence « {reference} » est déjà utilisée."
        super().__init__(message, *args, **kwargs)
        self.reference = reference


class IntegrationError(OrionException):
    """
    Erreur lors d'une intégration externe (API tierce, DNS, webhook, etc.).
    Exemple : échec de synchronisation Shopify, erreur Stripe.
    """

    code = 'integration_error'
    default_message = "Erreur d'intégration externe."

    def __init__(self, message=None, service=None, *args, **kwargs):
        if not message and service:
            message = f"Erreur lors de l'intégration avec « {service} »."
        super().__init__(message, *args, **kwargs)
        # Nom du service externe concerné (ex: 'Shopify', 'Stripe')
        self.service = service
