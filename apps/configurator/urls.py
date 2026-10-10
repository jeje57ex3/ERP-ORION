from django.urls import path
from . import erp_views

app_name = 'configurator'

urlpatterns = [
    path('simulateur/', erp_views.simulator_view, name='simulator'),
    path('simulateur/services/', erp_views.simulator_services, name='simulator_services'),
    path('simulateur/questions/', erp_views.simulator_questions, name='simulator_questions'),
    path('simulateur/estimer/', erp_views.simulator_estimate, name='simulator_estimate'),
    path('analytique/', erp_views.analytics_view, name='analytics'),
]
