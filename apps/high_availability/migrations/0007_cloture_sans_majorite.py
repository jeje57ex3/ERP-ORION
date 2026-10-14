"""Clôture du serveur actif privé de majorité.

Exiger une majorité pour PROMOUVOIR interdit à une minorité d'élire un nouveau
chef (voir 0006). Cela ne suffit pourtant pas : le serveur DÉJÀ actif qui se
retrouve du mauvais côté d'une coupure continue de se croire actif et
d'accepter des écritures, tandis que la majorité en élit légitimement un
autre. Deux serveurs écrivent alors — la divergence, par un autre chemin que
celui que 0006 ferme.

D'où ces deux champs : le serveur actif vérifie périodiquement qu'il voit
encore une majorité, et refuse les écritures sinon.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('high_availability', '0006_arbitrage_par_quorum'),
    ]

    operations = [
        migrations.AddField(
            model_name='orionhasettings',
            name='quorum_perdu',
            field=models.BooleanField(default=False, help_text='Posé automatiquement : ce serveur actif ne voit plus une majorité de la grappe, et refuse donc les écritures.', verbose_name='Majorité perdue'),
        ),
        migrations.AddField(
            model_name='orionhasettings',
            name='quorum_perdu_depuis',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
