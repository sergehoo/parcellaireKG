from django.contrib import admin

from .models import CopilotConversation, CopilotMessage, CopilotToolCall


@admin.register(CopilotToolCall)
class CopilotToolCallAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "tool_name", "status", "detail")
    list_filter = ("status", "tool_name")
    search_fields = ("tool_name", "user__username", "detail")
    readonly_fields = ("user", "conversation", "tool_name", "arguments",
                       "status", "detail", "created_at")

    def has_add_permission(self, request):
        return False


@admin.register(CopilotConversation)
class CopilotConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "title", "updated_at")
    search_fields = ("title", "user__username")


admin.site.register(CopilotMessage)
