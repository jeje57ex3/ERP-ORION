from django.urls import path
from . import views

app_name = 'site_customization'

urlpatterns = [
    path('',                                    views.dashboard,      name='dashboard'),

    # Thème
    path('theme/<int:website_id>/',             views.theme_edit,     name='theme_edit'),
    path('theme/<int:website_id>/publier/',     views.theme_publish,  name='theme_publish'),

    # Pages
    path('pages/',                              views.page_list,      name='page_list'),
    path('pages/nouvelle/',                     views.page_create,    name='page_create'),
    path('pages/<int:pk>/',                     views.page_detail,    name='page_detail'),
    path('pages/<int:pk>/modifier/',            views.page_edit,      name='page_edit'),
    path('pages/<int:pk>/publier/',             views.page_publish,   name='page_publish'),
    path('pages/<int:pk>/apercu/',              views.page_preview,   name='page_preview'),

    # Sections
    path('pages/<int:page_id>/sections/nouvelle/', views.section_create, name='section_create'),
    path('sections/<int:section_id>/modifier/',    views.section_edit,   name='section_edit'),
    path('sections/<int:section_id>/supprimer/',   views.section_delete, name='section_delete'),

    # Blocs
    path('sections/<int:section_id>/blocs/nouveau/', views.block_create, name='block_create'),
    path('blocs/<int:block_id>/modifier/',           views.block_edit,   name='block_edit'),
    path('blocs/<int:block_id>/supprimer/',          views.block_delete, name='block_delete'),
]
