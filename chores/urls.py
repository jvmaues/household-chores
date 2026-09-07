from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("chores/", views.chore_list, name="chore_list"),
    path("chores/new/", views.chore_create, name="chore_create"),
    path("chores/<int:pk>/edit/", views.chore_update, name="chore_update"),
    path("chores/<int:pk>/delete/", views.chore_delete, name="chore_delete"),
    path("chores/<int:pk>/toggle-pause/", views.chore_toggle_pause, name="chore_toggle_pause"),
]
