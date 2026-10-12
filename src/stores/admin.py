# stores/admin.py
from django.contrib import admin
from .models import Store, StoreTag, StoreSession, StoreError
import json
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils import timezone
from datetime import timedelta




from datetime import timedelta

from django.contrib import admin
from django.utils import timezone




@admin.register(StoreSession)
class StoreSessionAdmin(admin.ModelAdmin):
    list_display = (
        'store',
        'base_url',
        'status_badge',
        'last_updated_at',
        'next_update_due',
        'get_is_due_for_update',
    )
    list_filter = ('is_expired', 'last_updated_at', 'next_update_due')
    search_fields = ('store__domain', 'store__name', 'base_url')
    readonly_fields = ('last_updated_at', 'status_badge', 'formatted_session_data_preview')
    
    fields = (
        'store',
        'base_url',
        'is_expired',
        'next_update_due',
        'last_updated_at',
        'status_badge',
        'formatted_session_data_preview',
        'session_data',
    )

    actions = ['mark_as_expired', 'mark_as_active', 'extend_next_update_7_days']

    # --- Візуальні атрибути та індикатори ---

    @admin.display(description="Статус")
    def status_badge(self, obj):
        if not obj or not obj.pk:
            return "-"
        
        if obj.is_expired:
            return mark_safe(
                '<span style="background-color: #f8d7da; color: #721c24; padding: 3px 8px; border-radius: 4px; font-weight: bold;">EXPIRED</span>'
            )
        return mark_safe(
            '<span style="background-color: #d4edda; color: #155724; padding: 3px 8px; border-radius: 4px; font-weight: bold;">ACTIVE</span>'
        )

    @admin.display(description="Потребує оновлення", boolean=True)
    def get_is_due_for_update(self, obj):
        if not obj or not obj.next_update_due:
            return False
        return timezone.now() >= obj.next_update_due

    @admin.display(description="Preview JSON (Cookies/Storage)")
    def formatted_session_data_preview(self, obj):
        if not obj or not obj.session_data:
            return "Порожньо"
        
        try:
            formatted_json = json.dumps(obj.session_data, indent=2, ensure_ascii=False)
            # Передаємо formatted_json як аргумент у format_html — тепер все за правилами Django
            return format_html(
                '<pre style="background-color: #1e1e1e; color: #d4d4d4; padding: 10px; border-radius: 5px; max-height: 400px; overflow-y: auto;"><code>{}</code></pre>',
                formatted_json
            )
        except Exception:
            return str(obj.session_data)

    # --- Admin Actions ---

    @admin.action(description="Позначити обрані сесії як EXPIRED")
    def mark_as_expired(self, request, queryset):
        updated = queryset.update(is_expired=True)
        self.message_user(request, f"{updated} сесій позначено як застарілі.")

    @admin.action(description="Позначити обрані сесії як ACTIVE")
    def mark_as_active(self, request, queryset):
        updated = queryset.update(is_expired=False)
        self.message_user(request, f"{updated} сесій позначено як активні.")

    @admin.action(description="Продовжити планове оновлення на +7 днів")
    def extend_next_update_7_days(self, request, queryset):
        new_due = timezone.now() + timedelta(days=7)
        updated = queryset.update(next_update_due=new_due, is_expired=False)
        self.message_user(request, f"Для {updated} сесій планове оновлення встановлено на {new_due.strftime('%Y-%m-%d')}.")
@admin.register(StoreError)
class StoreErrorAdmin(admin.ModelAdmin):
    list_display = (
        'created_at',
        'store',
        'error_type_badge',
        'short_url',
        'short_message',
    )
    list_filter = ('error_type', 'created_at', 'store')
    search_fields = ('store__domain', 'url', 'message')
    readonly_fields = ('created_at', 'store', 'url', 'error_type', 'message')
    
    # Сортування за замовчуванням: найновіші помилки зверху
    ordering = ('-created_at',)
    
    # Пагінація для оптимізації продуктивності при великій кількості логів
    list_per_page = 50

    # Оптимізація SQL-запиту через select_related для FK Store
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('store')

    # --- Візуальні атрибути та індикатори ---

    @admin.display(description="Тип помилки")
    def error_type_badge(self, obj):
        colors = {
            StoreError.ErrorType.BOT_BLOCKED: '#dc3545',   # Червоний (Критично)
            StoreError.ErrorType.HTTP_ERROR: '#fd7e14',    # Помаранчевий
            StoreError.ErrorType.PARSING_FAILED: '#ffc107', # Жовтий
            StoreError.ErrorType.TIMEOUT: '#17a2b8',       # Блакитний
            StoreError.ErrorType.UNKNOWN: '#6c757d',       # Сірий
        }
        color = colors.get(obj.error_type, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: bold;">{}</span>',
            color,
            obj.get_error_type_display()
        )

    @admin.display(description="URL")
    def short_url(self, obj):
        """Скорочує довгий URL для компактності таблиці та додає клікабельне посилання."""
        if not obj.url:
            return "-"
        display_text = obj.url[:60] + "..." if len(obj.url) > 60 else obj.url
        return format_html('<a href="{}" target="_blank" title="{}">{}</a>', obj.url, obj.url, display_text)

    @admin.display(description="Повідомлення")
    def short_message(self, obj):
        if not obj.message:
            return "-"
        return obj.message[:80] + "..." if len(obj.message) > 80 else obj.message

    def has_add_permission(self, request):
        """Забороняємо вручну створювати помилки через адмінку (вони мають летяти лише з парсера)."""
        return False


@admin.register(StoreTag)
class StoreTagAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ('name', 'domain',  'is_active', 'total_products')
    list_filter = ('is_active', 'requires_js', 'has_cpa', 'force_ua_prefix')
    search_fields = ('name', 'domain')
    filter_horizontal = ('tags',)
    prepopulated_fields = {'slug': ('domain',)}

    fieldsets = (
        ('Основна інформація', {
            'fields': ('name', 'slug', 'domain', 'title_clean_patterns', 'tags', 'logo_url', 'is_active')
        }),
        ('Правила мовних роутів (Нормалізація URL)', {
            'fields': (
                'default_lang_prefix',
                'remove_lang_prefixes',
                'force_ua_prefix',
            ),
            'description': 'Налаштування для автоматичного перетворення російських версій посилань в українські.'
        }),
        ('Технічні налаштування', {
            'fields': ('requires_js',)
        }),
        ('CPA / Партнерка', {
            'fields': ('has_cpa', 'cpa_name', 'aff_url_start', 'aff_url_end', 'commission_rate')
        }),
        ('Статистика', {
            'fields': ('total_products', 'created_at', 'updated_at')
        }),
    )
    readonly_fields = ('total_products', 'created_at', 'updated_at')