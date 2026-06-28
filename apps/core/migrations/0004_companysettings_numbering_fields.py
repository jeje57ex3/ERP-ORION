from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_auditlog_module_old_values_new_values'),
    ]

    operations = [
        migrations.AddField(model_name='companysettings', name='next_purchase_order_number',
                            field=models.PositiveIntegerField(default=1)),
        migrations.AddField(model_name='companysettings', name='next_project_number',
                            field=models.PositiveIntegerField(default=1)),
        migrations.AddField(model_name='companysettings', name='next_ticket_number',
                            field=models.PositiveIntegerField(default=1)),
        migrations.AddField(model_name='companysettings', name='next_expense_report_number',
                            field=models.PositiveIntegerField(default=1)),
        migrations.AddField(model_name='companysettings', name='next_delivery_number',
                            field=models.PositiveIntegerField(default=1)),
        migrations.AddField(model_name='companysettings', name='next_return_number',
                            field=models.PositiveIntegerField(default=1)),
        migrations.AddField(model_name='companysettings', name='next_credit_note_number',
                            field=models.PositiveIntegerField(default=1)),
        migrations.AddField(model_name='companysettings', name='next_journal_entry_number',
                            field=models.PositiveIntegerField(default=1)),
    ]
