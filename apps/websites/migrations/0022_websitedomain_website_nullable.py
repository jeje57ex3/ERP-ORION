from django.db import migrations, models
import django.db.models.deletion


def backfill_company(apps, schema_editor):
    """Renseigne WebsiteDomain.company depuis website.company pour les
    domaines créés avant que ce champ direct existe (ex: ajout de domaine
    depuis la page d'un site — apps/websites/views.py) — nécessaire pour que
    le scoping par company (au lieu de website__company, cassé pour les
    domaines sans website) retrouve aussi ces domaines historiques.
    Boucle Python car F() ne supporte pas les traversées de relation dans
    un .update()."""
    WebsiteDomain = apps.get_model('websites', 'WebsiteDomain')
    qs = WebsiteDomain.objects.filter(
        company__isnull=True, website__isnull=False,
    ).select_related('website')
    for domain in qs:
        domain.company_id = domain.website.company_id
        domain.save(update_fields=['company'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        # 0012-0021 existent en local (poste de dev) mais n'ont jamais été
        # commitées sur git — elles correspondent à d'anciens modèles déjà
        # retirés de models.py depuis (CloudflareTunnel, CustomerAddress...),
        # donc orphelines et volontairement ignorées ici. 0011 est la
        # dernière migration réellement commitée/déployée.
        ('websites', '0011_domain_management'),
    ]

    operations = [
        migrations.AlterField(
            model_name='websitedomain',
            name='website',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='domains', to='websites.website',
            ),
        ),
        migrations.RunPython(backfill_company, noop),
    ]
