from django.urls import path
from notification.realtime import stream
from rest_framework import routers

from notification.views import NotificationViewSet


router = routers.DefaultRouter()
router.register(r"", NotificationViewSet, basename="notification")

urlpatterns = [path('stream/', stream, name='notification-stream'), *router.urls]
