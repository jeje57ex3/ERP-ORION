"""
Sépare Néostructura, Siècle et Lunea en entreprises distinctes.

- Renomme l'entreprise technique "siecle" en "Siècle" (elle porte déjà
  exclusivement le site Siècle — pas besoin de la recréer).
- Crée "Néostructura" et "Lunea" si elles n'existent pas encore.

Idempotent : peut être rejouée sans effet si les entreprises existent déjà
(comparaison insensible à la casse), pour rester sûre à exécuter sur des
bases dans des états différents (dev/prod).
"""
from django.db import migrations


def seed_companies(apps, schema_editor):
    from apps.private_saas.services import create_private_company

    Company = apps.get_model('core', 'Company')

    siecle = Company.objects.filter(name__iexact='siecle').first()
    if siecle and siecle.name != 'Siècle':
        siecle.name = 'Siècle'
        siecle.sector = 'watch'
        siecle.save(update_fields=['name', 'sector'])

    if not Company.objects.filter(name__iexact='Néostructura').exists():
        create_private_company(name='Néostructura', company_type='generic')

    if not Company.objects.filter(name__iexact='Lunea').exists():
        create_private_company(name='Lunea', company_type='beauty')


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_notification_related_names'),
        # create_private_company() -> seed_company_modules() écrit dans
        # CompanyModule (private_saas) : sans cette dépendance explicite,
        # une base neuve peut appliquer cette migration avant que la table
        # existe (ordre topologique non garanti entre apps indépendantes).
        ('private_saas', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_companies, noop_reverse),
    ]
