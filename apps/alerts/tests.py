import pytest
from unittest.mock import patch
from django.core import mail
from django.test import override_settings, Client
from django.urls import reverse
from apps.teams.models import Team, Membership
from apps.teams.roles import ROLE_ADMIN
from apps.devices.models import Site, Device
from apps.alerts.models import AlertRule, Alert
from apps.alerts.services import check_alerts_for_payload
from apps.users.models import CustomUser
from apps.alerts.tasks import dispatch_alert_whatsapp_task


@pytest.mark.django_db
@override_settings(SITE_URL="http://testserver", CELERY_TASK_ALWAYS_EAGER=True)
def test_check_alerts_for_payload_triggers_alert_and_email():
    # 1. Create a Team
    team = Team.objects.create(name="Test Team", slug="test-team")

    # 2. Create a Site
    site = Site.objects.create(team=team, name="Test Site")

    # 3. Create a Device
    device = Device.objects.create(
        team=team,
        site=site,
        name="Test Device",
        device_type="plc",
        protocol="modbus_tcp",
        status="online"
    )

    # 4. Create a user to receive the alert email
    user = CustomUser.objects.create_user(
        username="admin_test",
        email="admin@test.com",
        password="testpassword123"
    )
    # Associate user with team
    team.members.add(user)

    # 5. Create an AlertRule (threshold=100, condition='gt')
    rule = AlertRule.objects.create(
        team=team,
        name="High Active Power Alert",
        device=device,
        telemetry_key="active_power",
        condition="gt",
        threshold=100.0,
        is_active=True,
        notify_email=True,
        cooldown_minutes=15
    )
    rule.recipients.add(user)

    # 6. Trigger alert with payload 105 (greater than 100)
    check_alerts_for_payload(device, "active_power", 105.0)

    # 7. Asserts
    # Assert Alert instance was created
    alerts = Alert.objects.filter(rule=rule, device=device)
    assert alerts.count() == 1
    alert = alerts.first()
    assert alert.trigger_value == 105.0
    assert alert.status == "active"

    # Assert email was sent
    assert len(mail.outbox) == 1
    email = mail.outbox[0]
    assert "High Active Power Alert" in email.subject
    assert "admin@test.com" in email.to


@pytest.mark.django_db
@override_settings(SITE_URL="http://testserver", CELERY_TASK_ALWAYS_EAGER=True)
def test_targeted_recipients_email_dispatch():
    team = Team.objects.create(name="Test Team", slug="test-team")
    site = Site.objects.create(team=team, name="Test Site")
    device = Device.objects.create(
        team=team, site=site, name="Test Device", device_type="plc", protocol="modbus_tcp", status="online"
    )

    user1 = CustomUser.objects.create_user(username="user1", email="user1@test.com", password="pwd")
    user2 = CustomUser.objects.create_user(username="user2", email="user2@test.com", password="pwd")
    team.members.add(user1)
    team.members.add(user2)

    rule = AlertRule.objects.create(
        team=team,
        name="Targeted Email Alert",
        device=device,
        telemetry_key="temp",
        condition="gt",
        threshold=50.0,
        is_active=True,
        notify_email=True,
        cooldown_minutes=15
    )
    rule.recipients.add(user1)  # Only user1 is recipient

    check_alerts_for_payload(device, "temp", 55.0)

    assert len(mail.outbox) == 1
    email = mail.outbox[0]
    assert "user1@test.com" in email.to
    assert "user2@test.com" not in email.to


@pytest.mark.django_db
@override_settings(WHATSAPP_PROVIDER="meta", WHATSAPP_PHONE_NUMBER_ID="12345", WHATSAPP_ACCESS_TOKEN="token_abc")
@patch("apps.alerts.tasks.requests.post")
def test_targeted_whatsapp_dispatch(mock_post):
    team = Team.objects.create(name="Test Team", slug="test-team")
    site = Site.objects.create(team=team, name="Test Site")
    device = Device.objects.create(
        team=team, site=site, name="Test Device", device_type="plc", protocol="modbus_tcp", status="online"
    )

    user = CustomUser.objects.create_user(
        username="user1", email="user1@test.com", password="pwd", phone_number="+1 (555) 123-4567"
    )
    team.members.add(user)

    rule = AlertRule.objects.create(
        team=team,
        name="Targeted WhatsApp Alert",
        device=device,
        telemetry_key="temp",
        condition="gt",
        threshold=50.0,
        is_active=True,
        notify_whatsapp=True,
        cooldown_minutes=15
    )
    rule.recipients.add(user)

    alert = Alert.objects.create(
        team=team, rule=rule, device=device, trigger_value=55.0, status="active"
    )

    dispatch_alert_whatsapp_task(alert.id)

    assert mock_post.called
    args, kwargs = mock_post.call_args
    assert args[0] == "https://graph.facebook.com/v19.0/12345/messages"
    assert kwargs["headers"]["Authorization"] == "Bearer token_abc"
    payload = kwargs["json"]
    assert payload["to"] == "15551234567"
    assert "Targeted WhatsApp Alert" in payload["text"]["body"]


@pytest.mark.django_db
def test_search_team_members_htmx():
    client = Client()
    team = Team.objects.create(name="Test Team", slug="test-team")
    user = CustomUser.objects.create_user(
        username="john_doe", first_name="John", last_name="Doe", email="john@test.com", password="pwd"
    )
    Membership.objects.create(team=team, user=user, role=ROLE_ADMIN)

    # Login user to pass PermissionRequiredMixin
    client.force_login(user)

    # Test search with name
    url = reverse("web_team:alerts:search_users", args=[team.slug])
    response = client.get(url, {"q": "Joh"})
    assert response.status_code == 200
    assert b"John Doe" in response.content

    # Test search with no matching letters
    response = client.get(url, {"q": "XYZ"})
    assert response.status_code == 200
    assert b"John Doe" not in response.content

