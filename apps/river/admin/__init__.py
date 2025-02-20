from river.admin.function_admin import *
from river.admin.hook_admins import *
from river.admin.transitionapprovalmeta import *
from river.admin.transitionmeta import *
from river.admin.transitionapproval import *
from river.admin.workflow import *
from river.models import State

class StateAdmin(admin.ModelAdmin):
    # form = State
    list_display = ('id', 'slug', 'label', 'description')
    
admin.site.register(State, StateAdmin)
