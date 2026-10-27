from django.urls import path
from . import api, views

app_name = 'site_builder'

urlpatterns = [
    # ── ERP pages ────────────────────────────────────────────────────────────
    path('',                                      views.page_list_view,   name='page_list'),
    path('pages/new/',                            views.page_create_view, name='page_create'),
    path('pages/<int:page_id>/edit/',             views.page_edit_view,   name='page_edit'),
    path('pages/<int:page_id>/delete/',           views.page_delete_view, name='page_delete'),
    path('pages/<int:page_id>/builder/',          views.builder_view,     name='builder'),
    path('pages/<int:page_id>/preview/',          views.preview_view,     name='preview'),

    # ── Raccourcis par marque (ouvrir ou créer la homepage) ──────────────────
    path('siecle/open/',                          views.open_siecle_builder, name='open_siecle'),
    path('lunea/open/',                           views.open_lunea_builder,  name='open_lunea'),

    # ── AJAX API ─────────────────────────────────────────────────────────────
    path('upload-image/',                         api.upload_builder_image_api, name='upload_image'),
    path('pages/<int:page_id>/sections/add/',     api.add_section_api,    name='add_section'),
    path('pages/<int:page_id>/sections/reorder/', api.reorder_sections_api, name='reorder_sections'),
    path('pages/<int:page_id>/publish/',          api.publish_page_api,   name='publish_page'),
    path('sections/<int:section_id>/update/',     api.update_section_api, name='update_section'),
    path('sections/<int:section_id>/delete/',     api.delete_section_api, name='delete_section'),
]
