# from django.contrib import admin
# from django.contrib.auth.admin import UserAdmin
# from .models import CustomUser


# admin.site.register(CustomUser)
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):

    list_display = (
        'username',
        'email',
        'role',
        'is_verified',
        'is_staff',
        'is_active',
    )

    list_filter = (
        'role',
        'is_verified',
        'is_staff',
        'is_active',
    )

    fieldsets = UserAdmin.fieldsets + (
        ('Role Information', {
            'fields': ('role', 'is_verified'),
        }),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Role Information', {
            'fields': ('role', 'is_verified'),
        }),
    )