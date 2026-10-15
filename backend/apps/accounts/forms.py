"""Admin forms. Django's stock user forms assume a `username` field, which Farmer doesn't have."""

from django.contrib.auth.forms import BaseUserCreationForm, UserChangeForm

from .models import Farmer


class FarmerCreationForm(BaseUserCreationForm):
    class Meta:
        model = Farmer
        fields = ["phone"]


class FarmerChangeForm(UserChangeForm):
    class Meta:
        model = Farmer
        fields = "__all__"
