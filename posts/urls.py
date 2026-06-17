from django.urls import path

from posts import views

urlpatterns = [
    path("compose/", views.compose, name="compose"),
    path("compose/<uuid:pk>/", views.compose, name="compose_edit"),
    path("compose/search-handles/", views.search_handles_view, name="search_handles"),
    path("compose/select-handle/", views.select_handle_view, name="select_handle"),
    path("drafts/", views.draft_list, name="draft_list"),
]
