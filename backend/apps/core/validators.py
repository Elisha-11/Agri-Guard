"""Field validators shared by several apps, each mirroring a rule in docs/api-contract.yaml."""

from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator

# Contract schema `PhoneNumber`: Zambian mobile in E.164 (Airtel 097/077, MTN 096/076, Zamtel 095/075).
PHONE_REGEX = r"^\+260(9[5-7]|7[5-7])\d{7}$"
validate_zambian_phone = RegexValidator(
    PHONE_REGEX,
    message="Enter a Zambian mobile number in international format, e.g. +260971234567.",
    code="invalid_phone",
)

# Contract schema `GeoPoint`: a bounding box around Zambia. Points outside it are almost certainly GPS errors.
LATITUDE_VALIDATORS = [MinValueValidator(Decimal("-18.1")), MaxValueValidator(Decimal("-8.2"))]
LONGITUDE_VALIDATORS = [MinValueValidator(Decimal("21.9")), MaxValueValidator(Decimal("33.8"))]

# Contract `Prediction.confidence` and `top_k[].confidence`.
PROBABILITY_VALIDATORS = [MinValueValidator(0.0), MaxValueValidator(1.0)]
