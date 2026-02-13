from django.urls import path

from .auth_views import CsrfTokenView, LoginView, LogoutView, MeView

urlpatterns = [
    path("csrf/", CsrfTokenView.as_view(), name="api-auth-csrf"),
    path("login/", LoginView.as_view(), name="api-auth-login"),
    path("logout/", LogoutView.as_view(), name="api-auth-logout"),
    path("me/", MeView.as_view(), name="api-auth-me"),
]
