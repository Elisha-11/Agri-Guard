from django.contrib import admin

from .models import Farm


@admin.register(Farm)
class FarmAdmin(admin.ModelAdmin):
    list_display = ["name", "owner", "size_hectares", "created_at"]
    search_fields = ["name", "owner__phone"]
    raw_id_fields = ["owner"]
    readonly_fields = ["id", "client_id", "created_at"]
