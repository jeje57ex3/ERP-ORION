from django.urls import path
from . import views

app_name = 'accounting'

urlpatterns = [
    path('', views.index, name='index'),
    path('tableau-de-bord/', views.dashboard, name='dashboard'),

    # Plan comptable
    path('comptes/', views.account_list, name='account_list'),
    path('comptes/nouveau/', views.account_create, name='account_create'),
    path('comptes/<int:pk>/modifier/', views.account_edit, name='account_edit'),

    # Journaux
    path('journaux/', views.journal_list, name='journal_list'),
    path('journaux/nouveau/', views.journal_create, name='journal_create'),

    # Exercices & Périodes
    path('exercices/', views.fiscal_year_list, name='fiscal_year_list'),
    path('exercices/<int:year_pk>/periodes/', views.period_list, name='period_list'),

    # Écritures
    path('ecritures/', views.entry_list, name='entry_list'),
    path('ecritures/nouvelle/', views.entry_create, name='entry_create'),
    path('ecritures/<int:pk>/', views.entry_detail, name='entry_detail'),
    path('ecritures/<int:pk>/valider/', views.entry_validate, name='entry_validate'),
    path('ecritures/<int:pk>/extourner/', views.entry_reverse, name='entry_reverse'),
    path('ecritures/<int:pk>/annuler/', views.entry_cancel, name='entry_cancel'),

    # TVA
    path('tva/', views.tva_dashboard, name='tva'),

    # Paiements
    path('paiements/', views.payment_list, name='payment_list'),
    path('paiements/nouveau/', views.payment_create, name='payment_create'),

    # Banque
    path('comptes-bancaires/', views.bank_account_list, name='bank_account_list'),
    path('releves/', views.bank_statement_list, name='bank_statement_list'),
    path('releves/<int:statement_pk>/rapprochement/', views.bank_reconciliation, name='bank_reconciliation'),

    # Notes de frais
    path('notes-de-frais/', views.expense_report_list, name='expense_report_list'),
    path('notes-de-frais/<int:pk>/', views.expense_report_detail, name='expense_report_detail'),

    # Immobilisations
    path('immobilisations/', views.fixed_asset_list, name='fixed_asset_list'),
    path('immobilisations/<int:pk>/', views.fixed_asset_detail, name='fixed_asset_detail'),

    # Rapports
    path('rapports/balance/', views.report_balance, name='report_balance'),
    path('rapports/grand-livre/', views.report_grand_livre, name='report_grand_livre'),
    path('rapports/compte-de-resultat/', views.report_income_statement, name='report_income_statement'),
]
