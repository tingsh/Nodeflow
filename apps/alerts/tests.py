import pytest
from django.core import mail
from django.test import override_settings
from apps.teams.models import Team
from apps.devices.models import Site, Device
from apps.alerts.models import AlertRule, Alert
from apps.alerts.services import check_alerts_for_payload
from apps.users.models import CustomUser


@pytest.mark.django_db
@override_settings(SITE_URL="http://testserver")
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
