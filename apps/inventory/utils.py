from .models import *
from auth.utils import ResponseHandler
from rest_framework import status

from lead.models import Lead

from datetime import datetime
import os,json
import pdfkit
from django.template.loader import render_to_string
from django.conf import settings
from django.core.files import File
from django.db.models import Sum

def create_property_owner_and_inventory_cost_sheets(apartment_no, tower, lead):
    print('apartment_no:', apartment_no, tower,lead)
    from inventory.models import ProjectInventory,ProjectCostSheet,InventoryCostSheet,PropertyOwner
    # Create PropertyOwner
    property_instance = ProjectInventory.objects.get(apartment_no=apartment_no,tower=tower)
    print('property_instance:', property_instance)
    # print('here:')
    # property_instance.lead=lead
    # property_instance.save()
    # print('here2:')


    current_event_order = property_instance.tower.project.current_event_order
    print('current_event_order:', current_event_order)

    if not property_instance:
        return ResponseHandler(True, 'Inventory not found', None, status.HTTP_404_NOT_FOUND)

    property_owner = PropertyOwner.objects.get_or_create(
        lead=lead,
        property=property_instance
    )

    # Create InventoryCostSheet events based on ProjectCostSheet
    project_cost_sheets = ProjectCostSheet.objects.filter(project=property_instance.tower.project)

    for project_cost_sheet in project_cost_sheets:
        # if project_cost_sheet.event_order <= 2 or project_cost_sheet.event_order >= current_event_order:
        if project_cost_sheet.event_order >=1:
            print('project_cost_sheet:', project_cost_sheet.payment_type)
            if project_cost_sheet.payment_type == "Registration Fees":
                print('project_cost_sheet:', project_cost_sheet)
                InventoryCostSheet.objects.create(
                    inventory=property_instance,
                    event_order=project_cost_sheet.event_order,
                    event=project_cost_sheet.event,
                    completed=False,
                    payment_type=project_cost_sheet.payment_type,
                    payment_in_percentage=project_cost_sheet.payment_in_percentage,
                    amount=project_cost_sheet.amount,
                    lead=lead
                )
            else:
                InventoryCostSheet.objects.create(
                    inventory=property_instance,
                    event_order=project_cost_sheet.event_order,
                    event=project_cost_sheet.event,
                    completed=False,
                    payment_type=project_cost_sheet.payment_type,
                    payment_in_percentage=project_cost_sheet.payment_in_percentage,
                    lead=lead
                )

    collect_token_event = InventoryCostSheet.objects.filter(inventory__lead__id=lead.id, event_order = 0)
    print('collect_token_event:', collect_token_event)
    if not collect_token_event:
        print('here')
        InventoryCostSheet.objects.create(
            inventory=property_instance,
            event_order=0,
            event="Token amount of initial payment",
            completed=False,
            payment_type="Token",
            lead=lead
        )

    return property_owner

def reset_property_owner_and_inventory_cost_sheets(inventory_cost_sheets, lead):
    from inventory.models import PropertyOwner
    try:
        removed_cost_sheets = inventory_cost_sheets.delete()
        inventory_owner = PropertyOwner.objects.filter(lead=lead).first()
        inventory_owner.delete()
        print('inventory_owner:', inventory_owner)
        return
    except Exception as e:
            return ResponseHandler(True,f"Error: {str(e)}",None, status.HTTP_500_INTERNAL_SERVER_ERROR)
    

def generate_form_pdf(lead_id =None, booking_form_param =None, cost_sheet_param = None):
    from inventory.models import ProjectInventory,BookingForm,InventoryCostSheet,PropertyOwner
    try:
  
        if not lead_id:
            print("Lead ID is missing.")
            return None
        
        if not Lead.objects.filter(id=lead_id).exists():
            print("Lead does not exist.")
            return None
        
        lead_instance = Lead.objects.get(id=lead_id)
        print("lead instance: ", lead_instance)
        project_inventory = ProjectInventory.objects.filter(lead=lead_instance).first()
        print("lead project_inventory: ", project_inventory)
        if not project_inventory:
            print("Project inventory not found.")
            return None

        print("lead instance: ", lead_instance)
        booking_form = BookingForm.objects.filter(lead_id=lead_instance).first()
        print("lead booking_form: ", booking_form)
        if not booking_form:
            print("Booking form not found.")
            return None

        inventory_owner = PropertyOwner.objects.filter(lead=lead_instance).first()
        if not inventory_owner:
            print("Project owner not found.")
            return None
        project_details = booking_form.project 

        filename = project_details.name.lower().replace(" ", "_") + ".json"

        json_file_path = filename

        if os.path.exists(json_file_path):
            with open(json_file_path, "r") as file:
                json_data = json.load(file)
            print("JSON data loaded successfully:")
        else:
            return None

        if booking_form_param:
            image_url = json_data.get("image_url")
            inventory_owner = PropertyOwner.objects.filter(lead=lead_instance).first()
            deal_amount = float(inventory_owner.deal_amount) if inventory_owner and inventory_owner.deal_amount else 0
            sh_signature_url = lead_instance.sh_signature.url if lead_instance.sh_signature else None
            customer_signature_url = lead_instance.customer_signature.url if lead_instance.customer_signature else None
            co_owner1_signature_url = lead_instance.co_owner1_signature.url if lead_instance.co_owner1_signature else None
            co_owner2_signature_url = lead_instance.co_owner2_signature.url if lead_instance.co_owner2_signature else None
            co_owner3_signature_url = lead_instance.co_owner3_signature.url if lead_instance.co_owner3_signature else None
            co_owner4_signature_url = lead_instance.co_owner4_signature.url if lead_instance.co_owner4_signature else None
            co_owner5_signature_url = lead_instance.co_owner5_signature.url if lead_instance.co_owner5_signature else None

            context = {
                'project_name': project_details.name, 
                'configuration': project_inventory.configuration.name,
                'customer_name': getattr(booking_form, 'customer_name', None),
                'deal_amount': deal_amount,
                'pan_no': getattr(booking_form, 'pan_no', None),
                'aadhaar_details': getattr(booking_form, 'aadhaar_details', None),
                "contact_number" : lead_instance.primary_phone_no,
                'nationality': getattr(booking_form, 'nationality', None),
                'residence_address': getattr(booking_form, 'residence_address', None),
                'residence_phone_no': getattr(booking_form, 'residence_phone_no', None),
                'permanent_address': getattr(booking_form, 'permanent_address', None),
                'permanent_address_telephone_no': getattr(booking_form, 'permanent_address_telephone_no', None),
                'correspondance_address': getattr(booking_form, 'correspondance_address', None),
                'company_name': getattr(booking_form, 'company_name', None),
                'designation': getattr(booking_form, 'designation', None),
                'company_address': getattr(booking_form, 'company_address', None),
                'telephone_no': getattr(booking_form, 'telephone_no', None),
                'mobile_no': getattr(booking_form, 'mobile_no', None),
                'fax': getattr(booking_form, 'fax', None),
                'email_id': getattr(booking_form, 'email_id', None),
                 
                'guardian_name' : getattr(booking_form, 'guardian_name', None), 
                'guardian_dob' : getattr(booking_form, 'guardian_dob', None),
                'guardian_relationship' : getattr(booking_form, 'guardian_relationship', None),

                'co_owner1_name': getattr(booking_form, 'co_owner1_name', None),
                'co_owner1_pan_no': getattr(booking_form, 'co_owner1_pan_no', None),
                'co_owner1_nationality': getattr(booking_form, 'co_owner1_nationality', None),
                'relation_with_customer1': getattr(booking_form, 'relation_with_customer1', None),
                'co_owner1_company_name': getattr(booking_form, 'co_owner1_company_name', None),
                'co_owner1_designation': getattr(booking_form, 'co_owner1_designation', None),
                'co_owner1_company_address': getattr(booking_form, 'co_owner1_company_address', None),
                'co_owner1_telephone_no': getattr(booking_form, 'co_owner1_telephone_no', None),
                'co_owner1_mobile_no': getattr(booking_form, 'co_owner1_mobile_no', None),
                'co_owner1_fax': getattr(booking_form, 'co_owner1_fax', None),
                'co_owner1_email_id': getattr(booking_form, 'co_owner1_email_id', None),
                'co_owner2_name': getattr(booking_form, 'co_owner2_name', None),
                'co_owner2_pan_no': getattr(booking_form, 'co_owner2_pan_no', None),
                'co_owner2_nationality': getattr(booking_form, 'co_owner2_nationality', None),
                'relation_with_customer2': getattr(booking_form, 'relation_with_customer2', None),
                'co_owner2_company_name': getattr(booking_form, 'co_owner2_company_name', None),
                'co_owner2_designation': getattr(booking_form, 'co_owner2_designation', None),
                'co_owner2_company_address': getattr(booking_form, 'co_owner2_company_address', None),
                'co_owner2_telephone_no': getattr(booking_form, 'co_owner2_telephone_no', None),
                'co_owner2_mobile_no': getattr(booking_form, 'co_owner2_mobile_no', None),
                'co_owner2_fax': getattr(booking_form, 'co_owner2_fax', None),
                'co_owner2_email_id': getattr(booking_form, 'co_owner2_email_id', None),

                'co_owner3_name': getattr(booking_form, 'co_owner3_name', None),
                'co_owner3_pan_no': getattr(booking_form, 'co_owner3_pan_no', None),
                'co_owner3_nationality': getattr(booking_form, 'co_owner3_nationality', None),
                'relation_with_customer3': getattr(booking_form, 'relation_with_customer3', None),
                'co_owner3_company_name': getattr(booking_form, 'co_owner3_company_name', None),
                'co_owner3_designation': getattr(booking_form, 'co_owner3_designation', None),
                'co_owner3_company_address': getattr(booking_form, 'co_owner3_company_address', None),
                'co_owner3_telephone_no': getattr(booking_form, 'co_owner3_telephone_no', None),
                'co_owner3_mobile_no': getattr(booking_form, 'co_owner3_mobile_no', None),
                'co_owner3_fax': getattr(booking_form, 'co_owner3_fax', None),
                'co_owner3_email_id': getattr(booking_form, 'co_owner3_email_id', None),

                'co_owner4_name': getattr(booking_form, 'co_owner4_name', None),
                'co_owner4_pan_no': getattr(booking_form, 'co_owner4_pan_no', None),
                'co_owner4_nationality': getattr(booking_form, 'co_owner4_nationality', None),
                'relation_with_customer4': getattr(booking_form, 'relation_with_customer4', None),
                'co_owner4_company_name': getattr(booking_form, 'co_owner4_company_name', None),
                'co_owner4_designation': getattr(booking_form, 'co_owner4_designation', None),
                'co_owner4_company_address': getattr(booking_form, 'co_owner4_company_address', None),
                'co_owner4_telephone_no': getattr(booking_form, 'co_owner4_telephone_no', None),
                'co_owner4_mobile_no': getattr(booking_form, 'co_owner4_mobile_no', None),
                'co_owner4_fax': getattr(booking_form, 'co_owner4_fax', None),
                'co_owner4_email_id': getattr(booking_form, 'co_owner4_email_id', None),

                'co_owner5_name': getattr(booking_form, 'co_owner2_name', None),
                'co_owner5_pan_no': getattr(booking_form, 'co_owner2_pan_no', None),
                'co_owner5_nationality': getattr(booking_form, 'co_owner2_nationality', None),
                'relation_with_customer5': getattr(booking_form, 'relation_with_customer2', None),
                'co_owner5_company_name': getattr(booking_form, 'co_owner2_company_name', None),
                'co_owner5_designation': getattr(booking_form, 'co_owner2_designation', None),
                'co_owner5_company_address': getattr(booking_form, 'co_owner2_company_address', None),
                'co_owner5_telephone_no': getattr(booking_form, 'co_owner2_telephone_no', None),
                'co_owner5_mobile_no': getattr(booking_form, 'co_owner2_mobile_no', None),
                'co_owner5_fax': getattr(booking_form, 'co_owner2_fax', None),
                'co_owner5_email_id': getattr(booking_form, 'co_owner2_email_id', None),

                'referral1_name': getattr(booking_form, 'referral1_name', None), 
                'referral1_phone_number' : getattr(booking_form, 'referral1_phone_number', None),

                'referral2_name': getattr(booking_form, 'referral2_name', None), 
                'referral2_phone_number' : getattr(booking_form, 'referral2_phone_number', None), 

                'referral3_name': getattr(booking_form, 'referral3_name', None), 
                'referral3_phone_number' : getattr(booking_form, 'referral3_phone_number', None),

                'marital_status': getattr(booking_form, 'marital_status', None),
                'date_of_anniversary': getattr(booking_form, 'date_of_anniversary', None),
                'family_configuration': getattr(booking_form, 'family_configuration', None),
                'configuration_id': getattr(booking_form, 'configuration_id', None),
                'tower_id': booking_form.tower.name if booking_form.tower  else None,
                'project_id': getattr(booking_form, 'project_id', None),
                'apartment_no': getattr(booking_form, 'apartment_no', None),
                'floor': getattr(booking_form, 'floor', None),
                'date_of_booking': getattr(booking_form, 'date_of_booking', None),
                'booking_source': getattr(booking_form, 'booking_source', None),
                'sub_source': getattr(booking_form, 'sub_source', None),
                'source_of_finance' : getattr(booking_form, 'source_of_finance', None),
                'sales_manager_name_id': booking_form.sales_manager_name.name,
                'contact_person_name': getattr(booking_form, 'contact_person_name', None),
                'contact_person_number': getattr(booking_form, 'contact_person_number', None),
                'car_parking' : project_inventory.car_parking if project_inventory.car_parking else None,
                "image_url": image_url,
                'sh_signature_url' : sh_signature_url,
                'customer_signature_url' : customer_signature_url,
                'co_owner1_signature_url' : co_owner1_signature_url,
                'co_owner2_signature_url' : co_owner2_signature_url,
                'co_owner3_signature_url' : co_owner3_signature_url,
                'co_owner4_signature_url' : co_owner4_signature_url,
                'co_owner5_signature_url' : co_owner5_signature_url
            }

            html_content = render_to_string('booking_form_template.html', context)

            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')

            pdf_file_path = os.path.join(f'booking_form_{project_inventory.apartment_no}_{lead_id}.pdf')
            
            wkhtmltopdf_path = r'/usr/bin/wkhtmltopdf'
            # wkhtmltopdf_path = r'C:\\Program Files\\wkhtmltopdf\\bin\\wkhtmltopdf.exe'

            config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)

            pdfkit.from_string(html_content, pdf_file_path, configuration=config)

            with open(pdf_file_path, 'rb') as file:
                inventory_owner.booking_form_pdf.save(pdf_file_path, File(file), save=True)

            file_url = inventory_owner.booking_form_pdf.url if inventory_owner and inventory_owner.booking_form_pdf else None 
            os.remove(pdf_file_path) 
        elif cost_sheet_param and lead_instance:
            from inventory.serializers import InventoryCostSheetSerializer
            queryset = InventoryCostSheet.objects.filter(lead=lead_id, inventory__apartment_no=project_inventory.apartment_no, inventory__tower__project=project_inventory.tower.project).order_by('event_order')
            print("lead inventory_queryset: ", queryset)
            if not queryset.exists():
                print("Inventory cost sheet not found.")
                return None
            print("Inventory inventory  found.")


            head_office = json_data.get("head_office") 
            site_address = json_data.get("site_address")
            rera_website = json_data.get("rera_website")
            gst = json_data.get("gst")
            terms_and_conditions = json_data.get("terms_and_conditions")
            image_url = json_data.get("image_url")
            
            #Signatures
            client_signature_url = lead_instance.client_signature.url if lead_instance.client_signature else None
            cm_signature_url = lead_instance.cm_signature.url if lead_instance.cm_signature else None
            vp_signature_url = lead_instance.vp_signature.url if lead_instance.vp_signature else None
            cost_sheet_co_owner_signature_url = lead_instance.cost_sheet_co_owner_signature.url if lead_instance.cost_sheet_co_owner_signature else None
            cost_sheet_co_owner2_signature_url = lead_instance.cost_sheet_co_owner2_signature.url if lead_instance.cost_sheet_co_owner2_signature else None
            cost_sheet_co_owner3_signature_url = lead_instance.cost_sheet_co_owner3_signature.url if lead_instance.cost_sheet_co_owner3_signature else None
            cost_sheet_co_owner4_signature_url = lead_instance.cost_sheet_co_owner4_signature.url if lead_instance.cost_sheet_co_owner4_signature else None
            cost_sheet_co_owner5_signature_url = lead_instance.cost_sheet_co_owner5_signature.url if lead_instance.cost_sheet_co_owner5_signature else None

            # queryset = InventoryCostSheet.objects.filter(lead=lead_id, inventory__apartment_no=project_inventory.apartment_no, inventory__tower__project=project_inventory.tower.project).order_by('event_order')
            # if not queryset.exists():
            #     return None

            # inventory_owner = PropertyOwner.objects.filter(lead=lead_instance).first()
            # deal_amount = float(inventory_owner.deal_amount) if inventory_owner and inventory_owner.deal_amount else 0
            # serializer = InventoryCostSheetSerializer(queryset, many=True)
            # cost_sheets = serializer.data
            # registration_fees = next((event["amount"] for event in cost_sheets if event["event_order"] == 2), 0)
            # registration_fees = float(registration_fees) if registration_fees else 0
            # amount_per_car_parking = queryset[0].inventory.amount_per_car_parking
            # car_parking = queryset[0].inventory.car_parking
            # total_car_parking_amount = int(car_parking) * float(amount_per_car_parking)
            
            # total_value = (deal_amount * 0.08) + deal_amount + registration_fees + total_car_parking_amount

            queryset = queryset.exclude(event_order=0)
            
            context = {
                'date': booking_form.date_of_booking,  
                'project_name': project_details.name,  
                'location': project_details.address, 
                'rera_website': project_details.rera_number + ' and ' + rera_website + ' under registered projects' , 
                'head_office': head_office, 
                'site_address': site_address, 
                'agreement_value': inventory_owner.deal_amount,  
                'apartment_no': project_inventory.apartment_no,
                'configuration': project_inventory.configuration.name,
                'building': project_inventory.tower.name,
                'floors' : project_inventory.floor_number,
                'car_parking': project_inventory.car_parking, 
                'area': project_inventory.area,
                'cost_sheet_data': queryset,
                'payment_in_percentage_sum': queryset.aggregate(payment_in_percentage_sum=Sum('payment_in_percentage'))['payment_in_percentage_sum'],
                'amount_sum': queryset.aggregate(amount_sum=Sum('amount'))['amount_sum'],
                'gst_sum': queryset.aggregate(gst_sum=Sum('gst'))['gst_sum'],
                'tds_sum': queryset.aggregate(tds_sum=Sum('tds'))['tds_sum'],
                'total_amount_sum': queryset.aggregate(total_amount_sum=Sum('total_amount'))['total_amount_sum'],
                'agreement_amount': inventory_owner.total_value,
                "gst":gst,
                "terms_and_conditions": terms_and_conditions,
                "image_url": image_url,
                "client_signature_url" : client_signature_url,
                "cm_signature_url" : cm_signature_url,
                "vp_signature" : vp_signature_url,
                "co_owner_signature" : cost_sheet_co_owner_signature_url,
                "co_owner2_signature" : cost_sheet_co_owner2_signature_url,
                "co_owner3_signature" : cost_sheet_co_owner3_signature_url,
                "co_owner4_signature" : cost_sheet_co_owner4_signature_url,
                "co_owner5_signature" : cost_sheet_co_owner5_signature_url,
            }

            html_content = render_to_string('pdf_template.html', context)

            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')

            # file_path = os.path.join(settings.MEDIA_ROOT, f'pdf_file_{timestamp}.html')

            # with open(file_path, "w") as file:
            #     file.write(html_content)

            pdf_file_path = os.path.join(f'cost_sheet_{project_inventory.apartment_no}_{lead_id}.pdf')

            # wkhtmltopdf_path = r'C:\\Program Files\\wkhtmltopdf\\bin\\wkhtmltopdf.exe'
            wkhtmltopdf_path = r'/usr/bin/wkhtmltopdf'
            
            config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)

            pdfkit.from_string(html_content, pdf_file_path, configuration=config)

            with open(pdf_file_path, 'rb') as file:
                inventory_owner.cost_sheet_pdf.save(pdf_file_path, File(file), save=True)

            file_url = inventory_owner.cost_sheet_pdf.url if inventory_owner and inventory_owner.cost_sheet_pdf else None 

            os.remove(pdf_file_path) 

        print("PDF generated successfully.")
        return file_url
    except Exception as e:
        print(f"Error generating PDF: {e}")
        return None