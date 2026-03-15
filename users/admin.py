from django.contrib import admin
from . models import User, Customer, AgencyAgent, Agency, AgencyAdmin

admin.site.register(User)
admin.site.register(Customer)
admin.site.register(AgencyAgent)
admin.site.register(Agency)
admin.site.register(AgencyAdmin)
