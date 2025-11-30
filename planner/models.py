from django.db import models
from django.conf import settings
from pgvector.django import VectorField


class Plan(models.Model):
    title = models.CharField(max_length=64)
    content = models.TextField()
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now=True)


class Document(models.Model):
    name = models.CharField(max_length=64)


class Chunk(models.Model):
    content = models.CharField(max_length=512)
    position = models.IntegerField()
    embedding = VectorField(dimensions=384)
    document = models.ForeignKey(Document, on_delete=models.CASCADE)
