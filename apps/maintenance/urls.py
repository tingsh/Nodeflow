from django.urls import path
from . import views

app_name = "maintenance"

urlpatterns = [
    # Tickets
    path("tickets/", views.TicketListView.as_view(), name="ticket_list"),
    path("tickets/create/", views.TicketCreateView.as_view(), name="ticket_create"),
    path("tickets/<int:pk>/", views.TicketDetailView.as_view(), name="ticket_detail"),
    path("tickets/<int:pk>/edit/", views.TicketUpdateView.as_view(), name="ticket_edit"),
    path("tickets/<int:pk>/comment/", views.add_ticket_comment, name="ticket_comment"),
    
    # Templates
    path("templates/", views.TemplateListView.as_view(), name="template_list"),
    path("templates/create/", views.TemplateCreateView.as_view(), name="template_create"),
    
    # Preventive Schedules
    path("schedules/", views.ScheduleListView.as_view(), name="schedule_list"),
    path("schedules/create/", views.ScheduleCreateView.as_view(), name="schedule_create"),
]
