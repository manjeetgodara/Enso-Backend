from django.contrib import admin
from .models import Email,EmailTemplate
# Register your models here.

class EmailAdmin(admin.ModelAdmin):
   list_display = ('subject' , 'name' , 'message')

class EmailTemplateAdmin(admin.ModelAdmin):
   list_display = ('subject', 'message')

admin.site.register(Email,EmailAdmin)
admin.site.register(EmailTemplate,EmailTemplateAdmin)