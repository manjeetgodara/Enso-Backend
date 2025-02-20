from django.urls import path
from .views import *
from rest_framework import permissions
from django.urls import path

urlpatterns = [
    path('', ProjectInventoryListAPIView.as_view(), name='project-inventories-info'),
    # path('inventory/', InventoryCreateView.as_view(), name='inventory-create'),
    # path('inventory/<int:pk>/', InventoryDetailApiView.as_view(), name='inventory-detail'),
    path('bookingform/', BookingFormCreateView.as_view(), name= "bookingform-create"),
    path('bookingform/<int:pk>/', BookingFormDetailApiView.as_view(), name='bookingform-detail'),
    path('bookingform-meta-data/<int:pk>/', BookingFormMetaDataAPIView.as_view(), name='bookingform-meta-data'),
    # path('bookingform/<int:lead_id>/signature/', BookingFormSignatureView.as_view(), name='bookingform-signature'),
    # path('collecttoken/', CollectTokenCreateView.as_view(), name= "collecttoken-create"),
    # path('collecttoken/<int:pk>/', CollectTokenDetailApiView.as_view(), name='collecttoken-detail'),
    #path('lead/<int:lead_id>/history/', LeadHistoryView.as_view(), name='lead_history'),
    #path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    #path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    path('project-cost-sheet/', ProjectCostSheetListCreateView.as_view(), name='payment-cost-sheet-list-create'),
    path('project-cost-sheet/<int:pk>/', ProjectCostSheetDetailView.as_view(), name='payment-cost-sheet-detail'),
    path('get-inventory-cost-sheet-data/', GetInventoryCostSheetAPIView.as_view(), name='get-inventory-cost-sheet-data'),
    path('cost-sheet-data/', GetInventoryCostSheetAPIViewV2.as_view(), name='cost-sheet-data'),
    path('inventory-cost-sheet/', InventoryCostSheetListCreateUpdateView.as_view(), name='inventory-cost-sheet-list-create'), 
    path('inventory-total/', InventoryTotalAPIView.as_view(), name='inventory-total'),
    path('inventory-cost-sheet/bulk-update/', InventoryCostSheetListCreateUpdateView.as_view(), name='inventory-cost-sheet-bulk-update'),
    path('cost-sheet/request-approval/', CostSheetRequestApproval.as_view(), name='cost-sheet-request-approval'),
    path('get-cost-sheet-approval/', GetCostSheetApproval.as_view(), name='get-cost-sheet-approval'),
    path('inventory-cost-sheet/<int:pk>/', InventoryCostSheetDetailView.as_view(), name='inventory-cost-sheet-detail'),
    path('current-closure-step/<int:pk>/', ClosureStepView.as_view(), name='current-closure-step'),
    path('collect-token-info/<int:pk>/', CollectTokenInfoView.as_view(), name='collect-token-info'),
    path('collect-token-update-info/', CollectTokenUpdateView.as_view(), name='collect-token-update-info'),
    path('project-detail/', ProjectDetailCreateView.as_view(), name='project-detail-create'),
    path('project-detail/<int:pk>/', ProjectDetailRetrieveUpdateDeleteAPIView.as_view(), name='project-detail-retrieve-update-destroy'),
    path('projects/<int:project_id>/towers/', ProjectTowerCreateView.as_view(), name='create-project-towers'),
    path('project-inventory/', ProjectInventoryListCreateAPIView.as_view(), name='project-inventory-list-create'),
    path('project-inventory/<int:pk>/', ProjectInventoryRetrieveUpdateDestroyAPIView.as_view(), name='project-inventory-retrieve-update-destroy'),
    path('block-inventory/', BlockProjectInventoryUpdateView.as_view(), name='block-inventory'),
    path('update-key-transfer/<int:lead_id>/', PropertyOwnerUpdateKeyTransfer.as_view(), name='update-key-transfer'),
    path('metadata/', ProjectMetadataAPI.as_view(), name='project-metadata'),
    path('generate-pdf/', generate_pdf, name='generate-pdf'),
    path('get-pdf/', GetPdf.as_view(), name='get-pdf'),
    path('cancel-booking/', CancelBooking.as_view(), name='cancel-booking'),
    path('project-inventory/bulk-upload/', ProjectInventoryBulkUpload.as_view(), name='project-inventory bulk upload')
    #path('projects/<int:project_id>/costsheets/', ProjectCostSheetCreateView.as_view(), name='create-project-costsheets'),
]




