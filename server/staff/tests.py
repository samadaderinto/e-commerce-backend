from django.urls import include, path
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from core.models import User


urlpatterns = [path("staffs/", include("staff.urls"))]


@override_settings(ROOT_URLCONF=__name__)
class StaffAdministrationTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            email="admin@example.com",
            password="Admin-password-123!",
        )
        self.staff = User.objects.create_staffuser(
            email="staff@example.com",
            password="Staff-password-123!",
        )
        self.client = APIClient()

    def staff_payload(self):
        return {
            "email": "new.staff@example.com",
            "first_name": "New",
            "last_name": "Staff",
            "phone1": "+2348012345678",
            "gender": "female",
            "password": "New-staff-password-123!",
        }

    def test_admin_can_create_staff(self):
        self.client.force_authenticate(self.admin)

        response = self.client.post("/staffs/staffs/", self.staff_payload(), format="json")

        self.assertEqual(response.status_code, 201, response.data)
        created = User.objects.get(email="new.staff@example.com")
        self.assertTrue(created.is_staff)
        self.assertFalse(created.is_superuser)
        self.assertTrue(created.is_active)
        self.assertTrue(created.check_password("New-staff-password-123!"))
        self.assertNotIn("password", response.data)

    def test_staff_cannot_create_or_list_staff(self):
        self.client.force_authenticate(self.staff)

        self.assertEqual(self.client.get("/staffs/staffs/").status_code, 403)
        self.assertEqual(
            self.client.post("/staffs/staffs/", self.staff_payload(), format="json").status_code,
            403,
        )

    def test_admin_can_block_and_unblock_staff(self):
        self.client.force_authenticate(self.admin)

        response = self.client.post(f"/staffs/staffs/{self.staff.pk}/block/")
        self.assertEqual(response.status_code, 200, response.data)
        self.staff.refresh_from_db()
        self.assertFalse(self.staff.is_active)

        response = self.client.post(f"/staffs/staffs/{self.staff.pk}/unblock/")
        self.assertEqual(response.status_code, 200, response.data)
        self.staff.refresh_from_db()
        self.assertTrue(self.staff.is_active)

    def test_staff_cannot_block_another_staff(self):
        other_staff = User.objects.create_staffuser(
            email="other.staff@example.com",
            password="Other-password-123!",
        )
        self.client.force_authenticate(self.staff)

        response = self.client.post(f"/staffs/staffs/{other_staff.pk}/block/")

        self.assertEqual(response.status_code, 403)
        other_staff.refresh_from_db()
        self.assertTrue(other_staff.is_active)

    def test_admin_accounts_cannot_be_blocked_through_staff_endpoint(self):
        self.client.force_authenticate(self.admin)

        response = self.client.post(f"/staffs/staffs/{self.admin.pk}/block/")

        self.assertEqual(response.status_code, 404)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)


@override_settings(ROOT_URLCONF="storefront.urls")
class StaffFrontendApiIntegrationTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            email="frontend.admin@example.com",
            password="Admin-password-123!",
        )
        self.staff = User.objects.create_staffuser(
            email="frontend.staff@example.com",
            password="Staff-password-123!",
        )
        self.client = APIClient()

    def test_frontend_session_exposes_admin_role_and_routes_staff_actions(self):
        self.client.force_authenticate(self.admin)

        me = self.client.get("/api/v1/me/")
        listing = self.client.get("/api/v1/admin/staff/")
        blocked = self.client.post(f"/api/v1/admin/staff/{self.staff.pk}/block/")

        self.assertEqual(me.status_code, 200, me.data)
        self.assertTrue(me.data["is_superuser"])
        self.assertEqual(listing.status_code, 200, listing.data)
        self.assertEqual(listing.data["results"][0]["id"], self.staff.pk)
        self.assertEqual(blocked.status_code, 200, blocked.data)
        self.assertFalse(blocked.data["is_active"])

    def test_frontend_staff_route_rejects_non_admin_staff(self):
        self.client.force_authenticate(self.staff)

        response = self.client.get("/api/v1/admin/staff/")

        self.assertEqual(response.status_code, 403)

# Create your tests here.
