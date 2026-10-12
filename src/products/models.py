# products/models.py
import random
import re
from django.db import models
from django.utils.text import slugify
from stores.models import Store

# class Brand(models.Model):
#     name = models.CharField(max_length=255, unique=True, verbose_name="Назва бренду")
#     slug = models.SlugField(max_length=255, unique=True, db_index=True, verbose_name="Slug (для URL)")
#     total = models.PositiveIntegerField(
#             default=0,
#             db_index=True,
#             help_text="Кількість товарів цього бренду в базі",
#             verbose_name="Кількість товарів"
#         )
#     is_active = models.BooleanField(default=False, verbose_name="Активний бренд")
#     class Meta:
#         verbose_name = "Бренд"
#         verbose_name_plural = "Бренди"
#         ordering = ['name']

#     def __str__(self):
#         return self.name

#     def save(self, *args, **kwargs):
#         if not self.slug:
#             self.slug = slugify(self.name)
#         super().save(*args, **kwargs)

class Brand(models.Model):
    """
    Модель бренду/виробника товару (Nike, Apple, Samsung тощо).
    """
    name = models.CharField(
        max_length=255, 
        unique=True, 
        verbose_name="Назва бренду"
    )
    slug = models.SlugField(
        max_length=255, 
        unique=True, 
        db_index=True, 
        blank=True,
        null=True,
        verbose_name="Slug (для URL)"
    )
    logo_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name="URL логотипу"
    )
    is_active = models.BooleanField(
        default=False,
        verbose_name="Активний"
    )
    total = models.PositiveIntegerField(
        default=0,
        db_index=True,
        help_text="Кількість товарів цього бренду в базі",
        verbose_name="Кількість товарів"
    )

    # SEO Налаштування
    meta_title = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Meta Title"
    )
    meta_description = models.TextField(
        blank=True,
        null=True,
        verbose_name="Meta Description"
    )
    seo_text = models.TextField(
        blank=True,
        null=True,
        verbose_name="SEO Текст"
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Створено")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Оновлено")

    class Meta:
        verbose_name = "Бренд"
        verbose_name_plural = "Бренди"
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    @classmethod
    def get_or_create_by_name(cls, raw_name: str) -> tuple['Brand', bool]:
        """
        Хелпер для парсера: створює або повертає бренд із базовим очищенням рядка.
        """
        clean_name = raw_name.strip()
        if not clean_name:
            return None, False

        brand, created = cls.objects.get_or_create(
            name__iexact=clean_name,
            defaults={
                'name': clean_name,
                'slug': slugify(clean_name),
                'is_active': False
            }
        )
        return brand, created


class ProductTagGroup(models.Model):
    """
    Група тегів для товарів (наприклад: 'Взуття', 'Електроніка', 'Парфумерія').
    """
    name = models.CharField(max_length=100, unique=True, verbose_name="Назва групи")
    slug = models.SlugField(max_length=100, unique=True, verbose_name="Slug (для URL)")
    total = models.PositiveIntegerField(
            default=0,
            db_index=True,
            help_text="Кількість товарів, які мають теги з цієї групи",
            verbose_name="Кількість товарів"
        )
    class Meta:
        verbose_name = "Група тегів товарів"
        verbose_name_plural = "Групи тегів товарів"
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class ProductTag(models.Model):
    """
    Конкретний тег товару (наприклад: 'Черевики', 'Кросівки', 'Ноутбуки'), прив'язаний до групи.
    """
    group = models.ForeignKey(
        ProductTagGroup,
        on_delete=models.CASCADE,
        related_name='tags',
        verbose_name="Група тегів"
    )
    name = models.CharField(max_length=100, verbose_name="Назва тегу")
    slug = models.SlugField(max_length=100, unique=True, verbose_name="Slug (для URL)")
    total = models.PositiveIntegerField(
                default=0,
                db_index=True,
                help_text="Кількість товарів, які мають цей тег",
                verbose_name="Кількість товарів"
            )

    class Meta:
        verbose_name = "Тег товару"
        verbose_name_plural = "Теги товарів"
        unique_together = ('group', 'name')
        ordering = ['group', 'name']

    def __str__(self):
        return f"{self.group.name} -> {self.name}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(f"{self.group.name}-{self.name}")
        super().save(*args, **kwargs)


class Product(models.Model):
    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name='products',
        verbose_name="Магазин"
    )
    url = models.URLField(
        max_length=1000,
        unique=True,
        db_index=True,
        verbose_name="Пряме посилання на товар"
    )
    brand = models.ForeignKey(
        Brand,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products',
        verbose_name="Бренд"
    )
    gtin = models.CharField(
        max_length=250, null=True, blank=True, db_index=True,
        help_text="GTIN/EAN-13 штрихкод товару (наприклад: 8806097601326)", verbose_name="GTIN / EAN"
    )
    title = models.CharField(max_length=500, verbose_name="Назва товару")
    description = models.TextField(null=True, blank=True, verbose_name="Опис товару")
    image_url = models.URLField(max_length=1000, null=True, blank=True, verbose_name="URL зображення")
    
    # Цінові показники
    current_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        db_index=True, verbose_name="Поточна ціна"
    )
    old_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name="Попередня ціна"
    )
    min_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name="Мінімальна історична ціна"
    )
    max_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name="Максимальна історична ціна"
    )
    currency = models.CharField(max_length=10, default="UAH", verbose_name="Валюта")

    is_in_stock = models.BooleanField(default=True, verbose_name="Є в наявності")

    # Прапорець для адмінського каталогу (Топ-100 товарів для наповнення)
    is_admin_added = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Товар додано адміністратором для стартового наповнення каталогу/SEO",
        verbose_name="Додано адміном (Каталог)"
    )
    total_users = models.PositiveIntegerField(
        default=0,
        db_index=True,
        help_text="Кількість користувачів/сесій, які стежать за цим товаром",
        verbose_name="Кількість підписників"
    )

    tags = models.ManyToManyField(
        'ProductTag',
        related_name='products',
        blank=True,
        verbose_name="Теги товару"
    )

    last_parsed_at = models.DateTimeField(null=True, blank=True, verbose_name="Останній парсинг")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Створено")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Оновлено")

    class Meta:
        verbose_name = "Товар"
        verbose_name_plural = "Товари"
        ordering = ['-updated_at']

    def __str__(self):
        return f"[{self.store.name}] {self.title}"

    
    def clean_title(self) -> str:
        """Очищає назву товару на основі паттернів магазину"""
        cleaned = self.title
        if not self.store or not self.store.title_clean_patterns:
            return cleaned.strip()

        for pattern in self.store.title_clean_patterns:
            # flags=re.IGNORECASE дозволить ігнорувати регістр (купити / Купити)
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
        
        # Видаляємо зайві пробіли та HTML-сутності (наприклад &nbsp;)
        cleaned = re.sub(r'&nbsp;|\s+', ' ', cleaned).strip()
        return cleaned
    def save(self, *args, **kwargs):
        if self.title:
            self.title = self.clean_title()
        # Якщо товар додає адмін і це перше збереження, генеруємо фейкову кількість відстежень (наприклад, від 7 до 48)
        if not self.pk and self.is_admin_added and self.total_users == 0:
            self.total_users = random.randint(7, 48)
        super().save(*args, **kwargs)


class PriceHistory(models.Model):
    """
    Історія зміни ціни товару для побудови графіків.
    """
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='price_history',
        verbose_name="Товар"
    )
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Ціна")
    old_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Стара ціна")
    is_in_stock = models.BooleanField(default=True, verbose_name="В наявності")
    recorded_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Дата запису")

    class Meta:
        verbose_name = "Запис історії ціни"
        verbose_name_plural = "Історія цін"
        ordering = ['-recorded_at']

    def __str__(self):
        return f"{self.product.title} - {self.price} {self.product.currency} ({self.recorded_at.strftime('%Y-%m-%d %H:%M')})"