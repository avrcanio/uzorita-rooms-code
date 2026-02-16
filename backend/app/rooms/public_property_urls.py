from django.urls import path

from .public_property_views import PublicPropertyView


urlpatterns = [
    path("", PublicPropertyView.as_view(), {"code": "default"}, name="public-property"),
]
