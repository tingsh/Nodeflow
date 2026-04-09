from django.urls import path
from . import views

app_name = "onboarding"

urlpatterns = [
    path("", views.onboarding_start, name="start"),
    path("site/", views.step_1_site, name="step_1_site"),
    path("gateway/", views.step_2_gateway, name="step_2_gateway"),
    path("device/", views.step_3_device, name="step_3_device"),
    path("alert/", views.step_4_alert, name="step_4_alert"),
    path("complete/", views.complete, name="complete"),
]
