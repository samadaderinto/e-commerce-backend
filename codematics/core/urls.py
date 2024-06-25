from rest_framework import routers
from .views import AuthViewSet, UserViewSet


router = routers.DefaultRouter()

router.register(r"", AuthViewSet, basename="auth")
router.register(r"", UserViewSet, basename="user")


urlpatterns = router.urls