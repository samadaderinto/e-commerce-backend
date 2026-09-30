from rest_framework import routers
from .views import ProductViewSet, SearchProductViewSet

router = routers.DefaultRouter()

router.register(r"", ProductViewSet, basename="")
router.register(r"", SearchProductViewSet, basename="search")


urlpatterns = router.urls