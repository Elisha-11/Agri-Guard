from django.contrib import admin

from .models import Disease, DiseaseAdvice, UiMessage


class DiseaseAdviceInline(admin.StackedInline):
    model = DiseaseAdvice
    extra = 0


@admin.register(Disease)
class DiseaseAdmin(admin.ModelAdmin):
    """Read-only apart from advice: disease rows come from ml/labels.json via `manage.py load_taxonomy`."""

    list_display = ["class_index", "class_id", "crop", "is_healthy", "is_retired", "taxonomy_version"]
    list_filter = ["crop", "is_healthy", "is_retired"]
    readonly_fields = ["class_id", "class_index", "crop", "is_healthy", "is_retired", "taxonomy_version"]
    inlines = [DiseaseAdviceInline]

    def has_add_permission(self, request):
        return False


@admin.register(DiseaseAdvice)
class DiseaseAdviceAdmin(admin.ModelAdmin):
    list_display = ["disease", "lang", "name", "is_published", "reviewed_by", "reviewed_at", "updated_at"]
    list_filter = ["lang", "is_published", "disease__crop", "involves_chemicals"]
    search_fields = ["name", "local_name", "disease__class_id"]


@admin.register(UiMessage)
class UiMessageAdmin(admin.ModelAdmin):
    """Fixed messages for uncertain / consult / rejected results. Missing languages fall back to English."""

    list_display = ["key", "lang", "text", "updated_at"]
    list_filter = ["key", "lang"]
