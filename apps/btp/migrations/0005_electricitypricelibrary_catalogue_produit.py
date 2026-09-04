from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('btp', '0004_guidedquoterequest_electricite_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='electricitypricelibrary',
            name='metier',
            field=models.CharField(
                blank=True, default='', max_length=20,
                choices=[
                    ('', "Interne uniquement (main-d'œuvre, déplacement...)"),
                    ('electricite', 'Électricité générale'), ('domotique', 'Domotique'),
                    ('etancheite', 'Étanchéité'), ('informatique', 'Informatique & Réseaux'),
                    ('renovation', 'Rénovation'), ('maintenance', 'Maintenance'),
                ],
                verbose_name='Métier (configurateur public)',
            ),
        ),
        migrations.AddField(
            model_name='electricitypricelibrary',
            name='product_family',
            field=models.CharField(blank=True, default='', max_length=100, verbose_name='Famille de produit'),
        ),
        migrations.AddField(
            model_name='electricitypricelibrary',
            name='quality_level',
            field=models.CharField(
                choices=[('standard', 'Standard'), ('premium', 'Premium'), ('luxe', 'Luxe / Haut de gamme')],
                default='standard', max_length=10, verbose_name='Gamme',
            ),
        ),
        migrations.AddField(
            model_name='electricitypricelibrary',
            name='brand',
            field=models.CharField(blank=True, default='', max_length=100, verbose_name='Marque'),
        ),
        migrations.AddField(
            model_name='electricitypricelibrary',
            name='reference',
            field=models.CharField(blank=True, default='', max_length=100, verbose_name='Référence produit'),
        ),
    ]
