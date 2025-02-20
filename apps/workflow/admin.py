from django.contrib import admin
from .models import (
    # WorkflowDefinition,
    StageDefinition,
    TaskDefinition,
    # Workflow,
    Stage,
    Task,
    # Documents,
    Notifications,
    NotificationMeta,
    NotificationMetaDefinition
)

# class WorkflowDefinitionAdmin(admin.ModelAdmin):
#     list_display = ['name','workflow_type','creator','organization']

class StageDefinitionAdmin(admin.ModelAdmin):
    list_display = ['id', 'name','order','workflow']

class TaskDefinitionAdmin(admin.ModelAdmin):
    list_display = ['id', 'name','order','task_type','stage', 'workflow', 'minimum_approvals_required']

# class WorkflowAdmin(admin.ModelAdmin):
#     list_display = ['name','workflow_type','lead','assigned_to']

class StageAdmin(admin.ModelAdmin):
    list_display = ['id', 'name','order','current_task', 'workflow', 'definition','started','completed']
    search_fields = ['workflow__id']

class TaskAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'status','order', 'task_type','stage','workflow', 'minimum_approvals_required', 'completed']
    list_filter = ['task_type']
    search_fields = ['workflow__id']

# class DocumentsAdmin(admin.ModelAdmin):
#     list_display = ['brik','document_name','doc_type','document']

class NotificationsAdmin(admin.ModelAdmin):
    list_display = ['id','notification_id','notification_type','read','email','created']

class NotificationMetaAdmin(admin.ModelAdmin):
    list_display = ['name','time_interval']

class NotificationMetaDefinitionAdmin(admin.ModelAdmin):
    list_display = ['name','time_interval']

# Register your models here.
# admin.site.register(WorkflowDefinition, WorkflowDefinitionAdmin)
admin.site.register(StageDefinition, StageDefinitionAdmin)
admin.site.register(TaskDefinition, TaskDefinitionAdmin)
# admin.site.register(Workflow,WorkflowAdmin)
admin.site.register(Stage, StageAdmin)
admin.site.register(Task, TaskAdmin)
# admin.site.register(Documents, DocumentsAdmin)
admin.site.register(Notifications, NotificationsAdmin)
admin.site.register(NotificationMeta, NotificationMetaAdmin)
admin.site.register(NotificationMetaDefinition, NotificationMetaDefinitionAdmin)