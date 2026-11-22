from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile, name='profile'),
    path('profile/mot-de-passe/', views.changer_mot_de_passe,
         name='changer_mot_de_passe'),
    path('profile/signature/', views.signature_save, name='signature_save'),
    path('profile/signature/retirer/', views.signature_delete,
         name='signature_delete'),
    # Sert l'image elle-meme : signatures/ n'est pas servi par /media/,
    # et l'apercu du profil pointait vers une URL qui rend 404.
    path('profile/signature/image/', views.signature_image,
         name='signature_image'),
    path('users/', views.user_list, name='user_list'),
    path('users/new/', views.user_create, name='user_create'),
    path('users/<int:pk>/', views.user_detail, name='user_detail'),
    path('users/<int:pk>/supprimer/', views.user_delete, name='user_delete'),
    path('users/<int:pk>/deverrouiller/', views.user_unlock,
         name='user_unlock'),
    path('users/<int:pk>/renvoyer-le-code/', views.user_renvoyer_le_code,
         name='user_renvoyer_le_code'),
    path('users/<int:pk>/desactiver/', views.user_deactivate,
         name='user_deactivate'),
    path('missing-employee/', views.missing_employee, name='missing_employee'),
]
