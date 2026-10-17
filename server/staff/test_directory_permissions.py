from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from core.models import User
from staff.views import StaffViewSet


class DirectoryPermissionTests(TestCase):
    def setUp(self) -> None:
        self.staff = User.objects.create_user(email='operator@test.com', password='test-password', is_staff=True)
        self.peer = User.objects.create_user(email='peer@test.com', password='test-password', is_staff=True)
        self.admin = User.objects.create_superuser(email='root@test.com', password='test-password')
        self.customer = User.objects.create_user(email='customer@test.com', password='test-password')
        self.factory = APIRequestFactory()

    def test_staff_directory_never_exposes_privileged_accounts(self) -> None:
        for query in ('', '?role=staff', '?role=admin'):
            request = self.factory.get('/users/' + query)
            force_authenticate(request, self.staff)
            response = StaffViewSet.as_view({'get': 'users'})(request)
            ids = [row['id'] for row in response.data['results']]
            self.assertNotIn(self.peer.pk, ids)
            self.assertNotIn(self.admin.pk, ids)

    def test_staff_can_block_customer_but_not_change_roles_or_modify_peers(self) -> None:
        for target, payload, expected in (
            (self.customer, {'is_active': False}, 200),
            (self.customer, {'is_staff': True}, 403),
            (self.peer, {'is_active': False}, 403),
            (self.admin, {'is_active': False}, 403),
        ):
            request = self.factory.patch('/users/', payload, format='json')
            force_authenticate(request, self.staff)
            response = StaffViewSet.as_view({'patch': 'user_detail'})(request, user_pk=str(target.pk))
            self.assertEqual(response.status_code, expected, response.data)

    def test_admin_cannot_bypass_staff_invitation_by_promoting_a_customer(self) -> None:
        request = self.factory.patch(
            '/users/', {'is_staff': True}, format='json'
        )
        force_authenticate(request, self.admin)

        response = StaffViewSet.as_view({'patch': 'user_detail'})(
            request, user_pk=str(self.customer.pk)
        )

        self.assertEqual(response.status_code, 400, response.data)
        self.customer.refresh_from_db()
        self.assertFalse(self.customer.is_staff)
        self.assertTrue(self.customer.is_active)
        self.assertTrue(self.customer.staff_email_verified)
