from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Household, User

HOUSEHOLD_FIELDSET = ("Household", {"fields": ("household", "is_household_admin")})


@admin.register(Household)
class HouseholdAdmin(admin.ModelAdmin):
    list_display = ("name", "timezone", "member_count", "created_at")
    readonly_fields = ("created_at",)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (HOUSEHOLD_FIELDSET,)
    add_fieldsets = BaseUserAdmin.add_fieldsets + (HOUSEHOLD_FIELDSET,)
    list_display = ("username", "email", "household", "is_household_admin", "is_staff")
    list_filter = BaseUserAdmin.list_filter + ("household", "is_household_admin")
