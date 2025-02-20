from django.contrib import admin
from river.models.transitionapproval import TransitionApproval
from django import forms

class TransitionApprovalForm(forms.ModelForm):
    class Meta:
        model = TransitionApproval
        fields = ('workflow', 'status', 'transition', 'permissions', 'groups', 'users', 'priority')


class TransitionApprovalAdmin(admin.ModelAdmin):
    form = TransitionApprovalForm
    list_display = ('workflow', 'transition', 'priority')


admin.site.register(TransitionApproval, TransitionApprovalAdmin)


