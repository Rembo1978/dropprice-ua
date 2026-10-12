from urllib.parse import urlparse
from django.db import models,transaction
from django.utils.text import slugify
from django.contrib.postgres.fields import ArrayField

class StoreTag(models.Model):
    """
    Теги/категорії для магазинів (наприклад: 'Одяг та взуття', 'Електроніка', 'Косметика').
    """
    name = models.CharField(max_length=100, unique=True, verbose_name="Назва тегу")
    slug = models.SlugField(max_length=100, unique=True, verbose_name="Slug (для URL)")

    class Meta:
        verbose_name = "Тег магазину"
        verbose_name_plural = "Теги магазинів"
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Store(models.Model):
    """
    Модель інтернет-магазину (Rozetka, Prom, Citadel, iHerb тощо).
    """
    name = models.CharField(
        max_length=255,
        unique=True,
        null=True,
        blank=True,
        verbose_name="Назва магазину"
    )
    slug = models.SlugField(
        max_length=255,
        unique=True,
        db_index=True,
        verbose_name="Slug магазину (для URL)"
    )
    domain = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Основний домен (наприклад: rozetka.com.ua)",
        verbose_name="Домен"
    )
    base_url = models.URLField(max_length=500, unique=True,
                                help_text="Наприклад: https://aliexpress.com/pl/ " \
                                "або https://www.ceneo.pl/")
    tags = models.ManyToManyField(
        StoreTag,
        related_name='stores',
        blank=True,
        verbose_name="Теги магазину"
    )
    logo_url = models.URLField(
        max_length=500,
        null=True,
        blank=True,
        verbose_name="URL логотипу / Favicon"
    )
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
    is_active = models.BooleanField(
        default=False,
        help_text="Чи дозволено відстежувати товари з цього магазину",
        verbose_name="Активний"
    )
    title_clean_patterns = ArrayField(
        models.CharField(max_length=500),
        default=list,
        blank=True,
        verbose_name="SEO Patterns for Title Cleanup",
        help_text="Регулярні вирази для видалення. Наприклад: '– Купити .*? TENDO' або '– купити в Києві.*'"
    )
    default_lang_prefix = models.CharField(
        max_length=20,
        blank=True,
        default="",
        help_text="Префікс української версії. Наприклад: 'ua' або 'uk' або порожньо. (для Rozetka це 'ua')",
        verbose_name="Основний мовний префікс (UA)"
    )
    remove_lang_prefixes = models.CharField(
        max_length=255,
        blank=True,
        default="ru,rus",
        help_text="Префікси через кому, які потрібно ЗАМІНЯТИ або ВИДАЛЯТИ. Наприклад: 'ru,rus'",
        verbose_name="Префікси для видалення/заміни"
    )
    force_ua_prefix = models.BooleanField(
        default=False,
        help_text="Якщо True: примусово додає default_lang_prefix у шлях (наприклад, перетворює /p123/ на /ua/p123/)",
        verbose_name="Примусово додавати UA префікс"
    )
    # Технічні налаштування парсингу
    requires_js = models.BooleanField(
        default=False,
        help_text="Чи потрібен Playwright / JS-рендеринг для цього сайту",
        verbose_name="Потребує JS (Playwright)"
    )

    # CPA & Партнерська монетизація
    has_cpa = models.BooleanField(
        default=False,
        verbose_name="Має CPA-програму"
    )
    cpa_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Назва CPA мережі (Admitad, SalesDoubler тощо)"
    )
    aff_url_start = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name="Партнерський старт URL"
    )
    aff_url_end = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name="Партнерський кінець URL"
    )
    commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Партнерська ставка %",
        verbose_name="Комісія (%)"
    )

    # Статистика
    total_products = models.PositiveIntegerField(
        default=0,
        verbose_name="Всього товарів у системі"
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Створено")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Оновлено")

    class Meta:
        verbose_name = "Магазин"
        verbose_name_plural = "Магазини"
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        """
        Генерує назву та slug з домену, якщо вони не вказані.
        """
        if not self.name:
            self.name = self.domain.capitalize()
        if not self.slug:
            self.slug = slugify(self.domain.replace('.', '-'))
        super().save(*args, **kwargs)

    @classmethod
    def extract_domain(cls, url: str) -> str:
        """
        Очищає URL та витягує чистий домен без 'www.'.
        'https://www.rozetka.com.ua/ua/p123/' -> 'rozetka.com.ua'
        """
        netloc = urlparse(url).netloc.lower()
        if netloc.startswith('www.'):
            netloc = netloc[4:]
        return netloc

    @classmethod
    def get_or_create_from_url(cls, url: str) -> tuple['Store', bool]:
        """
        Отримує магазин або автоматично створює новий у статусі is_active=False.
        """
        domain = cls.extract_domain(url)
        store, created = cls.objects.get_or_create(
            domain=domain,
            defaults={
                'name': domain.capitalize(),
                'slug': slugify(domain.replace('.', '-')),
                'is_active': False
            }
        )
        return store, created
    
    def generate_affiliate_url(self, original_url: str) -> str:
        """
        Формує партнерське посилання для переходу користувача.
        """
        if not self.has_cpa:
            return original_url

        prefix = self.aff_url_start or ""
        suffix = self.aff_url_end or ""
        return f"{prefix}{original_url}{suffix}"
    
    def mark_as_requires_js(self):
        """Автоматично позначає магазин як такий, що потребує JS/Playwright."""
        if not self.requires_js:
            self.requires_js = True
            self.save(update_fields=['requires_js', 'updated_at'])
            
    @classmethod
    def extract_domain(cls, url: str) -> str:
        """
        Метод-хелпер для очищення URL та витягування чистого домену.
        Приклад: 'https://www.rozetka.com.ua/ua/p123/' -> 'rozetka.com.ua'
        """
        netloc = urlparse(url).netloc.lower()
        if netloc.startswith('www.'):
            netloc = netloc[4:]
        return netloc
    @staticmethod
    def extract_base_url(url: str) -> str:
        """Витягує протокол та домен (з урахуванням мовних префіксів, якщо потрібно)."""
        if not url:
            return ""

        # Додаємо scheme, якщо передано посилання без http/https
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        parsed = urlparse(url)
        netloc = parsed.netloc.lower()

        if not netloc:
            return ""

        # Формуємо базовий URL: https://example.com
        return f"{parsed.scheme}://{netloc}"

    @classmethod
    def get_or_create_from_url(cls, raw_url: str):
        """Безпечно отримує або створює магазин за базовим URL."""
        base_url = cls.extract_base_url(raw_url)

        if not base_url:
            raise ValueError(f"Неможливо витягти коректний base_url із посилання: '{raw_url}'")

        parsed = urlparse(base_url)
        domain = parsed.netloc

        # Використовуємо atomic для уникнення race conditions при створенні
        with transaction.atomic():
            store, created = cls.objects.get_or_create(
                base_url=base_url,
                defaults={
                    "domain": domain,
                    "name": domain.replace("www.", "").capitalize(),
                }
            )

        return store, created


class StoreSession(models.Model):
    store = models.OneToOneField(Store, on_delete=models.CASCADE, related_name="session")
    base_url = models.URLField(max_length=500)
    session_data = models.JSONField(help_text="Cookies та storageState з Playwright у форматі JSON")
    
    is_expired = models.BooleanField(
        default=False, 
        help_text="Ставиться в True, якщо за наявності сесії все одно отримуємо блок"
    )
    
    last_updated_at = models.DateTimeField(auto_now=True)
    next_update_due = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        status = "EXPIRED" if self.is_expired else "ACTIVE"
        return f"Session for [{status}]"


class StoreError(models.Model):
    class ErrorType(models.TextChoices):
        BOT_BLOCKED = "bot_blocked", "Заблоковано анти-ботом (Akamai/Cloudflare)"
        HTTP_ERROR = "http_error", "HTTP помилка (403, 404, 500)"
        PARSING_FAILED = "parsing_failed", "Не вдалося витягнути ціну/назву"
        TIMEOUT = "timeout", "Таймаут з'єднання"
        UNKNOWN = "unknown", "Невідома помилка"

    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="errors", null=True, blank=True)
    url = models.URLField(max_length=1000)
    error_type = models.CharField(max_length=50, choices=ErrorType.choices, default=ErrorType.UNKNOWN)
    message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.error_type}] {self.url} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"