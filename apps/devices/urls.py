from django.urls import path
from . import views

app_name = "devices"

urlpatterns = [
    # Site URLs
    path("sites/", views.SiteListView.as_view(), name="site_list"),
    path("sites/create/", views.SiteCreateView.as_view(), name="site_create"),
    path("sites/<int:pk>/", views.SiteDetailView.as_view(), name="site_detail"),
    path("sites/<int:pk>/edit/", views.SiteUpdateView.as_view(), name="site_edit"),
    path("sites/<int:pk>/delete/", views.SiteDeleteView.as_view(), name="site_delete"),

    # Gateway URLs
    path("gateways/", views.GatewayListView.as_view(), name="gateway_list"),
    path("gateways/create/", views.GatewayCreateView.as_view(), name="gateway_create"),
    path("gateways/<int:pk>/", views.GatewayDetailView.as_view(), name="gateway_detail"),
    path("gateways/<int:pk>/edit/", views.GatewayUpdateView.as_view(), name="gateway_edit"),
    path("gateways/<int:pk>/delete/", views.GatewayDeleteView.as_view(), name="gateway_delete"),

    # Device URLs
    path("", views.DeviceListView.as_view(), name="device_list"),
    path("create/", views.DeviceCreateView.as_view(), name="device_create"),
    path("<int:pk>/", views.DeviceDetailView.as_view(), name="device_detail"),
    path("<int:pk>/edit/", views.DeviceUpdateView.as_view(), name="device_edit"),
    path("<int:pk>/delete/", views.DeviceDeleteView.as_view(), name="device_delete"),

    # HTMX endpoints
    path("htmx/device/create/", views.htmx_device_create, name="htmx_device_create"),
    path("htmx/templates/search/", views.template_library_search, name="template_library_search"),
    # Remote Control Command URLs
    path("<int:pk>/command/", views.device_send_command, name="device_send_command"),
    path("<int:pk>/command/status/<uuid:tx_id>/", views.device_command_status, name="device_command_status"),

    # API endpoints for Edge Gateway
    path("api/discovery/", views.gateway_discovery_api, name="gateway_discovery_api"),
]
