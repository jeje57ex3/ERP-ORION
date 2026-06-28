"""
apps/core/managers.py — Managers et QuerySets filtrés par entreprise

Tous les modèles métier doivent utiliser CompanyManager pour éviter
les fuites de données entre entreprises.

Exemple d'utilisation dans un modèle :
    from apps.core.managers import CompanyManager

    class Customer(models.Model):
        company = models.ForeignKey('core.Company', ...)
        objects = CompanyManager()
"""
from django.db import models


class CompanyQuerySet(models.QuerySet):
    """QuerySet avec filtrage automatique par entreprise."""

    def for_company(self, company):
        """Filtre les objets appartenant à une entreprise."""
        if company is None:
            return self.none()
        return self.filter(company=company)

    def active(self):
        """Filtre les objets actifs (is_active=True)."""
        return self.filter(is_active=True)

    def for_company_active(self, company):
        """Filtre actif + entreprise."""
        return self.for_company(company).active()


class CompanyManager(models.Manager):
    """Manager standard avec accès au CompanyQuerySet."""

    def get_queryset(self):
        return CompanyQuerySet(self.model, using=self._db)

    def for_company(self, company):
        return self.get_queryset().for_company(company)

    def active(self):
        return self.get_queryset().active()

    def for_company_active(self, company):
        return self.get_queryset().for_company_active(company)


class CompanyBaseModel(models.Model):
    """
    Modèle abstrait pour tous les modèles métier Orion.
    Fournit : company, created_at, updated_at, created_by, updated_by, is_active.

    Utilisation :
        class Customer(CompanyBaseModel):
            name = models.CharField(...)
    """
    from django.conf import settings as _settings

    company = models.ForeignKey(
        'core.Company',
        on_delete=models.CASCADE,
        verbose_name='Entreprise',
        db_index=True,
    )
    created_at = models.DateTimeField('Créé le', auto_now_add=True)
    updated_at = models.DateTimeField('Modifié le', auto_now=True)
    is_active = models.BooleanField('Actif', default=True, db_index=True)

    objects = CompanyManager()

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=['company', 'is_active']),
            models.Index(fields=['company', 'created_at']),
        ]
