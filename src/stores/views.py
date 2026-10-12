# stores/views.py
from datetime import timedelta
from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated

from .models import Store, StoreSession, StoreError


class PendingSessionStoresView(APIView):
    """Повертає перелік унікальних base_url та цільових URL, які потребують запису сесії."""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Витягуємо магазини, для яких є записи в StoreError
        pending_errors = StoreError.objects.select_related('store').all()
        
        results = []
        visited_stores = set()

        for err in pending_errors:
            if err.store_id not in visited_stores:
                visited_stores.add(err.store_id)
                results.append({
                    "store_id": err.store.id,
                    "base_url": err.store.base_url,
                    "target_url": err.url  # Точна сторінка, на якій збійнула перевірка
                })

        return Response(results, status=status.HTTP_200_OK)


class UpdateStoreSessionView(APIView):
    """Приймає JSON сесії для base_url від record_sessions.py та видаляє відповідні StoreError."""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        base_url = request.data.get("base_url")
        session_json = request.data.get("session_data")

        if not base_url or not session_json:
            return Response(
                {"error": "base_url та session_data обов'язкові"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        store = get_object_or_404(Store, base_url=base_url)

        # 1. Оновлюємо або створюємо сесію для конкретного base_url (наприклад, aliexpress.com/pl/)
        session, _ = StoreSession.objects.update_or_create(
            store=store,
            defaults={
                "base_url": base_url,
                "session_data": session_json,
                "is_expired": False,
                "next_update_due": timezone.now() + timedelta(days=7)
            }
        )

        # 2. Видаляємо всі помилки для цього store із черги
        deleted_count, _ = StoreError.objects.filter(store=store).delete()

        return Response({
            "status": "success", 
            "base_url": base_url, 
            "session_id": session.id,
            "cleared_errors": deleted_count
        }, status=status.HTTP_200_OK)