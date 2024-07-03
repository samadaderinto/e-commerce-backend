from rest_framework import routers
from .views import StoreViewSet, VisibilityScheduleViewSet


router = routers.DefaultRouter()

router.register(r"", StoreViewSet, basename="store")
router.register(r"", VisibilityScheduleViewSet, basename="visiblity")



urlpatterns = router.urls
