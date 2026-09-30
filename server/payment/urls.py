from rest_framework import routers
from .views import PaymentViewSet


router = routers.DefaultRouter()
router.register(r"", PaymentViewSet, basename="")
urlpatterns = router.urls
