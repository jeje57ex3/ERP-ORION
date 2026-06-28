"""
apps/translations/models.py — Modeles du systeme de traduction Orion ERP
"""
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _


class Language(models.Model):
    """Langue disponible dans le systeme."""
    code        = models.CharField(_('Code'), max_length=5, unique=True)
    name        = models.CharField(_('Nom'), max_length=100)
    native_name = models.CharField(_('Nom natif'), max_length=100)
    is_active   = models.BooleanField(_('Active'), default=True)
    is_default  = models.BooleanField(_('Par defaut'), default=False)
    is_rtl      = models.BooleanField(_('Droite a gauche'), default=False)
    flag_icon   = models.CharField(_('Icone drapeau'), max_length=10, blank=True,
                                   help_text='Emoji drapeau, ex : 🇫🇷')
    order       = models.PositiveIntegerField(_('Ordre'), default=0)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = _('Langue')
        verbose_name_plural = _('Langues')
        ordering            = ['order', 'name']

    def __str__(self):
        return f'{self.native_name} ({self.code})'

    def save(self, *args, **kwargs):
        if self.is_default:
            Language.objects.exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


class CompanyLanguageSettings(models.Model):
    """Langues activees par entreprise."""
    company                       = models.OneToOneField(
        'core.Company', on_delete=models.CASCADE,
        related_name='language_settings', verbose_name=_('Entreprise')
    )
    default_language              = models.ForeignKey(
        Language, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='default_for_companies', verbose_name=_('Langue par defaut')
    )
    enabled_languages             = models.ManyToManyField(
        Language, blank=True, related_name='enabled_for_companies',
        verbose_name=_('Langues activees')
    )
    allow_users_to_change_language = models.BooleanField(
        _('Permettre aux utilisateurs de changer la langue'), default=True
    )
    auto_detect_browser_language  = models.BooleanField(
        _('Detection auto langue navigateur'), default=False
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = _('Parametres langue entreprise')
        verbose_name_plural = _('Parametres langue entreprises')

    def __str__(self):
        return f'{self.company.name} — langues'


class UserLanguagePreference(models.Model):
    """Preference de langue d un utilisateur ERP."""
    user       = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='language_preferences', verbose_name=_('Utilisateur')
    )
    company    = models.ForeignKey(
        'core.Company', on_delete=models.CASCADE,
        null=True, blank=True, verbose_name=_('Entreprise')
    )
    language   = models.ForeignKey(
        Language, on_delete=models.CASCADE, verbose_name=_('Langue')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = _('Preference langue utilisateur')
        verbose_name_plural = _('Preferences langue utilisateurs')
        unique_together     = ['user', 'company']

    def __str__(self):
        return f'{self.user} — {self.language}'


class WebsiteLanguageSettings(models.Model):
    """Langues activees pour un site web."""
    website                   = models.OneToOneField(
        'websites.Website', on_delete=models.CASCADE,
        related_name='language_settings', verbose_name=_('Site web')
    )
    default_language          = models.ForeignKey(
        Language, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='default_for_websites', verbose_name=_('Langue par defaut')
    )
    enabled_languages         = models.ManyToManyField(
        Language, blank=True, related_name='enabled_for_websites',
        verbose_name=_('Langues activees')
    )
    show_language_switcher    = models.BooleanField(
        _('Afficher selecteur de langue'), default=True
    )
    use_language_prefix_urls  = models.BooleanField(
        _('URLs avec prefixe langue (/fr/, /en/)'), default=False
    )
    auto_redirect_by_browser  = models.BooleanField(
        _('Redirection auto selon navigateur'), default=False
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = _('Parametres langue site web')
        verbose_name_plural = _('Parametres langue sites web')

    def __str__(self):
        return f'{self.website.name} — langues'

    def get_enabled_language_list(self):
        return self.enabled_languages.filter(is_active=True).order_by('order', 'name')


class InterfaceTranslation(models.Model):
    """Traduction personnalisee d une cle interface pour une entreprise."""
    company         = models.ForeignKey(
        'core.Company', on_delete=models.CASCADE,
        null=True, blank=True, verbose_name=_('Entreprise')
    )
    key             = models.CharField(_('Cle'), max_length=200)
    language        = models.ForeignKey(Language, on_delete=models.CASCADE, verbose_name=_('Langue'))
    source_text     = models.TextField(_('Texte source'))
    translated_text = models.TextField(_('Traduction'))
    context         = models.CharField(_('Contexte'), max_length=200, blank=True)
    module          = models.CharField(_('Module'), max_length=100, blank=True,
                                       help_text='Ex: crm, sales, btp, dashboard')
    is_verified     = models.BooleanField(_('Verifiee'), default=False)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = _('Traduction interface')
        verbose_name_plural = _('Traductions interface')
        unique_together     = ['company', 'key', 'language']
        ordering            = ['module', 'key']

    def __str__(self):
        return f'{self.key} [{self.language.code}]'
