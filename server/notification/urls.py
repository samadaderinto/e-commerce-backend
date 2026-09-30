from rest_framework import routers

from notification.views import NotificationViewSet


router = routers.DefaultRouter()
router.register(r"", NotificationViewSet, basename="notification")

urlpatterns = router.urls
