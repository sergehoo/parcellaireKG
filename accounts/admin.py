from django.contrib import admin

from .models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "job_title", "organization", "department", "language", "updated_at")
    list_filter = ("language", "organization")
    search_fields = ("user__username", "user__email", "user__first_name", "user__last_name",
                     "job_title", "organization")
    raw_id_fields = ("user",)
    readonly_fields = ("created_at", "updated_at")
