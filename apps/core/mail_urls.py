"""Routes de la page des courriels.

Relatives : le préfixe « orion-admin/courriels/ » est porté au point de
montage dans erp_btp/urls.py, comme pour apps/orion_ops.
"""
from django.urls import path

from apps.core import mail_views

app_name = 'core_mail'

urlpatterns = [
    path('', mail_views.reglages_mail_view, name='reglages'),
]
