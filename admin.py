from django.contrib import admin
from .models import UserProfile, CustomRule, UploadJob, FileRecord


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'total_files_organized', 'created_at')
    readonly_fields = ('total_files_organized', 'total_space_saved')


@admin.register(CustomRule)
class CustomRuleAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'rule_type', 'enabled', 'created_at')
    list_filter = ('rule_type', 'enabled', 'created_at')
    search_fields = ('name', 'user__username')


@admin.register(UploadJob)
class UploadJobAdmin(admin.ModelAdmin):
    list_display = ('job_name', 'user', 'status', 'total_files', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('job_name', 'user__username')
    readonly_fields = ('created_at', 'completed_at')


@admin.register(FileRecord)
class FileRecordAdmin(admin.ModelAdmin):
    list_display = ('original_name', 'new_name', 'category', 'job')
    list_filter = ('category', 'created_at')
    search_fields = ('original_name', 'new_name')
