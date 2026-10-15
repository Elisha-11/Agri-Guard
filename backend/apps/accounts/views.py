"""Auth endpoints: contract `/auth/otp/request/`, `/auth/otp/verify/` and `/auth/token/refresh/`.

The rules live in apps/accounts/otp.py; these views only translate between HTTP and that module.
"""

from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import exceptions, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from apps.core.exceptions import ServiceUnavailable

from . import otp
from .serializers import (
    ErrorSerializer,
    OtpRequestResponseSerializer,
    OtpRequestSerializer,
    OtpVerifySerializer,
    RefreshedTokensSerializer,
    TokenPairSerializer,
)
from .sms import SmsError


class InvalidCode(exceptions.APIException):
    """401, per the contract. Not AuthenticationFailed, which DRF turns into a 403 on views like these
    that have no authenticators."""

    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = "That code is wrong or has expired. Check the SMS or request a new code."
    default_code = "invalid_code"


class PublicAuthView(APIView):
    """No token needed: these are how a farmer gets one."""

    permission_classes = [AllowAny]
    authentication_classes = []


class OtpRequestView(PublicAuthView):
    @extend_schema(
        tags=["auth"],
        operation_id="requestOtp",
        summary="Send a 6-digit one-time code by SMS",
        request=OtpRequestSerializer,
        responses={
            202: OtpRequestResponseSerializer,
            400: ErrorSerializer,
            429: ErrorSerializer,
            503: OpenApiResponse(ErrorSerializer, description="SMS provider unavailable"),
        },
    )
    def post(self, request):
        serializer = OtpRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            expires_in = otp.request_code(serializer.validated_data["phone"])
        except otp.OtpRateLimited as exc:
            raise exceptions.Throttled(
                wait=exc.wait, detail="Too many codes requested for this number. Please wait and try again."
            ) from exc
        except SmsError as exc:
            raise ServiceUnavailable(
                "We couldn't send the SMS just now. Please try again in a few minutes.",
                code="sms_unavailable",
            ) from exc
        return Response({"expires_in": expires_in}, status=status.HTTP_202_ACCEPTED)


class OtpVerifyView(PublicAuthView):
    @extend_schema(
        tags=["auth"],
        operation_id="verifyOtp",
        summary="Exchange phone + code for tokens; creates the farmer account on first login",
        request=OtpVerifySerializer,
        responses={
            200: TokenPairSerializer,
            400: ErrorSerializer,
            401: ErrorSerializer,
            429: ErrorSerializer,
        },
    )
    def post(self, request):
        serializer = OtpVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            farmer, created = otp.verify_code(**serializer.validated_data)
        except otp.OtpInvalid as exc:
            raise InvalidCode() from exc
        except otp.OtpRateLimited as exc:
            raise exceptions.Throttled(
                wait=exc.wait, detail="Too many wrong codes. Please request a new code."
            ) from exc

        refresh = RefreshToken.for_user(farmer)
        return Response(
            {"access": str(refresh.access_token), "refresh": str(refresh), "is_new_user": created}
        )


@extend_schema_view(
    post=extend_schema(
        tags=["auth"],
        operation_id="refreshToken",
        summary="Get a new access token",
        responses={200: RefreshedTokensSerializer, 401: ErrorSerializer},
    )
)
class RefreshView(TokenRefreshView):
    """simplejwt's refresh, with rotation: each refresh token works once (see SIMPLE_JWT in settings)."""
