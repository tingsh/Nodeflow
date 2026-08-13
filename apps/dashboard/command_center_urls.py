from django.urls import path

from . import command_center_views as views

app_name = "command_center"

urlpatterns = [
    path("layout/", views.save_personal_layout, name="save_layout"),
    path("layout/reset/", views.reset_personal_layout, name="reset_layout"),
    path("layout/publish/", views.publish_team_default, name="publish_default"),
    path("layout/team-default/remove/", views.remove_team_default, name="remove_default"),
]
