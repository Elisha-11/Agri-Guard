from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .forms import FarmerChangeForm, FarmerCreationForm
from .models import Farmer


@admin.register(Farmer)
class FarmerAdmin(UserAdmin):
    """Django's user admin, adapted to phone login and the farmer profile fields."""

    form = FarmerChangeForm
    add_form = FarmerCreationForm
    ordering = ["-date_joined"]
    list_display = [
        "phone",
        "display_name",
        "role",
        "preferred_language",
        "district",
        "date_joined",
        "is_staff",
    ]
    list_filter = ["role", "preferred_language", "province", "is_staff", "is_active"]
    search_fields = ["phone", "display_name", "district"]
    readonly_fields = ["id", "date_joined", "last_login"]
    fieldsets = [
        (None, {"fields": ["id", "phone", "password"]}),
        ("Profile", {"fields": ["display_name", "preferred_language", "role", "province", "district"]}),
        ("Consent", {"fields": ["photo_consent", "location_consent"]}),
        ("Access", {"fields": ["is_active", "is_staff", "is_superuser", "groups", "user_permissions"]}),
        ("Dates", {"fields": ["date_joined", "last_login", "updated_at"]}),
    ]
    add_fieldsets = [(None, {"classes": ["wide"], "fields": ["phone", "password1", "password2"]})]
