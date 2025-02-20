from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models  import Users, OTPSession
from django.contrib.auth.models import Group
# Register your models here.
from .forms import UserCreationForm, UserChangeForm

class CustomUserAdmin(UserAdmin):

    form = UserChangeForm
    add_form = UserCreationForm

    list_display = ('id', 'name','email', 'mobile', 'get_groups_display', 'role')

    def get_groups_display(self, obj):
        return ", ".join([group.name for group in obj.groups.all()])

    get_groups_display.short_description = 'Groups'
    
    fieldsets = (
        (None, {'fields': ('email', 'name','mobile','password', 'gender', 'role', 'is_active', 'is_staff', 'is_superuser', 'profile_pic', 'organization', 'fcm_token', 'slug')}),
        (('Permissions'), {
        'fields': ('groups', 'user_permissions'),
    }),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'name', 'mobile', 'gender', 'role','is_active', 'is_staff', 'is_superuser', 'password1', 'password2')}
        ),
    )

    search_fields = ('email','name')
    ordering = ('email',)
    filter_horizontal = ()


class OTPAdmin(admin.ModelAdmin):
   list_display = ('otp', 'session_id', 'expires_at', 'identifier')

class CustomGroupAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', )

# Now register the new CustomUserAdmin
admin.site.register(Users, CustomUserAdmin)
admin.site.unregister(Group)
admin.site.register(Group, CustomGroupAdmin)
admin.site.register(OTPSession,OTPAdmin)

