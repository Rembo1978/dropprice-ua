from django.urls import path
from .views import BulkCashbackRateIngestView, cashback_click

urlpatterns = [
    path('api/cashback/', BulkCashbackRateIngestView.as_view(), name='cashback_ingest'),
    path('cashback/<int:rate_id>/', cashback_click, name='cashback_click'),
]