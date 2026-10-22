from datetime import time

from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from apps.core.models import Company
from apps.documents.validators import validate_sensitive_document


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
    LEVEL_CHOICES = [
        ('beginner', _('Débutant')),
        ('intermediate', _('Intermédiaire')),
        ('expert', _('Expert')),
    ]
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='skills')
    name = models.CharField('Compétence', max_length=100)
    level = models.CharField('Niveau', max_length=20, choices=LEVEL_CHOICES, default='intermediate')

    def __str__(self):
        return f'{self.name} ({self.employee})'


class EmployeeCertification(models.Model):
    CATEGORY_CHOICES = [
        ('caces', 'CACES'),
        ('habilitation', _('Habilitation')),
        ('certificate', _('Certificat')),
        ('diploma', _('Diplôme')),
        ('other', _('Autre')),
    ]
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='certifications')
    category = models.CharField('Type', max_length=20, choices=CATEGORY_CHOICES, default='certificate')
    name = models.CharField('Habilitation / Certification', max_length=200)
    reference = models.CharField('Référence', max_length=50, blank=True)
    issued_date = models.DateField('Délivrance', null=True, blank=True)
    expiry_date = models.DateField('Expiration', null=True, blank=True)
    issuing_body = models.CharField('Organisme', max_length=200, blank=True)
    file = models.FileField(
        'Document (scan)', upload_to='employee_certifications/', blank=True, null=True,
        validators=[validate_sensitive_document],
    )
    is_active = models.BooleanField('Active', default=True)

    class Meta:
        verbose_name = 'Certification'
        verbose_name_plural = 'Certifications'

    def __str__(self):
        return f'{self.name} — {self.employee}'

    @property
    def is_expired(self):
        if self.expiry_date:
            from datetime import date
            return self.expiry_date < date.today()
        return False

    @property
    def expires_soon(self):
        if self.expiry_date:
            from datetime import date, timedelta
            return date.today() <= self.expiry_date <= date.today() + timedelta(days=30)
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


# ─── PLANNING : RYTHME DE TRAVAIL ET ARRÊTS ──────────────────────────────────
#
# Deux modeles ajoutes ici, et non dans une application nouvelle : ils
# decrivent le temps d'un SALARIE, comme LeaveRequest juste au-dessus.
# Eparpiller les donnees de temps d'un salarie entre deux applications
# obligerait chaque lecture du planning a joindre deux fois, et chaque
# nouveau besoin a choisir arbitrairement un cote.
#
# Ce qui existait deja et n'est donc pas redit ici : les conges et la
# maladie (LeaveRequest, avec son circuit d'approbation) et les heures
# pointees (btp.BTPTimesheet). Le planning les LIT -- voir
# apps/hr/planning_service.py -- au lieu d'en creer un second exemplaire :
# deux endroits pour declarer un conge, c'est un conge sur deux qui manque
# quelque part.


JOURS_SEMAINE = (
    ('monday', 'Lundi'), ('tuesday', 'Mardi'), ('wednesday', 'Mercredi'),
    ('thursday', 'Jeudi'), ('friday', 'Vendredi'), ('saturday', 'Samedi'),
    ('sunday', 'Dimanche'),
)

# date.weekday() rend 0 pour lundi : l'index dans ce tuple est donc
# directement exploitable, sans table de correspondance.
CHAMPS_PAR_JOUR = tuple(f'hours_{cle}' for cle, _libelle in JOURS_SEMAINE)


class WorkSchedule(models.Model):
    """Rythme hebdomadaire d'un salarie : heures prevues pour chaque jour.

    Des HEURES par jour, et non une case « travaille / repos ». Le choix
    coute le meme travail et dit beaucoup plus : un 80 % avec le mercredi
    libre, une demi-journee le vendredi, un samedi a quatre heures. Avec
    des booleens, la demi-journee aurait ete inexprimable, et le planning
    aurait annonce une journee entiere.

    Un jour a zero heure EST un jour de repos : la notion n'a pas besoin
    d'un champ a elle, et ne peut donc pas contredire les heures.
    """

    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name='work_schedules',
        verbose_name='Entreprise')
    employee = models.OneToOneField(
        Employee, on_delete=models.CASCADE, related_name='work_schedule',
        verbose_name='Salarié')

    # 7 h du lundi au vendredi = 35 h : le temps plein legal francais, qui
    # est le cas de la grande majorite des fiches. Un defaut juste evite
    # d'avoir a remplir sept champs pour le salarie ordinaire.
    hours_monday = models.DecimalField(
        'Lundi (h)', max_digits=4, decimal_places=2, default=7)
    hours_tuesday = models.DecimalField(
        'Mardi (h)', max_digits=4, decimal_places=2, default=7)
    hours_wednesday = models.DecimalField(
        'Mercredi (h)', max_digits=4, decimal_places=2, default=7)
    hours_thursday = models.DecimalField(
        'Jeudi (h)', max_digits=4, decimal_places=2, default=7)
    hours_friday = models.DecimalField(
        'Vendredi (h)', max_digits=4, decimal_places=2, default=7)
    hours_saturday = models.DecimalField(
        'Samedi (h)', max_digits=4, decimal_places=2, default=0)
    hours_sunday = models.DecimalField(
        'Dimanche (h)', max_digits=4, decimal_places=2, default=0)

    # Pour la frise horaire. Le pointage ne porte AUCUNE heure d'horloge --
    # c'est un total declare par jour, choix assume -- donc la seule chose
    # qu'on puisse placer honnetement sur une frise est le PREVU. Ces deux
    # champs le rendent exact au lieu de supposer un 8 h - 17 h pour tout le
    # monde.
    heure_debut = models.TimeField(
        'Heure de debut', default=time(8, 0),
        help_text="Heure d'arrivee prevue. Sert a placer la journee sur la "
                  "frise horaire du planning.")
    pause_minutes = models.PositiveSmallIntegerField(
        'Pause (minutes)', default=60,
        help_text='Pause non travaillee, retiree du temps de presence.')

    notes = models.TextField('Notes', blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Rythme de travail'
        verbose_name_plural = 'Rythmes de travail'

    def __str__(self):
        return f'{self.employee} — {self.heures_hebdomadaires} h/semaine'

    def heures_du_jour(self, jour):
        """Heures prevues pour cette date. jour est un datetime.date."""
        from decimal import Decimal
        valeur = getattr(self, CHAMPS_PAR_JOUR[jour.weekday()], 0)
        return Decimal(valeur or 0)

    def est_jour_de_repos(self, jour):
        return self.heures_du_jour(jour) == 0

    @property
    def heures_hebdomadaires(self):
        from decimal import Decimal
        total = sum((Decimal(getattr(self, champ) or 0)
                     for champ in CHAMPS_PAR_JOUR), Decimal('0'))
        return total.normalize() if total else Decimal('0')

    @property
    def jours_travailles(self):
        """Libelles des jours effectivement travailles, dans l'ordre."""
        return [
            libelle
            for (cle, libelle), champ in zip(JOURS_SEMAINE, CHAMPS_PAR_JOUR)
            if (getattr(self, champ) or 0) > 0
        ]

    @property
    def heures_par_jour(self):
        """Les sept jours, dans l'ordre : [{'libelle', 'heures', 'repos'}].

        Existe pour les gabarits. Django n'accepte pas
        « {% for h in champ1,champ2,... %} » -- le tag for prend UNE
        expression, et une liste litterale y leve une TemplateSyntaxError.
        Enumerer les sept champs a la main dans chaque gabarit marcherait,
        au prix d'un ordre a maintenir en double et d'un huitieme jour le
        jour ou l'on en ajoute un.
        """
        from decimal import Decimal
        return [
            {
                'libelle': libelle,
                'heures': Decimal(getattr(self, champ) or 0),
                'repos': (getattr(self, champ) or 0) == 0,
            }
            for (cle, libelle), champ in zip(JOURS_SEMAINE, CHAMPS_PAR_JOUR)
        ]


class WorkStoppage(models.Model):
    """Arret de travail : DECLARE, pas demande.

    Volontairement distinct de LeaveRequest, dont le type « maladie »
    pouvait sembler suffire. Un arret ne s'approuve pas -- il s'impose,
    certificat a l'appui -- et un circuit « en attente / approuve / refuse »
    appliquerait a un fait medical la forme d'une demande. Un responsable
    qui « refuse » un arret de travail n'a aucun sens.

    Deux proprietes que LeaveRequest ne porte pas et ne doit pas porter :
    une date de fin FACULTATIVE, parce qu'un arret initial est souvent
    ouvert en attendant la suite, et la PROLONGATION, qui chaine les arrets
    successifs d'un meme episode. Sans ce chainage, trois arrets de huit
    jours se lisent comme trois absences sans rapport.
    """

    KINDS = [
        ('maladie', 'Maladie'),
        ('accident_travail', 'Accident du travail'),
        ('accident_trajet', 'Accident de trajet'),
        ('maladie_pro', 'Maladie professionnelle'),
        ('maternite', 'Maternité'),
        ('paternite', 'Paternité / accueil de l\'enfant'),
        ('autre', 'Autre'),
    ]

    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name='work_stoppages',
        verbose_name='Entreprise')
    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name='work_stoppages',
        verbose_name='Salarié')
    kind = models.CharField('Nature', max_length=20, choices=KINDS,
                            default='maladie')
    start_date = models.DateField('Début')
    end_date = models.DateField(
        'Fin', null=True, blank=True,
        help_text='Laisser vide si l\'arrêt est en cours sans date de reprise connue.')

    certificate_date = models.DateField(
        'Date du certificat', null=True, blank=True)
    certificate_reference = models.CharField(
        'Référence du certificat', max_length=100, blank=True)

    prolongation_de = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='prolongations', verbose_name='Prolongation de',
        help_text='Arrêt initial que celui-ci prolonge.')

    notes = models.TextField('Notes', blank=True)
    declared_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='declared_stoppages', verbose_name='Déclaré par')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Arrêt de travail'
        verbose_name_plural = 'Arrêts de travail'
        ordering = ['-start_date']
        indexes = [
            models.Index(fields=['company', 'start_date'],
                         name='hr_stop_comp_start_idx'),
            models.Index(fields=['employee', 'start_date'],
                         name='hr_stop_empl_start_idx'),
        ]

    def __str__(self):
        fin = self.end_date.strftime('%d/%m/%Y') if self.end_date else 'en cours'
        return f'{self.employee} — {self.get_kind_display()} — {self.start_date:%d/%m/%Y} → {fin}'

    def couvre(self, jour):
        """Cet arret couvre-t-il cette date ?

        Une fin absente signifie « toujours en cours » : l'arret couvre
        donc tout ce qui suit son debut. Traiter l'absence de fin comme une
        fin immediate ferait disparaitre du planning l'arret le plus
        preoccupant, celui dont on ne connait pas le terme.
        """
        if jour < self.start_date:
            return False
        return self.end_date is None or jour <= self.end_date

    def est_en_cours(self, a_la_date=None):
        from django.utils import timezone
        return self.couvre(a_la_date or timezone.localdate())

    @property
    def duree_jours(self):
        """Nombre de jours calendaires, ou None si la fin est inconnue."""
        if self.end_date is None:
            return None
        return (self.end_date - self.start_date).days + 1

    def clean(self):
        from django.core.exceptions import ValidationError
        erreurs = {}
        if self.end_date and self.end_date < self.start_date:
            erreurs['end_date'] = (
                'La fin de l\'arrêt ne peut pas précéder son début.')
        if self.prolongation_de_id:
            if self.prolongation_de_id == self.pk:
                erreurs['prolongation_de'] = (
                    'Un arrêt ne peut pas se prolonger lui-même.')
            else:
                initial = self.prolongation_de
                if initial.employee_id != self.employee_id:
                    erreurs['prolongation_de'] = (
                        'L\'arrêt prolongé appartient à un autre salarié.')
                elif self.start_date < initial.start_date:
                    erreurs['start_date'] = (
                        'Une prolongation ne peut pas commencer avant '
                        'l\'arrêt qu\'elle prolonge.')
        if erreurs:
            raise ValidationError(erreurs)


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
