from django.urls import path
from . import views

app_name = "automations"

urlpatterns = [
    path("", views.AutomationListView.as_view(), name="list"),
    path("create/", views.AutomationCreateView.as_view(), name="create"),
    path("<int:pk>/", views.AutomationDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.AutomationUpdateView.as_view(), name="edit"),
    path("<int:pk>/delete/", views.AutomationDeleteView.as_view(), name="delete"),
    path("logs/", views.AutomationLogListView.as_view(), name="logs"),
]
