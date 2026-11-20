from django.urls import path

from . import views

app_name = 'fiscal_pt'

urlpatterns = [
    path('', views.index, name='index'),
    path('parametres/', views.parametres, name='parametres'),

    path('cles/', views.cles, name='cles'),
    path('cles/creer/', views.cle_creer, name='cle_creer'),

    path('series/', views.series, name='series'),
    path('series/nouvelle/', views.serie_creer, name='serie_creer'),
    path('series/<int:pk>/', views.serie_modifier, name='serie_modifier'),

    path('documents/', views.documents, name='documents'),
    path('documents/<int:pk>/', views.document_detail, name='document_detail'),
    path('documents/<int:pk>/qr.png', views.document_qr, name='document_qr'),

    path('recus/', views.recus, name='recus'),
    path('recus/<int:pk>/', views.recu_detail, name='recu_detail'),
    path('recus/<int:pk>/qr.png', views.recu_qr, name='recu_qr'),

    path('verification/', views.verifier_les_chaines, name='verification'),
    path('saft/', views.export_saft, name='export_saft'),

    path('factures/<int:pk>/avoir/', views.note_de_credit,
         name='note_de_credit'),
    path('factures/<int:pk>/note-de-debit/', views.note_de_debit,
         name='note_de_debit'),
    path('factures/<int:pk>/recu/', views.recu_sur_facture,
         name='recu_sur_facture'),
]
