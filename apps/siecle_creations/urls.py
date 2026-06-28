from django.urls import path
from . import views

app_name = 'siecle_creations'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('catalogue/', views.catalog, name='catalog'),
    path('catalogue/<int:pk>/', views.creation_detail, name='detail'),
    path('catalogue/<int:pk>/publier/', views.publish_creation, name='publish'),
    path('catalogue/<int:pk>/archiver/', views.archive_creation, name='archive'),
    # Nouvelles pages
    path('collections/', views.collections_view, name='collections'),
    path('campagnes/', views.campaigns_view, name='campaigns'),
]
