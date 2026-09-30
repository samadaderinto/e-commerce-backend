from django.urls import path

from . import views

urlpatterns = [
    path('health/live/', views.live),
    path('health/ready/', views.ready),
    path('health/status/', views.health_status),
    path('metrics/', views.metrics),
]
