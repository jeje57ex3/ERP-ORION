from django.urls import path
from . import views
from . import views_signup as sv

app_name = 'portals'

urlpatterns = [
    path('', views.index, name='index'),

    # ── Gestion admin des demandes d'inscription ──────────────────────────────
    path('inscriptions/', sv.ClientSignupRequestListView.as_view(), name='signup_list'),
    path('inscriptions/<int:pk>/', sv.ClientSignupRequestDetailView.as_view(), name='signup_detail'),
    path('inscriptions/<int:pk>/valider/', sv.ApproveClientSignupView.as_view(), name='signup_approve'),
    path('inscriptions/<int:pk>/refuser/', sv.RejectClientSignupView.as_view(), name='signup_reject'),
]
