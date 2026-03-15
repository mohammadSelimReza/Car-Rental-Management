from django.contrib import admin

from .models import Car, ExtraService

admin.site.register(Car)
admin.site.register(ExtraService)