from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile, name='profile'),
    path('profile/signature/', views.signature_save, name='signature_save'),
    path('profile/signature/retirer/', views.signature_delete,
         name='signature_delete'),
    path('users/', views.user_list, name='user_list'),
    path('users/new/', views.user_create, name='user_create'),
    path('users/<int:pk>/', views.user_detail, name='user_detail'),
    path('users/<int:pk>/supprimer/', views.user_delete, name='user_delete'),
    path('users/<int:pk>/desactiver/', views.user_deactivate,
         name='user_deactivate'),
    path('missing-employee/', views.missing_employee, name='missing_employee'),
]
