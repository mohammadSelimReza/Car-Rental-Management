from django.contrib import admin

# Register your models here.
from .models import Quotation, Fine
admin.site.register(Quotation)
admin.site.register(Fine)