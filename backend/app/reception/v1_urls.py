from django.urls import path

from .scan_views import PaddleDocumentScanView

urlpatterns = [
    path("scan/", PaddleDocumentScanView.as_view(), name="api-v1-paddle-scan"),
]
