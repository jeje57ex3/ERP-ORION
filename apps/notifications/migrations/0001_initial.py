"""
Migration initiale — apps.notifications
Table : notifications_notification
"""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('core', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('notification_type', models.CharField(
                    choices=[
                        ('validation_pending', 'Validation en attente'),
                        ('message_received', 'Message reçu'),
                        ('quote_accepted', 'Devis accepté'),
                        ('invoice_overdue', 'Facture en retard'),
                        ('document_signed', 'Document signé'),
                        ('project_updated', 'Chantier mis à jour'),
                        ('stock_low', 'Stock faible'),
                        ('web_order', 'Commande web reçue'),
                        ('leave_request', 'Congé demandé'),
                        ('expense_validated', 'Note de frais validée'),
                        ('system', 'Système'),
                        ('info', 'Information'),
                        ('warning', 'Avertissement'),
                        ('error', 'Erreur'),
                    ],
                    default='info',
                    max_length=50,
                    verbose_name='Type',
                )),
                ('priority', models.CharField(
                    choices=[
                        ('low', 'Basse'),
                        ('normal', 'Normale'),
                        ('high', 'Haute'),
                        ('urgent', 'Urgente'),
                    ],
                    default='normal',
                    max_length=10,
                    verbose_name='Priorité',
                )),
                ('title', models.CharField(max_length=200, verbose_name='Titre')),
                ('message', models.TextField(blank=True, verbose_name='Message')),
                ('icon', models.CharField(default='bi-bell', max_length=50, verbose_name='Icône')),
                ('icon_color', models.CharField(default='primary', max_length=20, verbose_name='Couleur icône')),
                ('link_url', models.CharField(blank=True, max_length=500, verbose_name='URL lien')),
                ('link_label', models.CharField(blank=True, max_length=100, verbose_name='Libellé lien')),
                ('source_module', models.CharField(blank=True, max_length=50, verbose_name='Module source')),
                ('source_model', models.CharField(blank=True, max_length=100, verbose_name='Modèle source')),
                ('source_id', models.PositiveIntegerField(blank=True, null=True, verbose_name='ID source')),
                ('is_read', models.BooleanField(default=False, verbose_name='Lu')),
                ('read_at', models.DateTimeField(blank=True, null=True, verbose_name='Lu le')),
                ('email_sent', models.BooleanField(default=False, verbose_name='Email envoyé')),
                ('email_sent_at', models.DateTimeField(blank=True, null=True, verbose_name='Email envoyé le')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Créée le')),
                ('company', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    to='core.company',
                    verbose_name='Entreprise',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='erp_notifications',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Utilisateur',
                )),
            ],
            options={
                'verbose_name': 'Notification',
                'verbose_name_plural': 'Notifications',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='notification',
            index=models.Index(fields=['user', 'is_read', '-created_at'], name='notif_user_read_idx'),
        ),
        migrations.AddIndex(
            model_name='notification',
            index=models.Index(fields=['company', '-created_at'], name='notif_company_idx'),
        ),
    ]
