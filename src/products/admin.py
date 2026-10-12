# products/admin.py
from django.contrib import admin
from .models import ProductTagGroup, ProductTag, Product, PriceHistory, Brand


@admin.register(ProductTagGroup)
class ProductTagGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(ProductTag)
class ProductTagAdmin(admin.ModelAdmin):
    list_display = ('name', 'group', 'slug')
    list_filter = ('group',)
    search_fields = ('name', 'group__name')
    prepopulated_fields = {'slug': ('name',)}


class PriceHistoryInline(admin.TabularInline):
    model = PriceHistory
    extra = 0
    readonly_fields = ('recorded_at',)


# @admin.register(Product)
# class ProductAdmin(admin.ModelAdmin):
#     list_display = ('title', 'store', 'current_price', 'currency', 'is_in_stock', 'last_parsed_at')
#     list_filter = ('store', 'is_in_stock', 'tags__group', 'tags')
#     search_fields = ('title', 'url')
#     filter_horizontal = ('tags',)
#     inlines = [PriceHistoryInline]
#     readonly_fields = ('created_at', 'updated_at', 'last_parsed_at')
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('title', 'brand', 'store', 'current_price', 'total_users', 'is_admin_added', 'is_in_stock')
    list_filter = ('store', 'brand','tags__group', 'tags', 'is_admin_added', 'is_in_stock')
    search_fields = ('title', 'url', 'gtin',)
    filter_horizontal = ('tags',)
    inlines = [PriceHistoryInline]
    readonly_fields = ('created_at', 'updated_at', 'last_parsed_at')
    

    fieldsets = (
        ('Основне', {
            'fields': ('store', 'brand', 'url', 'title', 'description', 'image_url')
        }),
        ('Ідентифікатори (Schema.org)', {
            'fields': ('gtin',)
        }),
        ('Ціна та Наявність', {
            'fields': ('current_price', 'old_price', 'min_price', 'max_price', 'currency', 'is_in_stock')
        }),
        ('Каталог та Популярність', {
            'fields': ('is_admin_added', 'total_users', 'tags')
        }),
        ('Дати', {
            'fields': ('last_parsed_at', 'created_at', 'updated_at')
        }),
    )


@admin.register(PriceHistory)
class PriceHistoryAdmin(admin.ModelAdmin):
    list_display = ('product', 'price', 'is_in_stock', 'recorded_at')
    list_filter = ('recorded_at', 'is_in_stock')
    search_fields = ('product__title',)
    readonly_fields = ('recorded_at',)


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'total')
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}