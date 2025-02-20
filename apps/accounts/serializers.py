# from apps.marketing.serializers import AgencyDetailSerializer
from .models import *
from rest_framework import serializers
from marketing.models import Vendor,Campaign
from auth.models import Users
from river.models import Workflow
from river.models import *
from collections import Counter
from lead.serializers import ChannelPartnerId, ChannelPartnerSerializer

class AgencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Agency
        fields = '__all__'

class AgencyTypePaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgencyType
        fields = '__all__'

class AgencyPaymentSerializer(serializers.ModelSerializer):
    agency_type = AgencyTypePaymentSerializer(many =True, read_only=True)
    class Meta:
        model = Agency
        fields = ['id','agency_name', 'agency_type','vendors_full_name','gstin_number','gst_certificate','pan_card','pan_details','aadhaar_details','bank_name', 'account_holder_name', 'brand_name', 'phone_number' ,'account_number','ifsc_code']

class AgencyTypeAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgencyType
        fields = ['id','name']

class ChannelPartnerPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChannelPartner
        fields = ['id','full_name','firm']

class PaymentReterivalSerializer(serializers.ModelSerializer):
    channel_partner = ChannelPartnerPaymentSerializer() 
    agency_name = AgencyPaymentSerializer(many=True)
    agency_type = AgencyTypeAccountSerializer(many=True)
    attached_documents = serializers.SerializerMethodField()
    invoice_copy = serializers.SerializerMethodField()
    
    class Meta:
        model = Payment
        fields = '__all__'
        extra_kwargs = {
            'amount': {'required': True},
            # 'campaign': {'required': True},
            # 'vendor': {'required': True},
            'due_date': {'required': True},
            'attached_documents': {'required': True},
            #'invoice_copy' :{'required':True}
        }

    def get_attached_documents(self, obj):
        attached_docs = AttachedPaymentDoc.objects.filter(payment=obj)
        return [self.context['request'].build_absolute_uri(doc.attached_doc.url) for doc in attached_docs]

    def get_invoice_copy(self, obj):
        invoices = InvoicePaymentDoc.objects.filter(payment=obj)
        return [self.context['request'].build_absolute_uri(invoice.invoice_doc.url) for invoice in invoices]    


class PaymentSerializer(serializers.ModelSerializer):
    # channel_partner = serializers.PrimaryKeyRelatedField(queryset=ChannelPartner.objects.all())
    # agencies = AgencySerializer(many=True, read_only=True)
    # agency_types = AgencyTypePaymentSerializer(many=True, read_only=True)

    attached_documents = serializers.ListField(
        child=serializers.FileField(max_length=100000, allow_empty_file=False, use_url=False),
        write_only=True,
        required=False
    )
    invoice_copy = serializers.ListField(
        child=serializers.FileField(max_length=100000, allow_empty_file=False, use_url=False),
        write_only=True,
        required=False
    )

    class Meta:
        model = Payment
        fields = '__all__'
        extra_kwargs = {
            'amount': {'required': True},
            # 'campaign': {'required': True},
            # 'vendor': {'required': True},
            'due_date': {'required': True},
            'attached_documents': {'required': True},
            'invoice_copy' :{'required':True}
        }

    def create(self, validated_data):
        
        from workflow.models import TaskDefinition
        attached_docs = validated_data.pop('attached_documents', [])
        invoice_docs = validated_data.pop('invoice_copy', [])

        print("attached_doc",attached_docs)
        print("invoice_docs",invoice_docs)
        
        AE_slug = VP_slug = P1_slug = P2_slug = P3_slug = AH_slug = ''

        payment_definitions = TaskDefinition.objects.filter(workflow__name='Accounts Template')
        print('payment_definitions:', payment_definitions)

        for payment_definition in payment_definitions:
            print('payment_definition:', payment_definition)
            if payment_definition.name == "Payment Approval AE":
                ae_user = Users.objects.filter(groups__name="ACCOUNTS_EXECUTIVE").first()
                AE_slug = ae_user.slug
            if payment_definition.name == "Payment Approval VP":
                vp_user = Users.objects.filter(groups__name="VICE_PRESIDENT").first()
                VP_slug = vp_user.slug
            if payment_definition.name == "Payment Approval P1":
                users = payment_definition.users.all() 
                P1_slug = users[0].slug
            if payment_definition.name == "Payment Approval P2":
                users = payment_definition.users.all() 
                P2_slug = users[0].slug
            if payment_definition.name == "Payment Approval P3":
                users = payment_definition.users.all() 
                P3_slug = users[0].slug
            if payment_definition.name == "Payment Approval AH":
                ah_user = Users.objects.filter(groups__name="ACCOUNTS_HEAD").first()
                AH_slug = ah_user.slug

        default_invoice_overview_list = [
            {"role": "AE", "status": "Approval Pending", "slug": AE_slug},        
            {"role": "VP", "status": "Approval Pending", "slug": VP_slug},
            {"role": "P1", "status": "Approval Pending", "slug": P1_slug},
            {"role": "P2", "status": "Approval Pending", "slug": P2_slug},
            {"role": "P3", "status": "Approval Pending", "slug": P3_slug},
            {"role": "AH", "status": "Approval Pending", "slug": AH_slug}
        ]
        
        if 'invoice_overview_list' not in validated_data:
            validated_data['invoice_overview_list'] = default_invoice_overview_list
        payment = super().create(validated_data)

        for attached_doc in attached_docs:
            AttachedPaymentDoc.objects.create(payment=payment, attached_doc=attached_doc)
            print("attached doc added")
        
        # Handle InvoicePaymentDoc creation
        for invoice_doc in invoice_docs:
            InvoicePaymentDoc.objects.create(payment=payment, invoice_doc=invoice_doc)
            print("invoice doc added")
        
        return payment


class PaymentDirectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = '__all__'
        extra_kwargs = {
            'amount': {'required': True},
            'campaign': {'required': True},
            'paid_date': {'required': True},
        }
class PaymentbyIdSerializer(serializers.ModelSerializer):
    vendor = serializers.SerializerMethodField()
    channel_partner = serializers.SerializerMethodField()
    project = serializers.SerializerMethodField()
    apartment_no = serializers.SerializerMethodField()
    campaign = serializers.SerializerMethodField()
    task_id = serializers.SerializerMethodField()
    refund_task_id = serializers.SerializerMethodField()
    approval_status = serializers.SerializerMethodField()
    # invoice_overview_list = serializers.SerializerMethodField()
    due_date = serializers.SerializerMethodField()  
    #channel_partner = ChannelPartnerPaymentSerializer() 
    agency_name = AgencyPaymentSerializer(many=True)
    agency_type = AgencyTypeAccountSerializer(many=True)
    attached_documents = serializers.SerializerMethodField()
    invoice_copy = serializers.SerializerMethodField()
    refund_invoice_overview = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = '__all__'

    def get_vendor(self, obj):
        if obj.vendor:
            return VendorSerializer(obj.vendor).data
        else:
            return None 

    def get_due_date(self, obj):
        if obj.due_date:
           return obj.due_date.strftime('%d-%m-%Y') 
        else :
            None 

    def get_campaign(self, obj):
        if obj.campaign:
            return CampaignSerializer(obj.campaign).data
        else:
            return None

    def get_channel_partner(self, obj):
        if obj.channel_partner:
            return ChannelPartnerId(obj.channel_partner).data
        else:
            return None 

    def get_attached_documents(self, obj):
        attached_docs = AttachedPaymentDoc.objects.filter(payment=obj)
        return [self.context['request'].build_absolute_uri(doc.attached_doc.url) for doc in attached_docs]

    def get_invoice_copy(self, obj):
        invoices = InvoicePaymentDoc.objects.filter(payment=obj)
        return [self.context['request'].build_absolute_uri(invoice.invoice_doc.url) for invoice in invoices]     
        
    def get_project(self, obj):
        from inventory.serializers import ProjectDetailSerializer

        if obj.project:
            return ProjectDetailSerializer(obj.project).data
        else:
            return None 
        
    def get_apartment_no(self, obj):
        from inventory.serializers import ProjectInventorySerializer

        if obj.apartment_no:
            return ProjectInventorySerializer(obj.apartment_no).data
        else:
            return None 

    def get_refund_task_id(self, obj):

        first_stage = obj.payment_workflow.get().stages.first()
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
       
    def get_task_id(self, obj):

        first_stage = obj.payment_workflow.get().stages.first()
        # first_task = first_stage.tasks.filter().order_by('order').first()
        ae_task = first_stage.tasks.filter(name='Payment Approval AE').first()
        vp_task = first_stage.tasks.filter(name='Payment Approval VP').first()
        p1_task = first_stage.tasks.filter(name='Payment Approval P1').first()
        p2_task = first_stage.tasks.filter(name='Payment Approval P2').first()
        p3_task = first_stage.tasks.filter(name='Payment Approval P3').first()
        ah_task = first_stage.tasks.filter(name='Payment Approval AH').first()
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
        
    def get_refund_invoice_overview(self,obj):
        from accounts.models import Payment

        refund_data = Payment.objects.filter(lead=obj.lead).first()  
        if refund_data:
            refund_invoice = refund_data.invoice_overview_list
            return refund_invoice
        else:
            return None         


    def get_approval_status(self, obj):
        print(self.context['request'].user)
        current_user = self.context['request'].user
        if current_user.groups.filter(name="ACCOUNTS_HEAD").exists():
            STATUS_CHOICES = [
                    ('Approval Pending', 'Approval Pending'),
                    ('Reject', 'Reject'),
                    ('On Hold', 'On Hold'),
                    ('Payment Done', 'Payment Done'),
                ]
                
            approval_status_choices = dict(STATUS_CHOICES)
            approval_status_picked = obj.status
            print(self.context['request'].user)
            print(obj.status)
            approval_status_list = [
                {"status": status, "selected": status == approval_status_picked}
                if status != 'Payment Done'
                else {"status": "Record Payment", "selected": status == approval_status_picked}
                for status in approval_status_choices.keys()
            ]
            return approval_status_list  
        else:
            STATUS_CHOICES = [
                    ('Approval Pending', 'Approval Pending'),
                    ('Reject', 'Reject'),
                    ('On Hold', 'On Hold'),
                    ('Payment Done', 'Payment Done'),
                ]
                
            approval_status_choices = dict(STATUS_CHOICES)
            approval_status_picked = obj.status
            print(self.context['request'].user)
            print(obj.status)
            approval_status_list = [
                {"status": "Approve" if status == 'Payment Done' else status, "selected": status == approval_status_picked}
                for status in approval_status_choices.keys()
            ]
            return approval_status_list      

    # def get_invoice_overview_list(self, obj):
        
    #     vp_user = Users.objects.filter(groups__name="VICE_PRESIDENT").first()
    #     promoter_users = Users.objects.filter(groups__name="PROMOTER").order_by('id')[:3]
    #     ah_user = Users.objects.filter(groups__name="ACCOUNTS_HEAD").first()

    #     first_stage = obj.payment_workflow.get().stages.first()
    #     print("first_Stage: ", first_stage)
    #     all_tasks = first_stage.tasks.all().order_by('order')
    #     print("all_tasks: ", all_tasks)
    #     ids = all_tasks.values_list('id', flat=True)
    #     print("ids: ", ids)
    #     # vp_task = obj.payment_workflow.get().stages.first().tasks.filter(name='Payment Approval VP')
    #     # task_ids = obj.payment_workflow.get()

    #     user_dict = {
    #         'VP': vp_user.id if vp_user else None,
    #         'P1': promoter_users[0].id if len(promoter_users) > 0 else None,
    #         'P2': promoter_users[1].id if len(promoter_users) > 1 else None,
    #         'P3': promoter_users[2].id if len(promoter_users) > 2 else None,
    #         'AH': ah_user.id if ah_user else None,
    #     }
    #     #print("user_dict: ",user_dict)
    #     query = '''
    #         SELECT * FROM public.river_historicaltransitionapproval
    #         WHERE object_id = %s
    #         ORDER BY history_id ASC;
    #     '''

    #     payment_records = obj.history.all()
    #     payment_history_data = PaymentHistorySerializer(payment_records, many=True).data  
    #     first_task_id = obj.payment_workflow.get().stages.first().tasks.filter().order_by('order').first().id
    #     result_dict = {
    #         'VP': 'Approval Pending',
    #         'P1': 'Approval Pending',
    #         'P2': 'Approval Pending',
    #         'P3': 'Approval Pending',
    #         'AH': 'Approval Pending',
    #     }
    #     time_dict = {
    #         'VP': '',
    #         'P1': '',
    #         'P2': '',
    #         'P3': '',
    #         'AH': '',  
    #     }
    #     for id in ids:
    #         history_records = TransitionApproval.objects.raw(query, [str(id)])
    #         if history_records:
    #             for record in history_records:
    #                 #print("record : ", record, record.status,record.object_id, record.id, record.history_id) 
    #                 if record.status == 'cancelled':
    #                     # print("record.status: ", record.status, record.object_id, record.history_id)
    #                     approver_id = record.transactioner_id
                        
    #                     for key, value in user_dict.items():
    #                         if value == approver_id:
    #                             result_dict[key] = 'Reject'
    #                             time_dict[key] = record.history_date
    #     # print("time dict: ", time_dict)
    #     for record in payment_history_data:
    #         if record['status'] == 'On Hold' and obj.status == 'On Hold':
    #             history_user = record.get("history_user_id") 
    #             for key, value in user_dict.items():
    #                 if value == history_user:
    #                     result_dict[key] = 'On Hold'  

    #     first_stage = obj.payment_workflow.get().stages.first()
    #     vp_task = first_stage.tasks.filter(completed=True, status=4, name= "Payment Approval VP").order_by('-order').first()
    #     if vp_task is not None:
    #         result_dict['VP'] = 'Approve'   
    #     p1_task = first_stage.tasks.filter(completed=True, status=4, name= "Payment Approval P1").order_by('-order').first()
    #     if p1_task is not None:
    #         result_dict['P1'] = 'Approve' 
    #     p2_task = first_stage.tasks.filter(completed=True, status=4, name= "Payment Approval P2").order_by('-order').first()
    #     if p2_task is not None:
    #         result_dict['P2'] = 'Approve' 
    #     p3_task = first_stage.tasks.filter(completed=True, status=4, name= "Payment Approval P3").order_by('-order').first()
    #     if p3_task is not None:
    #         result_dict['P3'] = 'Approve' 
    #     vh_task = first_stage.tasks.filter(completed=True, status=4, name= "Payment Approval AH").order_by('-order').first()
    #     if vh_task is not None:
    #         result_dict['AH'] = 'Approve' 
    #     if 'Approve'  in result_dict.values() or obj.status == 'Approval Pending':
    #         for key in result_dict:
    #             if result_dict[key] == 'Reject':
    #                 result_dict[key] = 'Approval Pending'  

    #     reject_count = Counter(result_dict.values())['Reject']

    #     if reject_count > 1:
    #         latest_reject_timestamp = None
    #         latest_reject_role = None
            
    #         for role, status in result_dict.items():
    #             if status == 'Reject' and time_dict.get(role) and (not latest_reject_timestamp or time_dict[role] > latest_reject_timestamp):
    #                 latest_reject_timestamp = time_dict[role]
    #                 latest_reject_role = role
            
    #         for role, status in result_dict.items():
    #             if status == 'Reject' and role != latest_reject_role:
    #                 result_dict[role] = 'Approval Pending'

    #     converted_list = []
    #     print("data: ", result_dict)
    #     for role, status in result_dict.items():
    #         converted_list.append({"role": role, "status": status})                        
    #     return converted_list

class VendorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = ['id','name']

class CampaignSerializer(serializers.ModelSerializer):
    class Meta:
        model = Campaign
        fields = ['id','campaign_name']

class MarketingPaymentSerializer(serializers.ModelSerializer):
    #request_id = serializers.SerializerMethodField()
    vendor_data = serializers.SerializerMethodField()
    campaign_data = serializers.SerializerMethodField()
    # invoice_overview_list2 = serializers.SerializerMethodField()
    is_notes = serializers.SerializerMethodField()
    due_date = serializers.SerializerMethodField()
    channel_partner = ChannelPartnerPaymentSerializer() 
    agency_name = AgencyPaymentSerializer(many=True)
    agency_type = AgencyTypeAccountSerializer(many=True)
    attached_documents = serializers.SerializerMethodField()
    invoice_copy = serializers.SerializerMethodField()
    class Meta:
        model = Payment
        fields = ['id', 'vendor_data','agency_type', 'agency_name','channel_partner','campaign_data', 'customer_name' , 'payment_type','request_type','amount','denied_reason','created_on', 'due_date','attached_documents','invoice_copy' ,'source_id','paid_date','budget','amount_available', 'status','invoice_overview','invoice_overview_list', 'is_notes','invoice_copy','attached_documents']  

    # def get_request_id(self, obj):
    #     return obj.id

    def get_due_date(self, obj):
        return obj.due_date.strftime('%d-%m-%Y')
    
    def get_vendor_data(self, obj):
        if obj.vendor:
            return VendorSerializer(obj.vendor).data
        else:
            return None 
        
    def get_campaign_data(self, obj):
        if obj.campaign:
            return CampaignSerializer(obj.campaign).data
        else:
            return None 

    def get_is_notes(self, obj):
        is_notes = Notes.objects.filter(payment=obj).exists()
        return is_notes
    
   
    def get_attached_documents(self, obj):
        request = self.context.get('request')
        if request is None:
           return []
        attached_docs = AttachedPaymentDoc.objects.filter(payment=obj)
        return [request.build_absolute_uri(doc.attached_doc.url) for doc in attached_docs]

    def get_invoice_copy(self, obj):
        request = self.context.get('request')
        if request is None:
           return []
        invoices = InvoicePaymentDoc.objects.filter(payment=obj)
        return [request.build_absolute_uri(invoice.invoice_doc.url) for invoice in invoices]  
    
class AccountsPaymentSerializer(serializers.ModelSerializer):
    #request_id = serializers.SerializerMethodField()
    vendor_data = serializers.SerializerMethodField()
    campaign_data = serializers.SerializerMethodField()
    # invoice_overview_list2 = serializers.SerializerMethodField()
    is_notes = serializers.SerializerMethodField()
    due_date = serializers.SerializerMethodField()
    channel_partner_data = serializers.SerializerMethodField()
    #channel_partner = ChannelPartnerPaymentSerializer() 
    agency_name = AgencyPaymentSerializer(many=True)
    agency_type = AgencyTypeAccountSerializer(many=True)
    attached_documents = serializers.SerializerMethodField()
    invoice_copy = serializers.SerializerMethodField()
    paid_date = serializers.SerializerMethodField()
    class Meta:
        model = Payment
        fields = ['id', 'vendor_data', 'agency_name','agency_type', 'campaign_data', 'customer_name','source_id','budget','amount_available','channel_partner_data','payment_type', 'attached_documents','invoice_copy','request_type','amount','denied_reason','created_on', 'due_date' ,'paid_date', 'transaction_id', 'payment_mode','status','invoice_overview','invoice_overview_list', 'is_notes', 'payment_to']  

    # def get_request_id(self, obj):
    #     return obj.id

    def get_due_date(self, obj):
        return obj.due_date.strftime('%d-%m-%Y') if obj.due_date else None
    
    def get_paid_date(self, obj):
        return obj.paid_date.strftime('%d-%m-%Y') if obj.paid_date else None
    
    def get_vendor_data(self, obj):
        if obj.vendor:
            return VendorSerializer(obj.vendor).data
        else:
            return None 
        
    def get_channel_partner_data(self, obj):
        if obj.channel_partner:
            return ChannelPartnerId(obj.channel_partner).data
        else:
            return None 
        
    def get_campaign_data(self, obj):
        if obj.campaign:
            return CampaignSerializer(obj.campaign).data
        else:
            return None 

    def get_is_notes(self, obj):
        is_notes = Notes.objects.filter(payment=obj).exists()
        return is_notes


    def get_attached_documents(self, obj):
        request = self.context.get('request')
        if request is None:
           return []
        attached_docs = AttachedPaymentDoc.objects.filter(payment=obj)
        return [request.build_absolute_uri(doc.attached_doc.url) for doc in attached_docs]

    def get_invoice_copy(self, obj):
        request = self.context.get('request')
        if request is None:
           return []
        invoices = InvoicePaymentDoc.objects.filter(payment=obj)
        return [request.build_absolute_uri(invoice.invoice_doc.url) for invoice in invoices]    
    
class SalesPaymentSerializer(serializers.ModelSerializer):
    #request_id = serializers.SerializerMethodField()
    channel_partner_data = serializers.SerializerMethodField()
    firm_name = serializers.SerializerMethodField()
    # invoice_overview_list2 = serializers.SerializerMethodField()
    is_notes = serializers.SerializerMethodField()
    due_date = serializers.SerializerMethodField()
    paid_date = serializers.SerializerMethodField()
    #channel_partner = ChannelPartnerPaymentSerializer() 
    agency_name = AgencyPaymentSerializer(many=True)
    agency_type = AgencyTypeAccountSerializer(many=True)
    attached_documents = serializers.SerializerMethodField()
    invoice_copy = serializers.SerializerMethodField()
    class Meta:
        model = Payment
        fields = ['id', 'channel_partner_data', 'agency_name','agency_type' ,'customer_name' , 'firm_name', 'budget','amount_available','source_id', 'request_type','attached_documents','invoice_copy','amount','denied_reason','created_on', 'due_date' ,'paid_date', 'status','invoice_overview','invoice_overview_list', 'is_notes',]  

    # def get_request_id(self, obj):
    #     return obj.id

    def get_due_date(self, obj):
        return obj.due_date.strftime('%d-%m-%Y')
    
    def get_paid_date(self, obj):
        return obj.paid_date.strftime('%d-%m-%Y') if obj.paid_date else None
    
    def get_channel_partner_data(self, obj):
        if obj.channel_partner:
            return ChannelPartnerId(obj.channel_partner).data
        else:
            return None 
        
    def get_firm_name(self, obj):
        if obj.channel_partner:
            return obj.channel_partner.firm if obj.channel_partner.firm else ""
        else:
            return None 

    def get_is_notes(self, obj):
        is_notes = Notes.objects.filter(payment=obj).exists()
        return is_notes
    
    def get_attached_documents(self, obj):
        request = self.context.get('request')
        if request is None:
           return []
        attached_docs = AttachedPaymentDoc.objects.filter(payment=obj)
        return [request.build_absolute_uri(doc.attached_doc.url) for doc in attached_docs]

    def get_invoice_copy(self, obj):
        request = self.context.get('request')
        if request is None:
           return []
        invoices = InvoicePaymentDoc.objects.filter(payment=obj)
        return [request.build_absolute_uri(invoice.invoice_doc.url) for invoice in invoices]  
    
    # def get_invoice_overview_list2(self, obj):
        
    #     vp_user = Users.objects.filter(groups__name="VICE_PRESIDENT").first()
    #     promoter_users = Users.objects.filter(groups__name="PROMOTER").order_by('id')[:3]
    #     ah_user = Users.objects.filter(groups__name="ACCOUNTS_HEAD").first()

    #     first_stage = obj.payment_workflow.get().stages.first()
    #     print("first_Stage: ", first_stage)
    #     all_tasks = first_stage.tasks.all().order_by('order')
    #     print("all_tasks: ", all_tasks)
    #     ids = all_tasks.values_list('id', flat=True)
    #     print("ids: ", ids)
    #     # vp_task = obj.payment_workflow.get().stages.first().tasks.filter(name='Payment Approval VP')
    #     # task_ids = obj.payment_workflow.get()

    #     user_dict = {
    #         'VP': vp_user.id if vp_user else None,
    #         'P1': promoter_users[0].id if len(promoter_users) > 0 else None,
    #         'P2': promoter_users[1].id if len(promoter_users) > 1 else None,
    #         'P3': promoter_users[2].id if len(promoter_users) > 2 else None,
    #         'AH': ah_user.id if ah_user else None,
    #     }
    #     #print("user_dict: ",user_dict)
    #     # query = '''
    #     #     SELECT * FROM public.river_historicaltransitionapproval
    #     #     WHERE object_id = %s
    #     #     ORDER BY history_id ASC;
    #     # '''
    #     query = '''
    #         SELECT * FROM public.river_historicaltransitionapproval
    #         WHERE object_id = %s
    #         ORDER BY history_id ASC;
    #     '''

    #     payment_records = obj.history.all()
    #     payment_history_data = PaymentHistorySerializer(payment_records, many=True).data  
    #     first_task_id = obj.payment_workflow.get().stages.first().tasks.filter().order_by('order').first().id
    #     result_dict = {
    #         'VP': 'Approval Pending',
    #         'P1': 'Approval Pending',
    #         'P2': 'Approval Pending',
    #         'P3': 'Approval Pending',
    #         'AH': 'Approval Pending',
    #     }
    #     time_dict = {
    #         'VP': '',
    #         'P1': '',
    #         'P2': '',
    #         'P3': '',
    #         'AH': '',  
    #     }
    #     for id in ids:
    #         history_records = TransitionApproval.objects.raw(query, [str(id)])
    #         if history_records:
    #             for record in history_records:
    #                 #print("record : ", record, record.status,record.object_id, record.id, record.history_id) 
    #                 if record.status == 'cancelled':
    #                     # print("record.status: ", record.status, record.object_id, record.history_id)
    #                     approver_id = record.transactioner_id
                        
    #                     for key, value in user_dict.items():
    #                         if value == approver_id:
    #                             result_dict[key] = 'Reject'
    #                             time_dict[key] = record.history_date
    #     # print("time dict: ", time_dict)
    #     for record in payment_history_data:
    #         if record['status'] == 'On Hold' and obj.status == 'On Hold':
    #             history_user = record.get("history_user_id") 
    #             for key, value in user_dict.items():
    #                 if value == history_user:
    #                     result_dict[key] = 'On Hold'  

    #     first_stage = obj.payment_workflow.get().stages.first()
    #     vp_task = first_stage.tasks.filter(completed=True, status=4, name= "Payment Approval VP").order_by('-order').first()
    #     if vp_task is not None:
    #         result_dict['VP'] = 'Approve'  
    #     p1_task = first_stage.tasks.filter(completed=True, status=4, name= "Payment Approval P1").order_by('-order').first()
    #     if p1_task is not None:
    #         result_dict['P1'] = 'Approve' 
    #     p2_task = first_stage.tasks.filter(completed=True, status=4, name= "Payment Approval P2").order_by('-order').first()
    #     if p2_task is not None:
    #         result_dict['P2'] = 'Approve' 
    #     p3_task = first_stage.tasks.filter(completed=True, status=4, name= "Payment Approval P3").order_by('-order').first()
    #     if p3_task is not None:
    #         result_dict['P3'] = 'Approve' 
    #     vh_task = first_stage.tasks.filter(completed=True, status=4, name= "Payment Approval AH").order_by('-order').first()
    #     if vh_task is not None:
    #         result_dict['AH'] = 'Approve' 
    #     if 'Approve'  in result_dict.values() or obj.status == 'Approval Pending':
    #         for key in result_dict:
    #             if result_dict[key] == 'Reject':
    #                 result_dict[key] = 'Approval Pending'  

    #     reject_count = Counter(result_dict.values())['Reject']

    #     if reject_count > 1:
    #         latest_reject_timestamp = None
    #         latest_reject_role = None
            
    #         for role, status in result_dict.items():
    #             if status == 'Reject' and time_dict.get(role) and (not latest_reject_timestamp or time_dict[role] > latest_reject_timestamp):
    #                 latest_reject_timestamp = time_dict[role]
    #                 latest_reject_role = role
            
    #         for role, status in result_dict.items():
    #             if status == 'Reject' and role != latest_reject_role:
    #                 result_dict[role] = 'Approval Pending'

    #     converted_list = []
    #     print("data: ", result_dict)
    #     for role, status in result_dict.items():
    #         converted_list.append({"role": role, "status": status})                        
    #     return converted_list



class CustomerPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerPayment
        fields = ['id', 'lead', 'event_name', 'date', 'amount', 'time', 'payment_mode', 'payment_type' , 'transaction_id','tds_date',  'tds_time', 'tds_amount', 'tds_status','tds_transaction_id']
        read_only_fields = ['id']

    def create(self, validated_data):
        # Set `tds_date` and `tds_time` to None if not provided
        validated_data['tds_date'] = validated_data.get('tds_date', None)
        validated_data['tds_time'] = validated_data.get('tds_time', None)
        return super().create(validated_data)    


class HistorySerializer(serializers.ModelSerializer):

    history_date = serializers.DateTimeField()
    history_type = serializers.CharField()
    history_user_id = serializers.IntegerField()
    history_user = serializers.SerializerMethodField()
    message = serializers.SerializerMethodField()
    activity_type = serializers.SerializerMethodField()

    class Meta:
        model = None 
        fields = ['history_user_id', 'history_date', 'history_type', 'history_user', 'message','activity_type']

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
            return f"{model_name} Details Edited"
        elif history_type == "-":
            return f"{model_name} Deleted"
        return None
    
    def get_activity_type(self,obj):
        model_name = self.Meta.model.__name__ if self.Meta.model else None
        return model_name

class PaymentHistorySerializer(HistorySerializer):
    class Meta(HistorySerializer.Meta):
        model = Payment
        fields = HistorySerializer.Meta.fields +  ['amount', 'campaign', 'agency_name', 'customer_name','transaction_id','status','payment_mode','due_date','paid_date','paid_time','payment_to','payment_for','denied_reason','request_type','campaign','agency_type','source_id','campaign_type','invoice_overview','vendor']
        #fields = '__all__'




class TransitionApprovalHistorySerializer(HistorySerializer):
    class Meta(HistorySerializer.Meta):
        model = TransitionApproval
        fields = HistorySerializer.Meta.fields +  ['status']
        #fields = '__all__'
class NotesSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()
    created = serializers.SerializerMethodField()

    class Meta:
        model = Notes
        fields = '__all__'
        extra_kwargs = {
            'notes': {'required': True},
            'payment': {'required': True},
        }
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