from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse


class BuilderPage(models.Model):
    STATUS_DRAFT = 'draft'
    STATUS_PUBLISHED = 'published'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Brouillon'),
        (STATUS_PUBLISHED, 'Publié'),
    ]

    company = models.ForeignKey(
        'core.Company', on_delete=models.CASCADE, related_name='builder_pages',
    )
    website = models.ForeignKey(
        'websites.Website', on_delete=models.CASCADE, related_name='builder_pages',
    )
    brand_key = models.CharField(max_length=80, blank=True)
    title = models.CharField(max_length=220)
    slug = models.SlugField(max_length=240)
    is_homepage = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    published_at = models.DateTimeField(null=True, blank=True)
    meta_title = models.CharField(max_length=220, blank=True)
    meta_description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('website', 'slug')]
        ordering = ['-updated_at']

    def __str__(self):
        return f'{self.title} [{self.website.slug}]'

    def get_absolute_url(self):
        return reverse('site_builder:builder', kwargs={'page_id': self.pk})

    def save(self, *args, **kwargs):
        if not self.brand_key and self.website_id:
            try:
                self.brand_key = self.website.slug
            except Exception:
                pass
        super().save(*args, **kwargs)


class BuilderSection(models.Model):
    page = models.ForeignKey(
        BuilderPage, on_delete=models.CASCADE, related_name='sections',
    )
    module_type = models.CharField(max_length=60)
    position = models.PositiveIntegerField(default=0)
    settings = models.JSONField(default=dict)
    is_visible = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['position']

    def __str__(self):
        return f'{self.module_type} (pos {self.position}) – {self.page}'


class BuilderAsset(models.Model):
    TYPE_IMAGE = 'image'
    TYPE_VIDEO = 'video'
    TYPE_PDF = 'pdf'
    TYPE_CHOICES = [
        (TYPE_IMAGE, 'Image'),
        (TYPE_VIDEO, 'Vidéo'),
        (TYPE_PDF, 'PDF'),
    ]

    company = models.ForeignKey(
        'core.Company', on_delete=models.CASCADE, related_name='builder_assets',
    )
    file = models.FileField(upload_to='builder_assets/%Y/%m/')
    alt_text = models.CharField(max_length=220, blank=True)
    file_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_IMAGE)
    file_size = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.alt_text or str(self.file)


class BuilderPublishLog(models.Model):
    page = models.ForeignKey(
        BuilderPage, on_delete=models.CASCADE, related_name='publish_logs',
    )
    published_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    published_at = models.DateTimeField(auto_now_add=True)
    sections_snapshot = models.JSONField(default=list)

    class Meta:
        ordering = ['-published_at']

    def __str__(self):
        return f'Publish {self.page} at {self.published_at}'
