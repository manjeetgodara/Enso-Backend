from rest_framework import serializers

from auth.serializers import UserSerializer
from .models import LeadCallsMcube
from auth.models import Users  # Assuming Users is your executive model
from auth.serializers import *

class ExecutiveSerializer(serializers.ModelSerializer):
    class Meta:
        model = Users
        fields = '__all__'


class McubeSerializer(serializers.ModelSerializer):
    executive = UserSerializer() 
    class Meta:
        model = LeadCallsMcube
        fields = '__all__'

class LeadCallsMcubeSerializer(serializers.ModelSerializer):
    message = serializers.SerializerMethodField()
    history_user = serializers.SerializerMethodField()
    history_date = serializers.DateTimeField(source='created_at')
    activity_type = serializers.CharField(default='LeadCallsMcube')
    history_type = serializers.CharField(default='+')
    class Meta:
        model = LeadCallsMcube
        fields = '__all__'

    def get_message(self, obj):
        if obj.call_type == 'INCOMING':
           # return f"Incoming Call Received on {obj.created_at.date()}"
            return f"Incoming Call"
        elif obj.call_type == 'OUTGOING':
           # return f"Outgoing Call Made on {obj.created_at.date()}"
            return f"Outgoing Call"
        else:
            return ""
    
    def get_history_user(self, obj):
        return obj.executive.name if obj.executive else None 
    
class LeadCallsMcubeActivitySerializer(serializers.ModelSerializer):
    message = serializers.SerializerMethodField()
    history_user = serializers.SerializerMethodField()
    history_date = serializers.DateTimeField(source='created_at')
    activity_type = serializers.CharField(default='LeadCallsMcube')
    history_type = serializers.CharField(default='+')
    class Meta:
        model = LeadCallsMcube
        fields = '__all__'

    def get_message(self, obj):
        if obj.call_type == 'INCOMING':
            return f"Incoming Call Received"
        elif obj.call_type == 'OUTGOING':
            return f"Outgoing Call Made"
        else:
            return ""
    
    def get_history_user(self, obj):
        return obj.executive.name if obj.executive else None 