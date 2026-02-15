"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path
from django.views.generic.base import RedirectView
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from .health import health
from django.conf import settings
from django.conf.urls.static import static

admin.site.site_header = "Uzorita administracija"
admin.site.site_title = "Uzorita administracija"
admin.site.index_title = "Uzorita administracija"

urlpatterns = [
    path("favicon.ico", RedirectView.as_view(url="/static/favicon.ico", permanent=True)),
    path("logo.png", RedirectView.as_view(url="/static/logo.png", permanent=True)),
    path("admin/", admin.site.urls),
    path("health/", health, name="health"),
    path("api/schema/", SpectacularAPIView.as_view(), name="api-schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="api-schema"), name="api-docs"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="api-schema"), name="api-redoc"),
    path("api/auth/", include("config.auth_urls")),
    path("api/reception/", include("reception.api_urls")),
    path("api/rooms/", include("rooms.api_urls")),
    path("reception/", include("reception.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
