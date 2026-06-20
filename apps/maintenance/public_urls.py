from django.urls import path
from . import public_views

app_name = "maintenance_public"

urlpatterns = [
    path("ticket/<uuid:token>/", public_views.public_ticket_view, name="public_ticket_view"),
    path("ticket/<uuid:token>/toggle/<int:item_index>/", public_views.public_toggle_checklist_item, name="public_toggle_checklist_item"),
    path("ticket/<uuid:token>/comment/", public_views.public_add_comment, name="public_add_comment"),
    path("ticket/<uuid:token>/status/", public_views.public_update_status, name="public_update_status"),
]
