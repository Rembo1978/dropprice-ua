from django.db import models
from django.conf import settings
from stores.models import Store
from users.models import UserSession


class CashbackService(models.Model):
    name = models.CharField("Назва сервісу", max_length=100)  # LetyShops, SmartySale тощо
    slug = models.SlugField(unique=True)
    referral_base_url = models.URLField("Базове реферальне посилання", max_length=1000)
    is_active = models.BooleanField("Активний", default=True)

    def __str__(self):
        return self.name


class CashbackRate(models.Model):
    service = models.ForeignKey(CashbackService, on_delete=models.CASCADE, related_name="rates")
    domain = models.CharField("Домен магазину", null=True, blank=True, max_length=255, db_index=True)  # наприклад, moyo.ua
    name = models.CharField("Назва магазину", max_length=255, null=True, blank=True)
    logo_url = models.URLField("URL логотипу / Favicon", max_length=500, null=True, blank=True)
    is_reg = models.BooleanField("Після реєстрації", default=False)
    is_ua = models.BooleanField("Український магазин", default=False)
    rate_text = models.CharField("Текст ставки", max_length=100, help_text="Наприклад: 'до 1.5%' або '3%'")
    max_rate_value = models.DecimalField("Максимальний % (число)", max_digits=5, decimal_places=2, null=True, blank=True)
    
    url = models.URLField("Пряме посилання на магазин",null=True, max_length=1000, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('service', 'name')
        verbose_name = "Ставка кешбеку"
        verbose_name_plural = "Ставки кешбеку"

    def __str__(self):
        return f"{self.service.name} -> {self.domain}: {self.rate_text}"


class CashbackClick(models.Model):
    service = models.ForeignKey(CashbackService, on_delete=models.SET_NULL, null=True)
    store = models.ForeignKey(Store, on_delete=models.SET_NULL, null=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    session = models.ForeignKey(UserSession, on_delete=models.SET_NULL, null=True, blank=True)
    country = models.CharField("Країна", max_length=100, blank=True, null=True, db_index=True)
    city = models.CharField("Місто", max_length=100, blank=True, null=True, db_index=True)
    product_url = models.URLField("URL товару, з якого перейшли", max_length=2000)
    user_ip = models.GenericIPAddressField("IP-адреса", null=True, blank=True)
    user_agent = models.TextField("User-Agent", blank=True)
    created_at = models.DateTimeField("Час переходу", auto_now_add=True)

    class Meta:
        verbose_name = "Клік по кешбеку"
        verbose_name_plural = "Аналітика кліків кешбеку"
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['service', 'store']),
            models.Index(fields=['country', 'city']),
        ]

    def __str__(self):
        return f"Click {self.service.name if self.service else 'Unknown'} at {self.created_at.strftime('%Y-%m-%d %H:%M')}"