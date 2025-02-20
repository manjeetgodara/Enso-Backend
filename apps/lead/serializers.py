from rest_framework import serializers
from accounts.models import CustomerPayment, Payment
from .models import *
from auth.models import Users
from core.models import Organization
from auth.serializers import UserSerializer
from activity.serializers import NotesSerializer
from activity.models import CancelBookingReason, Notes, SiteVisit
from river.models import Workflow
from workflow.serializers import TaskSerializer
from django.utils import timezone
import json
from .models import DocumentSection
from django.db.models import OuterRef, Subquery, Q, Count
from auth.serializers import UserDataSerializer
from inventory.models import ProjectInventory, PropertyOwner, BookingForm, InventoryCostSheet
from datetime import datetime, timedelta

class LeadRequirementSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeadRequirements
        fields = '__all__'
        extra_kwargs = {
        'configuration': {'required': True},
        'area': {'required': True},
        'budget_min': {'required': True},
        'budget_max': {'required': True}, 
    }

class SourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Source
        fields = '__all__'

class ChannelPartnerId(serializers.ModelSerializer):
    class Meta:
        model = ChannelPartner
        fields = ['id','full_name', 'firm', 'primary_phone_no']

class CorporateLeadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lead
        fields = '__all__'
        extra_kwargs = {
        'first_name': {'required': True},
        'last_name': {'required': True},
        'primary_phone_no': {'required': True}, 
    }
    def __init__(self, *args, **kwargs):

        self.request = kwargs.pop('context', {}).get('request', None)
        self.assigned_to = kwargs.pop('assigned_to',{}).get('assigned_to', None)

        super().__init__(*args, **kwargs)

    def create(self, validated_data):

        lead = Lead.objects.create(followers=[self.assigned_to.id],**validated_data)

        return lead
    def update(self, instance, validated_data):
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance 
    
class LeadInquiryFormSerializer(serializers.ModelSerializer):
    lead_requirement = LeadRequirementSerializer()
    class Meta:
        model = Lead
        fields = '__all__'
        extra_kwargs = {
        'first_name': {'required': True},
        'last_name': {'required': True},
        'primary_phone_no': {'required': True},
        # 'primary_email': {'required': True},
        'gender': {'required': True},
        'age': {'required': True},
        'address': {'required': True},      
        'source': {'required': True},   
    }
    def __init__(self, *args, **kwargs):
        # Get the request object from the context
        self.request = kwargs.pop('context', {}).get('request', None)
        self.assigned_to = kwargs.pop('assigned_to',{}).get('assigned_to', None)
        #print("TESTING INSIDE INIT: ", self.assigned_to)
        super().__init__(*args, **kwargs)

    def create(self, validated_data):
        requirement_data = validated_data.pop('lead_requirement')

        lead_requirement=LeadRequirements.objects.create( **requirement_data)

        lead = Lead.objects.create(lead_requirement=lead_requirement,followers=[self.assigned_to.id],**validated_data)

        return lead
    def update(self, instance, validated_data):
        requirement_data = validated_data.pop('lead_requirement', {})
        
        # Update the fields of the main model instance
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Update or create the related LeadRequirements object
        requirement, created = LeadRequirements.objects.update_or_create(
            lead=instance,
            defaults=requirement_data
        )

        return instance  
    
class LeadSerializer(serializers.ModelSerializer):
    lead_requirement = LeadRequirementSerializer()
    note_response = serializers.SerializerMethodField()
    lead_name = serializers.SerializerMethodField()
    sv_id = serializers.SerializerMethodField()
    sv_status = serializers.SerializerMethodField()   
    created_on_date = serializers.SerializerMethodField()   
    current_stage = serializers.SerializerMethodField()   
    current_task = serializers.SerializerMethodField()
    current_task_details = serializers.SerializerMethodField()
    lead_status_list = serializers.SerializerMethodField()
    assigned_to = serializers.SerializerMethodField()
    closing_manager = serializers.SerializerMethodField()
    sourcing_manager = serializers.SerializerMethodField()
    channel_partner_data = serializers.SerializerMethodField()
    key_transfer = serializers.SerializerMethodField()
    property_name = serializers.SerializerMethodField()
    apartment_no = serializers.SerializerMethodField()  
    no_dues_certificate = serializers.SerializerMethodField()  
    source_id = serializers.SerializerMethodField()
    inventory_booking_status = serializers.SerializerMethodField()
    # booking_form = serializers.SerializerMethodField()
    # cost_sheet = serializers.SerializerMethodField()
    # pan_card  = serializers.SerializerMethodField()
    # aadhar_url = serializers.SerializerMethodField()
    class Meta:
        model = Lead
        fields = '__all__'
        extra_kwargs = {
        'first_name': {'required': True},
        'last_name': {'required': True},
        'primary_phone_no': {'required': True},
        'gender': {'required': True},
        'occupation': {'required': True},    
        'source': {'required': True},  
        'city': {'required': True},  
    }
    def get_lead_name(self, obj):
        # Concatenate the first_name and last_name fields from the Lead model
        return f"{obj.first_name} {obj.last_name}" 

    def get_created_on_date(self, obj):
        return f"{obj.created_on.date()}"
    
    def get_current_task_details(self, obj):
        lead_workflow =  Workflow.objects.filter(lead=obj).first()
        followup_tasks = lead_workflow.tasks.filter(name='Follow Up', completed=False).order_by('-time').last()
        if followup_tasks:
            data = TaskSerializer(followup_tasks).data
            data['date'] = followup_tasks.time.date()
            data['follow_up_pending'] = True if followup_tasks.time <= timezone.now() else False
            data['workflow_id'] = followup_tasks.workflow_id
            return data
        return None
    
    def get_current_task(self, obj):
        lead_workflow =  Workflow.objects.filter(lead=obj).first()
        current_stage = lead_workflow.stages.get(order=lead_workflow.current_stage)
        print('current_stage:', current_stage, current_stage.tasks.all())
        if current_stage.tasks.all():
            current_task = current_stage.tasks.filter(order=lead_workflow.current_task).first()
            print('current_task:', current_task)
            return current_task.id if current_task else None
        return None
 
    def get_latest_site_visit(self, lead):
        latest_site_visit = SiteVisit.objects.filter(
            lead=lead
        ).order_by('-visit_date', '-timeslot').first()

        return latest_site_visit
    
    # def get_booking_form(self,obj):
    #     project_owner = PropertyOwner.objects.get(lead=obj)
    #     print("project_owner: ", project_owner)
    #     if project_owner :
    #       booking_form_pdf_url = project_owner.booking_form_pdf.url if project_owner.booking_form_pdf else None
    #       return booking_form_pdf_url
    #     else:
    #         return None
        
    # def get_cost_sheet(self,obj): 
    #     project_owner = PropertyOwner.objects.get(lead=obj)
    #     print("project_owner: ", project_owner)
    #     if project_owner :
    #       cost_sheet_pdf_url = project_owner.cost_sheet_pdf.url if project_owner.cost_sheet_pdf else None
    #       return cost_sheet_pdf_url
    #     else:
    #         return None  

    # def get_pan_card(self,obj):
    #     pan_card = DocumentSection.objects.filter(lead=obj, slug='pan_card').first()    
    #     if pan_card and pan_card.upload_docs:
    #         return pan_card.upload_docs.url 
    #     else:
    #         return None 

    # def get_aadhar_url(self,obj):
    #     documents = DocumentSection.objects.filter(lead=obj)

    #     aadhar_card_url = None

    #     # Iterate through the documents to find the one with the slug 'pan_card'
    #     for doc in documents:
    #         if doc.slug == 'id_proof_front':
    #             aadhar_card_url = doc.upload_docs.url if doc.upload_docs else None
    #             break  

    #     # Return the URL if found, otherwise return None
    #     return aadhar_card_url       

    def get_sv_id(self, obj):
        latest_site_visit = self.get_latest_site_visit(obj)
        return latest_site_visit.id if latest_site_visit else None
    
    def get_inventory_booking_status(self, obj):
        owner = PropertyOwner.objects.filter(lead=obj).first()
        if owner:
            return owner.booking_status if owner.booking_status else None
        else:
            return None

    def get_sv_status(self, obj):
        latest_site_visit = self.get_latest_site_visit(obj)
        return latest_site_visit.site_visit_status if latest_site_visit else None

    def get_closing_manager(self, obj):
        latest_site_visit = self.get_latest_site_visit(obj)
        return UserDataSerializer(latest_site_visit.closing_manager).data if latest_site_visit and latest_site_visit.closing_manager else None
    
    def get_sourcing_manager(self, obj):
        latest_site_visit = self.get_latest_site_visit(obj)
        return UserDataSerializer(latest_site_visit.sourcing_manager).data if latest_site_visit and latest_site_visit.sourcing_manager else None

    def get_source_id(self, obj):
        if obj.source:
            return SourceSerializer(obj.source).data
        else:
            return None 

    def get_channel_partner_data(self, obj):
        return ChannelPartnerId(obj.channel_partner).data if obj.channel_partner  else None
        
    def get_key_transfer(self, obj):
        try:
            workflow = obj.workflow.get()
            key_transfer_task = workflow.tasks.filter(name='Key Transfer').first()
            if key_transfer_task:
                return key_transfer_task.completed if key_transfer_task.completed == True  else False
        except Workflow.DoesNotExist:
            return None

    def get_assigned_to(self, obj):
        try:
            workflow = obj.workflow.get()
            assigned_to = workflow.assigned_to
            first_stage = workflow.stages.all().order_by('order').first()
            if first_stage and first_stage.assigned_to:
                user = first_stage.assigned_to
                if user.groups.filter(name="CALL_CENTER_EXECUTIVE").exists():
                    return UserDataSerializer(first_stage.assigned_to).data  
                else:
                    return None
            else:
                return None 
        except Workflow.DoesNotExist:
            return None   

    def get_lead_status_list(self, obj):
        LEAD_STATUS_CHOICES = [
                ('New', 'New'),
                ('Hot', 'Hot'),
                ('Warm', 'Warm'),
                ('Cold', 'Cold'),
                ('Lost', 'Lost'),
            ]
            
        lead_status_choices = dict(LEAD_STATUS_CHOICES)
        lead_status_picked = obj.lead_status
        print(obj.lead_status)
        lead_status_list = [
        {"status": status, "selected": status == lead_status_picked}
        for status in lead_status_choices.keys()
    ]
        return lead_status_list
    
    def get_current_stage(self, obj):
        # lead_workflow =  Workflow.objects.filter(lead=obj).first()
        # current_stage = lead_workflow.stages.get(order=lead_workflow.current_stage)
        # return current_stage.id
        return obj.current_stage()
    
    def get_property_name(self, obj):
        try:
            projectinventory = obj.projectinventory_set.first()
            project_name = projectinventory.tower.project.name if projectinventory and projectinventory.tower and projectinventory.tower.project else None
            return project_name
        except ProjectInventory.DoesNotExist:
            return None

    def get_apartment_no(self, obj):
        #return None
        try:
            inventory = obj.projectinventory_set.first()
            if inventory:
                return inventory.apartment_no
        except ProjectInventory.DoesNotExist:
            return None
        
    def get_no_dues_certificate(self, obj):
        # try:
        #     inventory = obj.projectinventory_set.all()
        #     if inventory and all(event.event_status=="Done" for event in inventory):
        #         return True
        #     else:
        #         return False
        # except ProjectInventory.DoesNotExist:
        #     return False
        from inventory.models import ProjectCostSheet
        try:
            inventory = obj.projectinventory_set.first()
            if inventory:
                project_slabs = ProjectCostSheet.objects.filter(project=inventory.tower.project,event_status="Pending")
                return False if project_slabs.exists() else True
        except ProjectInventory.DoesNotExist:
            return False
    
    def __init__(self, *args, **kwargs):
        # Get the request object from the context
        self.request = kwargs.pop('context', {}).get('request', None)
        self.assigned_to = kwargs.pop('assigned_to',{}).get('assigned_to', None)
        #print("TESTING INSIDE INIT: ", self.assigned_to)
        super().__init__(*args, **kwargs)

    def create(self, validated_data):
        requirement_data = validated_data.pop('lead_requirement')

        lead_requirement=LeadRequirements.objects.create( **requirement_data)

        lead = Lead.objects.create(lead_requirement=lead_requirement,followers=[self.assigned_to.id],created_by= self.request.user.name,creator=self.request.user,**validated_data)

        return lead
    
  

    def update(self, instance, validated_data):
        requirement_data = validated_data.pop('lead_requirement', {})
        
        # Update the fields of the main model instance
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Update or create the related LeadRequirements object
        requirement, created = LeadRequirements.objects.update_or_create(
            lead=instance,
            defaults=requirement_data
        )
          # Check if lead_status is being updated to "lost" and reason is provided
        if 'lead_status' in validated_data and validated_data['lead_status'] == 'Lost':
            lost_reason = validated_data.get('lost_reason')
            if not lost_reason:
                raise serializers.ValidationError("Lost reason is not Provided")

        return instance

    def get_note_response(self, obj):
        # Retrieve the latest 2 notes associated with the lead
        latest_notes = Notes.objects.filter(lead=obj).order_by('-created_on')[:2]
        return NotesSerializer(latest_notes, many=True).data    

class LeadPostSaleReterieveSerializer(serializers.ModelSerializer):
    lead_requirement = LeadRequirementSerializer()
    note_response = serializers.SerializerMethodField()
    lead_name = serializers.SerializerMethodField()
    sv_id = serializers.SerializerMethodField()
    sv_status = serializers.SerializerMethodField()  
    crm_executive = serializers.SerializerMethodField() 
    created_on_date = serializers.SerializerMethodField()   
    current_stage = serializers.SerializerMethodField()   
    current_task = serializers.SerializerMethodField()
    current_task_details = serializers.SerializerMethodField()
    lead_status_list = serializers.SerializerMethodField()
    assigned_to = serializers.SerializerMethodField()
    closing_manager = serializers.SerializerMethodField()
    sourcing_manager = serializers.SerializerMethodField()
    channel_partner_data = serializers.SerializerMethodField()
    key_transfer = serializers.SerializerMethodField()
    property_name = serializers.SerializerMethodField()
    apartment_no = serializers.SerializerMethodField()  
    no_dues_certificate = serializers.SerializerMethodField()  
    source_id = serializers.SerializerMethodField()
    inventory_booking_status = serializers.SerializerMethodField()
    booking_form = serializers.SerializerMethodField()
    cost_sheet = serializers.SerializerMethodField()
    pan_card  = serializers.SerializerMethodField()
    aadhar_url = serializers.SerializerMethodField()
    payment_proof = serializers.SerializerMethodField()
    aadhar_back_url = serializers.SerializerMethodField()
    passport_url = serializers.SerializerMethodField()
    inventory_unit = serializers.SerializerMethodField()
    refund_amount = serializers.SerializerMethodField()
    refund_status = serializers.SerializerMethodField()
    cancel_booking_reason = serializers.SerializerMethodField()
    payment_id = serializers.SerializerMethodField()
    refund_task_id = serializers.SerializerMethodField()
    refund_invoice_overview = serializers.SerializerMethodField()
    nationality = serializers.SerializerMethodField()

    class Meta:
        model = Lead
        fields = '__all__'
        extra_kwargs = {
        'first_name': {'required': True},
        'last_name': {'required': True},
        'primary_phone_no': {'required': True},
        'gender': {'required': True},
        'occupation': {'required': True},    
        'source': {'required': True},  
        'city': {'required': True},  
    }
    def get_lead_name(self, obj):
        # Concatenate the first_name and last_name fields from the Lead model
        return f"{obj.first_name} {obj.last_name}" 

    def get_created_on_date(self, obj):
        return f"{obj.created_on.date()}"
    
    def get_current_task_details(self, obj):
        lead_workflow =  Workflow.objects.filter(lead=obj).first()
        followup_tasks = lead_workflow.tasks.filter(name='Follow Up', completed=False).order_by('-time').last()
        if followup_tasks:
            data = TaskSerializer(followup_tasks).data
            data['date'] = followup_tasks.time.date()
            data['follow_up_pending'] = True if followup_tasks.time <= timezone.now() else False
            data['workflow_id'] = followup_tasks.workflow_id
            return data
        return None
    
    def get_current_task(self, obj):
        try:
            lead_workflow =  Workflow.objects.filter(lead=obj).first()
            current_stage = lead_workflow.stages.get(order=lead_workflow.current_stage)
            print('current_stage:', current_stage, current_stage.tasks.all())
            if current_stage.tasks.all():
                current_task = current_stage.tasks.filter(order=lead_workflow.current_task).first()
                print('current_task:', current_task)
                return current_task.id if current_task else None
            return None
        except Exception as e:
            return None
 
    def get_latest_site_visit(self, lead):
        latest_site_visit = SiteVisit.objects.filter(
            lead=lead
        ).order_by('-visit_date', '-timeslot').first()

        return latest_site_visit
    
    def get_crm_executive(self, obj):
        user_ids = obj.followers 

        crm_executive = Users.objects.filter(id__in=user_ids, groups__name="CRM_EXECUTIVE").first()

        return UserDataSerializer(crm_executive).data if crm_executive else None
    
    def get_booking_form(self,obj):
            project_owner = PropertyOwner.objects.filter(lead=obj).first()
            print("project_owner: ", project_owner)
            if project_owner :
                booking_form_pdf_url = project_owner.booking_form_pdf.url if project_owner.booking_form_pdf else None
                return booking_form_pdf_url
            else:
                return None  
         
        
    def get_cost_sheet(self,obj):
            project_owner = PropertyOwner.objects.filter(lead=obj).first()
            print("project_owner: ", project_owner)
            if project_owner :
                cost_sheet_pdf_url = project_owner.cost_sheet_pdf.url if project_owner.cost_sheet_pdf else None
                return cost_sheet_pdf_url
            else:
                return None  
        

    def get_payment_id(self,obj):
        payment = Payment.objects.filter(lead=obj).first()
        if payment:
            return payment.id
        else:
            None

    def get_nationality(self,obj):
        booking_form = BookingForm.objects.filter(lead_id=obj).first()
        if booking_form:
            return booking_form.nationality
        else:
            return None     
        
    def get_refund_invoice_overview(self,obj):
        from accounts.models import Payment

        refund_data = Payment.objects.filter(lead=obj).first()  
        if refund_data:
            refund_invoice = refund_data.invoice_overview_list
            return refund_invoice
        else:
            return None  
        
    def get_refund_task_id(self, obj):
        payment = Payment.objects.filter(lead=obj).first()  
        if payment: 
            first_stage = payment.payment_workflow.get().stages.first()
            # first_task = first_stage.tasks.filter().order_by('order').first()
            ae_task = first_stage.tasks.filter(name='Refund Approval AE').first()
            vp_task = first_stage.tasks.filter(name='Refund Approval VP').first()
            p1_task = first_stage.tasks.filter(name='Refund Approval P1').first()
            p2_task = first_stage.tasks.filter(name='Refund Approval P2').first()
            p3_task = first_stage.tasks.filter(name='Refund Approval P3').first()
            ah_task = first_stage.tasks.filter(name='Refund Approval AH').first()
            converted_list = []

            response_data = { 
                'AE': ae_task.id if ae_task else None,
                'VP': vp_task.id if vp_task else None,
                'P1': p1_task.id if p1_task else None,
                'P2': p2_task.id if p2_task else None,
                'P3': p3_task.id if p3_task else None,
                'AH': ah_task.id if ah_task else None,
            } 
            
            for role, task_id in response_data.items():
                converted_list.append({"role": role, "task_id": task_id})                        
            return converted_list      
        else:
            return None     
                           
        
    def get_pan_card(self,obj):
        try:
            pan_card = DocumentSection.objects.filter(lead=obj, slug='pan_card').first()    
            if pan_card and pan_card.upload_docs:
                return pan_card.upload_docs.url 
            else:
                return None
        except Exception as e:
            return None     

    def get_aadhar_url(self,obj):
        try:
            documents = DocumentSection.objects.filter(lead=obj)

            aadhar_card_url = None

            # Iterate through the documents to find the one with the slug 'pan_card'
            for doc in documents:
                if doc.slug == 'id_proof_front':
                    aadhar_card_url = doc.upload_docs.url if doc.upload_docs else None
                    break  

            # Return the URL if found, otherwise return None
            return aadhar_card_url  
        except Exception as e:
            return None

    def get_aadhar_back_url(self, obj):
        try:
            # Filter documents related to the specific lead
            documents = DocumentSection.objects.filter(lead=obj)

            id_proof_back_url = None

            # Iterate through the documents to find the one with the slug 'id_proof_back'
            for doc in documents:
                if doc.slug == 'id_proof_back':
                    id_proof_back_url = doc.upload_docs.url if doc.upload_docs else None
                    break  

            # Return the URL if found, otherwise return None
            return id_proof_back_url
        except Exception as e:
            return None   

    def get_passport_url(self,obj) :
        try:
            documents = DocumentSection.objects.filter(lead=obj)
            passport_url = None
            for doc in documents:
                if doc.slug == "passport":
                    passport_url = doc.upload_docs.url if doc.upload_docs else None
                    break
            return passport_url
        except Exception as e:
            return None        

    def get_payment_proof(self, obj):
        try:
            # Filter documents related to the specific lead
            documents = DocumentSection.objects.filter(lead=obj)

            payment_proof_url = None

            # Iterate through the documents to find the one with the slug 'payment_proof'
            for doc in documents:
                if doc.slug == 'payment_proof':
                    payment_proof_url = doc.upload_docs.url if doc.upload_docs else None
                    break  

            # Return the URL if found, otherwise return None
            return payment_proof_url
        except Exception as e:
            return None  

    def get_cancel_booking_reason(self,obj):
            try:
                cancelreason = CancelBookingReason.objects.filter(lead=obj).first() 
                if cancelreason :
                    reason = cancelreason.reason
                    return reason
                else:
                    return None

            except Exception as e:
               return None     
    def get_refund_status(self,obj):
        try:
            inventory_owner = PropertyOwner.objects.filter(lead=obj).first()
            if inventory_owner :
                if inventory_owner.refund_status == True:
                    return "Refunded"
                else:
                    return "Pending" 
            else:  
                return None   
        except Exception as e:
            return None       

    def get_sv_id(self, obj):
        latest_site_visit = self.get_latest_site_visit(obj)
        return latest_site_visit.id if latest_site_visit else None
    
    def get_inventory_booking_status(self, obj):
        try :
            owner = PropertyOwner.objects.filter(lead=obj).first()
            if owner:
                return owner.booking_status if owner.booking_status else None
            else:
                return None
        except Exception as e:
            return None    

    
    def get_inventory_unit(self,obj):
        try:
            from inventory.models import ProjectInventory

            inventory = ProjectInventory.objects.filter(lead=obj).first()
            # print("inventory",inventory)

            if inventory :
                flat_number = inventory.flat_no
                tower = inventory.tower.name
                return f"{tower}-{flat_number}"
            else :
                return None   
        except Exception as e:
            return None    


    def get_refund_amount(self,obj):
        try :
            inventory_owner = PropertyOwner.objects.filter(lead=obj).first()
            if inventory_owner:
                return inventory_owner.refund_amount  
            else:
                return None  
        except Exception as e:
            return None     

    def get_sv_status(self, obj):
        latest_site_visit = self.get_latest_site_visit(obj)
        return latest_site_visit.site_visit_status if latest_site_visit else None

    def get_closing_manager(self, obj):
        latest_site_visit = self.get_latest_site_visit(obj)
        return UserDataSerializer(latest_site_visit.closing_manager).data if latest_site_visit and latest_site_visit.closing_manager else None
    
    def get_sourcing_manager(self, obj):
        latest_site_visit = self.get_latest_site_visit(obj)
        return UserDataSerializer(latest_site_visit.sourcing_manager).data if latest_site_visit and latest_site_visit.sourcing_manager else None

    def get_source_id(self, obj):
        if obj.source:
            return SourceSerializer(obj.source).data
        else:
            return None 

    def get_channel_partner_data(self, obj):
        return ChannelPartnerId(obj.channel_partner).data if obj.channel_partner  else None
        
    def get_key_transfer(self, obj):
        try:
            workflow = obj.workflow.get()
            key_transfer_task = workflow.tasks.filter(name='Key Transfer').first()
            if key_transfer_task:
                return key_transfer_task.completed if key_transfer_task.completed == True  else False
        except Workflow.DoesNotExist:
            return None

    def get_assigned_to(self, obj):
        try:
            workflow = obj.workflow.get()
            assigned_to = workflow.assigned_to
            first_stage = workflow.stages.all().order_by('order').first()
            if first_stage and first_stage.assigned_to:
                user = first_stage.assigned_to
                if user.groups.filter(name="CALL_CENTER_EXECUTIVE").exists():
                    return UserDataSerializer(first_stage.assigned_to).data  
                else:
                    return None
            else:
                return None 
        except Workflow.DoesNotExist:
            return None   

    def get_lead_status_list(self, obj):
        LEAD_STATUS_CHOICES = [
                ('New', 'New'),
                ('Hot', 'Hot'),
                ('Warm', 'Warm'),
                ('Cold', 'Cold'),
                ('Lost', 'Lost'),
            ]
            
        lead_status_choices = dict(LEAD_STATUS_CHOICES)
        lead_status_picked = obj.lead_status
        print(obj.lead_status)
        lead_status_list = [
        {"status": status, "selected": status == lead_status_picked}
        for status in lead_status_choices.keys()
    ]
        return lead_status_list
    
    def get_current_stage(self, obj):
        # lead_workflow =  Workflow.objects.filter(lead=obj).first()
        # current_stage = lead_workflow.stages.get(order=lead_workflow.current_stage)
        # return current_stage.id
        return obj.current_stage()
    
    def get_property_name(self, obj):
        try:
            projectinventory = obj.projectinventory_set.first()
            project_name = projectinventory.tower.project.name if projectinventory and projectinventory.tower and projectinventory.tower.project else None
            return project_name
        except ProjectInventory.DoesNotExist:
            return None

    def get_apartment_no(self, obj):
        #return None
        try:
            inventory = obj.projectinventory_set.first()
            if inventory:
                return inventory.apartment_no
        except ProjectInventory.DoesNotExist:
            return None
        
    def get_no_dues_certificate(self, obj):
        # try:
        #     inventory = obj.projectinventory_set.all()
        #     if inventory and all(event.event_status=="Done" for event in inventory):
        #         return True
        #     else:
        #         return False
        # except ProjectInventory.DoesNotExist:
        #     return False
        from inventory.models import ProjectCostSheet
        try:
            inventory = obj.projectinventory_set.first()
            if inventory:
                project_slabs = ProjectCostSheet.objects.filter(project=inventory.tower.project,event_status="Pending")
                return False if project_slabs.exists() else True
        except ProjectInventory.DoesNotExist:
            return False
    
    def __init__(self, *args, **kwargs):
        # Get the request object from the context
        self.request = kwargs.pop('context', {}).get('request', None)
        self.assigned_to = kwargs.pop('assigned_to',{}).get('assigned_to', None)
        #print("TESTING INSIDE INIT: ", self.assigned_to)
        super().__init__(*args, **kwargs)

    def create(self, validated_data):
        requirement_data = validated_data.pop('lead_requirement')

        lead_requirement=LeadRequirements.objects.create( **requirement_data)

        lead = Lead.objects.create(lead_requirement=lead_requirement,followers=[self.assigned_to.id],created_by= self.request.user.name,creator=self.request.user,**validated_data)

        return lead
    
  

    def update(self, instance, validated_data):
        requirement_data = validated_data.pop('lead_requirement', {})
        
        # Update the fields of the main model instance
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Update or create the related LeadRequirements object
        requirement, created = LeadRequirements.objects.update_or_create(
            lead=instance,
            defaults=requirement_data
        )
          # Check if lead_status is being updated to "lost" and reason is provided
        if 'lead_status' in validated_data and validated_data['lead_status'] == 'Lost':
            lost_reason = validated_data.get('lost_reason')
            if not lost_reason:
                raise serializers.ValidationError("Lost reason is not Provided")

        return instance

    def get_note_response(self, obj):
        # Retrieve the latest 2 notes associated with the lead
        latest_notes = Notes.objects.filter(lead=obj).order_by('-created_on')[:2]
        return NotesSerializer(latest_notes, many=True).data    



class LeadSignatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lead
        fields = ['sh_signature', 'cost_sheet_co_owner4_signature', 'cost_sheet_co_owner5_signature',
                  'co_owner1_signature', 'cost_sheet_co_owner3_signature',
                  'co_owner2_signature', 'cost_sheet_co_owner2_signature',
                  'co_owner3_signature', 'cost_sheet_co_owner_signature',
                  'co_owner4_signature' , 'vp_signature',
                  'co_owner5_signature', 'cm_signature',
                  'customer_signature', 'client_signature']


class LeadBulkuploadSerializer(serializers.ModelSerializer):
    lead_requirement = LeadRequirementSerializer()
    
    class Meta:
        model = Lead
        fields = '__all__'
        extra_kwargs = {
        'first_name': {'required': True},
        'last_name': {'required': True},
        'primary_phone_no': {'required': True},
        'gender': {'required': True},
        'occupation': {'required': True},    
        'source': {'required': True},  
        'city': {'required': True},  
    
    }
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('context', {}).get('request', None)
        self.assigned_to = kwargs.pop('assigned_to',{}).get('assigned_to', None)

        super().__init__(*args, **kwargs)

    def create(self, validated_data):

        requirement_data = validated_data.pop('lead_requirement')
        lead_requirement=LeadRequirements.objects.create( **requirement_data)
        lead = Lead.objects.create(lead_requirement=lead_requirement,**validated_data)
        return lead        



class ChannelPartnerSerializer(serializers.ModelSerializer):
    leads = serializers.SerializerMethodField()  
    status = serializers.SerializerMethodField()
    class Meta:
        model = ChannelPartner
        fields = '__all__'
        extra_kwargs = {
            'full_name': {'required': True},
            'primary_phone_no': {'required': True},
            'firm': {'required': True},
            'primary_email': {'required': True},
            'rera_id': {'required': True},
            'bank_account_number': {'required': True, 'allow_blank': False, 'allow_null': False},
            'bank_account_holder_name': {'required': True, 'allow_blank': False, 'allow_null': False},
            'ifsc_code': {'required': True, 'allow_blank': False, 'allow_null': False},
            'brokerage_category' : {'required' : True}
        }
    def get_leads(self, obj):
        try:
            queryset = Lead.objects.all()
            leads_generated = queryset.filter(channel_partner=obj).count()
            leads_generated_queryset = queryset.filter(channel_partner=obj)
            leads_booked = leads_generated_queryset.filter(projectinventory__status="Booked").count()
            return f"{leads_booked} / {leads_generated}"
        except Exception as e:
            return None
        
    def get_status(self, obj):
        active_channel_partner = obj.lead_set.filter(projectinventory__status="Booked").count()
        return "Active" if active_channel_partner > 0 else "Inactive"    


class MeetingCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Meeting
        fields = '__all__'
        extra_kwargs = {
            'channel_partner': {'required': False},
        }

    
class ChannelPartnerUploadSerializer(serializers.ModelSerializer):
    meetings = MeetingCreateSerializer(many=True, required=False)

    class Meta:
        model = ChannelPartner
        fields = '__all__'
        extra_kwargs = {
        #     'full_name': {'required': True},
            'primary_phone_no': {'required': True},
            'firm': {'required': True},
        #     'primary_email': {'required': True},
        #     # 'rera_id': {'required': True},
        #     'address': {'required': True},
        #     'pin_code': {'required': True}
         }

    def create(self, validated_data):
        meetings_data = validated_data.pop('meetings', [])
        print('meetings_data:', meetings_data)
        channel_partner = ChannelPartner.objects.create(**validated_data)
        print('channel_partner:', channel_partner)
        
        for meeting_data in meetings_data:
            Meeting.objects.create(channel_partner=channel_partner, **meeting_data)
        
        return channel_partner

    
class MeetingSerializer(serializers.ModelSerializer):
    channel_partner_data = serializers.SerializerMethodField()
    class Meta:
        model = Meeting
        fields = '__all__'
    def get_channel_partner_data(self,obj):
        return ChannelPartnerId(obj.channel_partner).data if obj.channel_partner else None  


class MeetingExportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Meeting
        fields = ['id', 'date', 'start_time', 'end_time', 'location', 'notes', 'duration']

class ChannelPartnerExportSerializer(serializers.ModelSerializer):
    ph_number = serializers.CharField(source='primary_phone_no')
    email = serializers.CharField(source='primary_email')
    cp_status = serializers.CharField(source='channel_partner_status')
    sourcing_manager = serializers.SerializerMethodField()
    date = serializers.SerializerMethodField()
    start_time = serializers.SerializerMethodField()
    end_time = serializers.SerializerMethodField()
    locality = serializers.SerializerMethodField()
    remarks = serializers.SerializerMethodField()
    time_spent_with_cp = serializers.SerializerMethodField()
    type_of_visit = serializers.SerializerMethodField()
    latest_date_of_revisit = serializers.SerializerMethodField()
    latest_feedback_of_revisit = serializers.SerializerMethodField()
    meetings = MeetingExportSerializer(many=True, read_only=True)

    class Meta:
        model = ChannelPartner
        fields = [
            "id", "full_name", "sourcing_manager", "firm", "ph_number", "rera_id",
            "pan_no", "cp_status", "date", "start_time", "end_time", "meetings",
            "locality", "remarks", "category", "type_of_cp", "pin_code", "address",
            "email", "time_spent_with_cp", "type_of_visit", "latest_date_of_revisit",
            "latest_feedback_of_revisit"
        ]

    def get_latest_meeting(self, obj):
        return Meeting.objects.filter(channel_partner=obj).order_by('-date', '-end_time').first()

    def get_sourcing_manager(self, obj):
        return obj.creator.name if obj.creator else None  
    
    def get_location_meeting(self,obj):
        latest_meeting = Meeting.objects.filter(channel_partner__id=obj.id).order_by('-date','-end_time').first()
        if latest_meeting and latest_meeting.location:
            return latest_meeting.location
        return None

    def get_date(self, obj):
        latest_meeting = self.get_latest_meeting(obj)
        if latest_meeting and latest_meeting.date:
            return latest_meeting.date.strftime('%Y-%m-%d')
        return None

    def get_start_time(self, obj):
        latest_meeting = self.get_latest_meeting(obj)
        if latest_meeting and latest_meeting.start_time:
            return latest_meeting.start_time.strftime('%H:%M')
        return None

    def get_end_time(self, obj):
        latest_meeting = self.get_latest_meeting(obj)
        if latest_meeting and latest_meeting.end_time:
            return latest_meeting.end_time.strftime('%H:%M')
        return None

    def get_locality(self, obj):
        latest_meeting = self.get_latest_meeting(obj)
        if latest_meeting and latest_meeting.location:
            return latest_meeting.location
        return None

    def get_remarks(self, obj):
        latest_meeting = self.get_latest_meeting(obj)
        if latest_meeting and latest_meeting.notes:
            return latest_meeting.notes
        return None

    def get_time_spent_with_cp(self, obj):
        latest_meeting = self.get_latest_meeting(obj)
        if latest_meeting and latest_meeting.start_time and latest_meeting.end_time:
            start_time = datetime.strptime(latest_meeting.start_time.strftime('%H:%M'), '%H:%M')
            end_time = datetime.strptime(latest_meeting.end_time.strftime('%H:%M'), '%H:%M')
            duration = end_time - start_time
            return str(duration)
        return None

    def get_type_of_visit(self, obj):
        latest_meeting = self.get_latest_meeting(obj)
        if latest_meeting:
            previous_meetings_today = Meeting.objects.filter(channel_partner=obj, date__lte=latest_meeting.date).count()
            return "fresh" if previous_meetings_today == 1 else "revisit"
        return None

    def get_latest_date_of_revisit(self, obj):
        latest_meeting = self.get_latest_meeting(obj)
        if latest_meeting:
            previous_meetings_today = Meeting.objects.filter(channel_partner=obj, date__lte=latest_meeting.date).count()
            if previous_meetings_today > 1:
                return latest_meeting.date.strftime('%Y-%m-%d')
        return None

    def get_latest_feedback_of_revisit(self, obj):
        latest_meeting = self.get_latest_meeting(obj)
        if latest_meeting:
            previous_meetings_today = Meeting.objects.filter(channel_partner=obj, date__lte=latest_meeting.date).count()
            if previous_meetings_today > 1:
                return latest_meeting.notes
        return None    
class ChannelPartnerIncompleteExportSerializer(serializers.ModelSerializer):
    location_meeting = serializers.SerializerMethodField()
    meeting_date_time = serializers.SerializerMethodField()
    phone_number = serializers.CharField(source='primary_phone_no')
    class Meta:
        model = ChannelPartner
        fields = ["firm","phone_number","meeting_date_time","location_meeting"]

    def get_location_meeting(self,obj):
        latest_meeting = Meeting.objects.filter(channel_partner=obj).order_by('-date','-end_time').first()
        if latest_meeting:
            return latest_meeting.location
        return None   
    
    def get_meeting_date_time(self,obj):
        latest_meeting = Meeting.objects.filter(channel_partner=obj).order_by('-date','-end_time').first()
        if latest_meeting and latest_meeting.start_time:
            return f"{latest_meeting.date}  {latest_meeting.start_time} - {latest_meeting.end_time}"
        return None

  
class ChannelPartnerSerializerFirmName(serializers.ModelSerializer):
    leads_generated =  serializers.SerializerMethodField()
    leads_booked = serializers.SerializerMethodField()
    channel_partner_status_list = serializers.SerializerMethodField()
    type_of_cp_list = serializers.SerializerMethodField()
    category_list = serializers.SerializerMethodField()
    location_meeting = serializers.SerializerMethodField()
    isNotes = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()
    meeting_date_time = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    brokerage_percentage = serializers.SerializerMethodField()
    class Meta:
        model = ChannelPartner
        fields =  '__all__'

    def validate(self, data):
        if not data.get('firm'):
            raise serializers.ValidationError("Firm Name is required.")
        return data

    def get_leads_generated(self, obj):
        try:
            queryset = Lead.objects.all()
            leads_generated = queryset.filter(channel_partner=obj).count()
            return  leads_generated
        except Exception as e:
            return None
        
    def get_leads_booked(self, obj):
        try:
            queryset = Lead.objects.all()
            leads_generated_queryset = queryset.filter(channel_partner=obj)
            leads_booked = leads_generated_queryset.filter(projectinventory__status="Booked").count()
            return leads_booked
        except Exception as e:
            return None

    def get_channel_partner_status_list(self, obj):
        CP_STATUS = [
            ('New','New'),
            ('Interested', 'Interested'),
            ('Not Interested', 'Not Interested'),
            ('Might be Interested', 'Might be Interested')
        ]
            
        channel_partner_status_choices = dict(CP_STATUS)
        channel_partner_picked = obj.channel_partner_status

        cp_status_list = [
        {"status": status, "selected": status == channel_partner_picked}
        for status in channel_partner_status_choices.keys()
    ]
        return cp_status_list   
    
    def get_created_by(self,obj):
        return UserDataSerializer(obj.creator).data if obj.creator else None  

    def get_type_of_cp_list(self, obj):
        TYPE_OF_CP = [
            ('ICP', 'ICP'),
            ('RETAIL', 'RETAIL')
        ]
            
        type_of_cp_choices = dict(TYPE_OF_CP)
        type_of_cp_picked = obj.type_of_cp

        type_of_cp_list = [
            {"type": cp_type, "selected": cp_type == type_of_cp_picked}
            for cp_type in type_of_cp_choices.keys()
        ]
        return type_of_cp_list

    def get_category_list(self, obj):
        CATEGORY = [
            ('1', '1'),
            ('2', '2'),
            ('3', '3')
        ]
            
        category_choices = dict(CATEGORY)
        category_picked = obj.category

        category_list = [
            {"category": category, "selected": category == category_picked}
            for category in category_choices.keys()
        ]
        return category_list  

    def get_isNotes(self,obj):
        latest_meeting = Meeting.objects.filter(channel_partner=obj).order_by('-date','-end_time').first()
        if latest_meeting:
            return True if latest_meeting.notes else False
        return False
    
    def get_location_meeting(self,obj):
        latest_meeting = Meeting.objects.filter(channel_partner=obj).order_by('-date','-end_time').first()
        if latest_meeting:
            return latest_meeting.location
        return None   
    
    def get_meeting_date_time(self,obj):
        latest_meeting = Meeting.objects.filter(channel_partner=obj).order_by('-date','-end_time').first()
        if latest_meeting and latest_meeting.start_time:
            return f"{latest_meeting.date} {latest_meeting.start_time}"
        return None
    

    def get_status(self, obj):
        #active_channel_partner = Lead.objects.filter(channel_partner=obj, projectinventory__status="Booked").count()
        # active_channel_partner = ProjectInventory.objects.filter(lead__channel_partner=obj, status='Booked').count()
        # print('booked',active_channel_partner)
        # return "Active" if active_channel_partner > 0 else "Inactive"

        three_months_ago = timezone.now() - timedelta(days=90)

        # Queryset for active CPs within the last 5 minutes
        active_cps = ChannelPartner.objects.filter(
            Q(created_on__gte=three_months_ago) |  # Created within the last 90 days
            Q(lead__projectinventory__status="Booked", lead__projectinventory__booked_on__gte=three_months_ago)  # At least one booking in the last 3 months
        ).exclude(
            Q(full_name__isnull=True) & 
            Q(primary_email__isnull=True) & 
            Q(address__isnull=True) & 
            Q(pin_code__isnull=True)
        ).distinct()

        is_active = active_cps.filter(id=obj.id).exists()

        print(is_active)

        # Return status based on whether the ChannelPartner is active
        return "Active" if is_active else "Inactive"
    
    def get_brokerage_percentage(self, obj):
        print("inside brokerage perecebtage")
        return self.get_brokerage_percentage_static(obj)

    @staticmethod
    def get_brokerage_percentage_static(channel_partner):
        print("here static")
        brokerage_entry = ChannelPartnerBrokerage.objects.filter(channel_partner=channel_partner).order_by("-updated_on").first()
        print("brokerage entry",brokerage_entry)
        if brokerage_entry:
            channel_partner.brokerage_category = brokerage_entry.brokerage_category
            channel_partner.save()
            return str(brokerage_entry.brokerage_percentage)
        else:
            # Calculate the brokerage percentage based on the number of deals
            brokerage_category = channel_partner.brokerage_category
            #booked_count = channel_partner.lead_set.filter(projectinventory__status="Booked").count()
            booked_count = ProjectInventory.objects.filter(lead__channel_partner=channel_partner, status='Booked').count()
            print(booked_count)
            deal_ranges = BrokerageDeal.objects.filter(category=brokerage_category)
            print(deal_ranges)
            for deal in deal_ranges:
                deal_range = deal.deal_range
                print(deal_range)
                if 'Onwards' in deal_range:
                    range_start = int(deal_range.split()[0])  # Extract the start value
                    if booked_count >= range_start:
                        return str(deal.percentage)
                else:
                    # Handle ranges in the format 'start-end'
                    try:
                        range_start, range_end = map(int, deal_range.split('-'))
                        if range_start <= booked_count <= range_end:
                            return str(deal.percentage)
                    except ValueError:
                        # Handle unexpected format
                        continue

            return "3.00"
            
    
class ChannelPartnerByIdSerializer(serializers.ModelSerializer):
    leads_generated =  serializers.SerializerMethodField()
    leads_booked = serializers.SerializerMethodField()
    channel_partner_status_list = serializers.SerializerMethodField()
    type_of_cp_list = serializers.SerializerMethodField()
    category_list = serializers.SerializerMethodField()
    location_meeting = serializers.SerializerMethodField()
    isNotes = serializers.SerializerMethodField()
    meeting_date_time = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    brokerage_percentage = serializers.SerializerMethodField()
    class Meta:
        model = ChannelPartner
        fields = '__all__'
        extra_kwargs = {
            'full_name': {'required': True},
            'primary_phone_no': {'required': True},
            'firm': {'required': True},
            'primary_email': {'required': True},
            # 'rera_id': {'required': True},
            'address': {'required': True},
            'pin_code': {'required': True}
        }
    
    def validate_phone_number(self, value):
        existing_cp = ChannelPartner.objects.exclude(pk=self.instance.pk).filter(phone_number=value)
        if existing_cp.exists():
            raise serializers.ValidationError("Phone number already exists for another Channel Partner.")
        return value
    
    def validate_rera_id(self, value):
        existing_cp = ChannelPartner.objects.exclude(pk=self.instance.pk).filter(rera_id=value)
        if existing_cp.exists():
            raise serializers.ValidationError("RERA ID already exists for another Channel Partner.")
        return value

    def validate_primary_email(self, value):
        existing_cp = ChannelPartner.objects.exclude(pk=self.instance.pk).filter(primary_email=value)
        if existing_cp.exists():
            raise serializers.ValidationError("Primary email already exists for another Channel Partner.")
        return value
    
    
    def get_leads_generated(self, obj):
        try:
            queryset = Lead.objects.all()
            leads_generated = queryset.filter(channel_partner=obj).count()
            return  leads_generated
        except Exception as e:
            return None
        
    def get_leads_booked(self, obj):
        try:
            queryset = Lead.objects.all()
            leads_generated_queryset = queryset.filter(channel_partner=obj)
            leads_booked = leads_generated_queryset.filter(projectinventory__status="Booked").count()
            return leads_booked
        except Exception as e:
            return None

    def get_channel_partner_status_list(self, obj):
        CP_STATUS = [
            ('New','New'),
            ('Interested', 'Interested'),
            ('Not Interested', 'Not Interested'),
            ('Might be Interested', 'Might be Interested')
        ]
            
        channel_partner_status_choices = dict(CP_STATUS)
        channel_partner_picked = obj.channel_partner_status

        cp_status_list = [
        {"status": status, "selected": status == channel_partner_picked}
        for status in channel_partner_status_choices.keys()
    ]
        return cp_status_list 
    
    def get_type_of_cp_list(self, obj):
        TYPE_OF_CP = [
            ('ICP', 'ICP'),
            ('RETAIL', 'RETAIL')
        ]
            
        type_of_cp_choices = dict(TYPE_OF_CP)
        type_of_cp_picked = obj.type_of_cp

        type_of_cp_list = [
            {"type": cp_type, "selected": cp_type == type_of_cp_picked}
            for cp_type in type_of_cp_choices.keys()
        ]
        return type_of_cp_list 

    def get_category_list(self, obj):
        CATEGORY = [
            ('1', '1'),
            ('2', '2'),
            ('3', '3')
        ]
            
        category_choices = dict(CATEGORY)
        category_picked = obj.category

        category_list = [
            {"category": category, "selected": category == category_picked}
            for category in category_choices.keys()
        ]
        return category_list      

    def get_isNotes(self,obj):
        latest_meeting = Meeting.objects.filter(channel_partner=obj).order_by('-date','-end_time').first()
        if latest_meeting:
            return True if latest_meeting.notes else False
        return False
    
    def get_location_meeting(self,obj):
        latest_meeting = Meeting.objects.filter(channel_partner=obj).order_by('-date','-end_time').first()
        if latest_meeting:
            return latest_meeting.location
        return None
    
    def get_meeting_date_time(self,obj):
        latest_meeting = Meeting.objects.filter(channel_partner=obj).order_by('-date','-end_time').first()
        if latest_meeting  and latest_meeting.start_time:
            return f"{latest_meeting.date} {latest_meeting.start_time}"
        return None
    
   
    def get_status(self, obj):
        #active_channel_partner = Lead.objects.filter(channel_partner=obj, projectinventory__status="Booked").count()
        active_channel_partner = ProjectInventory.objects.filter(lead__channel_partner=obj, status='Booked').count()
        print('booked',active_channel_partner)
        return "Active" if active_channel_partner > 0 else "Inactive"
    
    def get_brokerage_percentage(self, obj):
        print("inside brokerage perecebtage")
        return self.get_brokerage_percentage_static(obj)

    @staticmethod
    def get_brokerage_percentage_static(channel_partner):
        print("here static")
        brokerage_entry = ChannelPartnerBrokerage.objects.filter(channel_partner=channel_partner).order_by("-updated_on").first()
        print("brokerage entry",brokerage_entry)
        if brokerage_entry:
            channel_partner.brokerage_category = brokerage_entry.brokerage_category
            channel_partner.save()
            return str(brokerage_entry.brokerage_percentage)
        else:
            # Calculate the brokerage percentage based on the number of deals
            brokerage_category = channel_partner.brokerage_category
            #booked_count = channel_partner.lead_set.filter(projectinventory__status="Booked").count()
            booked_count = ProjectInventory.objects.filter(lead__channel_partner=channel_partner, status='Booked').count()
            print(booked_count)
            deal_ranges = BrokerageDeal.objects.filter(category=brokerage_category)
            print(deal_ranges)
            for deal in deal_ranges:
                deal_range = deal.deal_range
                print(deal_range)
                if 'Onwards' in deal_range:
                    range_start = int(deal_range.split()[0])  # Extract the start value
                    if booked_count >= range_start:
                        return str(deal.percentage)
                else:
                    # Handle ranges in the format 'start-end'
                    try:
                        range_start, range_end = map(int, deal_range.split('-'))
                        if range_start <= booked_count <= range_end:
                            return str(deal.percentage)
                    except ValueError:
                        # Handle unexpected format
                        continue

            return "3.00"
            
    


#Brokerage Deal Serializer (for default ladder)
class BrokerageDealSerializer(serializers.ModelSerializer):
    class Meta:
        model = BrokerageDeal
        fields = ['id', 'deal_range', 'percentage']


#Brokerage Ladder Category serializer(for default ladder)
# serializers.py

class BrokerageCategorySerializer(serializers.ModelSerializer):
    deals = BrokerageDealSerializer(many=True)

    class Meta:
        model = BrokerageCategory
        fields = ['id', 'name', 'deals']

    def create(self, validated_data):
        deals_data = validated_data.pop('deals')
        category = BrokerageCategory.objects.create(**validated_data)
        for deal_data in deals_data:
            BrokerageDeal.objects.create(category=category, **deal_data)
        return category

    def update(self, instance, validated_data):
        deals_data = validated_data.pop('deals')
        instance.name = validated_data.get('name', instance.name)
        instance.save()

        # Get existing deals and mark them for deletion if not in the updated data
        existing_deals = {deal.id: deal for deal in instance.deals.all()}
        updated_deals = []

        for deal_data in deals_data:
            deal_id = deal_data.get('id')
            if deal_id and deal_id in existing_deals:
                # Update existing deal
                deal = existing_deals.pop(deal_id)
                deal.deal_range = deal_data.get('deal_range', deal.deal_range)
                deal.percentage = deal_data.get('percentage', deal.percentage)
                deal.save()
                updated_deals.append(deal)
            else:
                # Create new deal
                new_deal = BrokerageDeal.objects.create(category=instance, **deal_data)
                updated_deals.append(new_deal)

        # Delete deals that were not updated
        for deal in existing_deals.values():
            deal.delete()

        return instance

    

class ChannelPartnerBrokerageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChannelPartnerBrokerage
        fields = '__all__'

    
class LeadConvertedSales(serializers.ModelSerializer):
    lead_name = serializers.SerializerMethodField()
    phone_number = serializers.SerializerMethodField()
    created_on = serializers.SerializerMethodField()
    has_notes = serializers.SerializerMethodField()
    no_of_calls = serializers.SerializerMethodField()
    source_id = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()
    assigned_to = serializers.SerializerMethodField()   
    class Meta:
        model = Lead
        fields = ('id','lead_name','created_on','created_by','assigned_to','phone_number','source_id','converted_on','has_notes', 'no_of_calls', 'is_important' )

    def get_phone_number(self, obj):
        return obj.primary_phone_no
            
    def get_lead_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"

    def get_created_on(self, obj):
        return f"{obj.created_on.date()}"
    
    def get_has_notes(self, obj):
        return obj.notes_set.exists()  
    
    def get_no_of_calls(self, obj):
        return None

    def get_source_id(self, obj):
        if obj.source:
            src_data = {"source_id": obj.source.source_id, "source_data": obj.source.name}
            return src_data
        else:
            return None 
        
    def get_created_by(self,obj):
        return UserDataSerializer(obj.creator).data if obj.creator else None  

    def get_assigned_to(self, obj):
        try:
            workflow = obj.workflow.get()
            assigned_to = workflow.assigned_to
            first_stage = workflow.stages.all().order_by('order').first()
            if first_stage and first_stage.assigned_to:
                user = first_stage.assigned_to
                if user.groups.filter(name="CALL_CENTER_EXECUTIVE").exists():
                    return UserDataSerializer(first_stage.assigned_to).data  
                else:
                    return None
            else:
                return None 
        except Workflow.DoesNotExist:
            return None   
    
class LeadConvertedSalesExport(serializers.ModelSerializer):
    lead_name = serializers.SerializerMethodField()
    phone_number = serializers.SerializerMethodField()
    created_on = serializers.SerializerMethodField()
    source_id = serializers.SerializerMethodField()
    assigned_to = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()   
    class Meta:
        model = Lead
        fields = ('id','lead_name','created_on','created_by','assigned_to','phone_number','source_id','converted_on' )

    def get_phone_number(self, obj):
        return obj.primary_phone_no
            
    def get_lead_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"

    def get_created_on(self, obj):
        return f"{obj.created_on.date()}"
    

    def get_source_id(self, obj):
        if obj.source:
            src_data =  f"{obj.source.source_id} - {obj.source.name}"
            return src_data
        else:
            return None 
        
    def get_created_by(self,obj):
        return obj.creator.name if obj.creator else None  
    
    def get_assigned_to(self, obj):
        try:
            workflow = obj.workflow.get()
            assigned_to = workflow.assigned_to
            first_stage = workflow.stages.all().order_by('order').first()
            if first_stage and first_stage.assigned_to:
                user = first_stage.assigned_to
                if user.groups.filter(name="CALL_CENTER_EXECUTIVE").exists():
                    return first_stage.assigned_to.name 
                else:
                    return None
            else:
                return None 
        except Workflow.DoesNotExist:
            return None    
        
class LeadUnallocatedExport(serializers.ModelSerializer):
    lead_name = serializers.SerializerMethodField()
    phone_number = serializers.SerializerMethodField()
    created_on = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()
    assigned_to = serializers.SerializerMethodField()
    source_id = serializers.SerializerMethodField()
    next_follow_up = serializers.SerializerMethodField()   

    class Meta:
        model = Lead
        fields = ('id','lead_name','created_on','created_by','assigned_to','phone_number','source_id','lead_status', 'next_follow_up')

    def get_phone_number(self, obj):
        return obj.primary_phone_no
            
    def get_lead_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"

    def get_created_on(self, obj):

        return f"{obj.created_on.date()}"
    
    def get_source_id(self, obj):
        if obj.source:
            src_data =  f"{obj.source.source_id} - {obj.source.name}"
            return src_data
        else:
            return None 
        
    def get_created_by(self,obj):
        return obj.creator.name if obj.creator else None  

    
    def get_assigned_to(self, obj):
        try:
            workflow = obj.workflow.get()
            assigned_to = workflow.assigned_to
            first_stage = workflow.stages.all().order_by('order').first()
            if first_stage and first_stage.assigned_to:
                user = first_stage.assigned_to
                if user.groups.filter(name="CALL_CENTER_EXECUTIVE").exists():
                    return first_stage.assigned_to.name  
                else:
                    return None
            else:
                return None 
        except Workflow.DoesNotExist:
            return None   
            
    def get_next_follow_up(self, obj):
        workflow = obj.workflow.get()
        # print('workflow-tasks:', workflow.tasks.filter(name='Follow Up', completed=False))
        
        followup_tasks = workflow.tasks.filter(name='Follow Up', completed=False).order_by('-time').last()
        if followup_tasks:
            data = TaskSerializer(followup_tasks).data
            data['date'] = followup_tasks.time.date()
            data['follow_up_pending'] = True if followup_tasks.time <= timezone.now() else False
            data['workflow_id'] = followup_tasks.workflow_id
            return data['date']
        return None   
    
        
class LeadUnallocated(serializers.ModelSerializer):
    lead_name = serializers.SerializerMethodField()
    phone_number = serializers.SerializerMethodField()
    created_on = serializers.SerializerMethodField()
    created_on_time = serializers.SerializerMethodField()
    lead_status_list = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()
    assigned_to = serializers.SerializerMethodField()
    source_id = serializers.SerializerMethodField()
    next_follow_up = serializers.SerializerMethodField()   
    task_details = serializers.SerializerMethodField()   
    class Meta:
        model = Lead
        fields = ('id','lead_name','created_on','created_on_time','created_by','assigned_to','phone_number','source_id','lead_status_list', 'lost_reason', 'next_follow_up','is_important','task_details')

    def get_phone_number(self, obj):
        return obj.primary_phone_no
            
    def get_lead_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"

    def get_created_on_time(self, obj):
        return obj.created_on
    
    def get_created_on(self, obj):

        return f"{obj.created_on.date()}"
    
    def get_created_by(self,obj):
        return UserDataSerializer(obj.creator).data if obj.creator else None 
    
    def get_assigned_to(self, obj):
        try:
            workflow = obj.workflow.get()
            assigned_to = workflow.assigned_to
            first_stage = workflow.stages.all().order_by('order').first()
            if first_stage and first_stage.assigned_to:
                user = first_stage.assigned_to
                if user.groups.filter(name="CALL_CENTER_EXECUTIVE").exists():
                    return UserDataSerializer(first_stage.assigned_to).data  
                else:
                    return None
            else:
                return None 
        except Workflow.DoesNotExist:
            return None        
        
    def get_next_follow_up(self, obj):
        workflow = obj.workflow.get()
        # print('workflow-tasks:', workflow.tasks.filter(name='Follow Up', completed=False))
        
        followup_tasks = workflow.tasks.filter(name='Follow Up', completed=False).order_by('-time').last()
        if followup_tasks:
            data = TaskSerializer(followup_tasks).data
            data['date'] = followup_tasks.time.date()
            data['follow_up_pending'] = True if followup_tasks.time <= timezone.now() else False
            data['workflow_id'] = followup_tasks.workflow_id
            return data
        return None   
    
    def get_task_details(self, obj):
        workflow = obj.workflow.get()
        # print('workflow-tasks:', workflow.tasks.filter(name='Follow Up', completed=False))
        
        followup_tasks = workflow.tasks.filter(name='Follow Up').order_by('-time').last()
        if followup_tasks:
            data = TaskSerializer(followup_tasks).data
            data['date'] = followup_tasks.time.date()
            data['workflow_id'] = followup_tasks.workflow_id
            return data
        return None   
    
    def get_lead_status_list(self, obj):
        LEAD_STATUS_CHOICES = [
                ('New', 'New'),
                ('Hot', 'Hot'),
                ('Warm', 'Warm'),
                ('Cold', 'Cold'),
                ('Lost', 'Lost'),
            ]
            
        lead_status_choices = dict(LEAD_STATUS_CHOICES)
        lead_status_picked = obj.lead_status
        print(obj.lead_status)
        lead_status_list = [
        {"status": status, "selected": status == lead_status_picked}
        for status in lead_status_choices.keys()
    ]
        return lead_status_list

    def get_source_id(self, obj):
        if obj.source:
            src_data = {"source_id": obj.source.source_id, "source_data": obj.source.name}
            return src_data
        else:
            return None 


class LeadPreSalesExportSerializer(serializers.ModelSerializer):
    lead_name = serializers.SerializerMethodField()
    phone_number = serializers.SerializerMethodField()
    created_on = serializers.SerializerMethodField()
    source_id = serializers.SerializerMethodField()
    next_follow_up = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()
    assigned_to = serializers.SerializerMethodField()
 

    class Meta:
        model = Lead
        fields = ('id','lead_name','created_on', 'created_by','assigned_to','phone_number','source_id','lead_status', 'next_follow_up')

    def get_phone_number(self, obj):
        return obj.primary_phone_no
            
    def get_lead_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"

    def get_created_on(self, obj):
        return f"{obj.created_on.date()}"

    def get_source_id(self, obj):
        if obj.source:
            src_data =  f"{obj.source.name}"
            return src_data
        else:
            return None 
        
    def get_created_by(self,obj):
        return obj.creator.name if obj.creator else None  

    def get_assigned_to(self, obj):
        try:
            workflow = obj.workflow.get()
            assigned_to = workflow.assigned_to
            first_stage = workflow.stages.all().order_by('order').first()
            if first_stage and first_stage.assigned_to:
                user = first_stage.assigned_to
                if user.groups.filter(name="CALL_CENTER_EXECUTIVE").exists():
                    return first_stage.assigned_to.name 
                else:
                    return None
            else:
                return None 
        except Workflow.DoesNotExist:
            return None     
        
    def get_next_follow_up(self, obj):
        workflow = obj.workflow.get()
        # print('workflow-tasks:', workflow.tasks.filter(name='Follow Up', completed=False))
        
        followup_tasks = workflow.tasks.filter(name='Follow Up', completed=False).order_by('-time').last()
        if followup_tasks:
            data = TaskSerializer(followup_tasks).data
            data['date'] = followup_tasks.time.date()
            data['follow_up_pending'] = True if followup_tasks.time <= timezone.now() else False
            data['workflow_id'] = followup_tasks.workflow_id
            return data['date']
        return None

    
    


class LeadPreSalesSerializer(serializers.ModelSerializer):
    lead_name = serializers.SerializerMethodField()
    phone_number = serializers.SerializerMethodField()
    created_on = serializers.SerializerMethodField()
    created_on_time = serializers.SerializerMethodField()
    source_id = serializers.SerializerMethodField()
    next_follow_up = serializers.SerializerMethodField()
    lead_status_list = serializers.SerializerMethodField()
    assigned_to = serializers.SerializerMethodField()
    has_notes = serializers.SerializerMethodField()  
    no_of_calls = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()
    task_details = serializers.SerializerMethodField()

    class Meta:
        model = Lead
        fields = ('id','lead_name','created_on', 'created_on_time', 'created_by','assigned_to', 'phone_number','source_id','lead_status_list', 'next_follow_up', 'has_notes', 'no_of_calls','lost_reason', 'is_important','task_details')

    def get_phone_number(self, obj):
        return obj.primary_phone_no
            
    def get_lead_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"

    def get_created_on(self, obj):
        return f"{obj.created_on.date()}"
    
    def get_created_on_time(self, obj):
        return obj.created_on
    
    def get_source_id(self, obj):
        if obj.source:
            src_data = {"source_id": obj.source.source_id, "source_data": obj.source.name}
            return src_data
        else:
            return None  

    def get_created_by(self,obj):
        return UserDataSerializer(obj.creator).data if obj.creator else None
        
    def get_next_follow_up(self, obj):
        workflow = obj.workflow.get()
        # print('workflow-tasks:', workflow.tasks.filter(name='Follow Up', completed=False))
        
        followup_tasks = workflow.tasks.filter(name='Follow Up', completed=False).order_by('-time').last()
        if followup_tasks:
            data = TaskSerializer(followup_tasks).data
            data['date'] = followup_tasks.time.date()
            data['follow_up_pending'] = True if followup_tasks.time <= timezone.now() else False
            data['workflow_id'] = followup_tasks.workflow_id
            return data
        return None

    def get_task_details(self, obj):
        workflow = obj.workflow.get()
        # print('workflow-tasks:', workflow.tasks.filter(name='Follow Up', completed=False))
        
        followup_tasks = workflow.tasks.filter(name='Follow Up').order_by('-time').last()
        if followup_tasks:
            data = TaskSerializer(followup_tasks).data
            data['date'] = followup_tasks.time.date()
            data['workflow_id'] = followup_tasks.workflow_id
            return data
        return None 
    
    def get_no_of_calls(self, obj):
        return None     
    
    def get_has_notes(self, obj):
        return obj.notes_set.exists()
    
    def get_lead_status_list(self, obj):
        LEAD_STATUS_CHOICES = [
                ('New', 'New'),
                ('Hot', 'Hot'),
                ('Warm', 'Warm'),
                ('Cold', 'Cold'),
                ('Lost', 'Lost'),
            ]
            
        lead_status_choices = dict(LEAD_STATUS_CHOICES)
        lead_status_picked = obj.lead_status
        # print(obj.lead_status)
        lead_status_list = [
        {"status": status, "selected": status == lead_status_picked}
        for status in lead_status_choices.keys()
    ]
        return lead_status_list


    def get_assigned_to(self, obj):
        try:
            workflow = obj.workflow.get()
            assigned_to = workflow.assigned_to
            first_stage = workflow.stages.all().order_by('order').first()
            if first_stage and first_stage.assigned_to:
                user = first_stage.assigned_to
                if user.groups.filter(name="CALL_CENTER_EXECUTIVE").exists():
                    return UserDataSerializer(first_stage.assigned_to).data  
                else:
                    return None
            else:
                return None 
        except Workflow.DoesNotExist:
            return None   
        
class LeadSalesSerializer(serializers.ModelSerializer):
    lead_name = serializers.SerializerMethodField()
    phone_number = serializers.SerializerMethodField()
    sv_done = serializers.IntegerField() 
    #sv_status = serializers.CharField()
    sv_status_list = serializers.SerializerMethodField()      
    sv_datetime = serializers.CharField()
    sv_id = serializers.SerializerMethodField()
    closing_manager= serializers.SerializerMethodField()
    sourcing_manager = serializers.SerializerMethodField()
    lead_status_list = serializers.SerializerMethodField() 
    source_id = serializers.SerializerMethodField()
    has_notes = serializers.SerializerMethodField()
    class Meta:
        model = Lead
        fields = ('id','lead_name', 'phone_number','lead_status_list', 'sv_done', 'sv_id', 'sv_status_list', 'sv_datetime','closing_manager','sourcing_manager','lost_reason','source_id', 'has_notes') 

    def get_lead_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"

    def get_phone_number(self, obj):
        return obj.primary_phone_no if obj.primary_phone_no else None
    
    def get_closing_manager(self, obj):
        return obj.closing_manager if obj.closing_manager else None
    
    def get_sourcing_manager(self,obj):
        site_visit = SiteVisit.objects.filter(lead=obj).order_by('-visit_date')
        sv = site_visit.first()
        print("site_visit fetching",sv.id)
        if sv and sv.sourcing_manager:
            sm_instance = Users.objects.filter(id=sv.sourcing_manager.id).first()
            return {
                "id" : sm_instance.id,
                'name' : sm_instance.name
            }
        return None
    
    # def get_sourcing_manager(self,obj):
    #     sv = SiteVisit.objects.filter(lead=obj).first()
    #     return sv.sourcing_manager if sv.sourcing_manager else None
    
    def get_sv_id(self, obj):  # 
        return obj.sv_id if obj.sv_id else None
    
    def get_has_notes(self, obj):
        return obj.notes_set.exists()
    
    def get_source_id(self, obj):
        if obj.source:
            src_data = {"source_id": obj.source.source_id, "source_data": obj.source.name}
            return src_data
        else:
            return None  
        
    def get_sv_status_list(self, obj):
        SITEVISIT_CHOICES = [
            ("Site Visit Done", "Site Visit Done"), 
            ("Missed", "Missed"),
            ("Scheduled", "Scheduled"),
        ]

        SiteVisit_choices = dict(SITEVISIT_CHOICES)
        sitevisit_picked = obj.sv_status 
        print(sitevisit_picked)
        sv_status_list = [
            {"status": status, "selected": status == sitevisit_picked}
            for status in SiteVisit_choices.keys()
        ]
        return sv_status_list
    
    def get_lead_status_list(self, obj):
        LEAD_STATUS_CHOICES = [
                ('New', 'New'),
                ('Hot', 'Hot'),
                ('Warm', 'Warm'),
                ('Cold', 'Cold'),
                ('Lost', 'Lost'),
            ]
            
        lead_status_choices = dict(LEAD_STATUS_CHOICES)
        lead_status_picked = obj.lead_status
        print(obj.lead_status)
        lead_status_list = [
        {"status": status, "selected": status == lead_status_picked}
        for status in lead_status_choices.keys()
    ]
        return lead_status_list
    def to_representation(self, instance):
        data = super(LeadSalesSerializer, self).to_representation(instance)
        data['sv_done'] = instance.sv_done
        data['sv_status'] = instance.sv_status
        data['sv_datetime'] = instance.sv_datetime
        #data['closing_manager'] = instance.closing_manager
        return data

# from .models import Inventory, Project,BookingForm, CollectToken

# class InventorySerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Inventory
#         fields = '__all__'

# class BookingFormSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = BookingForm
#         fields = '__all__'

# class CollectTokenSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = CollectToken
#         fields = '__all__'


class LeadClosureSerializer(serializers.Serializer):
    id = serializers.CharField()
    lead_name = serializers.SerializerMethodField()
    sv_datetime = serializers.CharField()  # Add the Site Visit Date and Time 
    closing_manager= serializers.SerializerMethodField('get_closing_manager')
    channel_partner = serializers.CharField()
    apartment_no = serializers.SerializerMethodField()
    pre_deal_amount = serializers.SerializerMethodField()
    deal_amount = serializers.SerializerMethodField('get_deal_amount')



    def get_lead_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"

    def get_apartment_no(self, obj):
        #return None
        try:
            inventory = obj.projectinventory_set.first()
            if inventory:
                return inventory.apartment_no
        except ProjectInventory.DoesNotExist:
            return None
        
    def get_pre_deal_amount(self, obj):
        #return None
        try:
            inventory = obj.projectinventory_set.first()
            if inventory:
                return inventory.pre_deal_amount
        except ProjectInventory.DoesNotExist:
            return None

    def get_deal_amount(self, obj):
        try:
            property_owner_details = obj.property_owner.first()
            if property_owner_details:
                return property_owner_details.deal_amount
        except PropertyOwner.DoesNotExist:
            return None

    def get_closing_manager(self, obj):
        #return None
        try:
            bookingform = obj.bookingform_set.first()
            if bookingform:
                return UserDataSerializer(bookingform.sales_manager_name).data
        except BookingForm.DoesNotExist:
            return None      
class UserAllocationSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()  # ID of the user to assign
    lead_ids = serializers.ListField(child=serializers.IntegerField())  # List of lead IDs to assign

class UserReallocationSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()  # ID of the user to assign
    lead_id = serializers.IntegerField()  # List of lead IDs to assign

class LeadDocSerializer(serializers.ModelSerializer):
    date  = serializers.SerializerMethodField() 
    documents = serializers.SerializerMethodField()
    lead_name = serializers.SerializerMethodField()
    phone_number = serializers.SerializerMethodField()
    paid_in  = serializers.SerializerMethodField() 
    class Meta:
        model = Lead
        fields = ['date','id','lead_name', 'phone_number','paid_in', 'documents']

    def get_documents(self, lead):
        try:
            document_section = DocumentSection.objects.filter(lead=lead).order_by('-id')
            documents = DocumentSectionSerializer(document_section.first()).data
            return documents
        except DocumentSection.DoesNotExist:
            return None
            #return {'upload_link': f'/api/upload-documents/{lead.id}/'}
        
    def get_lead_name(self, obj):
        # Concatenate the first_name and last_name fields from the Lead model
        return f"{obj.first_name} {obj.last_name}"
    
    def get_phone_number(self, obj):
        return obj.primary_phone_no if obj.primary_phone_no else None
    
    def get_paid_in(self, obj):
        return None
    
    def get_date(self, obj):
        return f"{obj.created_on.date()}"  
    
class UpdatesSerializer(serializers.ModelSerializer):
    slab = serializers.SerializerMethodField()
    class Meta:
        model = Updates
        fields = ['lead','welcome_call_status', 'welcome_email_status', 'demand_letter_status', 'snagging_email_status','possession_due_email_status', 'slab']

    def get_slab(self, obj):
        from inventory.serializers import ProjectCostSheetSerializer
        if obj.slab:
            return ProjectCostSheetSerializer(obj.slab).data
        else:
            return None

class LeadPostSalesExportSerializer(serializers.ModelSerializer):
    lead_name = serializers.SerializerMethodField()
    phone_number = serializers.SerializerMethodField()
    crm_executive = serializers.SerializerMethodField()
    welcome_call_status = serializers.SerializerMethodField()
    welcome_email_status = serializers.SerializerMethodField()
    demand_letter_status = serializers.SerializerMethodField()
    snagging_email_status = serializers.SerializerMethodField()
    event_name = serializers.SerializerMethodField() 
    inventory_unit = serializers.SerializerMethodField()
    payment_status = serializers.SerializerMethodField()
    aging = serializers.SerializerMethodField()
    interest = serializers.SerializerMethodField()
    sv_status = serializers.SerializerMethodField()
    # sv_datetime = serializers.SerializerMethodField()
    has_notes = serializers.SerializerMethodField()
    # reminder = serializers.SerializerMethodField()
    # due_date = serializers.SerializerMethodField()
    

    class Meta:
        model = Lead
        fields = ['id','lead_name', 'phone_number','crm_executive','welcome_call_status','welcome_email_status','demand_letter_status', 'snagging_email_status','inventory_unit','payment_status','aging','interest','sv_status','has_notes', 'event_name']

    def get_lead_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"

    def get_phone_number(self, obj):
        return obj.primary_phone_no if obj.primary_phone_no else None
    
    def get_welcome_call_status(self, obj):
        updates_record, created = Updates.objects.get_or_create(lead=obj)

        if created:
            updates_record.save()

        return updates_record.welcome_call_status

    def get_welcome_email_status(self, obj):
        updates_record, created = Updates.objects.get_or_create(lead=obj)

        if created:
            updates_record.save()

        return updates_record.welcome_email_status
    
    def get_demand_letter_status(self, obj):
        updates_record, created = Updates.objects.get_or_create(lead=obj)

        if created:
            updates_record.save()

        return updates_record.demand_letter_status
    
    def get_snagging_email_status(self, obj):
        updates_record, created = Updates.objects.get_or_create(lead=obj)

        if created:
            updates_record.save()

        return updates_record.snagging_email_status

    def get_event_name(self, obj):
        from inventory.models import InventoryCostSheet
        
        next_event = InventoryCostSheet.objects.filter(lead=obj,completed=False).order_by('event_order').first()
        print("inventory_sheeting",next_event)
        if next_event:
        # Return the event name if an incomplete event is found
            return next_event.event
        else:
            # If no incomplete event is found, return a message or None
            return "All events completed"   
    
    def get_crm_executive(self, obj):
        user_ids = obj.followers 

        crm_executive = Users.objects.filter(id__in=user_ids, groups__name="CRM_EXECUTIVE").first()

        return UserDataSerializer(crm_executive).data if crm_executive else None
    
    # def get_due_date(self,obj):
    #     print("inside due date")
    #     from inventory.models import InventoryCostSheet
        
    #     inventory_sheet = InventoryCostSheet.objects.filter(lead=obj).first()
        
    #     if inventory_sheet:
    #         event_name = inventory_sheet.event
    #         event_order = inventory_sheet.event_order
    #         print(event_name)
    #         print(event_order)

    #         due_date = inventory_sheet.due_date
    #         print(due_date)
    #         return due_date    
    #     else :
    #         return None
        
    
    def get_aging(self,obj):
        from inventory.models import InventoryCostSheet
        from django.utils.timezone import make_aware, make_naive, get_current_timezone, is_naive

        status = Updates.objects.filter(lead=obj).first()
        demand_letter_status = status.demand_letter_status
        print("demand letter status" , status.demand_letter_status)
        print("lead id",obj)
        inventory_sheet = InventoryCostSheet.objects.filter(lead=obj).first()
        print("inventory_sheet",inventory_sheet)
        current_date = datetime.now()
        print(current_date)
        if demand_letter_status == "Sent"  and inventory_sheet :
            due_date = inventory_sheet.due_date
            paid_status = inventory_sheet.paid
            print("due_date",due_date)
            print("paid_status",paid_status)
            if due_date is not None and paid_status == False:
                if is_naive(inventory_sheet.due_date):
                    inventory_sheet_due_date = make_aware(inventory_sheet.due_date, timezone=get_current_timezone())
                else:
                    inventory_sheet_due_date = inventory_sheet.due_date

                # Ensure current_date is timezone-aware
                if is_naive(current_date):
                    current_date_aware = make_aware(current_date, timezone=get_current_timezone())
                else:
                    current_date_aware = current_date

                diff_days = (current_date_aware - inventory_sheet_due_date ).days
                print("diff_days",diff_days)
            
                # Determine the aging based on the difference
                if diff_days > 60:
                    return ">60 Days"
                elif 30 < diff_days <= 60:
                    return ">30 Days"
                else:
                    return "<=30 Days"
            else :
                return None    
           
        return None 


    
    def get_interest(self, obj):
        from inventory.models import InventoryCostSheet
        from decimal import Decimal

        inventory_sheet = InventoryCostSheet.objects.filter(lead=obj).first()
       
        # if inventory_sheet:
        #     total_amount = inventory_sheet.total_amount

        aging = self.get_aging(obj)

        if aging == ">60 Days" and inventory_sheet:
            interest_amount = Decimal('0.1') * inventory_sheet.total_amount
            inventory_sheet.total_amount = inventory_sheet.total_amount + interest_amount
            inventory_sheet.save()
            return "10% interest after 60 days"
        elif aging == ">30 Days" and inventory_sheet:
            interest_amount = Decimal('0.05') * inventory_sheet.total_amount
            inventory_sheet.total_amount = inventory_sheet.total_amount + interest_amount
            inventory_sheet.save()
            return "5% interest after 30 days"
        else:
            return None
    
    def get_payment_status(self,obj):
        from inventory.models import InventoryCostSheet

        inventory_sheet = InventoryCostSheet.objects.filter(lead=obj).first()
        aging = self.get_aging(obj)
        if inventory_sheet:
           paid_status = inventory_sheet.paid
        else:
            paid_status = False   

        # Determine payment status based on aging and paid_status
        if aging == "<=30 Days" and not paid_status:
            return "raised"
        elif aging in [">30 Days", ">60 Days"] and not paid_status:
            return "due"
        elif paid_status and aging:
            return "recieved"
        elif aging is None:
            return "raised"
        

    
    def get_inventory_unit(self,obj):
        from inventory.models import ProjectInventory

        inventory = ProjectInventory.objects.filter(lead=obj).first()
        # print("inventory",inventory)

        if inventory :
            flat_number = inventory.flat_no
            tower = inventory.tower.name
            return f"{tower}-{flat_number}"
        else :
            return None
    
    def get_registration_status(self,obj):
        workflow = obj.workflow.get()
        registration_fee_task = workflow.tasks.filter(name='Registration Fees').first()
        print("registration fee task",registration_fee_task)
        if registration_fee_task and registration_fee_task.completed:
            return True
        else:
            return False

  

    def get_has_notes(self, obj):
        return obj.notes_set.exists()  

        

    def get_sv_status(self, obj):
        # Fetch the sv_status from the context data
        lead_data = next((data for data in self.context.get('leads_data', []) if data['lead'] == obj), None)
        return lead_data.get('sv_status') if lead_data else None 

    # def get_sv_datetime(self, obj):
    #     # Fetch the sv_datetime from the context data
    #     lead_data = next((data for data in self.context.get('leads_data', []) if data['lead'] == obj), None)
    #     return lead_data.get('sv_datetime') if lead_data else None  
    
    def get_has_notes(self, obj):
        # Access has_notes field from lead data or directly from the object
        lead_data = next((data for data in self.context.get('leads_data', []) if data['lead'] == obj), None)
        return lead_data.get('has_notes') if lead_data else False

    # def get_sv_status_list(self, obj):
    #     SITEVISIT_CHOICES = [
    #         ("Site Visit Done", "Site Visit Done"),
    #         ("Missed", "Missed"),
    #         ("Scheduled", "Scheduled"),
    #     ]

    #     SiteVisit_choices = dict(SITEVISIT_CHOICES)
    #     sv_status = self.get_sv_status(obj)  # Use the custom method to fetch sv_status

    #     sv_status_list = [
    #         {"status": status, "selected": status == sv_status}
    #         for status in SiteVisit_choices.keys()
    #     ]
    #     return sv_status_list
    


class LeadPostSalesSerializer(serializers.ModelSerializer):
    lead_name = serializers.SerializerMethodField()
    phone_number = serializers.SerializerMethodField()
    crm_executive = serializers.SerializerMethodField()
    welcome_call_status = serializers.SerializerMethodField()
    welcome_email_status = serializers.SerializerMethodField()
    demand_letter_status = serializers.SerializerMethodField()
    snagging_email_status = serializers.SerializerMethodField()
    welcome_call_isimportant = serializers.SerializerMethodField()
    welcome_email_isimportant = serializers.SerializerMethodField()
    has_notes = serializers.SerializerMethodField()
    # slab = serializers.SerializerMethodField()
    event_name = serializers.SerializerMethodField()
    inventory_unit = serializers.SerializerMethodField()
    payment_status = serializers.SerializerMethodField()
    aging = serializers.SerializerMethodField()
    interest = serializers.SerializerMethodField()
    sv_status = serializers.SerializerMethodField()
    sv_status_list = serializers.SerializerMethodField()
    sv_datetime = serializers.SerializerMethodField()
    has_notes = serializers.SerializerMethodField()
    # reminder = serializers.SerializerMethodField()
    due_date = serializers.SerializerMethodField()
    payment_status_event = serializers.SerializerMethodField()
    payment_date_and_time = serializers.SerializerMethodField()
    due_date_color = serializers.SerializerMethodField()
    percentage_recieved = serializers.SerializerMethodField()
    current_status_value = serializers.SerializerMethodField()
    registration_status = serializers.SerializerMethodField()
    stamp_duty_status = serializers.SerializerMethodField()
    total_notifications = serializers.SerializerMethodField() 
    sent_reminder_colour = serializers.SerializerMethodField()
    tds_paid_date= serializers.SerializerMethodField()
    tds_paid_status = serializers.SerializerMethodField()

    class Meta:
        model = Lead
        fields = ['id','lead_name', 'phone_number','crm_executive','welcome_call_status','welcome_email_status','demand_letter_status','sent_reminder_colour','welcome_call_isimportant','welcome_email_isimportant', 'snagging_email_status','current_status_value', 'registration_status', 'stamp_duty_status','inventory_unit', 'aging','due_date', 'tds_paid_status','tds_paid_date', 'due_date_color','payment_date_and_time','payment_status','payment_status_event','percentage_recieved', 'has_notes', 'interest','event_name', 'total_notifications', 'sv_status','sv_status_list', 'sv_datetime']

    def get_lead_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"

    def get_phone_number(self, obj):
        return obj.primary_phone_no if obj.primary_phone_no else None
    
    def get_welcome_call_status(self, obj):
        updates_record, created = Updates.objects.get_or_create(lead=obj)

        if created:
            updates_record.save()

        return updates_record.welcome_call_status

    def get_welcome_email_status(self, obj):
        updates_record, created = Updates.objects.get_or_create(lead=obj)

        if created:
            updates_record.save()

        return updates_record.welcome_email_status
    
    def get_demand_letter_status(self, obj):
        updates_record, created = Updates.objects.get_or_create(lead=obj)

        if created:
            updates_record.save()

        return updates_record.demand_letter_status
    

    def get_sent_reminder_colour(self, obj):
        try:
            # Fetch the Updates object
            updates_data = Updates.objects.filter(
                lead=obj,  # Filter by the specific lead
                demand_letter_status='Sent'  # Ensure the demand letter status is 'Sent'
            ).select_related('slab').first()

            # Default color if no matching Updates record
            if not updates_data:
                return "White"

            # Fetch the slab's due date
            due_date = updates_data.slab.due_date if updates_data.slab else None
            if not due_date:
                return "White"

            # Fetch the paid status from InventoryCostSheet
            inventory_sheet = InventoryCostSheet.objects.filter(lead=obj).first()
            paid_status = inventory_sheet.paid if inventory_sheet else False

            # Check demand letter status and payment status
            if updates_data.demand_letter_status != 'Sent' or paid_status:
                return "White"

            # Calculate the time difference
            current_date = timezone.now()
            time_diff = current_date - due_date

            # Fetch the NotificationCount object
            notification_data = NotificationCount.objects.filter(lead=obj).first()
            last_notified = notification_data.last_notified if notification_data else None

            # Determine the color based on conditions
            if time_diff.days <= 7 and not paid_status:
                return "Green"
            elif time_diff.days > 7 and not paid_status:
                # Check if last_notified is within 7 days
                if last_notified:
                    days_since_last_notification = (current_date - last_notified).days
                    if days_since_last_notification <= 7:
                        return "Green"
                return "Red"
            elif paid_status:
                return "White"

        except Exception as e:
            # Log the error if needed and return a default
            print(f"Error occurred: {e}")
            return "White"

    
    def get_stamp_duty_status(self,obj):
        workflow = obj.workflow.get()
        stamp_duty_task = workflow.tasks.filter(name='Stamp Duty').first()
        print("stamp duty task",stamp_duty_task)
        if stamp_duty_task and stamp_duty_task.completed:
            return True
        else:
            return False
    
    def get_snagging_email_status(self, obj):
        updates_record, created = Updates.objects.get_or_create(lead=obj)

        if created:
            updates_record.save()

        return updates_record.snagging_email_status
    
    
    def get_total_notifications(self, obj):
        from django.db.models import Sum
        # Aggregate notification count for the lead
        total_count = NotificationCount.objects.filter(lead=obj).aggregate(
            total_count=Sum('count')
        )['total_count'] or 0
        return total_count

    def get_current_status_value(self,obj):
        lead_obj = obj
        if lead_obj:
            workflow = lead_obj.workflow.get()      
            welcome_call_task = workflow.tasks.filter(name='Welcome Call', completed=True).first()
            welcome_mail_task = workflow.tasks.filter(name='Welcome Mail', completed=True).first()           
            demand_letter_task = workflow.tasks.filter(name='Demand Letter', completed=True).order_by('-time').last()
            stamp_duty_task = workflow.tasks.filter(name='Stamp Duty', completed = True).first()
            registration_fee_task = workflow.tasks.filter(name='Registeration Fee',completed = True).first()
            print("welcome...........",welcome_call_task)
            print(welcome_mail_task)
            print(demand_letter_task)
            print(stamp_duty_task)
            print(registration_fee_task)
            # Determine the current status based on the sequence of tasks
            if registration_fee_task:
                return "Registration"
            elif stamp_duty_task:
                return "Stamp Duty"
            elif demand_letter_task:
                return "Demand Letter"
            elif welcome_mail_task:
                return "Welcome Mail"
            elif welcome_call_task:
                return "Welcome Call"     
        return None
    
    def get_payment_status_event(self,obj):
        from inventory.models import InventoryCostSheet

        inventory_sheet = InventoryCostSheet.objects.filter(lead=obj).first()
        # print("Inventory sheet",inventory_sheet)

        if inventory_sheet:
            return inventory_sheet.payment_status
        else:
            return None 
    
    def get_tds_paid_status(self,obj):
        from inventory.models import InventoryCostSheet

        inventory_sheet = InventoryCostSheet.objects.filter(lead=obj).first()
        # print("Inventory sheet",inventory_sheet)

        if inventory_sheet:
            return inventory_sheet.tds_paid
        else:
            return None 

    def get_tds_paid_date(self,obj):
        from inventory.models import InventoryCostSheet

        inventory_sheet = InventoryCostSheet.objects.filter(lead=obj).first()
        # print("Inventory sheet",inventory_sheet)

        if inventory_sheet:
            return inventory_sheet.tds_paid_date
        else:
            return None     

    def get_payment_date_and_time(self,obj):
        from inventory.models import InventoryCostSheet
        inventory_sheet = InventoryCostSheet.objects.filter(lead=obj).first()
    
        if inventory_sheet:
            return inventory_sheet.paid_date
        else:
            return None 

    def get_due_date(self,obj):
        print("inside due date")
        from inventory.models import InventoryCostSheet
        
        inventory_sheet = InventoryCostSheet.objects.filter(lead=obj).first()
        
        if inventory_sheet:
            event_name = inventory_sheet.event
            event_order = inventory_sheet.event_order
            print(event_name)
            print(event_order)

            due_date = inventory_sheet.due_date
            print(due_date)
            return due_date    
        else :
            return None
        
    
    def get_aging(self,obj):
        from inventory.models import InventoryCostSheet
        from django.utils.timezone import make_aware, make_naive, get_current_timezone, is_naive

        status = Updates.objects.filter(lead=obj).first()
        demand_letter_status = status.demand_letter_status
        print("demand letter status" , status.demand_letter_status)
        print("lead id",obj)
        inventory_sheet = InventoryCostSheet.objects.filter(lead=obj).first()
        print("inventory_sheet",inventory_sheet)
        current_date = datetime.now()
        print(current_date)
        if demand_letter_status == "Sent"  and inventory_sheet :
            due_date = inventory_sheet.due_date
            paid_status = inventory_sheet.paid
            print("due_date",due_date)
            print("paid_status",paid_status)
            if due_date is not None and paid_status == False:
                if is_naive(inventory_sheet.due_date):
                    inventory_sheet_due_date = make_aware(inventory_sheet.due_date, timezone=get_current_timezone())
                else:
                    inventory_sheet_due_date = inventory_sheet.due_date

                # Ensure current_date is timezone-aware
                if is_naive(current_date):
                    current_date_aware = make_aware(current_date, timezone=get_current_timezone())
                else:
                    current_date_aware = current_date

                diff_days = (current_date_aware - inventory_sheet_due_date ).days
                print("diff_days",diff_days)
            
                # Determine the aging based on the difference
                if diff_days > 60:
                    return ">60 Days"
                elif 30 < diff_days <= 60:
                    return ">30 Days"
                else:
                    return "<=30 Days"
            else :
                return None    
           
        return None 

    def get_due_date_color(self,obj):
        aging = self.get_aging(obj)
        # print("inside due date color",aging)
        # aging = ">60 Days"

        if aging == '>60 Days' or aging == '>30 Days':
            return True
        else:
            return False

    
    def get_interest(self, obj):
        from inventory.models import InventoryCostSheet
        from decimal import Decimal

        inventory_sheet = InventoryCostSheet.objects.filter(lead=obj).first()
       
        # if inventory_sheet:
        #     total_amount = inventory_sheet.total_amount

        aging = self.get_aging(obj)

        if aging == ">60 Days" and inventory_sheet:
            interest_amount = Decimal('0.1') * inventory_sheet.total_amount
            inventory_sheet.total_amount = inventory_sheet.total_amount + interest_amount
            inventory_sheet.save()
            return "10% interest after 60 days"
        elif aging == ">30 Days" and inventory_sheet:
            interest_amount = Decimal('0.05') * inventory_sheet.total_amount
            inventory_sheet.total_amount = inventory_sheet.total_amount + interest_amount
            inventory_sheet.save()
            return "5% interest after 30 days"
        else:
            return None
    
    def get_payment_status(self,obj):
        from inventory.models import InventoryCostSheet

        inventory_sheet = InventoryCostSheet.objects.filter(lead=obj).first()
        aging = self.get_aging(obj)
        if inventory_sheet:
           paid_status = inventory_sheet.paid
        else:
            paid_status = False   

        # Determine payment status based on aging and paid_status
        if aging == "<=30 Days" and not paid_status:
            return "raised"
        elif aging in [">30 Days", ">60 Days"] and not paid_status:
            return "due"
        elif paid_status and aging:
            return "recieved"
        elif aging is None:
            return "raised"

    def get_percentage_recieved (self,obj):
        from inventory.models import InventoryCostSheet
        from django.db.models import Sum

        # Get the next incomplete event
        next_event = InventoryCostSheet.objects.filter(lead=obj, completed=False).order_by('event_order').first()
        
        if next_event:
            # Sum up payment_in_percent for all completed events before the current event
            total_percentage_received = InventoryCostSheet.objects.filter(
                lead=obj,
                completed=True,
                event_order__lt=next_event.event_order  # Only include events before the current one
            ).aggregate(total=Sum('payment_in_percentage'))['total'] or 0  # Default to 0 if no completed events

            return total_percentage_received

    
    def get_inventory_unit(self,obj):
        from inventory.models import ProjectInventory

        inventory = ProjectInventory.objects.filter(lead=obj).first()
        # print("inventory",inventory)

        if inventory :
            flat_number = inventory.flat_no
            tower = inventory.tower.name
            return f"{tower}-{flat_number}"
        else :
            return None
    
    def get_registration_status(self,obj):
        workflow = obj.workflow.get()
        registration_fee_task = workflow.tasks.filter(name='Registration Fees').first()
        print("registration fee task",registration_fee_task)
        if registration_fee_task and registration_fee_task.completed:
            return True
        else:
            return False

    
    def get_crm_executive(self, obj):
        user_ids = obj.followers 

        crm_executive = Users.objects.filter(id__in=user_ids, groups__name="CRM_EXECUTIVE").first()

        return UserDataSerializer(crm_executive).data if crm_executive else None

    def get_has_notes(self, obj):
        return obj.notes_set.exists()  

    def get_welcome_call_isimportant(self, obj):
        try:
            workflow = obj.workflow.get()
            welcome_call_task = workflow.tasks.filter(name='Welcome Call').first()
            # print("welcome_call_task: ",welcome_call_task)
            if welcome_call_task and welcome_call_task.started_at:
                if welcome_call_task.started_at + timedelta(hours=24) <= timezone.now(): 
                    return True
                else:
                    return False
            else:
                 return False    
        except Workflow.DoesNotExist:
            return False  
    
    def get_welcome_email_isimportant(self, obj):
        try:
            workflow = obj.workflow.get()
            welcome_mail_task = workflow.tasks.filter(name='Welcome Mail').first()
            # print("welcome_mail_task",welcome_mail_task)
            if welcome_mail_task and welcome_mail_task.started_at:
                if welcome_mail_task.started_at + timedelta(hours=48) <= timezone.now(): 
                    return True
                else:
                    return False
            else:
                return False    
        except Workflow.DoesNotExist:
            return False

    # def get_slab(self, obj):
    #     from inventory.serializers import ProjectCostSheetSerializer

    #     updates_record, created = Updates.objects.get_or_create(lead=obj)

    #     if created:
    #         updates_record.save()

    #     if updates_record.slab:
    #         return ProjectCostSheetSerializer(updates_record.slab).data
    #     else:
    #         return None 
        
    def get_event_name(self, obj):
        from inventory.models import InventoryCostSheet
        
        next_event = InventoryCostSheet.objects.filter(lead=obj,completed=False).order_by('event_order').first()
        print("inventory_sheeting",next_event)
        if next_event:
        # Return the event name if an incomplete event is found
            return next_event.event
        else:
            # If no incomplete event is found, return a message or None
            return "All events completed" 

        
    # def get_sv_status_list(self, obj):
    #     SITEVISIT_CHOICES = [
    #         ("Site Visit Done", "Site Visit Done"), 
    #         ("Missed", "Missed"),
    #         ("Scheduled", "Scheduled"),
    #     ]

    #     SiteVisit_choices = dict(SITEVISIT_CHOICES)
    #     sitevisit_picked = obj.sv_status 
    #     print(sitevisit_picked)
    #     sv_status_list = [
    #         {"status": status, "selected": status == sitevisit_picked}
    #         for status in SiteVisit_choices.keys()
    #     ]
    #     return sv_status_list

    def get_sv_status(self, obj):
        # Fetch the sv_status from the context data
        lead_data = next((data for data in self.context.get('leads_data', []) if data['lead'] == obj), None)
        return lead_data.get('sv_status') if lead_data else None 

    def get_sv_datetime(self, obj):
        # Fetch the sv_datetime from the context data
        lead_data = next((data for data in self.context.get('leads_data', []) if data['lead'] == obj), None)
        return lead_data.get('sv_datetime') if lead_data else None  
    
    def get_has_notes(self, obj):
        # Access has_notes field from lead data or directly from the object
        lead_data = next((data for data in self.context.get('leads_data', []) if data['lead'] == obj), None)
        return lead_data.get('has_notes') if lead_data else False

    def get_sv_status_list(self, obj):
        SITEVISIT_CHOICES = [
            ("Site Visit Done", "Site Visit Done"),
            ("Missed", "Missed"),
            ("Scheduled", "Scheduled"),
        ]

        SiteVisit_choices = dict(SITEVISIT_CHOICES)
        sv_status = self.get_sv_status(obj)  # Use the custom method to fetch sv_status

        sv_status_list = [
            {"status": status, "selected": status == sv_status}
            for status in SiteVisit_choices.keys()
        ]
        return sv_status_list
    
class DocumentSectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentSection
        fields = '__all__'

class PostSalesDocumentSectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PostSalesDocumentSection
        fields = '__all__'


class LeadRefundSerializer(serializers.ModelSerializer):
    lead_name = serializers.SerializerMethodField()
    phone_number = serializers.SerializerMethodField()
    crm_executive = serializers.SerializerMethodField()
    # slab = serializers.SerializerMethodField()
    # event_name = serializers.SerializerMethodField()
    inventory_unit = serializers.SerializerMethodField()
    refund_amount = serializers.SerializerMethodField()
    refund_initiated_on = serializers.SerializerMethodField()
    refund_status = serializers.SerializerMethodField()
    payment_date_and_time = serializers.SerializerMethodField()
    refund_invoice_overview = serializers.SerializerMethodField()
    payment_id = serializers.SerializerMethodField()
   

    class Meta:
        model = Lead
        fields = ['id','lead_name', 'phone_number','payment_id','crm_executive','inventory_unit', 'refund_amount','refund_initiated_on','refund_status','refund_invoice_overview','payment_date_and_time']

    def get_lead_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"

    def get_phone_number(self, obj):
        return obj.primary_phone_no if obj.primary_phone_no else None
    
    def get_payment_id(self,obj):
        payment = Payment.objects.filter(lead=obj).first()
        if payment:
            return payment.id
        else:
            None
    
      
    def get_inventory_unit(self,obj):
        from inventory.models import ProjectInventory

        inventory = ProjectInventory.objects.filter(lead=obj).first()
        # print("inventory",inventory)

        if inventory :
            flat_number = inventory.flat_no
            tower = inventory.tower.name
            return f"{tower}-{flat_number}"
        else :
            return None
    
     
    def get_crm_executive(self, obj):
        user_ids = obj.followers 

        crm_executive = Users.objects.filter(id__in=user_ids, groups__name="CRM_EXECUTIVE").first()

        return UserDataSerializer(crm_executive).data if crm_executive else None

    def get_refund_amount(self,obj):
        inventory_owner = PropertyOwner.objects.filter(lead=obj).first()
        if inventory_owner:
            return inventory_owner.refund_amount

    def get_refund_initiated_on(self,obj):
        inventory_owner = PropertyOwner.objects.filter(lead=obj).first()
        if inventory_owner and inventory_owner.booking_cancelled_at:
            # Extract the date part from the DateTimeField
            return inventory_owner.booking_cancelled_at.date()
        return None
    
    def get_refund_status(self,obj):
        inventory_owner = PropertyOwner.objects.filter(lead=obj).first()
        if inventory_owner :
            if inventory_owner.refund_status == True:
                return "Refunded"
            else:
                return "Pending"
         
    def get_payment_date_and_time(self,obj):
        refund_status = self.get_refund_status(obj)
        if refund_status == "Refunded":
            latest_entry = CustomerPayment.objects.filter(lead=obj , payment_type="Refund").last()
            if latest_entry:
              return f"{latest_entry.date} {latest_entry.time}" 
            else:
                return None

    
    def get_refund_invoice_overview(self,obj):
        from accounts.models import Payment

        refund_data = Payment.objects.filter(lead=obj).first()  
        if refund_data:
            refund_invoice = refund_data.invoice_overview_list
            return refund_invoice
        else:
            return None              


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

class LeadHistorySerializer(HistorySerializer):
    class Meta(HistorySerializer.Meta):
        model = Lead
        fields = HistorySerializer.Meta.fields + ['lead_status','converted_on','followers','first_name','last_name','primary_phone_no','secondary_phone_no','primary_email','secondary_email','gender','address','city','state','pincode','occupation','source','no_of_family','remarks' ]
        #fields = '__all__'


class LeadRequirementHistorySerializer(HistorySerializer):
    class Meta(HistorySerializer.Meta):
        model = LeadRequirements
        fields = HistorySerializer.Meta.fields + ['purpose','budget_min','budget_max','funding','area','configuration']
        #fields = '__all__'


class SiteVisitHistorySerializer(HistorySerializer):
    site_visit_status = serializers.CharField(source='instance.site_visit_status') 
    class Meta(HistorySerializer.Meta):
        model = SiteVisit
        fields = HistorySerializer.Meta.fields + ['site_visit_status', 'site_visit_type','snagging_status','visit_date', 'timeslot','closing_manager','lead', 'snagging_issues']

class UpdatesHistorySerializer(HistorySerializer):
    class Meta(HistorySerializer.Meta):
        model = Updates
        fields = HistorySerializer.Meta.fields + ['welcome_call_status','welcome_email_status','demand_letter_status']

class BookingFormHistorySerializer(HistorySerializer):
    class Meta(HistorySerializer.Meta):
        model = BookingForm
        fields = HistorySerializer.Meta.fields 

class NotesHistorySerializer(HistorySerializer):
    notes = serializers.CharField(source='instance.notes')  
    #created_by = serializers.CharField(source='instance.created_by')  
    created_by = serializers.SerializerMethodField()
    class Meta(HistorySerializer.Meta):
        model = Notes
        fields = HistorySerializer.Meta.fields + ['notes', 'created_by']
        
    def get_created_by(self,obj):
        return obj.created_by.name if obj.created_by else None  

class CustomerPaymentHistorySerializer(HistorySerializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, source='instance.amount')
    event_name = serializers.CharField(source='instance.event_name', allow_null=True)
    payment_mode = serializers.CharField(source='instance.payment_mode')
    transaction_id = serializers.CharField(source='instance.transaction_id')
    payment_type = serializers.CharField(source='instance.payment_type')
    date = serializers.DateField(source='instance.date')
    time = serializers.TimeField(source='instance.time')
    created_by = serializers.SerializerMethodField()
    message = serializers.SerializerMethodField()

    class Meta(HistorySerializer.Meta):
        model = CustomerPayment
        fields = HistorySerializer.Meta.fields + [
            'amount', 
            'event_name', 
            'payment_mode', 
            'transaction_id', 
            'payment_type', 
            'date', 
            'time', 
            'created_by', 
            'message'
        ]

    def get_created_by(self, obj):
        # Assuming history_user stores the creator of the record
        return obj.history_user.name if obj.history_user else 'Unknown User'

    def get_message(self, obj):
        created_by = self.get_created_by(obj)
        if obj.history_type == '+':  # '+' indicates creation
            if obj.instance.payment_type == "Refund":
                return f"Refund Amount recorded by Accounts Head."
        # Default message if other conditions are not met
        return f"CustomerPayment {obj.get_history_type_display()} by {created_by}."

class PropertyOwnerHistorySerializer(HistorySerializer):
    booking_status = serializers.CharField(source='instance.booking_status')
    refund_amount = serializers.DecimalField(max_digits=20, decimal_places=2, source='instance.refund_amount')
    refund_status = serializers.BooleanField(source='instance.refund_status')
    booking_cancelled_at = serializers.DateTimeField(source='instance.booking_cancelled_at', allow_null=True)
    created_by = serializers.SerializerMethodField()
    message = serializers.SerializerMethodField()

    class Meta(HistorySerializer.Meta):
        model = PropertyOwner
        fields = HistorySerializer.Meta.fields + [
            'booking_status',
            'refund_amount',
            'refund_status',
            'booking_cancelled_at',
            'created_by',
            'message'
        ]

    def get_created_by(self, obj):
        # Assuming `history_user` stores the user who made the change
        return obj.history_user.name if obj.history_user else 'Unknown User'

    def get_message(self, obj):
        created_by = self.get_created_by(obj)
        if obj.history_type == '~' and obj.instance.booking_status == 'cancel':
            # '~' indicates an update, specifically checking if booking status is 'cancel'
            return f"Refund amount created by {created_by} and sent to Accounts Head."
        return f"PropertyOwner {obj.get_history_type_display()} by {created_by}."


class NotificationCountSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationCount
        fields = ['lead', 'user', 'count', 'last_notified']
