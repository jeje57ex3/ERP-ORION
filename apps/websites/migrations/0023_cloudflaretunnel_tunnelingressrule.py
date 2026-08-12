# Restaure CloudflareTunnel/TunnelIngressRule — les classes avaient été
# retirées de models_domains.py sans migration ni nettoyage des vues
# (apps/websites/views_cloudflare.py, views_tunnel.py), alors que les
# tables existaient toujours en base avec des données réelles (1 compte,
# 2 tunnels, 8 règles d'ingress). Schéma identique à la migration
# d'origine (0013_cloudflare_tunnel, jamais commitée sur git) — voir
# commit de restauration pour le détail.

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        # 0007/0008 n'ont jamais été commitées sur git (migrations
        # orphelines locales, même piège que ae171f5) — 0006 est la
        # dernière migration core réellement présente en dépôt.
        ('core', '0006_notification_related_names'),
        ('websites', '0022_websitedomain_website_nullable'),
    ]

    operations = [
        migrations.CreateModel(
            name='CloudflareTunnel',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tunnel_id', models.CharField(blank=True, help_text='UUID du tunnel (ex: f4aa00aa-1df4-41f9-b676-946933560b2f)', max_length=100, verbose_name='ID Tunnel')),
                ('name', models.CharField(max_length=100, verbose_name='Nom')),
                ('credentials_file', models.CharField(blank=True, help_text='Chemin vers le .json de credentials cloudflared', max_length=500, verbose_name='Fichier credentials')),
                ('config_file', models.CharField(blank=True, help_text='Chemin vers config.yml (ex: C:\\Users\\jessy\\.cloudflared\\config.yml)', max_length=500, verbose_name='Fichier config.yml')),
                ('is_active', models.BooleanField(default=True, verbose_name='Actif')),
                ('notes', models.TextField(blank=True, verbose_name='Notes')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('cloudflare_account', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='tunnels', to='websites.cloudflareaccount', verbose_name='Compte Cloudflare')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cloudflare_tunnels', to='core.company', verbose_name='Entreprise')),
            ],
            options={
                'verbose_name': 'Tunnel Cloudflare',
                'verbose_name_plural': 'Tunnels Cloudflare',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='TunnelIngressRule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('hostname', models.CharField(help_text='Ex: login.elysiums.fr (sans https://)', max_length=253, verbose_name='Hostname')),
                ('service', models.CharField(help_text='Ex: http://localhost:8000', max_length=200, verbose_name='Service local')),
                ('order', models.PositiveSmallIntegerField(default=0, verbose_name='Ordre')),
                ('is_active', models.BooleanField(default=True, verbose_name='Actif')),
                ('dns_synced', models.BooleanField(default=False, verbose_name='DNS synchronisé')),
                ('dns_synced_at', models.DateTimeField(blank=True, null=True, verbose_name='DNS sync à')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('tunnel', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ingress_rules', to='websites.cloudflaretunnel', verbose_name='Tunnel')),
                ('website', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='tunnel_rules', to='websites.website', verbose_name='Site associé')),
            ],
            options={
                'verbose_name': "Règle d'ingress",
                'verbose_name_plural': "Règles d'ingress",
                'ordering': ['order', 'hostname'],
            },
        ),
    ]
