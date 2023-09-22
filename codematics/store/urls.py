from django.urls import path

from store.views import (
    delete_file,
    delete_store,
    edit_store_info,
    get_stores,

    ProductCreateView,
   delete_product,
    IsOwnerSearchProduct,
    delete_schedule,
    add_schedule,
    get_schedule,
    edit_product,
    get_store_product,
    store_add_product_image,
    store_product_image,
    store_product_images
)



urlpatterns = [
     
    
    path("<int:storeId>/delete/", delete_store, name="delete_store"),

    path("<int:storeId>/edit/", edit_store_info, name="edit_store"),


    path("<int:storeId>/schedules/<int:productId>/get/", get_schedule, name="get_product_schedule"),
    path("schedules/add/", add_schedule, name="products"),
    path("<int:storeId>/schedules/<int:productId>/delete/", delete_schedule, name="delete_schedule"),

    path("<int:storeId>/products/<int:productId>/get/", get_store_product, name="get_store_product"),
    path("products/create/", ProductCreateView.as_view(), name="create_product"),
    path("<int:storeId>/products/<int:productId>/edit/", edit_product, name="edit_product"),
    path("<int:storeId>/products/<int:productId>/delete/", delete_product, name="delete_product"),
    path("products/search", IsOwnerSearchProduct.as_view(), name="get_store_products"),


    path("<int:storeId>/products/<int:productId>/images/get/", store_product_images, name="store_product_images"),
    path("<int:storeId>/products/<int:productId>/images/<int:imageId>/get/", store_product_image, name="store_product_image"),
    path("products/images/create/", store_add_product_image, name="store_add_product_image"),
    path("<int:storeId>/products/<int:productId>/images/<str:filename>/delete/", delete_file, name="file_delete"),
]
