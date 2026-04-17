from django.urls import path
from . import team_views as views

app_name = "dashboard_team"

urlpatterns = [
    path("", views.SharedDashboardListView.as_view(), name="list"),
    path("create/", views.SharedDashboardCreateView.as_view(), name="create"),
    path("<int:pk>/edit/", views.SharedDashboardUpdateView.as_view(), name="edit"),
    path("<int:pk>/delete/", views.SharedDashboardDeleteView.as_view(), name="delete"),
]
