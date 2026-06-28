from django.urls import path
from . import guided_quote_views as v

app_name = 'guided_quote'

urlpatterns = [
    path('', v.wizard_start, name='wizard_start'),
    path('etape-2/', v.wizard_step2, name='wizard_step2'),
    path('etape-3/', v.wizard_step3, name='wizard_step3'),
    path('etape-4/', v.wizard_step4, name='wizard_step4'),
    path('confirmation/', v.wizard_success, name='wizard_success'),
    path('photos/<int:pk>/', v.wizard_upload_photos, name='upload_photos'),
]
