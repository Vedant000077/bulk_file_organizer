from django.db import models
from django.contrib.auth.models import User
from django.utils.timezone import now


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    total_files_organized = models.IntegerField(default=0)
    total_space_saved = models.BigIntegerField(default=0)  # in bytes
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} Profile"


class CustomRule(models.Model):
    MATCH_TYPE_CHOICES = [
        ('extension', 'File Extension'),
        ('size', 'File Size'),
        ('date', 'Modified Date'),
        ('name', 'File Name Pattern'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='custom_rules')
    name = models.CharField(max_length=100)
    rule_type = models.CharField(max_length=20, choices=MATCH_TYPE_CHOICES)
    match_value = models.CharField(max_length=255, help_text='Extension, size range, date pattern, or name regex')
    target_folder = models.CharField(max_length=100)
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.rule_type})"


class UploadJob(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='upload_jobs')
    job_name = models.CharField(max_length=255, default='Untitled Job')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    total_files = models.IntegerField(default=0)
    processed_files = models.IntegerField(default=0)
    total_size = models.BigIntegerField(default=0)  # in bytes
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    zip_file = models.FileField(upload_to='jobs/', null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.job_name} - {self.status}"


class FileRecord(models.Model):
    job = models.ForeignKey(UploadJob, on_delete=models.CASCADE, related_name='files')
    original_name = models.CharField(max_length=255)
    new_name = models.CharField(max_length=255)
    category = models.CharField(max_length=50)
    file_size = models.BigIntegerField()  # in bytes
    original_path = models.CharField(max_length=500)
    organized_path = models.CharField(max_length=500, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.original_name} → {self.new_name}"
