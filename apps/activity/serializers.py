from rest_framework import serializers
from .models import CancelBookingReason, Notes,SiteVisit
from auth.serializers import UserDataSerializer
from django.utils import timezone
from datetime import datetime, timedelta
from simple_history.models import HistoricalRecords
from auth.models import Users
from lead.models import *

class NotesSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()
    created = serializers.SerializerMethodField()

    class Meta:
        model = Notes
        fields = '__all__'

    def get_created_by_name(self, obj):
       return obj.created_by.name if obj.created_by else None
        
    def get_created(self, obj):
        now = timezone.now()
        created_on = obj.created_on.astimezone(timezone.pytz.timezone('Asia/Kolkata'))

        if now.date() == created_on.date():
            return created_on.strftime("Today %I:%M %p")
        elif now.date() - created_on.date() == timezone.timedelta(days=1):
            return created_on.strftime("Yesterday %I:%M %p")
        else:
            return created_on.strftime("%B %d, %Y")


class HistorySerializer(serializers.ModelSerializer):
    #history_id = serializers.IntegerField(source='id')
    history_date = serializers.DateTimeField()
    history_type = serializers.CharField()
    history_user_id = serializers.IntegerField()
    history_user = serializers.SerializerMethodField()
    message = serializers.SerializerMethodField()
    activity_type = serializers.SerializerMethodField()

    class Meta:
        model = None  # Placeholder, to be set dynamically in the view
        fields = [ 'history_date', 'history_type', 'history_user', 'message','activity_type']

    def get_history_user(self, obj):
        user_id = obj.history_user_id
        user = Users.objects.get(id=user_id) if Users.objects.filter(id=user_id).exists() else None
        return user.name if user else None

    def get_message(self, obj):
        history_type = obj.history_type
        model_name = self.Meta.model.__name__ if self.Meta.model else "Model"
        
        if history_type == "+":
            return f"{model_name} Created"
        elif history_type == "~":
            return f"{model_name} Updated"
        elif history_type == "-":
            return f"{model_name} Deleted"
        return None
    
    def get_activity_type(self,obj):
        model_name = self.Meta.model.__name__ if self.Meta.model else None
        return model_name


class SiteVisitHistorySerializer(HistorySerializer):
    site_visit_status = serializers.CharField(source='instance.site_visit_status') 
    class Meta(HistorySerializer.Meta):
        model = SiteVisit
        fields = HistorySerializer.Meta.fields + ['site_visit_status', 'site_visit_type','snagging_status','visit_date', 'timeslot']
# class SiteVisitHistorySerializer(serializers.ModelSerializer):
#     history_date = serializers.DateTimeField()
#     history_type = serializers.CharField()
#     history_user_id = serializers.IntegerField()
#     history_user = serializers.SerializerMethodField()
#     message = serializers.SerializerMethodField()
#     activity_type = serializers.SerializerMethodField()

#     class Meta:
#         model = None 
#         fields = [ 'history_date', 'history_type', 'history_user', 'message','activity_type']

#     def get_history_user(self, obj):
#         user_id = obj.history_user_id
#         user = Users.objects.get(id=user_id) if Users.objects.filter(id=user_id).exists() else None
#         return user.name if user else None

#     def get_message(self, obj):
#         history_type = obj.history_type
#         model_name = self.Meta.model.__name__ if self.Meta.model else "Model"
        
#         if history_type == "+":
#             return f"{model_name} Created"
#         elif history_type == "~":
#             return f"{model_name} Updated"
#         elif history_type == "-":
#             return f"{model_name} Deleted"
#         return None
    
#     def get_activity_type(self,obj):
#         model_name = self.Meta.model.__name__ if self.Meta.model else None
#         return model_name
#     class Meta:
#         model = SiteVisit
#         fields = '__all__'

class SiteVisitSerializer(serializers.ModelSerializer):
    sv_status_list = serializers.SerializerMethodField() 
    closing_manager_data = serializers.SerializerMethodField()
    sourcing_manager_data = serializers.SerializerMethodField()
    message = serializers.SerializerMethodField()
    document = serializers.SerializerMethodField()
    history = serializers.SerializerMethodField()
    class Meta:
        model = SiteVisit
        fields = ['id', 'sv_status_list', 'closing_manager', 'sourcing_manager', 'visit_date', 'property', 'closing_manager_data', 'sourcing_manager_data', 'timeslot', 'site_visit_status', 'lead','site_visit_type', 'constructor','snagging_status','snagging_issues','document','history','message']
        extra_kwargs = {
            'visit_date': {'required': True},
            'lead': {'required': True},
            'timeslot': {'required': True},
        }

    def get_sv_status_list(self, obj):
        SITEVISIT_CHOICES = [
            ("Site Visit Done", "Site Visit Done"), 
            ("Missed", "Missed"),
            ("Scheduled", "Scheduled"),
        ]

        SiteVisit_choices = dict(SITEVISIT_CHOICES)
        sitevisit_picked = obj.site_visit_status 
        sv_status_list = [
            {"status": status, "selected": status == sitevisit_picked}
            for status in SiteVisit_choices.keys()
        ]
        return sv_status_list 
    
    def get_closing_manager_data(self, obj):
        closing_manager_instance = obj.closing_manager
        serializer = UserDataSerializer(instance=closing_manager_instance, many=False, read_only=True)
        serialized_data = serializer.data
        return serialized_data if obj.closing_manager else None

    def get_sourcing_manager_data(self, obj):
        sourcing_manager_instance = obj.sourcing_manager
        serializer = UserDataSerializer(instance=sourcing_manager_instance, many=False, read_only=True)
        serialized_data = serializer.data
        return serialized_data if obj.sourcing_manager else None
     
    def get_history(self, obj):
        history_queryset = obj.history.all()
        history_data = SiteVisitHistorySerializer(history_queryset, many=True).data
        return history_data if history_data else None
    
    def get_message(self, obj):
        if obj.site_visit_status == 'Missed':
            return 'Site Visit Scheduled and Missed'
        elif obj.site_visit_status == 'Scheduled':
            return 'Site Visit Scheduled'
        elif obj.site_visit_status == 'Site Visit Done':
            return 'Site Visit Done'
        else:
            return ''

    def get_document(self,obj):
        from lead.serializers import DocumentSectionSerializer
        if obj.site_visit_type == "Snagging" and obj.snagging_status =="Defects Spotted":
            lead_obj = obj.lead
            tag = "snagging_" + str(obj.id)
            if lead_obj and tag:
                queryset = DocumentSection.objects.filter(lead__id=lead_obj.id, doc_tag=tag)
                return DocumentSectionSerializer(queryset,many=True).data if queryset.exists() else []
        else:
            return []

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['message'] = self.get_message(instance)
        #representation['history'] = self.get_history(instance)
        return representation




class CalendarViewSerializer(serializers.ModelSerializer):
    lead_id = serializers.CharField(source = 'lead.id')
    first_name = serializers.CharField(source='lead.first_name')
    last_name = serializers.CharField(source='lead.last_name')
    primary_phone_no = serializers.CharField(source='lead.primary_phone_no')
    lead_status = serializers.CharField(source='lead.lead_status')
    lead_status_list = serializers.SerializerMethodField()
    closing_manager_data= serializers.SerializerMethodField()  
    #site_visit_count = serializers.SerializerMethodField() 
    #closing_manager = serializers.CharField()
    #status = serializers.CharField(source='get_status')
    print(SiteVisit.visit_date) 
    class Meta:
        model = SiteVisit
        fields = ['lead_id','first_name', 'last_name', 'primary_phone_no', 'lead_status', 'lead_status_list', 'site_visit_status','visit_date','timeslot','closing_manager', 'closing_manager_data']

    def get_lead_status_list(self, obj):
        LEAD_STATUS_CHOICES = [
                ('New', 'New'),
                ('Hot', 'Hot'),
                ('Warm', 'Warm'),
                ('Cold', 'Cold'),
                ('Lost', 'Lost'),
            ]
            
        lead_status_choices = dict(LEAD_STATUS_CHOICES)
        lead_status_picked = obj.lead.lead_status
        #print(obj.lead_status)
        lead_status_list = [
        {"status": status, "selected": status == lead_status_picked}
        for status in lead_status_choices.keys()
    ]
        return lead_status_list  

    def get_closing_manager_data(self, obj):
        closing_manager_instance = obj.closing_manager
        serializer = UserDataSerializer(instance=closing_manager_instance, many=False, read_only=True)
        serialized_data = serializer.data
        return serialized_data 
       

class AvailableTimeslotsSerializer(serializers.Serializer):
    error = serializers.BooleanField()
    message = serializers.CharField(required=False)
    available_timeslots = serializers.ListField(child=serializers.CharField(), required=False)



class CancelReasonSerializer(serializers.ModelSerializer):
    class Meta:
        model = CancelBookingReason
        fields = ['lead', 'reason', 'create_date']
        read_only_fields = ['create_date']

