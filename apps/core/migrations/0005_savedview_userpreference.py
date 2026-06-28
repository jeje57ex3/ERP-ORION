"""
Migration — ajout SavedView et UserPreference dans apps.core
"""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_companysettings_numbering_fields'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SavedView',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('module', models.CharField(max_length=50, verbose_name='Module')),
                ('name', models.CharField(max_length=100, verbose_name='Nom de la vue')),
                ('filters_json', models.JSONField(blank=True, default=dict, verbose_name='Filtres')),
                ('columns_json', models.JSONField(blank=True, default=list, verbose_name='Colonnes')),
                ('sort_json', models.JSONField(blank=True, default=dict, verbose_name='Tri')),
                ('is_default', models.BooleanField(default=False, verbose_name='Par défaut')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='saved_views',
                    to='core.company',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='saved_views',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Vue sauvegardée',
                'verbose_name_plural': 'Vues sauvegardées',
                'ordering': ['module', 'name'],
                'unique_together': {('user', 'company', 'module', 'name')},
            },
        ),
        migrations.CreateModel(
            name='UserPreference',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('theme', models.CharField(
                    choices=[
                        ('light', 'Clair'),
                        ('dark', 'Sombre'),
                        ('system', 'Système'),
                    ],
                    default='light',
                    max_length=10,
                    verbose_name='Thème',
                )),
                ('compact_mode', models.BooleanField(default=False, verbose_name='Mode compact')),
                ('sidebar_collapsed', models.BooleanField(default=False, verbose_name='Sidebar réduite')),
                ('default_dashboard', models.CharField(blank=True, max_length=50, verbose_name='Dashboard par défaut')),
                ('items_per_page', models.PositiveIntegerField(default=25, verbose_name='Éléments par page')),
                ('language', models.CharField(default='fr', max_length=10, verbose_name='Langue')),
                ('email_notifications', models.BooleanField(default=True, verbose_name='Notif. email')),
                ('erp_notifications', models.BooleanField(default=True, verbose_name='Notif. ERP')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='preference',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Préférences utilisateur',
                'verbose_name_plural': 'Préférences utilisateurs',
            },
        ),
    ]
