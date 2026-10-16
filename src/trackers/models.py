# src/trackers/models.py
from django.db import models
from django.conf import settings
from users.models import UserSession
from products.models import Product


class UserTracker(models.Model):
    """
    Модель підписки користувача (або анонімної Cookie-сесії) на відстеження ціни товару.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='trackers',
        null=True,
        blank=True,
        verbose_name="Користувач"
    )
    session = models.ForeignKey(
        UserSession,
        on_delete=models.CASCADE,
        related_name='trackers',
        null=True,
        blank=True,
        verbose_name="Сесія браузера"
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='trackers',
        verbose_name="Товар"
    )

    # Налаштування відстеження
    target_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Якщо пусто — сповіщати про будь-яке зниження ціни",
        verbose_name="Бажана ціна"
    )
    initial_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Ціна на момент створення підписки"
    )
    notify_on_increase = models.BooleanField(
        default=False,
        verbose_name="Сповістити, якщо товар подорожчає"
    )
    increase_threshold_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Поріг спрацьовування сповіщення при зростанні ціни (за замовчуванням +1%)",
        verbose_name="Поріг подорожчання"
    )
    notify_on_stock = models.BooleanField(
        default=True,
        verbose_name="Сповістити про появу в наявності"
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name="Активне відстеження"
    )

    # Мета-інформація про сповіщення
    last_notified_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Ціна при останньому сповіщенні"
    )
    last_notified_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Дата останнього сповіщення"
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Створено")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Оновлено")

    class Meta:
        verbose_name = "Підписка на товар"
        verbose_name_plural = "Підписки на товари"
        ordering = ['-created_at']
        # Гарантуємо, що один користувач/сесія не підпишеться двічі на один товар
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'product'],
                name='unique_user_product_tracker',
                condition=models.Q(user__isnull=False)
            ),
            models.UniqueConstraint(
                fields=['session', 'product'],
                name='unique_session_product_tracker',
                condition=models.Q(session__isnull=False)
            ),
        ]

    def __str__(self):
        owner = f"@{self.user.telegram_username}" if self.user else f"Session {self.session_id}"
        return f"[{owner}] -> {self.product.title}"

    def save(self, *args, **kwargs):
        # Записуємо початкову ціну товару при першому створенні підписки
        if not self.pk and self.product and not self.initial_price:
            self.initial_price = self.product.current_price or 0
        super().save(*args, **kwargs)