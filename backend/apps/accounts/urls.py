from django.urls import path

from .views import OtpRequestView, OtpVerifyView, RefreshView

urlpatterns = [
    path("otp/request/", OtpRequestView.as_view(), name="otp-request"),
    path("otp/verify/", OtpVerifyView.as_view(), name="otp-verify"),
    path("token/refresh/", RefreshView.as_view(), name="token-refresh"),
]
