# Migration manuelle (isolée) — ajoute uniquement les champs requis par le site
# public Électricité : quality_level (niveau de gamme du configurateur) et
# crm_prospect (traçabilité CRM). Générée manuellement plutôt que via
# `makemigrations` pour éviter d'embarquer des changements de modèles sans
# rapport déjà en attente ailleurs dans le dépôt (ex: btptimesheet.employee).
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0004_remove_customer_crm_cust_co_date_idx'),
        ('btp', '0003_btptimesheet_employee_fk_to_hr_employee'),
    ]

    operations = [
        migrations.AddField(
            model_name='guidedquoterequest',
            name='quality_level',
            field=models.CharField(choices=[('standard', 'Standard'), ('premium', 'Premium'), ('luxe', 'Luxe')], default='standard', max_length=10, verbose_name='Niveau de gamme'),
        ),
        migrations.AddField(
            model_name='guidedquoterequest',
            name='crm_prospect',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='guided_quote_requests', to='crm.prospect'),
        ),
    ]
