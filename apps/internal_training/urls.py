from django.urls import path
from . import views, api

app_name = 'internal_training'

urlpatterns = [
    # ── Dashboard & liste ─────────────────────────────────────────────────────
    path('erp/formations/', views.dashboard, name='dashboard'),
    path('erp/formations/liste/', views.course_list, name='course_list'),

    # ── Formations CRUD ───────────────────────────────────────────────────────
    path('erp/formations/nouvelle/', views.course_create, name='course_create'),
    path('erp/formations/<int:pk>/', views.course_detail, name='course_detail'),
    path('erp/formations/<int:pk>/modifier/', views.course_edit, name='course_edit'),
    path('erp/formations/<int:pk>/publier/', views.course_publish_toggle, name='course_publish'),
    path('erp/formations/<int:pk>/supprimer/', views.course_delete, name='course_delete'),
    path('erp/formations/<int:pk>/inscription/', views.course_enroll, name='course_enroll'),

    # ── Chapitres ─────────────────────────────────────────────────────────────
    path('erp/formations/<int:course_pk>/chapitres/nouveau/', views.chapter_create, name='chapter_create'),
    path('erp/formations/chapitres/<int:pk>/modifier/', views.chapter_edit, name='chapter_edit'),
    path('erp/formations/chapitres/<int:pk>/supprimer/', views.chapter_delete, name='chapter_delete'),

    # ── Pages ─────────────────────────────────────────────────────────────────
    path('erp/formations/chapitres/<int:chapter_pk>/pages/nouvelle/', views.page_create, name='page_create'),
    path('erp/formations/pages/<int:pk>/modifier/', views.page_edit, name='page_edit'),
    path('erp/formations/pages/<int:pk>/supprimer/', views.page_delete, name='page_delete'),
    path('erp/formations/pages/<int:pk>/editeur/', views.page_editor, name='page_editor'),
    path('erp/formations/pages/<int:pk>/voir/', views.page_view, name='page_view'),

    # ── Blocs ─────────────────────────────────────────────────────────────────
    path('erp/formations/pages/<int:page_pk>/blocs/ajouter/', views.block_add, name='block_add'),
    path('erp/formations/blocs/<int:pk>/modifier/', views.block_edit, name='block_edit'),
    path('erp/formations/blocs/<int:pk>/supprimer/', views.block_delete, name='block_delete'),

    # ── API ───────────────────────────────────────────────────────────────────
    path('api/v1/formations/pages/<int:pk>/terminer/', api.api_mark_page_complete, name='api_mark_complete'),
    path('api/v1/formations/pages/<int:page_pk>/blocs/ordre/', api.api_reorder_blocks, name='api_reorder_blocks'),
    path('api/v1/formations/<int:pk>/progression/', api.api_course_progress, name='api_progress'),
]
