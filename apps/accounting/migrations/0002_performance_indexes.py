"""Index de performance sur les modèles Accounting."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0001_initial'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='journalentry',
            index=models.Index(fields=['company', 'status'], name='acc_je_co_status_idx'),
        ),
        migrations.AddIndex(
            model_name='journalentry',
            index=models.Index(fields=['company', 'entry_date'], name='acc_je_co_date_idx'),
        ),
        migrations.AddIndex(
            model_name='journalentry',
            index=models.Index(fields=['company', 'journal'], name='acc_je_co_journal_idx'),
        ),
        migrations.AddIndex(
            model_name='journalentryline',
            index=models.Index(fields=['account'], name='acc_jel_account_idx'),
        ),
        migrations.AddIndex(
            model_name='journalentryline',
            index=models.Index(fields=['reconciliation_code'], name='acc_jel_reconcil_idx'),
        ),
        migrations.AddIndex(
            model_name='account',
            index=models.Index(fields=['company', 'number'], name='acc_acct_co_num_idx'),
        ),
        migrations.AddIndex(
            model_name='fiscalyear',
            index=models.Index(fields=['company', 'status'], name='acc_fy_co_status_idx'),
        ),
    ]
