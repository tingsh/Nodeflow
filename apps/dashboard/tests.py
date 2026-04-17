from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from apps.users.models import CustomUser
from apps.teams.models import Team, Membership
from apps.teams.roles import ROLE_MANAGER, ROLE_VIEWER
from apps.dashboard.models import SharedDashboard

class SharedDashboardTests(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Test Team", slug="test-team")
        self.user_manager = CustomUser.objects.create_user(username="manager", email="m@ex.com", password="pwd")
        self.user_viewer = CustomUser.objects.create_user(username="viewer", email="v@ex.com", password="pwd")
        
        Membership.objects.create(team=self.team, user=self.user_manager, role=ROLE_MANAGER)
        Membership.objects.create(team=self.team, user=self.user_viewer, role=ROLE_VIEWER)
        
        self.link = SharedDashboard.objects.create(
            team=self.team,
            name="Reception Screen",
            is_active=True
        )
        self.client = Client()

    def test_rbac_manage_links(self):
        # Viewer cannot manage links
        self.client.force_login(self.user_viewer)
        response = self.client.get(reverse('web_team:dashboard_team:list', args=[self.team.slug]))
        self.assertEqual(response.status_code, 403)
        
        # Manager can manage links
        self.client.force_login(self.user_manager)
        response = self.client.get(reverse('web_team:dashboard_team:list', args=[self.team.slug]))
        self.assertEqual(response.status_code, 200)

    def test_public_dashboard_unauthenticated(self):
        url = reverse('dashboard_public:view', args=[self.link.token])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Team - Reception Screen")
        self.assertContains(response, "Powered by")
        
        # Check that view count increased
        self.link.refresh_from_db()
        self.assertEqual(self.link.view_count, 1)

    def test_public_dashboard_inactive(self):
        self.link.is_active = False
        self.link.save()
        
        url = reverse('dashboard_public:view', args=[self.link.token])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_public_dashboard_expired(self):
        self.link.expires_at = timezone.now() - timedelta(days=1)
        self.link.save()
        
        url = reverse('dashboard_public:view', args=[self.link.token])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_public_dashboard_password_protected(self):
        self.link.set_password("secret123")
        self.link.save()
        
        url = reverse('dashboard_public:view', args=[self.link.token])
        
        # GET should prompt for password without incrementing view
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Protected Dashboard")
        self.link.refresh_from_db()
        self.assertEqual(self.link.view_count, 0)
        
        # POST with wrong password
        response = self.client.post(url, {"password": "wrong"})
        self.assertContains(response, "Incorrect password.")
        self.link.refresh_from_db()
        self.assertEqual(self.link.view_count, 0)
        
        # POST with correct password
        response = self.client.post(url, {"password": "secret123"})
        self.assertEqual(response.status_code, 200)
        
        # Follow-up GET should now be allowed and increment view
        response = self.client.get(url)
        self.assertContains(response, "Test Team - Reception Screen")
        self.link.refresh_from_db()
        self.assertEqual(self.link.view_count, 1)

    def test_public_dashboard_kiosk_mode(self):
        url = reverse('dashboard_public:view', args=[self.link.token]) + "?kiosk=1"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # In kiosk mode, the header shouldn't be rendered
        self.assertNotContains(response, "Test Team - Reception Screen")
