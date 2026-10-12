import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """
    Кастомна модель користувача DropPrice UA.
    Головним ідентифікатором виступає telegram_id.
    """
    telegram_id = models.BigIntegerField(
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        verbose_name="Telegram ID"
    )
    chat_id = models.BigIntegerField(
        null=True,
        blank=True,
        verbose_name="Telegram Chat ID"
    )
    telegram_username = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="Telegram @username"
    )
    is_bot_active = models.BooleanField(
        default=True,
        help_text="False якщо користувач заблокував бота",
        verbose_name="Бот активний"
    )
    avatar_url = models.URLField(max_length=500, null=True, blank=True)

    # Реферальна система
    referral_code = models.UUIDField(default=uuid.uuid4,
                                      editable=False, unique=True,
                                        verbose_name="Реферальний код")
    referred_by = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='referrals',
        verbose_name="Хто запросив"
    )
    country = models.CharField("Країна", max_length=100, blank=True, null=True)
    city = models.CharField("Місто", max_length=100, blank=True, null=True)
    # Динамічні ліміти (базові + бонуси від рефералів)
    base_max_trackers = models.PositiveIntegerField(default=5, verbose_name="Базовий ліміт відстежень")
    bonus_trackers = models.PositiveIntegerField(default=0, verbose_name="Бонусні відстеження за рефералів")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Створено")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Оновлено")

    @property
    def max_trackers_limit(self) -> int:
        """Загальний ліміт відстежуваних товарів для користувача"""
        return self.base_max_trackers + self.bonus_trackers
    
    class Meta:
        verbose_name = "Користувач"
        verbose_name_plural = "Користувачі"

    def __str__(self):
        if self.telegram_username:
            return f"@{self.telegram_username} ({self.telegram_id})"
        if self.telegram_id:
            return f"TG: {self.telegram_id}"
        return self.username or f"User {self.pk}"


class UserSession(models.Model):
    """
    Модель для прив'язки Cookie браузера до Telegram користувача.
    """
    token = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        db_index=True,
        verbose_name="Сесійний Токен"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sessions',
        null=True,
        blank=True,
        verbose_name="Прив'язаний користувач"
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP адреса")
    user_agent = models.TextField(null=True, blank=True, verbose_name="User Agent")
    daily_parse_count = models.PositiveIntegerField(default=0)
    country = models.CharField("Країна", max_length=100, blank=True, null=True)
    city = models.CharField("Місто", max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Створено")
    last_used_at = models.DateTimeField(auto_now=True, verbose_name="Останнє використання")

    class Meta:
        verbose_name = "Сесія браузера"
        verbose_name_plural = "Сесії браузерів"

    def __str__(self):
        status = f"User: {self.user}" if self.user else "Анонімна сесія"
        return f"Session {self.token} [{status}]"