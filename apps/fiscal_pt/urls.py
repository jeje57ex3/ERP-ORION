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

    path('verification/', views.verifier_les_chaines, name='verification'),
    path('saft/', views.export_saft, name='export_saft'),

    path('factures/<int:pk>/avoir/', views.note_de_credit,
         name='note_de_credit'),
]
