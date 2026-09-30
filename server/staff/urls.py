from rest_framework import routers
from .views import StaffViewSet


router = routers.DefaultRouter()

router.register(r"", StaffViewSet, basename="staff")



urlpatterns = router.urls
