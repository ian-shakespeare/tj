from django.db import models
from django.conf import settings


class Plan(models.Model):
    title = models.CharField(max_length=64)
    content = models.TextField()
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now=True)
