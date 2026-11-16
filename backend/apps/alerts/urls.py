from django.urls import path

from .views import NearbyAlertsView

urlpatterns = [
    path("alerts/nearby/", NearbyAlertsView.as_view(), name="alerts-nearby"),
]
