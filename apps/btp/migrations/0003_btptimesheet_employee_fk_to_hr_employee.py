from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('btp', '0002_clientconversation_clientmessage_documentcategory_and_more'),
        ('hr', '0004_employee_user_related_name'),
    ]

    operations = [
        migrations.AlterField(
            model_name='btptimesheet',
            name='employee',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='btp_timesheets',
                to='hr.employee',
                verbose_name='Employé',
            ),
        ),
    ]
