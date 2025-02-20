from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from lead.models import Lead, LeadRequirements, ChannelPartner
from emails.models import Email,EmailTemplate
from activity.models import Notes,SiteVisit
from auth.models import Users
from core.models import Organization,Category
from workflow.models import Workflow,WorkflowDefinition,Stage,StageDefinition,Task,Notifications,TaskDefinition

class Command(BaseCommand):
    help = 'Create groups and permissions for your application'

    model_permissions = [
        {
            'model': Lead,
            'groups': {
                'ADMIN': ['view_lead', 'change_lead', 'add_lead', 'delete_lead'],
                'CALL_CENTER_EXECUTIVE': ['view_lead', 'add_lead', 'change_lead'],
                'RECEPTIONIST': ['view_lead', 'add_lead', 'change_lead'],
                'SITE_HEAD': ['view_lead', 'add_lead', 'change_lead'],
                'CLOSING_MANAGER': ['view_lead', 'add_lead', 'change_lead'],
                'CRM_EXECUTIVE': ['view_lead', 'add_lead', 'change_lead'],
                'CRM_HEAD': ['view_lead', 'add_lead', 'change_lead'],        
                'VICE_PRESIDENT': ['view_lead', 'add_lead', 'change_lead'],          

            }
        },
        {
            'model': LeadRequirements,
            'groups': {
                'ADMIN': ['view_leadrequirements', 'change_leadrequirements', 'add_leadrequirements', 'delete_leadrequirements'],
                'CALL_CENTER_EXECUTIVE': ['view_leadrequirements', 'add_leadrequirements', 'change_leadrequirements'],
                'RECEPTIONIST': ['view_leadrequirements', 'add_leadrequirements', 'change_leadrequirements'],
                'SITE_HEAD': ['view_leadrequirements', 'add_leadrequirements', 'change_leadrequirements'],
                'CLOSING_MANAGER': ['view_leadrequirements', 'add_leadrequirements', 'change_leadrequirements'],
                'CRM_EXECUTIVE': ['view_leadrequirements', 'add_leadrequirements', 'change_leadrequirements'],
                'CRM_HEAD': ['view_leadrequirements', 'add_leadrequirements', 'change_leadrequirements'],
                'VICE_PRESIDENT': ['view_leadrequirements', 'add_leadrequirements', 'change_leadrequirements'],    

            }
        },
        {
            'model': ChannelPartner,
            'groups': {
                'ADMIN': ['view_channelpartner', 'change_channelpartner', 'add_channelpartner', 'delete_channelpartner'],
                'CALL_CENTER_EXECUTIVE': ['view_channelpartner', 'add_channelpartner', 'change_channelpartner'],
                'RECEPTIONIST': ['view_channelpartner', 'add_channelpartner', 'change_channelpartner'],
                'SITE_HEAD': ['view_channelpartner', 'add_channelpartner', 'change_channelpartner'],
                'CLOSING_MANAGER': ['view_channelpartner', 'add_channelpartner', 'change_channelpartner'],
                'CRM_EXECUTIVE': ['view_channelpartner', 'add_channelpartner', 'change_channelpartner'],
                'CRM_HEAD': ['view_channelpartner', 'add_channelpartner', 'change_channelpartner'],   
                'VICE_PRESIDENT': ['view_channelpartner', 'add_channelpartner', 'change_channelpartner'],
            }
        },
        {
            'model': SiteVisit,
            'groups': {
                'ADMIN': ['view_sitevisit', 'change_sitevisit', 'add_sitevisit', 'delete_sitevisit'],
                'CALL_CENTER_EXECUTIVE': ['view_sitevisit', 'change_sitevisit', 'add_sitevisit'],
                'RECEPTIONIST': ['view_sitevisit', 'change_sitevisit', 'add_sitevisit'],
                'SITE_HEAD': ['view_sitevisit', 'change_sitevisit', 'add_sitevisit'],
                'CLOSING_MANAGER': ['view_sitevisit', 'change_sitevisit', 'add_sitevisit'],
                'CRM_EXECUTIVE': ['view_sitevisit', 'change_sitevisit', 'add_sitevisit'],
                'CRM_HEAD': ['view_sitevisit', 'change_sitevisit', 'add_sitevisit'],
                'VICE_PRESIDENT': ['view_sitevisit', 'change_sitevisit', 'add_sitevisit'],

            }
        },
        {
            'model': Notes,
            'groups': {
                'ADMIN': ['view_notes', 'change_notes', 'add_notes', 'delete_notes'],
                'CALL_CENTER_EXECUTIVE': ['view_notes', 'change_notes', 'add_notes'],
                'RECEPTIONIST': ['view_notes', 'change_notes', 'add_notes'],
                'SITE_HEAD': ['view_notes', 'change_notes', 'add_notes'],
                'CLOSING_MANAGER': ['view_notes', 'change_notes', 'add_notes'], 
                'CRM_EXECUTIVE': ['view_notes', 'change_notes', 'add_notes'], 
                'CRM_HEAD': ['view_notes', 'change_notes', 'add_notes'], 
                'VICE_PRESIDENT': ['view_notes', 'change_notes', 'add_notes'],

            }
        },
        {
            'model': EmailTemplate,
            'groups': {
                'ADMIN': ['view_emailtemplate', 'change_emailtemplate', 'add_emailtemplate', 'delete_emailtemplate'],
                'CALL_CENTER_EXECUTIVE': ['view_emailtemplate', 'change_emailtemplate', 'add_emailtemplate'],
                'RECEPTIONIST': ['view_emailtemplate', 'change_emailtemplate', 'add_emailtemplate'],
                'SITE_HEAD': ['view_emailtemplate', 'change_emailtemplate', 'add_emailtemplate'],
                'VICE_PRESIDENT': ['view_emailtemplate', 'change_emailtemplate', 'add_emailtemplate'],
                'CLOSING_MANAGER': ['view_emailtemplate', 'change_emailtemplate', 'add_emailtemplate'],  
                'CRM_EXECUTIVE': ['view_emailtemplate', 'change_emailtemplate', 'add_emailtemplate'],  
                'CRM_HEAD': ['view_emailtemplate', 'change_emailtemplate', 'add_emailtemplate'],  
            }
        }

    ]


    def handle(self, *args, **options):
        for model_permissions_config in self.model_permissions:

            model = model_permissions_config['model']

            for group_name, permissions in model_permissions_config['groups'].items():

                group, created = Group.objects.get_or_create(name=group_name)
                content_type = ContentType.objects.get_for_model(model)

                model_permissions = Permission.objects.filter(content_type=content_type, codename__in=permissions)

                for permission in model_permissions:
                    group.permissions.add(permission)

