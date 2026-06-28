"""Index de performance sur les modèles CRM."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0002_remove_customer_unique_together'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='customer',
            index=models.Index(fields=['company', 'created_at'], name='crm_cust_co_date_idx'),
        ),
    ]
