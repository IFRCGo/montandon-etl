from django.contrib import admin

# Register your models here.
from .models import ExtractionLog, ExtractionData

admin.site.register(ExtractionData)
admin.site.register(ExtractionLog)
