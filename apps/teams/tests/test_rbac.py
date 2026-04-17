from django.test import TestCase, RequestFactory
from django.template import Context, Template
from django.http import HttpResponse
from django.views import View
from types import SimpleNamespace

from apps.teams.models import Team, Membership
from apps.teams.roles import (
    ROLE_OWNER, ROLE_ADMIN, ROLE_MANAGER, ROLE_OPERATOR, ROLE_VIEWER,
    has_permission, is_admin
)
from apps.teams.mixins import PermissionRequiredMixin
from apps.teams.decorators import require_permission
from apps.users.models import CustomUser

class RBACLogicTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.team = Team.objects.create(name="Test Team", slug="test")
        
        cls.owner = CustomUser.objects.create(email="owner@test.com", username="owner@test.com")
        Membership.objects.create(user=cls.owner, team=cls.team, role=ROLE_OWNER)
        
        cls.admin = CustomUser.objects.create(email="admin@test.com", username="admin@test.com")
        Membership.objects.create(user=cls.admin, team=cls.team, role=ROLE_ADMIN)
        
        cls.manager = CustomUser.objects.create(email="manager@test.com", username="manager@test.com")
        Membership.objects.create(user=cls.manager, team=cls.team, role=ROLE_MANAGER)
        
        cls.operator = CustomUser.objects.create(email="operator@test.com", username="operator@test.com")
        Membership.objects.create(user=cls.operator, team=cls.team, role=ROLE_OPERATOR)
        
        cls.viewer = CustomUser.objects.create(email="viewer@test.com", username="viewer@test.com")
        Membership.objects.create(user=cls.viewer, team=cls.team, role=ROLE_VIEWER)
        
        cls.stranger = CustomUser.objects.create(email="stranger@test.com", username="stranger@test.com")

    def test_has_permission(self):
        # view_dashboard: all 5 roles
        for user in [self.owner, self.admin, self.manager, self.operator, self.viewer]:
            self.assertTrue(has_permission(user, self.team, "view_dashboard"), f"{user.email} should have view_dashboard")
        self.assertFalse(has_permission(self.stranger, self.team, "view_dashboard"))
        
        # manage_devices: Owner, Admin, Manager
        for user in [self.owner, self.admin, self.manager]:
            self.assertTrue(has_permission(user, self.team, "manage_devices"), f"{user.email} should have manage_devices")
        for user in [self.operator, self.viewer]:
            self.assertFalse(has_permission(user, self.team, "manage_devices"), f"{user.email} should NOT have manage_devices")
            
        # manage_team: Owner, Admin
        for user in [self.owner, self.admin]:
            self.assertTrue(has_permission(user, self.team, "manage_team"), f"{user.email} should have manage_team")
        for user in [self.manager, self.operator, self.viewer]:
            self.assertFalse(has_permission(user, self.team, "manage_team"), f"{user.email} should NOT have manage_team")
            
        # manage_billing: Owner only
        self.assertTrue(has_permission(self.owner, self.team, "manage_billing"))
        for user in [self.admin, self.manager, self.operator, self.viewer]:
            self.assertFalse(has_permission(self.owner, self.team, "manage_billing") is False if user == self.owner else has_permission(user, self.team, "manage_billing"), f"{user.email} should NOT have manage_billing")
            # Wait, fixed loop logic above
            self.assertFalse(has_permission(user, self.team, "manage_billing"))

    def test_is_admin(self):
        self.assertTrue(is_admin(self.owner, self.team))
        self.assertTrue(is_admin(self.admin, self.team))
        self.assertFalse(is_admin(self.manager, self.team))
        self.assertFalse(is_admin(self.operator, self.team))
        self.assertFalse(is_admin(self.viewer, self.team))

class RBACViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.factory = RequestFactory()
        cls.team = Team.objects.create(name="Test Team", slug="test")
        
        cls.admin = CustomUser.objects.create(username="admin@test.com")
        Membership.objects.create(user=cls.admin, team=cls.team, role=ROLE_ADMIN)
        
        cls.viewer = CustomUser.objects.create(username="viewer@test.com")
        Membership.objects.create(user=cls.viewer, team=cls.team, role=ROLE_VIEWER)

    def _get_request(self, user):
        request = self.factory.get("/")
        request.user = user
        request.team = self.team
        request.session = {}
        return request

    def test_permission_required_mixin(self):
        class TestView(PermissionRequiredMixin, View):
            permission_required = "manage_devices"
            def get(self, request, *args, **kwargs):
                return HttpResponse("Success")

        view = TestView.as_view()
        
        # Admin has manage_devices
        request = self._get_request(self.admin)
        response = view(request)
        self.assertEqual(response.status_code, 200)
        
        # Viewer does not have manage_devices -> 403
        request = self._get_request(self.viewer)
        response = view(request)
        self.assertEqual(response.status_code, 403)

    def test_require_permission_decorator(self):
        @require_permission("manage_devices")
        def test_view(request, team_slug):
            return HttpResponse("Success")

        # Admin has manage_devices
        request = self._get_request(self.admin)
        response = test_view(request, team_slug="test")
        self.assertEqual(response.status_code, 200)
        
        # Viewer does not have manage_devices -> 403
        request = self._get_request(self.viewer)
        response = test_view(request, team_slug="test")
        self.assertEqual(response.status_code, 403)

class RBACTemplateTagTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.team = Team.objects.create(name="Test Team", slug="test")
        cls.admin = CustomUser.objects.create(username="admin@test.com")
        Membership.objects.create(user=cls.admin, team=cls.team, role=ROLE_ADMIN)
        cls.viewer = CustomUser.objects.create(username="viewer@test.com")
        Membership.objects.create(user=cls.viewer, team=cls.team, role=ROLE_VIEWER)

    def test_has_perm_tag(self):
        template = Template(
            "{% load team_permissions %}"
            "{% has_perm 'manage_devices' as can_manage %}"
            "{% if can_manage %}YES{% else %}NO{% endif %}"
        )
        
        # Admin
        request = SimpleNamespace(user=self.admin, team=self.team)
        context = Context({'request': request})
        self.assertIn("YES", template.render(context))
        
        # Viewer
        request = SimpleNamespace(user=self.viewer, team=self.team)
        context = Context({'request': request})
        self.assertIn("NO", template.render(context))
