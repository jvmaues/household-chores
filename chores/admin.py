from django.contrib import admin

from .models import Chore


@admin.register(Chore)
class ChoreAdmin(admin.ModelAdmin):
    list_display = ("title", "household", "recurrence", "points", "is_paused", "rotation_start_member")
    list_filter = ("household", "recurrence", "is_paused")
    search_fields = ("title",)
    readonly_fields = ("created_by", "created_at")
