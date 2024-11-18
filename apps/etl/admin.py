from django.contrib import admin

# Register your models here.
from .models import ExtractionData, ExtractionLog

admin.site.register(ExtractionData)
admin.site.register(ExtractionLog)
