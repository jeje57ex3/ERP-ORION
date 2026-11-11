from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class TrainingCourse(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Brouillon'),
        ('published', 'Publié'),
        ('archived', 'Archivé'),
    ]

    company = models.ForeignKey(
        'core.Company', on_delete=models.CASCADE, related_name='training_courses',
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    cover_image = models.ImageField(upload_to='training/covers/', null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    order = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_training_courses',
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    # ── Parcours ────────────────────────────────────────────────────────────
    #
    # Le verrouillage est une OPTION, pas la règle. Une formation de
    # référence qu'on consulte par morceaux — « comment saisir un avoir » —
    # n'a aucune raison d'imposer un ordre. Un parcours d'habilitation, si.
    # Forcer l'un ou l'autre pour tout le monde serait un choix de
    # bibliothécaire, pas de formateur.
    progression_sequentielle = models.BooleanField(
        default=False,
        verbose_name='Imposer l’ordre des chapitres',
        help_text='Un chapitre reste fermé jusqu’à ce que le précédent soit '
                  'entièrement lu. À activer pour un parcours '
                  'd’habilitation, à laisser décoché pour un support de '
                  'référence qu’on consulte par morceaux.',
    )
    competences = models.ManyToManyField(
        'Competence', blank=True, related_name='formations',
        verbose_name='Compétences visées',
        help_text='Ce que la personne devra savoir FAIRE. Chacune donnera '
                  'lieu à une validation sur le terrain après le quiz.',
    )

    class Meta:
        ordering = ['order', 'created_at']
        verbose_name = 'Formation'
        verbose_name_plural = 'Formations'

    def __str__(self):
        return self.title

    @property
    def is_published(self):
        return self.status == 'published'

    @property
    def chapters_count(self):
        return self.chapters.count()

    @property
    def pages_count(self):
        return TrainingPage.objects.filter(chapter__course=self).count()

    @property
    def enrolled_count(self):
        return self.enrollments.count()


class TrainingChapter(models.Model):
    course = models.ForeignKey(
        TrainingCourse, on_delete=models.CASCADE, related_name='chapters',
    )
    title = models.CharField(max_length=200)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['order', 'created_at']
        verbose_name = 'Chapitre'
        verbose_name_plural = 'Chapitres'

    def __str__(self):
        return f"{self.course.title} › {self.title}"

    @property
    def pages_count(self):
        return self.pages.count()


class TrainingPage(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Brouillon'),
        ('published', 'Publié'),
    ]

    chapter = models.ForeignKey(
        TrainingChapter, on_delete=models.CASCADE, related_name='pages',
    )
    title = models.CharField(max_length=200)
    order = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'created_at']
        verbose_name = 'Page'
        verbose_name_plural = 'Pages'

    def __str__(self):
        return f"{self.chapter.course.title} › {self.chapter.title} › {self.title}"


class TrainingPageBlock(models.Model):
    BLOCK_TYPES = [
        ('text', 'Texte'),
        ('image', 'Image'),
        ('annotation', 'Annotation'),
        ('audio', 'Audio'),
    ]

    page = models.ForeignKey(
        TrainingPage, on_delete=models.CASCADE, related_name='blocks',
    )
    block_type = models.CharField(max_length=20, choices=BLOCK_TYPES, default='text')
    order = models.PositiveIntegerField(default=0)
    content = models.TextField(blank=True, help_text='Contenu texte ou annotation')
    file = models.FileField(
        upload_to='training/blocks/', null=True, blank=True,
        help_text='Fichier image ou audio',
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['order']
        verbose_name = 'Bloc de page'
        verbose_name_plural = 'Blocs de page'

    def __str__(self):
        return f"{self.page.title} — {self.get_block_type_display()}"

    @property
    def is_image(self):
        return self.block_type == 'image'

    @property
    def is_audio(self):
        return self.block_type == 'audio'


class TrainingEnrollment(models.Model):
    course = models.ForeignKey(
        TrainingCourse, on_delete=models.CASCADE, related_name='enrollments',
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='training_enrollments',
    )
    enrolled_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('course', 'user')
        ordering = ['-enrolled_at']
        verbose_name = 'Inscription'
        verbose_name_plural = 'Inscriptions'

    def __str__(self):
        return f"{self.user} → {self.course.title}"

    @property
    def is_completed(self):
        return self.completed_at is not None


class TrainingPageProgress(models.Model):
    page = models.ForeignKey(
        TrainingPage, on_delete=models.CASCADE, related_name='progress_records',
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='training_page_progress',
    )
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('page', 'user')
        verbose_name = 'Progression page'
        verbose_name_plural = 'Progressions pages'

    def __str__(self):
        status = '✓' if self.is_completed else '…'
        return f"{self.user} — {self.page.title} ({status})"


# ═══════════════════════════════════════════════════════════════════════════
# Parcours : étapes verrouillées, quiz final, validation sur le terrain
# ═══════════════════════════════════════════════════════════════════════════
#
# Les modèles ci-dessous portent des noms français, contrairement aux cinq
# premiers de ce fichier. Ce n'est pas une négligence : c'est la convention du
# reste du dépôt depuis plusieurs mois (ReglagesMail, OperationDeStockage,
# ControleDeLInstallation). Renommer les cinq anciens demanderait une
# migration de table sur des données existantes pour un gain de confort — ce
# n'est pas le moment.
#
# LES TROIS ÉTAPES, ET POURQUOI ELLES SONT SÉPARÉES
#
# Lire des pages prouve qu'on a lu. Réussir un quiz prouve qu'on a retenu. Ni
# l'un ni l'autre ne prouve qu'on sait FAIRE. D'où la troisième étape, qui ne
# se joue pas devant un écran : un responsable constate sur place, et le
# consigne. C'est celle-là qui a une valeur en cas de contrôle, et c'est la
# seule que le logiciel ne peut pas décider seul.


class Competence(models.Model):
    """Un savoir-faire constatable, indépendant du support de formation.

    **Séparée de la formation, et c'est le point.** Une compétence survit au
    support qui l'enseigne : celui-ci sera refait, renommé, remplacé, tandis
    que « sait consigner une installation avant intervention » reste la même
    exigence. Rattacher la validation au support ferait perdre l'historique à
    chaque refonte.

    Plusieurs formations peuvent donc viser la même compétence, et une
    formation en viser plusieurs.
    """

    company = models.ForeignKey(
        'core.Company', on_delete=models.CASCADE,
        related_name='competences_formation',
    )
    code = models.CharField(
        max_length=40,
        help_text='Référence courte, par exemple « ELEC-VAT ».',
    )
    libelle = models.CharField(max_length=200)
    description = models.TextField(
        blank=True,
        help_text='Ce que la personne doit savoir faire, formulé de façon '
                  'observable — c’est ce que le valideur aura sous les yeux.',
    )
    validite_mois = models.PositiveSmallIntegerField(
        default=0,
        verbose_name='Validité (mois)',
        help_text='0 = sans expiration. Au-delà, la validation devra être '
                  'renouvelée : une habilitation acquise en 2019 ne dit plus '
                  'rien de 2026.',
    )
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ('company', 'code')
        ordering = ['code']
        verbose_name = 'Compétence'
        verbose_name_plural = 'Compétences'

    def __str__(self):
        return f'{self.code} — {self.libelle}'


class Quiz(models.Model):
    """Le contrôle de connaissances d'une formation.

    Un seul par formation : « le quiz à la fin ». Des quiz intermédiaires par
    chapitre seraient une autre fonctionnalité, pas une variante de celle-ci.
    """

    course = models.OneToOneField(
        TrainingCourse, on_delete=models.CASCADE, related_name='quiz',
    )
    titre = models.CharField(max_length=200, default='Contrôle final')
    consignes = models.TextField(blank=True)
    note_minimale = models.PositiveSmallIntegerField(
        default=70,
        help_text='Pourcentage de bonnes réponses exigé pour réussir.',
    )
    tentatives_max = models.PositiveSmallIntegerField(
        default=3,
        help_text='0 = sans limite. Au-delà, la personne doit être débloquée '
                  'par un responsable — un quiz qu’on repasse indéfiniment '
                  'finit par être réussi par élimination.',
    )
    melanger_les_questions = models.BooleanField(default=True)
    montrer_les_corrections = models.BooleanField(
        default=True,
        help_text='Affiche la bonne réponse et son explication après coup. À '
                  'décocher si le quiz sert de contrôle et non '
                  'd’apprentissage.',
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = 'Quiz'
        verbose_name_plural = 'Quiz'

    def __str__(self):
        return f'{self.titre} — {self.course.title}'

    @property
    def nombre_de_questions(self):
        return self.questions.count()


class QuestionDeQuiz(models.Model):
    TYPE_CHOICES = [
        ('unique', 'Une seule bonne réponse'),
        ('multiple', 'Plusieurs bonnes réponses'),
        ('vrai_faux', 'Vrai ou faux'),
    ]

    quiz = models.ForeignKey(
        Quiz, on_delete=models.CASCADE, related_name='questions')
    enonce = models.TextField()
    type_de_question = models.CharField(
        max_length=20, choices=TYPE_CHOICES, default='unique')
    explication = models.TextField(
        blank=True,
        help_text='Montrée après la réponse. C’est là que le quiz enseigne '
                  'quelque chose, plutôt que de seulement noter.',
    )
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']
        verbose_name = 'Question de quiz'
        verbose_name_plural = 'Questions de quiz'

    def __str__(self):
        return self.enonce[:80]

    @property
    def choix_corrects(self):
        return set(self.choix.filter(est_correct=True)
                   .values_list('pk', flat=True))


class ChoixDeQuestion(models.Model):
    question = models.ForeignKey(
        QuestionDeQuiz, on_delete=models.CASCADE, related_name='choix')
    libelle = models.CharField(max_length=300)
    est_correct = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']
        verbose_name = 'Choix de question'
        verbose_name_plural = 'Choix de question'

    def __str__(self):
        marque = '✓' if self.est_correct else '·'
        return f'{marque} {self.libelle[:60]}'


class TentativeDeQuiz(models.Model):
    quiz = models.ForeignKey(
        Quiz, on_delete=models.CASCADE, related_name='tentatives')
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='tentatives_de_quiz')
    numero = models.PositiveSmallIntegerField(default=1)
    debutee_le = models.DateTimeField(default=timezone.now)
    finie_le = models.DateTimeField(null=True, blank=True)
    score = models.PositiveSmallIntegerField(default=0)
    reussie = models.BooleanField(default=False)
    # Figée au moment de la tentative : abaisser la note minimale plus tard ne
    # doit pas transformer rétroactivement un échec en réussite.
    note_minimale_appliquee = models.PositiveSmallIntegerField(default=70)

    class Meta:
        ordering = ['-debutee_le']
        verbose_name = 'Tentative de quiz'
        verbose_name_plural = 'Tentatives de quiz'

    def __str__(self):
        etat = 'réussie' if self.reussie else 'échouée'
        if self.finie_le is None:
            etat = 'en cours'
        return f'{self.user} — {self.quiz.titre} #{self.numero} ({etat})'


class ReponseDeTentative(models.Model):
    tentative = models.ForeignKey(
        TentativeDeQuiz, on_delete=models.CASCADE, related_name='reponses')
    question = models.ForeignKey(
        QuestionDeQuiz, on_delete=models.CASCADE, related_name='reponses')
    choix_retenus = models.ManyToManyField(ChoixDeQuestion, blank=True)
    est_correcte = models.BooleanField(default=False)

    class Meta:
        unique_together = ('tentative', 'question')
        verbose_name = 'Réponse de tentative'
        verbose_name_plural = 'Réponses de tentative'

    def __str__(self):
        return f'{self.tentative_id} / {self.question_id}'


class ValidationTerrain(models.Model):
    """Un responsable constate sur place que la personne sait faire.

    **La seule étape que le logiciel ne décide pas.** Elle est demandée par le
    système, puis tranchée par un humain qui était présent. D'où les champs
    qui l'ancrent dans le réel : la date du constat, le lieu, et qui a
    constaté.

    **Un apprenant ne peut pas valider sa propre compétence.** C'est la règle
    que le service et la vue font respecter, et la seule qui, si elle tombait,
    rendrait tout le dispositif décoratif.
    """

    STATUT_CHOICES = [
        ('en_attente', 'En attente de validation'),
        ('validee', 'Validée sur le terrain'),
        ('a_revoir', 'À revoir'),
        ('refusee', 'Refusée'),
    ]

    competence = models.ForeignKey(
        Competence, on_delete=models.CASCADE, related_name='validations')
    apprenant = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='validations_terrain_recues')
    course = models.ForeignKey(
        TrainingCourse, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='validations_terrain',
        help_text='La formation qui a mené à cette demande. Effaçable sans '
                  'perdre la validation : la compétence survit au support.',
    )

    statut = models.CharField(
        max_length=20, choices=STATUT_CHOICES, default='en_attente')
    demandee_le = models.DateTimeField(default=timezone.now)

    valide_par = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='validations_terrain_prononcees')
    constatee_le = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Date du constat',
        help_text='La date où la personne a été vue à l’œuvre, qui n’est pas '
                  'forcément celle de la saisie.',
    )
    lieu = models.CharField(
        max_length=200, blank=True,
        verbose_name='Lieu ou chantier',
        help_text='Où le constat a eu lieu. En texte libre, pour rester '
                  'utilisable hors BTP.',
    )
    commentaire = models.TextField(blank=True)
    piece_jointe = models.FileField(
        upload_to='training/validations/', null=True, blank=True,
        help_text='Photo ou document du constat, facultatif.',
    )
    expire_le = models.DateField(
        null=True, blank=True,
        help_text='Calculé depuis la validité de la compétence au moment de '
                  'la validation.',
    )

    class Meta:
        ordering = ['-demandee_le']
        verbose_name = 'Validation terrain'
        verbose_name_plural = 'Validations terrain'
        indexes = [
            models.Index(fields=['apprenant', 'statut']),
        ]

    def __str__(self):
        return (f'{self.apprenant} — {self.competence.code} '
                f'({self.get_statut_display()})')

    @property
    def est_expiree(self):
        if self.statut != 'validee' or self.expire_le is None:
            return False
        return timezone.localdate() > self.expire_le

    @property
    def est_acquise(self):
        """Validée et non expirée. C'est la seule lecture qui compte."""
        return self.statut == 'validee' and not self.est_expiree
