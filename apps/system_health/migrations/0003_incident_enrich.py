"""
Migration 0003 — Enrichissement du modèle SystemIncident

Ajout de champs de traçabilité, d'escalade, de contexte métier et de lien
vers les déploiements. Tous les champs sont nullable ou ont une valeur par
défaut — migration additive sans risque sur les données existantes.
"""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('system_health', '0002_healthsnapshot'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ── Nouveaux statuts d'incident ────────────────────────────────────────
        # (AlterField pour mettre à jour les choices sans toucher aux données)
        migrations.AlterField(
            model_name='systemincident',
            name='status',
            field=models.CharField(
                choices=[
                    ('detected',      'Détecté'),
                    ('confirmed',     'Confirmé'),
                    ('assigned',      'Assigné'),
                    ('investigating', 'En investigation'),
                    ('fixing',        'En correction'),
                    ('monitoring',    'Surveillance'),
                    ('resolved',      'Résolu'),
                    ('closed',        'Clôturé'),
                    ('reopened',      'Rouvert'),
                ],
                db_index=True,
                default='detected',
                max_length=20,
                verbose_name='Statut',
            ),
        ),

        # ── Champs de traçabilité / accusé de réception ────────────────────────
        migrations.AddField(
            model_name='systemincident',
            name='uid',
            field=models.CharField(
                blank=True, max_length=20, verbose_name='Référence',
                help_text='Format INC-XXXX — généré automatiquement'
            ),
        ),
        migrations.AddField(
            model_name='systemincident',
            name='acknowledged_at',
            field=models.DateTimeField(null=True, blank=True, verbose_name='Accusé le'),
        ),
        migrations.AddField(
            model_name='systemincident',
            name='acknowledged_by',
            field=models.ForeignKey(
                null=True, blank=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='acknowledged_incidents',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Accusé par',
            ),
        ),

        # ── Contexte technique ─────────────────────────────────────────────────
        migrations.AddField(
            model_name='systemincident',
            name='app_version',
            field=models.CharField(blank=True, max_length=50, verbose_name='Version app'),
        ),
        migrations.AddField(
            model_name='systemincident',
            name='component',
            field=models.CharField(
                blank=True, max_length=60, verbose_name='Composant',
                help_text='server | database | celery | redis | app | external_api…'
            ),
        ),

        # ── Contexte métier ────────────────────────────────────────────────────
        migrations.AddField(
            model_name='systemincident',
            name='business_module',
            field=models.CharField(
                blank=True, max_length=100, verbose_name='Module métier affecté',
            ),
        ),
        migrations.AddField(
            model_name='systemincident',
            name='affected_users_count',
            field=models.PositiveIntegerField(
                null=True, blank=True, verbose_name='Utilisateurs impactés (estimation)',
            ),
        ),

        # ── Équipe & escalade ──────────────────────────────────────────────────
        migrations.AddField(
            model_name='systemincident',
            name='team',
            field=models.JSONField(
                default=list, blank=True, verbose_name='Équipe assignée',
                help_text='[{"user_id": N, "role": "lead|support"}]'
            ),
        ),
        migrations.AddField(
            model_name='systemincident',
            name='aggravating_factors',
            field=models.TextField(blank=True, verbose_name='Facteurs aggravants'),
        ),
        migrations.AddField(
            model_name='systemincident',
            name='detection_delay_reason',
            field=models.TextField(blank=True, verbose_name='Raison du délai de détection'),
        ),

        # ── Lien déploiement ──────────────────────────────────────────────────
        # La FK vers orion_ops.Deployment est optionnelle — orion_ops peut ne
        # pas être encore installé lors d'un déploiement partiel.
        migrations.AddField(
            model_name='systemincident',
            name='probable_deployment_id',
            field=models.IntegerField(
                null=True, blank=True,
                verbose_name='ID déploiement probable',
                help_text='Lien souple vers orion_ops.Deployment — évite la dépendance circulaire',
            ),
        ),

        # ── Indicateurs de répétition ──────────────────────────────────────────
        migrations.AddField(
            model_name='systemincident',
            name='auto_created',
            field=models.BooleanField(
                default=False, verbose_name='Créé automatiquement',
                help_text='True si créé par le superviseur de capteurs',
            ),
        ),
        migrations.AddField(
            model_name='systemincident',
            name='reopen_count',
            field=models.PositiveSmallIntegerField(
                default=0, verbose_name='Nombre de réouvertures',
            ),
        ),

        # ── Impact SLO ────────────────────────────────────────────────────────
        migrations.AddField(
            model_name='systemincident',
            name='slo_impact',
            field=models.JSONField(
                default=dict, blank=True, verbose_name='Impact SLO',
                help_text='{slo_slug: {before_pct, breach_minutes}}'
            ),
        ),

        # ── PostIncidentReport — champs supplémentaires ────────────────────────
        migrations.AddField(
            model_name='postincidentreport',
            name='executive_summary',
            field=models.TextField(blank=True, verbose_name='Résumé exécutif'),
        ),
        migrations.AddField(
            model_name='postincidentreport',
            name='user_impact_detail',
            field=models.TextField(blank=True, verbose_name='Impact concret sur les utilisateurs'),
        ),
        migrations.AddField(
            model_name='postincidentreport',
            name='duration_minutes',
            field=models.PositiveIntegerField(
                null=True, blank=True, verbose_name='Durée (minutes)',
                help_text='Calculé automatiquement depuis started_at → resolved_at',
            ),
        ),
        migrations.AddField(
            model_name='postincidentreport',
            name='corrective_actions',
            field=models.JSONField(
                default=list, blank=True,
                verbose_name='Actions correctives',
                help_text='[{action, owner, due_date, status}]'
            ),
        ),
        migrations.AddField(
            model_name='postincidentreport',
            name='preventive_actions',
            field=models.JSONField(
                default=list, blank=True,
                verbose_name='Actions préventives',
                help_text='[{action, owner, due_date, status}]'
            ),
        ),
        migrations.AddField(
            model_name='postincidentreport',
            name='validated_by',
            field=models.ForeignKey(
                null=True, blank=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='validated_post_reports',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Validé par',
            ),
        ),
        migrations.AddField(
            model_name='postincidentreport',
            name='validated_at',
            field=models.DateTimeField(null=True, blank=True, verbose_name='Validé le'),
        ),
    ]
