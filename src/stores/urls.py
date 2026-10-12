from django.urls import path
from .views import PendingSessionStoresView,UpdateStoreSessionView

urlpatterns = [
    # Головна сторінка з формою
    path('api/stores/pending-sessions/', PendingSessionStoresView.as_view(), name='stores_pending_sessions'),
    path('api/stores/update-session/', UpdateStoreSessionView.as_view(), name='stores_update_session'),
]