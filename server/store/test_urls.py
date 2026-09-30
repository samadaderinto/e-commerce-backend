from django.urls import include, path

urlpatterns = [path('stores/', include('store.urls'))]
