"""Only SSE and health probes are available in the dedicated stream process."""
from django.urls import path

from notification.realtime import stream
from observability.views import live, ready

urlpatterns = [
    path('api/v1/notifications/stream/', stream),
    path('health/live/', live),
    path('health/ready/', ready),
]
