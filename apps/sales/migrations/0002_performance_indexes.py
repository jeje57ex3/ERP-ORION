"""Index de performance sur les modèles Sales."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0001_initial'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='invoice',
            index=models.Index(fields=['company', 'status'], name='sales_inv_co_status_idx'),
        ),
        migrations.AddIndex(
            model_name='invoice',
            index=models.Index(fields=['company', 'issue_date'], name='sales_inv_co_date_idx'),
        ),
        migrations.AddIndex(
            model_name='invoice',
            index=models.Index(fields=['company', 'due_date'], name='sales_inv_co_due_idx'),
        ),
        migrations.AddIndex(
            model_name='invoice',
            index=models.Index(fields=['customer'], name='sales_inv_customer_idx'),
        ),
        migrations.AddIndex(
            model_name='quote',
            index=models.Index(fields=['company', 'status'], name='sales_qte_co_status_idx'),
        ),
        migrations.AddIndex(
            model_name='quote',
            index=models.Index(fields=['company', 'issue_date'], name='sales_qte_co_date_idx'),
        ),
        migrations.AddIndex(
            model_name='salesorder',
            index=models.Index(fields=['company', 'status'], name='sales_ord_co_status_idx'),
        ),
    ]
