# src/products/models.py
import random
import re
from django.db import models
from django.utils.text import slugify
from stores.models import Store
from django_ckeditor_5.fields import CKEditor5Field
from pgvector.django import VectorField, HnswIndex
from django.db import IntegrityError, transaction
from django.db.models import UniqueConstraint
from django.db.models.functions import Lower


class PriceRating(models.IntegerChoices):
    VERY_GOOD = 1, "Дуже вигідна ціна"
    GOOD = 2, "Вигідна ціна"
    FAIR = 3, "Справедлива ціна"
    HIGH = 4, "Висока ціна"
    VERY_HIGH = 5, "Занадто висока ціна"


UA_TO_LAT = str.maketrans({
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'h', 'ґ': 'g',
    'д': 'd', 'е': 'e', 'є': 'ye', 'ж': 'zh', 'з': 'z',
    'и': 'y', 'і': 'i', 'ї': 'yi', 'й': 'y', 'к': 'k',
    'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p',
    'р': 'r', 'с': 's', 'т': 't', 'у': 'u', 'ф': 'f',
    'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh',
    'щ': 'shch', 'ю': 'yu', 'я': 'ya',
    'ь': '', 'ъ': '', 'ы': 'y', 'э': 'e', 'ё': 'yo',
    'і': 'i',
})


def translit_slug(value: str) -> str:
    if not value:
        return ''

    value = value.strip().lower()

    # Апострофи не повинні створювати зайвих роздільників.
    value = value.replace('’', '').replace('ʼ', '').replace("'", '')

    value = value.translate(UA_TO_LAT)

    return slugify(value)


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
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='synonyms',  # або 'children'
        verbose_name="Головний (батьківський) бренд"
    )
    is_active = models.BooleanField(
        default=False, db_index=True,
        verbose_name="Активний"
    )
    is_top = models.BooleanField(default=False, db_index=True)
    is_local = models.BooleanField(default=False, db_index=True)
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
        constraints = [
            UniqueConstraint(
                Lower("name"),
                name="brand_name_lower_uniq",
            ),
        ]

    @classmethod
    def get_or_create_by_name(cls, raw_name):
        if not raw_name:
            return None, False

        clean_name = " ".join(raw_name.split())
        if not clean_name:
            return None, False

        try:
            with transaction.atomic():
                brand, created = cls.objects.get_or_create(
                    name__iexact=clean_name,
                    defaults={
                        "name": clean_name,
                        "is_active": False,
                    },
                )
        except IntegrityError:
            # Інший процес міг створити цей бренд одночасно.
            brand = cls.objects.get(name__iexact=clean_name)
            created = False

        # Якщо знайдений запис є синонімом,
        # повертаємо канонічний бренд.
        if brand.parent_id:
            brand = brand.parent

        return brand, created

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = translit_slug(self.name)
        super().save(*args, **kwargs)
        
    # @classmethod
    # def get_or_create_by_name(cls, raw_name: str):
    #     if not raw_name or not raw_name.strip():
    #         return None, False

    #     clean_name = raw_name.strip()

    #     return cls.objects.get_or_create(
    #         name__iexact=clean_name,
    #         defaults={
    #             'name': clean_name,
    #             'is_active': False,
    #         },
    #     )



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
    keywords = models.JSONField(default=list, blank=True)
    seo_h1 = models.CharField(
        max_length=255, 
        blank=True, 
        null=True, 
        verbose_name="H1 Заголовок (на сторінці)"
    )
    meta_desc = models.TextField(
        blank=True, 
        null=True, 
        verbose_name="Meta Description"
    )

    # Замінюємо старий desc на потужний SEO текст
    seo_text = CKEditor5Field(
        blank=True, 
        null=True, 
        config_name='extends',
        verbose_name="SEO Текст (опис тега)"
    )
    total = models.PositiveIntegerField(
                default=0,
                db_index=True,
                help_text="Кількість товарів, які мають цей тег",
                verbose_name="Кількість товарів"
            )
    is_top = models.BooleanField(default=False, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
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
    min_price_30_days = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name="Мінімальна історична ціна (30 днів)"
    )
    max_price_30_days = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name="Максимальна історична ціна (30 днів)"
    )
    avg_price_30_days = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name="Середня історична ціна (30 днів)"
    )
    percent_deal = models.SmallIntegerField(
        null=True,
        blank=True,
        db_index=True,
        help_text=(
            "Відхилення поточної ціни від середньої "
            "історичної ціни у відсотках: "
            "-20 означає на 20% дешевше, "
            "+20 — на 20% дорожче."
        ),
    )
    price_rating = models.PositiveSmallIntegerField(
            choices=PriceRating.choices,
            null=True,
            blank=True,
            default=None,
            db_index=True,
            verbose_name="Оцінка ціни",
        )
    currency = models.CharField(max_length=10, default="UAH", verbose_name="Валюта")
    search_vector = VectorField(
        dimensions=768,
        null=True,
        blank=True,
    )
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
        indexes = [
            HnswIndex(
                name="product_vector_hnsw",
                fields=["search_vector"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            ),
        ]
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
    percent_deal = models.SmallIntegerField(
    null=True,
    blank=True,
    db_index=True,
    help_text=(
        "Відхилення поточної ціни від середньої "
        "історичної ціни у відсотках: "
        "-20 означає на 20% дешевше, "
        "+20 — на 20% дорожче."
    ),
)
    recorded_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Дата запису")

    class Meta:
        verbose_name = "Запис історії ціни"
        verbose_name_plural = "Історія цін"
        ordering = ['-recorded_at']

    def __str__(self):
        return f"{self.product.title} - {self.price} {self.product.currency} ({self.recorded_at.strftime('%Y-%m-%d %H:%M')})"