from django.contrib import admin

from .models import Document, Plan

admin.site.register(Plan)
admin.site.register(Document)
