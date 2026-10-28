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
