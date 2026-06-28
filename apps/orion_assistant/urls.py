from django.urls import path
from . import views

app_name = 'orion_assistant'

urlpatterns = [
    path('', views.conversation_list, name='list'),
    path('nouveau/', views.new_conversation, name='new'),
    path('<int:pk>/', views.conversation_detail, name='detail'),
    path('<int:pk>/message/', views.send_message, name='send'),
    path('<int:pk>/archiver/', views.archive_conv, name='archive'),
]
