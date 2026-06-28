# Generated migration for websites app
# Adds: slug/is_published/published_at/unpublished_at/maintenance_mode/home_page to Website
# Creates: WebsiteDomain, WebsiteMedia, WebsiteForm, WebsiteFormField,
#          WebsiteFormSubmission, WebsiteAnalyticsEvent

import django.db.models.deletion
import django.db.models.functions
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('websites', '0003_add_show_powered_by_orion'),
        ('core', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ── New fields on Website ──────────────────────────────────────────────
        migrations.AddField(
            model_name='website',
            name='slug',
            field=models.SlugField('Slug', max_length=100, blank=True),
        ),
        migrations.AddField(
            model_name='website',
            name='is_published',
            field=models.BooleanField('Publié', default=False),
        ),
        migrations.AddField(
            model_name='website',
            name='published_at',
            field=models.DateTimeField('Publié le', null=True, blank=True),
        ),
        migrations.AddField(
            model_name='website',
            name='unpublished_at',
            field=models.DateTimeField('Dépublié le', null=True, blank=True),
        ),
        migrations.AddField(
            model_name='website',
            name='maintenance_mode',
            field=models.BooleanField('Mode maintenance', default=False),
        ),
        migrations.AddField(
            model_name='website',
            name='home_page',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='+',
                to='websites.websitepage',
                verbose_name="Page d'accueil",
            ),
        ),

        # ── WebsiteDomain ──────────────────────────────────────────────────────
        migrations.CreateModel(
            name='WebsiteDomain',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('domain', models.CharField(max_length=253, verbose_name='Domaine')),
                ('domain_type', models.CharField(
                    choices=[
                        ('root', 'Domaine racine'),
                        ('subdomain', 'Sous-domaine'),
                        ('test', 'Domaine de test'),
                        ('temporary', 'Domaine temporaire Orion'),
                    ],
                    default='subdomain',
                    max_length=20,
                    verbose_name='Type',
                )),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'À configurer'),
                        ('dns_pending', 'En attente DNS'),
                        ('dns_verified', 'DNS vérifié'),
                        ('ssl_pending', 'SSL en attente'),
                        ('active', 'Actif'),
                        ('error', 'Erreur'),
                        ('disabled', 'Désactivé'),
                    ],
                    default='pending',
                    max_length=20,
                    verbose_name='Statut',
                )),
                ('is_primary', models.BooleanField(default=False, verbose_name='Domaine principal')),
                ('dns_verified', models.BooleanField(default=False, verbose_name='DNS vérifié')),
                ('dns_verified_at', models.DateTimeField(blank=True, null=True, verbose_name='Vérifié le')),
                ('ssl_enabled', models.BooleanField(default=False, verbose_name='SSL activé')),
                ('ssl_status', models.CharField(
                    choices=[
                        ('none', 'Non configuré'),
                        ('pending', 'En attente'),
                        ('active', 'Actif'),
                        ('expired', 'Expiré'),
                        ('error', 'Erreur'),
                    ],
                    default='none',
                    max_length=10,
                    verbose_name='Statut SSL',
                )),
                ('ssl_expires_at', models.DateField(blank=True, null=True, verbose_name='Expiration SSL')),
                ('verification_token', models.CharField(blank=True, max_length=64, verbose_name='Token de vérification')),
                ('expected_cname', models.CharField(
                    blank=True,
                    default='sites.orion-erp.com',
                    max_length=253,
                    verbose_name='CNAME attendu',
                )),
                ('expected_txt_record', models.CharField(blank=True, max_length=300, verbose_name='TXT attendu')),
                ('last_checked_at', models.DateTimeField(blank=True, null=True, verbose_name='Dernier check')),
                ('last_error', models.TextField(blank=True, verbose_name='Dernière erreur')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('website', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='domains',
                    to='websites.website',
                )),
            ],
            options={
                'verbose_name': 'Domaine site web',
                'verbose_name_plural': 'Domaines sites web',
                'ordering': ['-is_primary', 'domain'],
            },
        ),
        migrations.AlterUniqueTogether(
            name='websitedomain',
            unique_together={('website', 'domain')},
        ),

        # ── WebsiteMedia ───────────────────────────────────────────────────────
        migrations.CreateModel(
            name='WebsiteMedia',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(upload_to='websites/media/%Y/%m/', verbose_name='Fichier')),
                ('title', models.CharField(blank=True, max_length=200, verbose_name='Titre')),
                ('alt_text', models.CharField(blank=True, max_length=200, verbose_name='Texte alternatif')),
                ('caption', models.CharField(blank=True, max_length=300, verbose_name='Légende')),
                ('media_type', models.CharField(
                    choices=[
                        ('image', 'Image'),
                        ('video', 'Vidéo'),
                        ('pdf', 'PDF'),
                        ('document', 'Document'),
                        ('icon', 'Icône'),
                        ('logo', 'Logo'),
                        ('favicon', 'Favicon'),
                        ('other', 'Autre'),
                    ],
                    default='image',
                    max_length=20,
                    verbose_name='Type',
                )),
                ('file_size', models.PositiveIntegerField(default=0, verbose_name='Taille fichier (octets)')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='website_media',
                    to='core.company',
                )),
                ('website', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='media_files',
                    to='websites.website',
                )),
                ('uploaded_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Média site web',
                'verbose_name_plural': 'Médias sites web',
                'ordering': ['-created_at'],
            },
        ),

        # ── WebsiteForm ────────────────────────────────────────────────────────
        migrations.CreateModel(
            name='WebsiteForm',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='Nom interne')),
                ('form_type', models.CharField(
                    choices=[
                        ('contact', 'Contact'),
                        ('quote', 'Demande de devis'),
                        ('repair', 'Dépannage'),
                        ('works', 'Travaux'),
                        ('booking', 'Réservation'),
                        ('support', 'Support'),
                        ('newsletter', 'Newsletter'),
                        ('application', 'Candidature'),
                        ('other', 'Autre'),
                    ],
                    default='contact',
                    max_length=20,
                    verbose_name='Type',
                )),
                ('title', models.CharField(blank=True, max_length=200, verbose_name='Titre affiché')),
                ('description', models.TextField(blank=True, verbose_name='Description')),
                ('success_message', models.TextField(
                    default='Merci, votre message a été envoyé.',
                    verbose_name='Message succès',
                )),
                ('send_notification_email', models.BooleanField(default=True, verbose_name='Email de notification')),
                ('notification_email', models.EmailField(blank=True, verbose_name='Email destinataire')),
                ('create_crm_prospect', models.BooleanField(default=False, verbose_name='Créer prospect CRM')),
                ('create_client_request', models.BooleanField(default=False, verbose_name='Créer demande client')),
                ('create_support_ticket', models.BooleanField(default=False, verbose_name='Créer ticket support')),
                ('is_active', models.BooleanField(default=True, verbose_name='Actif')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('website', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='advanced_forms',
                    to='websites.website',
                )),
            ],
            options={
                'verbose_name': 'Formulaire site web',
                'verbose_name_plural': 'Formulaires sites web',
            },
        ),

        # ── WebsiteFormField ───────────────────────────────────────────────────
        migrations.CreateModel(
            name='WebsiteFormField',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('label', models.CharField(max_length=100, verbose_name='Libellé')),
                ('field_type', models.CharField(
                    choices=[
                        ('text', 'Texte'),
                        ('email', 'Email'),
                        ('phone', 'Téléphone'),
                        ('textarea', 'Zone de texte'),
                        ('select', 'Liste déroulante'),
                        ('checkbox', 'Case à cocher'),
                        ('radio', 'Bouton radio'),
                        ('file', 'Fichier'),
                        ('date', 'Date'),
                        ('number', 'Nombre'),
                        ('hidden', 'Champ caché'),
                    ],
                    default='text',
                    max_length=20,
                    verbose_name='Type',
                )),
                ('placeholder', models.CharField(blank=True, max_length=200, verbose_name='Placeholder')),
                ('help_text', models.CharField(blank=True, max_length=300, verbose_name='Aide')),
                ('is_required', models.BooleanField(default=False, verbose_name='Obligatoire')),
                ('choices', models.TextField(blank=True, verbose_name='Choix (un par ligne)')),
                ('order', models.PositiveIntegerField(default=0, verbose_name='Ordre')),
                ('form', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='fields',
                    to='websites.websiteform',
                )),
            ],
            options={
                'verbose_name': 'Champ formulaire',
                'ordering': ['order'],
            },
        ),

        # ── WebsiteFormSubmission ──────────────────────────────────────────────
        migrations.CreateModel(
            name='WebsiteFormSubmission',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(blank=True, max_length=100, verbose_name='Nom')),
                ('email', models.EmailField(blank=True, verbose_name='Email')),
                ('phone', models.CharField(blank=True, max_length=20, verbose_name='Téléphone')),
                ('subject', models.CharField(blank=True, max_length=200, verbose_name='Sujet')),
                ('message', models.TextField(blank=True, verbose_name='Message')),
                ('data', models.JSONField(default=dict, verbose_name='Données brutes')),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True, verbose_name='IP')),
                ('user_agent', models.TextField(blank=True, verbose_name='User agent')),
                ('status', models.CharField(
                    choices=[
                        ('new', 'Nouvelle'),
                        ('read', 'Lue'),
                        ('processing', 'En traitement'),
                        ('converted_prospect', 'Convertie en prospect'),
                        ('converted_request', 'Convertie en demande'),
                        ('done', 'Traitée'),
                        ('archived', 'Archivée'),
                    ],
                    default='new',
                    max_length=25,
                    verbose_name='Statut',
                )),
                ('created_prospect', models.BooleanField(default=False, verbose_name='Prospect créé')),
                ('created_request', models.BooleanField(default=False, verbose_name='Demande créée')),
                ('created_ticket', models.BooleanField(default=False, verbose_name='Ticket créé')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('website', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='form_submissions',
                    to='websites.website',
                )),
                ('form', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='submissions',
                    to='websites.websiteform',
                )),
            ],
            options={
                'verbose_name': 'Soumission formulaire',
                'verbose_name_plural': 'Soumissions formulaires',
                'ordering': ['-created_at'],
            },
        ),

        # ── WebsiteAnalyticsEvent ──────────────────────────────────────────────
        migrations.CreateModel(
            name='WebsiteAnalyticsEvent',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event_type', models.CharField(
                    choices=[
                        ('page_view', 'Vue de page'),
                        ('form_submission', 'Soumission formulaire'),
                        ('button_click', 'Clic bouton'),
                        ('product_view', 'Vue produit'),
                        ('add_to_cart', 'Ajout panier'),
                        ('checkout_started', 'Commande démarrée'),
                        ('order_completed', 'Commande complétée'),
                    ],
                    default='page_view',
                    max_length=25,
                    verbose_name='Type',
                )),
                ('path', models.CharField(max_length=500, verbose_name='Chemin')),
                ('referrer', models.CharField(blank=True, max_length=500, verbose_name='Référent')),
                ('ip_address_hash', models.CharField(blank=True, max_length=64, verbose_name='Hash IP')),
                ('user_agent', models.CharField(blank=True, max_length=300, verbose_name='User agent')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('website', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='analytics_events',
                    to='websites.website',
                )),
            ],
            options={
                'verbose_name': 'Événement analytics',
                'verbose_name_plural': 'Événements analytics',
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['website', 'event_type', 'created_at'], name='websites_we_website_evtype_created_idx'),
                    models.Index(fields=['website', 'path'], name='websites_we_website_path_idx'),
                ],
            },
        ),
    ]
