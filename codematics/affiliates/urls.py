from rest_framework import routers
from .views import AffiliatesViewSet


router = routers.DefaultRouter()

router.register(r"", AffiliatesViewSet, basename="affiliate")


urlpatterns = router.urls