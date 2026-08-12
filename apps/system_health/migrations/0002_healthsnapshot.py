from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('system_health', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='HealthSnapshot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('global_score',    models.PositiveSmallIntegerField(verbose_name='Score global')),
                ('global_status',   models.CharField(max_length=20, verbose_name='Statut',
                                    choices=[('healthy','Sain'),('degraded','Dégradé'),
                                             ('unstable','Instable'),('critical','Critique'),
                                             ('unavailable','Indisponible'),('unknown','Inconnu')])),
                ('server_score',    models.PositiveSmallIntegerField(default=0, verbose_name='Serveur')),
                ('app_score',       models.PositiveSmallIntegerField(default=0, verbose_name='Application')),
                ('database_score',  models.PositiveSmallIntegerField(default=0, verbose_name='Base de données')),
                ('backups_score',   models.PositiveSmallIntegerField(default=0, verbose_name='Sauvegardes')),
                ('security_score',  models.PositiveSmallIntegerField(default=0, verbose_name='Sécurité')),
                ('celery_score',    models.PositiveSmallIntegerField(default=0, verbose_name='Celery')),
                ('critical_sensors', models.JSONField(default=list, verbose_name='Capteurs critiques')),
                ('warning_sensors',  models.JSONField(default=list, verbose_name='Capteurs en alerte')),
                ('collected_at',    models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Enregistré à')),
            ],
            options={
                'verbose_name': 'Snapshot de santé',
                'verbose_name_plural': 'Historique de santé',
                'ordering': ['-collected_at'],
            },
        ),
        migrations.AddIndex(
            model_name='healthsnapshot',
            index=models.Index(fields=['-collected_at'], name='system_heal_collect_idx'),
        ),
    ]
