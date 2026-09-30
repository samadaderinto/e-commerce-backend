from rest_framework import routers
from .views import MerchantProductViewSet, StoreViewSet, VisibilityScheduleViewSet


router = routers.DefaultRouter()

router.register(r"schedules", VisibilityScheduleViewSet, basename="visibility")
router.register(r"(?P<store_pk>\d+)/products", MerchantProductViewSet, basename="merchant-product")
router.register(r"", StoreViewSet, basename="store")



urlpatterns = router.urls
