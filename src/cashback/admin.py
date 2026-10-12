from django.contrib import admin
from .models import CashbackService, CashbackRate, CashbackClick
from django.utils.html import format_html


class CashbackRateInline(admin.TabularInline):
    model = CashbackRate
    extra = 0
    fields = ('domain', 'name', 'logo_url', 'is_reg', 'rate_text', 'max_rate_value', 'url', 'updated_at')
    readonly_fields = ('updated_at',)
    show_change_link = True


@admin.register(CashbackService)
class CashbackServiceAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_active', 'rates_count', 'referral_base_url')
    list_filter = ('is_active',)
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ('is_active',)
    inlines = [CashbackRateInline]

    @admin.display(description="Кількість ставок")
    def rates_count(self, obj):
        return obj.rates.count()


@admin.register(CashbackRate)
class CashbackRateAdmin(admin.ModelAdmin):
    list_display = ('logo_preview','name','is_ua', 'domain', 'rate_text','is_reg', 'updated_at')
    list_filter = ('is_ua','is_reg','service', 'updated_at')
    search_fields = ('domain', 'name',)
    list_select_related = ('service',)  # Оптимізація SQL-запитів (JOIN)
    readonly_fields = ('updated_at',)
    ordering = ('name',)
    list_editable = ('domain', 'is_ua')  # Дозволяємо редагування цих полів безпосередньо в списку


    @admin.display(description='Logo')
    def logo_preview(self, obj):
        if obj.logo_url:
            return format_html(
                '<img src="{}" style="max-height:30px;border-radius:8px;" />',
                obj.logo_url
            )
        return '-'

@admin.register(CashbackClick)
class CashbackClickAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'country', 'city', 'user', 'user_ip')
    list_filter = ('service', 'created_at', 'store', 'country', 'city')
    search_fields = ('product_url', 'user_ip', 'user__username', 'user__email')
    list_select_related = ('service', 'store', 'user', 'session')
    readonly_fields = ('service', 'store', 'user', 'session', 'product_url', 'user_ip', 'user_agent', 'created_at')
    ordering = ('-created_at',)
    
    # Забороняємо ручне створення та редагування кліків з адмінки, бо це лог-дані
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description="URL товару")
    def short_product_url(self, obj):
        if len(obj.product_url) > 50:
            return f"{obj.product_url[:50]}..."
        return obj.product_url