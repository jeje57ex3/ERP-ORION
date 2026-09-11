from django.db import migrations, models


CHECK_TYPE_CHOICES = [
    ('database', 'Base de données'), ('cache', 'Cache'),
    ('storage', 'Stockage'), ('email', 'E-mail'),
    ('external_api', 'API externe'), ('queue', 'File de tâches'),
    ('disk_space', 'Espace disque'), ('memory', 'Mémoire'),
    ('cpu', 'CPU'), ('backup', 'Sauvegardes'),
    ('website', 'Site web'), ('ssl', 'Certificat SSL'),
    ('migrations', 'Migrations'), ('custom', 'Personnalisé'),
]


class Migration(migrations.Migration):

    dependencies = [
        ('system_observability', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='systemhealthcheck',
            name='check_type',
            field=models.CharField(choices=CHECK_TYPE_CHOICES, max_length=80),
        ),
        migrations.AlterField(
            model_name='systemalertrule',
            name='check_type',
            field=models.CharField(choices=CHECK_TYPE_CHOICES, max_length=80),
        ),
        migrations.AlterField(
            model_name='systemobservabilityalert',
            name='alert_type',
            field=models.CharField(choices=CHECK_TYPE_CHOICES, max_length=80),
        ),
    ]
