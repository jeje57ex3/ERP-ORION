from django.db import models
from django.contrib.auth.models import User
from apps.core.models import Company


class Employee(models.Model):
    CONTRACT_TYPES = [
        ('cdi', 'CDI'), ('cdd', 'CDD'), ('interim', 'Intérim'),
        ('apprentice', 'Apprentissage'), ('intern', 'Stage'), ('freelance', 'Freelance'),
    ]
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='employees')
    user = models.OneToOneField(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='employee_profile', verbose_name='Compte utilisateur',
    )
    employee_number = models.CharField(max_length=20, blank=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    job_title = models.CharField(max_length=100, blank=True)
    department = models.CharField(max_length=100, blank=True)
    contract_type = models.CharField(max_length=20, choices=CONTRACT_TYPES, default='cdi')
    hire_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    gross_salary = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    manager = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Salarié'
        verbose_name_plural = 'Salariés'

    def __str__(self):
        return f'{self.first_name} {self.last_name}'

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'.strip()


class EmployeeSkill(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='skills')
    name = models.CharField('Compétence', max_length=100)
    level = models.CharField('Niveau', max_length=20, choices=[('beginner', 'Débutant'), ('intermediate', 'Intermédiaire'), ('expert', 'Expert')], default='intermediate')

    def __str__(self):
        return f'{self.name} ({self.employee})'


class EmployeeCertification(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='certifications')
    name = models.CharField('Habilitation / Certification', max_length=200)
    reference = models.CharField('Référence', max_length=50, blank=True)
    issued_date = models.DateField('Délivrance', null=True, blank=True)
    expiry_date = models.DateField('Expiration', null=True, blank=True)
    issuing_body = models.CharField('Organisme', max_length=200, blank=True)
    is_active = models.BooleanField('Active', default=True)

    class Meta:
        verbose_name = 'Habilitation'
        verbose_name_plural = 'Habilitations'

    def __str__(self):
        return f'{self.name} — {self.employee}'

    @property
    def is_expired(self):
        if self.expiry_date:
            from datetime import date
            return self.expiry_date < date.today()
        return False


class LeaveRequest(models.Model):
    LEAVE_TYPES = [
        ('paid', 'Congés payés'), ('sick', 'Maladie'), ('unpaid', 'Sans solde'),
        ('rtt', 'RTT'), ('family', 'Événement familial'), ('other', 'Autre'),
    ]
    STATUS_CHOICES = [
        ('pending', 'En attente'), ('approved', 'Approuvé'), ('refused', 'Refusé'), ('cancelled', 'Annulé'),
    ]
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='leave_requests')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='leave_requests')
    leave_type = models.CharField(max_length=20, choices=LEAVE_TYPES, default='paid')
    start_date = models.DateField()
    end_date = models.DateField()
    days_count = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Demande de congé'

    def __str__(self):
        return f'{self.employee} - {self.start_date} au {self.end_date}'


class ExpenseReport(models.Model):
    STATUS_CHOICES = [('draft', 'Brouillon'), ('submitted', 'Soumise'), ('approved', 'Approuvée'), ('paid', 'Remboursée'), ('refused', 'Refusée')]
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='expense_reports')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='expense_reports')
    title = models.CharField(max_length=200)
    period_start = models.DateField()
    period_end = models.DateField()
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Note de frais'

    def __str__(self):
        return f'{self.title} - {self.employee}'


# ─── DOSSIERS PRIVÉS SALARIÉS ─────────────────────────────────────────────────

class EmployeePrivateFolder(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='private_folders')
    employee = models.OneToOneField(Employee, on_delete=models.CASCADE, related_name='private_folder')
    folder_name = models.CharField('Nom du dossier', max_length=200)
    description = models.TextField('Description', blank=True)
    is_locked = models.BooleanField('Verrouillé', default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Dossier privé salarié'
        verbose_name_plural = 'Dossiers privés salariés'

    def __str__(self):
        return self.folder_name

    @property
    def expiring_soon_count(self):
        from datetime import date, timedelta
        threshold = date.today() + timedelta(days=30)
        return self.documents.filter(expires_at__lte=threshold, expires_at__gte=date.today()).count()

    @property
    def expired_count(self):
        from datetime import date
        return self.documents.filter(expires_at__lt=date.today()).count()

    @property
    def pending_signature_count(self):
        return self.documents.filter(requires_signature=True, signed_at__isnull=True).count()


class EmployeePrivateDocument(models.Model):
    DOC_TYPE_CHOICES = [
        ('contract', 'Contrat de travail'), ('contract_amendment', 'Avenant contrat'),
        ('id_card', 'Pièce d\'identité'), ('rib', 'RIB'), ('address_proof', 'Justificatif domicile'),
        ('diploma', 'Diplôme'), ('certification', 'Certification'), ('electrical_habilitation', 'Habilitation électrique'),
        ('driving_license', 'Permis de conduire'), ('medical_visit', 'Visite médicale'),
        ('training_certificate', 'Attestation formation'), ('payslip', 'Bulletin de paie'),
        ('expense_report', 'Note de frais'), ('hr_letter', 'Courrier RH'),
        ('disciplinary', 'Sanction disciplinaire'), ('administrative', 'Document administratif'),
        ('other', 'Autre'),
    ]
    CONFIDENTIALITY_CHOICES = [
        ('standard', 'Standard'), ('confidential', 'Confidentiel'),
        ('very_confidential', 'Très confidentiel'), ('hr_only', 'RH uniquement'),
        ('direction_only', 'Direction uniquement'),
    ]
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='employee_private_docs')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='private_documents')
    folder = models.ForeignKey(EmployeePrivateFolder, on_delete=models.CASCADE, related_name='documents', null=True, blank=True)
    document_type = models.CharField('Type', max_length=30, choices=DOC_TYPE_CHOICES)
    title = models.CharField('Titre', max_length=200)
    file = models.FileField('Fichier', upload_to='employee_private/')
    description = models.TextField('Description', blank=True)
    confidentiality_level = models.CharField('Confidentialité', max_length=20, choices=CONFIDENTIALITY_CHOICES, default='confidential')
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='uploaded_private_docs')
    visible_to_employee = models.BooleanField('Visible par le salarié', default=True)
    requires_signature = models.BooleanField('Signature requise', default=False)
    signed_at = models.DateTimeField('Signé le', null=True, blank=True)
    expires_at = models.DateField('Date d\'expiration', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Document privé salarié'
        verbose_name_plural = 'Documents privés salariés'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title} — {self.employee}'

    @property
    def is_expired(self):
        if self.expires_at:
            from datetime import date
            return self.expires_at < date.today()
        return False

    @property
    def expires_soon(self):
        if self.expires_at:
            from datetime import date, timedelta
            return self.expires_at <= date.today() + timedelta(days=30)
        return False

    @property
    def needs_signature(self):
        return self.requires_signature and not self.signed_at


class EmployeeDocumentAccessLog(models.Model):
    ACTION_CHOICES = [
        ('view', 'Consultation'), ('download', 'Téléchargement'), ('upload', 'Upload'),
        ('edit', 'Modification'), ('delete', 'Suppression'), ('sign', 'Signature'), ('archive', 'Archivage'),
    ]
    document = models.ForeignKey(EmployeePrivateDocument, on_delete=models.CASCADE, related_name='access_logs')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField('Action', max_length=15, choices=ACTION_CHOICES)
    ip_address = models.GenericIPAddressField('IP', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Journal d\'accès document'
        verbose_name_plural = 'Journal d\'accès documents'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.get_action_display()} — {self.document.title} — {self.user}'
