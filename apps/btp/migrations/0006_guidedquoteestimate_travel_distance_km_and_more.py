# Frais de déplacement du devis guidé : coordonnées du chantier (mises en
# cache après géocodage) et distance retenue dans l'estimation.
#
# Les AlterField sur btptimesheet.employee et electricitypricelibrary.
# product_family générés par makemigrations ont été retirés : ce sont des
# dérives de modèles préexistantes sans rapport avec cette fonctionnalité
# (même convention que la migration 0004 de cette app).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('btp', '0005_electricitypricelibrary_catalogue_produit'),
    ]

    operations = [
        migrations.AddField(
            model_name='guidedquoteestimate',
            name='travel_distance_km',
            field=models.DecimalField(decimal_places=1, default=0, help_text='Distance entreprise → chantier ; le déplacement est facturé aller-retour.', max_digits=7, verbose_name='Distance aller (km)'),
        ),
        migrations.AddField(
            model_name='guidedquoterequest',
            name='site_latitude',
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True, verbose_name='Latitude chantier'),
        ),
        migrations.AddField(
            model_name='guidedquoterequest',
            name='site_longitude',
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True, verbose_name='Longitude chantier'),
        ),
    ]
