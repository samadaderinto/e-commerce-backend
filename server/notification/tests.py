from django.test import TestCase, override_settings
from django.urls import include, path
from rest_framework.test import APIClient

from core.models import User
from notification.models import Notification
from notification.views import create_notification, notify_staff


urlpatterns = [
    path("notifications/", include("notification.urls")),
]


@override_settings(ROOT_URLCONF=__name__)
class NotificationApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="buyer@example.com",
            password="pass12345",
            first_name="Buyer",
            last_name="One",
            gender="male",
            phone1="+2348012345678",
        )
        self.staff = User.objects.create_staffuser(
            email="staff@example.com",
            password="pass12345",
            first_name="Staff",
            last_name="One",
            gender="female",
            phone1="+2348012345679",
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_user_can_list_and_count_own_notifications(self):
        create_notification(
            recipient=self.user,
            verb="order shipped",
            description="Your order is on the way.",
            data={"event": "order_shipped"},
        )
        create_notification(
            recipient=self.staff,
            verb="staff only",
            description="Hidden from buyer.",
        )

        response = self.client.get("/notifications/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["verb"], "order shipped")

        counts = self.client.get("/notifications/counts/")
        self.assertEqual(counts.status_code, 200, counts.data)
        self.assertEqual(counts.data["unread"], 1)
        self.assertEqual(counts.data["total"], 1)

    def test_mark_read_unread_archive_and_restore(self):
        notification = create_notification(recipient=self.user, verb="refund requested")

        read = self.client.post(f"/notifications/{notification.pk}/mark-read/")
        self.assertEqual(read.status_code, 200, read.data)
        self.assertFalse(read.data["unread"])

        unread = self.client.post(f"/notifications/{notification.pk}/mark-unread/")
        self.assertEqual(unread.status_code, 200, unread.data)
        self.assertTrue(unread.data["unread"])

        archived = self.client.post(f"/notifications/{notification.pk}/archive/")
        self.assertEqual(archived.status_code, 200, archived.data)
        self.assertTrue(archived.data["deleted"])
        self.assertEqual(self.client.get("/notifications/").data["count"], 0)
        self.assertEqual(self.client.get("/notifications/archived/").data["count"], 1)

        restored = self.client.post(f"/notifications/{notification.pk}/restore/")
        self.assertEqual(restored.status_code, 200, restored.data)
        self.assertFalse(restored.data["deleted"])

    def test_mark_all_read_and_event_filter(self):
        create_notification(recipient=self.user, verb="one", data={"event": "orders"})
        create_notification(recipient=self.user, verb="two", data={"event": "refunds"})

        filtered = self.client.get("/notifications/", {"event": "refunds"})
        self.assertEqual(filtered.status_code, 200, filtered.data)
        self.assertEqual(filtered.data["count"], 1)
        self.assertEqual(filtered.data["results"][0]["verb"], "two")

        response = self.client.post("/notifications/mark-all-read/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["updated"], 2)
        self.assertEqual(Notification.objects.filter(recipient=self.user, unread=True).count(), 0)

    def test_notify_staff_only_targets_active_staff(self):
        inactive_staff = User.objects.create_staffuser(
            email="inactive@example.com",
            password="pass12345",
            first_name="Inactive",
            last_name="Staff",
            gender="female",
            phone1="+2348012345680",
            is_active=False,
        )

        notify_staff("dashboard alert", actor=self.user, data={"event": "dashboard_alert"})

        self.assertTrue(Notification.objects.filter(recipient=self.staff).exists())
        self.assertFalse(Notification.objects.filter(recipient=self.user).exists())
        self.assertFalse(Notification.objects.filter(recipient=inactive_staff).exists())
