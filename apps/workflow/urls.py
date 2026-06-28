from django.urls import path
from . import views

app_name = 'workflow'

urlpatterns = [
    path('', views.index, name='index'),
]

