from django.contrib import admin
from .models import Dashboard


@admin.register(Dashboard)
class DashboardAdmin(admin.ModelAdmin):
    list_display = ['user', 'theme', 'sidebar_collapsed', 'created_at', 'updated_at']
    list_filter = ['theme', 'sidebar_collapsed']
    search_fields = ['user__email']
    readonly_fields = ['created_at', 'updated_at']
