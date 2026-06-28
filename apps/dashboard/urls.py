from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.DashboardView.as_view(), name='home'),
    path('personnaliser/', views.DashboardCustomizeView.as_view(), name='customize'),
    path('widgets/', views.WidgetCatalogView.as_view(), name='widget_catalog'),
    path('widgets/ajouter/<int:widget_id>/', views.AddWidgetView.as_view(), name='add_widget'),
    path('widgets/<int:pk>/configurer/', views.ConfigureWidgetView.as_view(), name='configure_widget'),
    path('widgets/<int:pk>/supprimer/', views.RemoveWidgetView.as_view(), name='remove_widget'),
    path('widgets/<int:pk>/toggle/', views.ToggleWidgetView.as_view(), name='toggle_widget'),
    path('raccourcis/creer/', views.ShortcutCreateView.as_view(), name='shortcut_create'),
    path('raccourcis/<int:pk>/modifier/', views.ShortcutUpdateView.as_view(), name='shortcut_update'),
    path('raccourcis/<int:pk>/supprimer/', views.ShortcutDeleteView.as_view(), name='shortcut_delete'),
    path('sauvegarder-disposition/', views.SaveDashboardLayoutView.as_view(), name='save_layout'),
    path('reinitialiser/', views.ResetDashboardView.as_view(), name='reset'),
]
