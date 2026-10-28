from django.urls import path

from apps.orion_website import views

app_name = "orion_website"

urlpatterns = [
    path("orion/", views.home_view, name="home"),
    path("orion/modules/", views.modules_view, name="modules"),
    path("orion/modules/<str:module_code>/", views.module_detail_view, name="module_detail"),
    path("orion/apps/", views.apps_view, name="apps"),
    path("orion/downloads/", views.downloads_view, name="downloads"),
    path("orion/install/windows/", views.install_windows_view, name="install_windows"),
    path("orion/install/android/", views.install_android_view, name="install_android"),
    path("orion/install/apple/", views.install_apple_view, name="install_apple"),
    path("orion/security/", views.security_view, name="security"),
    path("orion/faq/", views.faq_view, name="faq"),
    path("orion/contact/", views.contact_view, name="contact"),
]
