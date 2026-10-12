# users/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import User, UserSession


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Кастомна адмінка для моделі User.
    Успадкована від BaseUserAdmin для коректної роботи з паролями та правами.
    """
    # Поля, які відображаються у списку користувачів
    list_display = (
        'username',
        'telegram_id',
        'telegram_username',
        'is_bot_active',
        'country',
        'city',
        'is_staff',
        'created_at',
    )
    list_filter = ('is_bot_active', 'is_staff', 'is_superuser', 'is_active', 'created_at')
    search_fields = ('username', 'telegram_id', 'telegram_username', 'first_name', 'last_name')
    ordering = ('-created_at',)

    # Групування полів у формі редагування користувача
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Особисті дані'), {'fields': ('first_name', 'last_name', 'email')}),
        (
            _('Telegram інтеграція'),
            {
                'fields': (
                    'telegram_id',
                    'chat_id',
                    'telegram_username',
                    'is_bot_active',
                )
            },
        ),
        (
            _('Права доступу'),
            {
                'fields': (
                    'is_active',
                    'is_staff',
                    'is_superuser',
                    'groups',
                    'user_permissions',
                ),
            },
        ),
        (_('Важливі дати'), {'fields': ('last_login', 'date_joined', 'created_at', 'updated_at')}),
    )

    # Поля, які можна лише читати
    readonly_fields = ('created_at', 'updated_at', 'last_login', 'date_joined')

    # Форма створення нового користувача з адмінки
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        (
            _('Telegram дані (Опціонально)'),
            {
                'classes': ('wide',),
                'fields': ('telegram_id', 'chat_id', 'telegram_username'),
            },
        ),
    )


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    """
    Адмінка для перегляду сесій та прив'язаних куків.
    """
    list_display = ('token', 'user','country','city', 'ip_address', 'created_at', 'last_used_at')
    list_filter = ('created_at', 'last_used_at')
    search_fields = ('token', 'user__username', 'user__telegram_id', 'ip_address')
    readonly_fields = ('token', 'created_at', 'last_used_at')
    ordering = ('-last_used_at',)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')