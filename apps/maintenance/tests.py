from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from django.urls import reverse

from apps.users.models import CustomUser
from apps.teams.models import Team, Membership
from apps.teams.roles import ROLE_MANAGER, ROLE_VIEWER
from apps.devices.models import Site, Device
from apps.alerts.models import AlertRule, Alert
from apps.maintenance.models import MaintenanceTicket, PreventiveSchedule, TicketTemplate
from apps.maintenance.services import auto_create_ticket
from apps.maintenance.tasks import generate_preventive_tickets

class MaintenanceTests(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Test Team", slug="test")
        self.manager = CustomUser.objects.create_user(username="m", email="m@ex.com", password="pwd")
        self.viewer = CustomUser.objects.create_user(username="v", email="v@ex.com", password="pwd")
        Membership.objects.create(team=self.team, user=self.manager, role=ROLE_MANAGER)
        Membership.objects.create(team=self.team, user=self.viewer, role=ROLE_VIEWER)
        
        self.site = Site.objects.create(team=self.team, name="HQ")
        self.device = Device.objects.create(
            team=self.team, 
            site=self.site, 
            name="Pump 1", 
            device_type='power_meter', 
            protocol='modbus_tcp'
        )

    def test_auto_create_ticket_from_critical_alert(self):
        rule = AlertRule.objects.create(
            team=self.team,
            device=self.device,
            name="High Temp",
            telemetry_key="temp",
            condition="gt",
            threshold=100.0,
            severity='critical'
        )
        alert = Alert.objects.create(team=self.team, rule=rule, device=self.device, trigger_value=105.0)
        
        # Manually invoke the service that trigger_alert now calls
        ticket = auto_create_ticket(alert)
        
        self.assertIsNotNone(ticket)
        self.assertEqual(ticket.priority, MaintenanceTicket.PriorityChoices.CRITICAL)
        self.assertEqual(ticket.ticket_type, MaintenanceTicket.TypeChoices.REACTIVE)
        self.assertEqual(ticket.device, self.device)
        self.assertIn("High Temp", ticket.title)
        
    def test_generate_preventive_tickets_task(self):
        template = TicketTemplate.objects.create(team=self.team, name="Monthly Check")
        schedule = PreventiveSchedule.objects.create(
            team=self.team,
            device=self.device,
            template=template,
            title="Monthly Pump Calibration",
            interval='monthly',
            next_due_at=timezone.now() - timedelta(hours=1) # due in the past
        )
        
        # Run Celery task synchronously
        generate_preventive_tickets()
        
        # Check that a ticket was created
        ticket = MaintenanceTicket.objects.filter(schedule_reference=schedule).first()
        self.assertIsNotNone(ticket)
        self.assertEqual(ticket.ticket_type, MaintenanceTicket.TypeChoices.PREVENTIVE)
        self.assertEqual(ticket.priority, MaintenanceTicket.PriorityChoices.MEDIUM)
        
        # Check that schedule next_due_at was pushed forward by ~1 month safely into the future
        schedule.refresh_from_db()
        self.assertTrue(schedule.next_due_at > timezone.now())

    def test_rbac_view_access(self):
        self.client.force_login(self.viewer)
        response = self.client.get(reverse('web_team:maintenance:ticket_list', args=[self.team.slug]))
        self.assertEqual(response.status_code, 200) # viewers can view

    def test_rbac_manage_access(self):
        self.client.force_login(self.viewer)
        response = self.client.get(reverse('web_team:maintenance:ticket_create', args=[self.team.slug]))
        self.assertEqual(response.status_code, 403) # viewers cannot create
        
        self.client.force_login(self.manager)
        response = self.client.get(reverse('web_team:maintenance:ticket_create', args=[self.team.slug]))
        self.assertEqual(response.status_code, 200) # managers can create
