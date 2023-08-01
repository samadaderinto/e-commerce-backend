from django.urls import path


from product.views import (
    view_product
)


from store.views import (
    create_store,
    delete_file,
    delete_store,
    edit_store_info,
    get_store,
    get_stores,
    store_products,
    create_product,
   
    IsOwnerSearchProduct
)

urlpatterns = [
     
    path("create/", create_store, name="create_store"),
    path("<int:storeId>/delete/", delete_store, name="products"),
    path("<int:store>/edit/", edit_store_info, name="products"),


    path("get/", get_stores, name="products"),
    path("<int:user>/", get_store, name="get_store"),

    path("<int:store>/products/",
         store_products, name="store_products"),

    path("schedules/", store_products, name="products"),
    path("schedules/add/", store_products, name="products"),
    path("schedules/<int:id>/delete/", store_products, name="products"),
    path("schedules/<int:id>/edit/", store_products, name="products"),

    path("products/<int:id>/", store_products, name="product"),
    path("products/create/", create_product, name="create_product"),
    path("products/<int:id>/edit/", store_products, name="product"),
    path("products/<int:id>/delete/", view_product, name="product"),

    path("products/search", IsOwnerSearchProduct.as_view(), name="products"),




    # path("productImg/", ProductsDetailAPIView(), name="products"),
    # path("productImg/<int:productId>/", ProductsDetailAPIView(), name="products"),
    # path("ProductImg/id/<int:id>/", ProductsDetailAPIView(), name="products"),
   
    path("delete_file/<str:filename>/", delete_file, name="file_delete"),
]
