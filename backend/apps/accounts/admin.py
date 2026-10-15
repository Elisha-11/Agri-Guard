from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .forms import FarmerChangeForm, FarmerCreationForm
from .models import Farmer, OtpCode


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


@admin.register(OtpCode)
class OtpCodeAdmin(admin.ModelAdmin):
    """Read-only, for support ("I never got my code"). Codes are hashed, so no one can read them here."""

    list_display = ["phone", "created_at", "expires_at", "attempts", "used_at"]
    search_fields = ["phone"]
    date_hierarchy = "created_at"
    exclude = ["code_hash"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
