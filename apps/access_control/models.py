"""
apps/access_control/models.py
Gestion granulaire des accès utilisateurs aux modules, vues et actions ERP.
"""
from django.db import models
from django.contrib.auth.models import User
from apps.core.models import Company


# ─── RÉFÉRENTIELS ─────────────────────────────────────────────────────────────

class ERPModule(models.Model):
    name = models.CharField('Nom', max_length=100)
    code = models.CharField('Code', max_length=50, unique=True)
    description = models.TextField('Description', blank=True)
    icon = models.CharField('Icône Bootstrap', max_length=50, default='grid')
    color = models.CharField('Couleur CSS', max_length=30, default='#6B7280')
    is_active = models.BooleanField('Actif', default=True)
    order = models.PositiveIntegerField('Ordre', default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Module ERP'
        verbose_name_plural = 'Modules ERP'
        ordering = ['order', 'name']

    def __str__(self):
        return f'{self.name} ({self.code})'


class ERPView(models.Model):
    module = models.ForeignKey(ERPModule, on_delete=models.CASCADE, related_name='views')
    name = models.CharField('Nom', max_length=100)
    code = models.CharField('Code', max_length=100, unique=True)
    url_name = models.CharField('Nom URL Django', max_length=100, blank=True)
    description = models.TextField('Description', blank=True)
    is_active = models.BooleanField('Actif', default=True)
    order = models.PositiveIntegerField('Ordre', default=0)

    class Meta:
        verbose_name = 'Vue ERP'
        verbose_name_plural = 'Vues ERP'
        ordering = ['module', 'order', 'name']

    def __str__(self):
        return f'{self.code}'


class ERPAction(models.Model):
    name = models.CharField('Nom', max_length=100)
    code = models.CharField('Code', max_length=50, unique=True)
    description = models.TextField('Description', blank=True)

    class Meta:
        verbose_name = 'Action ERP'
        verbose_name_plural = 'Actions ERP'
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.code})'


# ─── RÔLES ────────────────────────────────────────────────────────────────────

class Role(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='roles', null=True, blank=True)
    name = models.CharField('Nom', max_length=100)
    code = models.CharField('Code', max_length=50)
    description = models.TextField('Description', blank=True)
    is_system_role = models.BooleanField('Rôle système', default=False)
    is_active = models.BooleanField('Actif', default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Rôle'
        verbose_name_plural = 'Rôles'
        ordering = ['name']
        unique_together = ['company', 'code']

    def __str__(self):
        return self.name

    @property
    def user_count(self):
        return self.user_accesses.filter(is_active=True).count()


class RolePermission(models.Model):
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='permissions')
    module = models.ForeignKey(ERPModule, on_delete=models.CASCADE)
    view = models.ForeignKey(ERPView, on_delete=models.CASCADE, null=True, blank=True)
    action = models.ForeignKey(ERPAction, on_delete=models.CASCADE, null=True, blank=True)
    allowed = models.BooleanField('Autorisé', default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Permission de rôle'
        verbose_name_plural = 'Permissions de rôle'
        unique_together = ['role', 'module', 'view', 'action']

    def __str__(self):
        status = '✓' if self.allowed else '✗'
        return f'{status} {self.role.name} — {self.module.code}/{self.view or "*"}/{self.action or "*"}'


# ─── ACCÈS UTILISATEUR ────────────────────────────────────────────────────────

class UserCompanyAccess(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='company_accesses')
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='user_accesses')
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True, related_name='user_accesses')
    is_active = models.BooleanField('Actif', default=True)
    can_switch_company = models.BooleanField('Peut changer d\'entreprise', default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Accès utilisateur-entreprise'
        verbose_name_plural = 'Accès utilisateur-entreprise'
        unique_together = ['user', 'company']

    def __str__(self):
        return f'{self.user.get_full_name() or self.user.username} — {self.company.name} ({self.role})'


class UserPermissionOverride(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='permission_overrides')
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    module = models.ForeignKey(ERPModule, on_delete=models.CASCADE)
    view = models.ForeignKey(ERPView, on_delete=models.CASCADE, null=True, blank=True)
    action = models.ForeignKey(ERPAction, on_delete=models.CASCADE, null=True, blank=True)
    allowed = models.BooleanField('Autorisé', default=True)
    reason = models.TextField('Raison', blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='overrides_created')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Override de permission'
        verbose_name_plural = 'Overrides de permissions'

    def __str__(self):
        status = 'Accordé' if self.allowed else 'Refusé'
        return f'{status} — {self.user} — {self.module.code}'


class DepartmentAccess(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='department_accesses')
    department = models.CharField('Service / Département', max_length=100)
    module = models.ForeignKey(ERPModule, on_delete=models.CASCADE)
    view = models.ForeignKey(ERPView, on_delete=models.CASCADE, null=True, blank=True)
    action = models.ForeignKey(ERPAction, on_delete=models.CASCADE, null=True, blank=True)
    allowed = models.BooleanField('Autorisé', default=True)

    class Meta:
        verbose_name = 'Accès par service'
        verbose_name_plural = 'Accès par service'

    def __str__(self):
        return f'{self.department} — {self.module.code}'


class AccessLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    company = models.ForeignKey(Company, on_delete=models.SET_NULL, null=True)
    module = models.CharField('Module', max_length=50, blank=True)
    view_code = models.CharField('Vue', max_length=100, blank=True)
    action = models.CharField('Action', max_length=50, blank=True)
    object_repr = models.CharField('Objet', max_length=200, blank=True)
    ip_address = models.GenericIPAddressField('IP', null=True, blank=True)
    user_agent = models.TextField('User-Agent', blank=True)
    allowed = models.BooleanField('Autorisé')
    reason = models.CharField('Raison', max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Journal d\'accès'
        verbose_name_plural = 'Journal des accès'
        ordering = ['-created_at']

    def __str__(self):
        status = '✓' if self.allowed else '✗'
        return f'{status} {self.user} — {self.module}/{self.view_code} ({self.created_at:%d/%m/%Y %H:%M})'
