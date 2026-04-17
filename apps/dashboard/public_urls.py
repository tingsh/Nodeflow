from django.urls import path
from . import public_views as views

app_name = "dashboard_public"

urlpatterns = [
    path("<uuid:token>/", views.public_dashboard, name="view"),
]
