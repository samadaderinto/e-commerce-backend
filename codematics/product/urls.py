from django.urls import path
from product.views import view_product, SearchProduct, get_product_reviews



urlpatterns = [
    path("<int:productId>/", view_product, name="get_product"),
    path("<int:productId>/reviews/", get_product_reviews, name="get_product_reviews"),
    path("search", SearchProduct.as_view(), name="products"),
    
]
