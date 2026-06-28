from django.urls import path
from . import views

app_name = 'competitor'

urlpatterns = [
    path('',                                   views.dashboard,        name='dashboard'),
    path('liste/',                             views.competitor_list,  name='list'),
    path('nouveau/',                           views.competitor_create,name='create'),
    path('<int:pk>/',                          views.competitor_detail,name='detail'),
    path('<int:pk>/modifier/',                 views.competitor_edit,  name='edit'),

    # Produits
    path('produits/',                          views.product_list,     name='product_list'),
    path('<int:competitor_pk>/produit/',        views.add_product,      name='add_product'),
    path('import-csv/',                        views.csv_import,       name='csv_import'),

    # Prix & historique
    path('prix/',                              views.price_history,    name='price_history'),

    # Trafic
    path('trafic/',                            views.traffic_view,     name='traffic'),

    # Avantages
    path('avantages/',                         views.advantages_view,  name='advantages'),
    path('<int:competitor_pk>/avantage/',       views.add_advantage,    name='add_advantage'),

    # Comparaison
    path('comparaison/',                       views.compare_view,     name='compare'),

    # Alertes
    path('alertes/',                           views.alerts_view,      name='alerts'),
    path('alertes/<int:pk>/lue/',              views.alert_mark_read,  name='alert_mark_read'),

    # Rapports
    path('rapports/',                          views.reports_view,     name='reports'),
]
