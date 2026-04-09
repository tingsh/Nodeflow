from django.urls import path
from . import views

app_name = "alerts"

urlpatterns = [
    path("", views.AlertListView.as_view(), name="alert_list"),
    path("acknowledge/<int:alert_id>/", views.acknowledge_alert, name="acknowledge_alert"),
]
