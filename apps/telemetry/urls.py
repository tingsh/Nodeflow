from django.urls import path
from . import views

app_name = "telemetry"

urlpatterns = [
    path("chart/<int:device_id>/<str:key>/", views.get_chart_partial, name="chart_partial"),
    path("kpi/<int:device_id>/<str:key>/", views.get_kpi_partial, name="kpi_partial"),
]
