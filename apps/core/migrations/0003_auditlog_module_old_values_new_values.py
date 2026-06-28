from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_company_database_archived_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='auditlog',
            name='module',
            field=models.CharField(blank=True, max_length=50, verbose_name='Module'),
        ),
        migrations.AddField(
            model_name='auditlog',
            name='old_values',
            field=models.JSONField(blank=True, null=True, verbose_name='Anciennes valeurs'),
        ),
        migrations.AddField(
            model_name='auditlog',
            name='new_values',
            field=models.JSONField(blank=True, null=True, verbose_name='Nouvelles valeurs'),
        ),
        migrations.AlterField(
            model_name='auditlog',
            name='action',
            field=models.CharField(
                choices=[
                    ('create', 'Création'),
                    ('update', 'Modification'),
                    ('delete', 'Suppression'),
                    ('login', 'Connexion'),
                    ('logout', 'Déconnexion'),
                    ('view', 'Consultation'),
                    ('export', 'Export'),
                    ('import', 'Import'),
                    ('validate', 'Validation'),
                    ('reject', 'Rejet'),
                    ('payment', 'Paiement'),
                    ('download', 'Téléchargement'),
                    ('upload', 'Upload'),
                    ('permission_change', 'Changement permission'),
                    ('db_create', 'Création base'),
                    ('db_delete', 'Suppression base'),
                    ('db_backup', 'Sauvegarde base'),
                    ('other', 'Autre'),
                ],
                max_length=20,
                verbose_name='Action',
            ),
        ),
        migrations.AddIndex(
            model_name='auditlog',
            index=models.Index(fields=['company', 'created_at'], name='audit_comp_cre_idx'),
        ),
        migrations.AddIndex(
            model_name='auditlog',
            index=models.Index(fields=['user', 'action'], name='audit_usr_act_idx'),
        ),
        migrations.AddIndex(
            model_name='auditlog',
            index=models.Index(fields=['model_name', 'object_id'], name='audit_mod_obj_idx'),
        ),
    ]
