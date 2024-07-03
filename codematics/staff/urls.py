from rest_framework import routers
from .views import StoreViewSet, VisibilityScheduleViewSet


router = routers.DefaultRouter()

router.register(r"", StaffViewSet, basename="staff")



urlpatterns = router.urls