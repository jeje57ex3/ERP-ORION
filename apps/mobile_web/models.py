"""Trace des envois de photos venus du téléphone.

Une file d'attente hors ligne renvoie ce qui n'est pas passé. Elle ne peut
donc pas savoir si un envoi a échoué AVANT ou APRÈS l'enregistrement côté
serveur : une coupure pendant la réponse — le cas le plus banal sur un
chantier — laisse la photo enregistrée et la file persuadée du contraire. Au
prochain réseau, elle la renvoie, et le chantier se retrouve avec deux fois la
même photo.

D'où cette table : le téléphone attribue une clé à chaque envoi, le serveur la
retient, et un envoi déjà vu est reconnu au lieu d'être refait. Sans elle, la
file d'attente produirait des doublons précisément dans la situation de réseau
instable qui la justifie.
"""

from django.conf import settings
from django.db import models


class EnvoiPhotoMobile(models.Model):
    """Un envoi de photos identifié par le téléphone qui l'a produit."""

    cle = models.CharField(
        'Clé d’envoi',
        max_length=64,
        unique=True,
        help_text='Générée par le téléphone, une par envoi mis en file.',
    )

    company = models.ForeignKey(
        'core.Company',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='envois_photos_mobiles',
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='envois_photos_mobiles',
    )

    photos = models.PositiveIntegerField('Photos enregistrées', default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'mobile_web'
        verbose_name = 'Envoi de photos (téléphone)'
        verbose_name_plural = 'Envois de photos (téléphone)'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.cle} — {self.photos} photo(s)'
