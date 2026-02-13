from django.urls import path

from .views import ReceptionHealthView

urlpatterns = [
    path("health/", ReceptionHealthView.as_view(), name="reception-health"),
]
