from django.contrib import admin, messages

from .models import ModelRelease


@admin.register(ModelRelease)
class ModelReleaseAdmin(admin.ModelAdmin):
    """Releases are created by `manage.py register_model`, which checks the files.

    Here you only make a release current (or roll back) and edit its notes.
    """

    list_display = [
        "model_version",
        "is_current",
        "taxonomy_version",
        "size_bytes",
        "min_app_version",
        "created_at",
    ]
    readonly_fields = [f.name for f in ModelRelease._meta.fields if f.name != "notes"]
    actions = ["make_current"]

    def has_add_permission(self, request):
        return False

    @admin.action(description="Make the selected release current (phones switch to it)")
    def make_current(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, "Select exactly one release.", messages.ERROR)
            return
        release = queryset.get()
        release.make_current()
        self.message_user(request, f"{release.model_version} is now current.", messages.SUCCESS)
