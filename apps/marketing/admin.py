from django.contrib import admin
from .models import *

admin.site.register(Document)
admin.site.register(Folder)
admin.site.register(Campaign)
admin.site.register(CampaignDocument)
admin.site.register(Vendor)
admin.site.register(Agency)
admin.site.register(AgencyType)
admin.site.register(AgencyRemark)
admin.site.register(CampaignSpecificBudget)