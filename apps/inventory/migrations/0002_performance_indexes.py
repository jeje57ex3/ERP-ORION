"""Index de performance sur les modèles Inventory."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0001_initial'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='product',
            index=models.Index(fields=['company', 'is_active'], name='inv_prod_co_active_idx'),
        ),
        migrations.AddIndex(
            model_name='product',
            index=models.Index(fields=['company', 'reference'], name='inv_prod_co_ref_idx'),
        ),
        migrations.AddIndex(
            model_name='stockmovement',
            index=models.Index(fields=['company', 'movement_date'], name='inv_mov_co_date_idx'),
        ),
        migrations.AddIndex(
            model_name='stockmovement',
            index=models.Index(fields=['product', 'movement_type'], name='inv_mov_prod_type_idx'),
        ),
        migrations.AddIndex(
            model_name='stockmovement',
            index=models.Index(fields=['company', 'movement_type'], name='inv_mov_co_type_idx'),
        ),
    ]
