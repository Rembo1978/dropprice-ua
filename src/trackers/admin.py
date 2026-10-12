# trackers/admin.py
from django.contrib import admin
from .models import UserTracker


@admin.register(UserTracker)
class UserTrackerAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'get_owner',
        'product',
        'initial_price',
        'target_price',
        'is_active',
        'last_notified_at',
        'created_at',
    )
    list_filter = ('is_active', 'notify_on_stock', 'created_at')
    search_fields = (
        'product__title',
        'user__username',
        'user__telegram_username',
        'user__telegram_id',
        'session__token',
    )
    readonly_fields = ('created_at', 'updated_at', 'last_notified_at', 'last_notified_price')
    list_editable = ('is_active',)

    def get_owner(self, obj):
        if obj.user:
            return f"User: {obj.user}"
        return f"Session: {obj.session.token if obj.session else '—'}"
    get_owner.short_description = "Власник підписки"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'session', 'product', 'product__store')