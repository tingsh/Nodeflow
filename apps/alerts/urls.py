from django.urls import path

from . import views

app_name = "alerts"

urlpatterns = [
    path("", views.AlertListView.as_view(), name="alert_list"),
    path("<int:alert_id>/acknowledge/", views.acknowledge_alert, name="acknowledge_alert"),
    path("<int:alert_id>/escalate/", views.escalate_alert_to_ticket, name="escalate_alert"),
    path("search-users/", views.search_team_members, name="search_users"),
    # Alert Rules
    path("rules/", views.AlertRuleListView.as_view(), name="rule_list"),
    path("rules/create/", views.AlertRuleCreateView.as_view(), name="rule_create"),
    path("rules/<int:pk>/update/", views.AlertRuleUpdateView.as_view(), name="rule_update"),
    path("rules/<int:pk>/delete/", views.AlertRuleDeleteView.as_view(), name="rule_delete"),
]
