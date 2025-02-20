from django.urls import path, include
from .views import *

urlpatterns = [
    path('payments/', PaymentReterivalView.as_view(), name = 'payment-create'),
    path('create_payments/',PaymentCreateView.as_view(),name='payment-data'),
    path('payments/<int:pk>/', PaymentDetailView.as_view(), name='payment-detail'),
    path('record-payment/<int:lead_id>/', CustomerPaymentCreateView.as_view(), name='customer_payment_create'),
    path('record-payment-tds/<int:lead_id>/',RecordTDSPaymentView.as_view(),name='tds_payment_record'),
    path('transaction_updates/<int:lead_id>/', CustomerPaymentListView.as_view(), name='customer_payment_list'),
    path('latest-refund/<int:lead_id>/', LatestRefundPaymentView.as_view(), name='latest-refund-payment'),
    path('get_meta_data/', GetMetaDataAPIView.as_view(), name='get_meta_data'),
    path('history-retrieval/<int:payment_id>/', HistoryRetrievalView.as_view(), name='history_retrieval'),
    path('notes/', NotesListCreateView.as_view(), name='notes-list-create'),
    path('notes/payment/<int:payment_id>/', NotesListView.as_view(), name='notes-list'),
    path('notes/<int:id>/', UpdateOrDeleteNoteView.as_view(), name='update-or-delete-note'),
    path('sales-payment/meta-data/', SalesPaymentMetadataAPI.as_view(), name='update-or-delete-note'),
]
 