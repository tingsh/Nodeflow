from django.urls import path
from . import views

app_name = "telemetry"

urlpatterns = [
    path("chart/<int:device_id>/<str:key>/", views.get_chart_partial, name="chart_partial"),
    path("kpi/<int:device_id>/<str:key>/", views.get_kpi_partial, name="kpi_partial"),
    
    # JSON API for Chart.js
    path("api/metrics/<int:device_id>/", views.device_metrics_api, name="device_metrics_api"),
    path("api/history/<int:device_id>/", views.device_telemetry_history_api, name="device_telemetry_history_api"),
    path("api/export/<int:device_id>/", views.export_telemetry_csv, name="export_telemetry_csv"),
    
    path("analyze/<int:device_id>/", views.telemetry_analyzer, name="telemetry_analyzer"),
]
