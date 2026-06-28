from django.urls import path
from . import views

app_name = 'bi'

urlpatterns = [
    path('', views.report_list, name='index'),
    path('rapports/', views.report_list, name='report_list'),
    path('commercial/', views.commercial, name='commercial'),
    path('finance/', views.finance, name='finance'),
    path('comptabilite/', views.accounting, name='accounting'),
    path('btp/', views.btp, name='btp'),
    path('stocks/', views.stocks, name='stocks'),
    path('ecommerce/', views.ecommerce, name='ecommerce'),
    path('commerce/', views.commerce, name='commerce'),
    path('production/', views.production, name='production'),
    path('rh/', views.hr, name='hr'),
    path('sites/', views.websites, name='websites'),
    path('support/', views.support, name='support'),
    path('export/<str:module>/<str:format>/', views.export, name='export'),
]
