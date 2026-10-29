from django.db import models
from django.contrib.auth.models import User

class DashboardPreset(models.Model):
    # This model is used as a preset for users configure the charts before creating it
    
    # Links the preset to the user who created it
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='dashboard_presets')
    
    # The display name of the preset
    name = models.CharField(max_length=100)
    
    # The actual filter parameters to configure the charts
    city = models.CharField(max_length=100, blank=True, null=True)
    district = models.CharField(max_length=100, blank=True, null=True)
    waste_type = models.CharField(max_length=20, blank=True, null=True)
    severity = models.CharField(max_length=10, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} - {self.user.username}"