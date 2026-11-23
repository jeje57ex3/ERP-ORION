from django.urls import path

from apps.translations import views_messages

app_name = 'translations_messages'

urlpatterns = [
    path('', views_messages.messages_traduits, name='etat'),
    path('lot/', views_messages.traduire_un_lot, name='lot'),
]
