from django.urls import path
from product.views import view_product, SearchProduct, get_product_reviews



urlpatterns = [
    path("<int:productId>/", view_product, name="get_product"),
    path("<int:productId>/reviews/", get_product_reviews, name="get_product_reviews"),
    path("search", SearchProduct.as_view(), name="products"),
    
]


# from rest_framework import routers
# from .views import StoreViewSet, VisibilityScheduleViewSet


# router = routers.DefaultRouter()

# router.register(r"", StoreViewSet, basename="store")
# router.register(r"", VisibilityScheduleViewSet, basename="visiblity")



# urlpatterns = router.urls