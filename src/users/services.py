# users/services.py
from typing import Tuple
from django.db import transaction
from django.utils.timezone import now
from users.models import User, UserSession

SESSION_COOKIE_NAME = "dp_session_token"
DAILY_ANONYMOUS_PARSE_LIMIT = 1  # 1 безкоштовний парсинг для аноніма
BONUS_TRACKERS_PER_REF = 3        # +3 слоти за кожного запрошеного друга


def get_or_create_browser_session(request) -> Tuple[UserSession, bool]:
    """
    Отримує або створює сесію браузера за допомогою UUID cookie.
    Також скидає лічильник daily_parse_count, якщо настав новий день.
    """
    token_str = request.COOKIES.get(SESSION_COOKIE_NAME)
    session_obj = None
    created = False

    if token_str:
        session_obj = UserSession.objects.filter(token=token_str).first()

    if not session_obj:
        ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', '')).split(',')[0].strip()
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
        
        user = request.user if request.user.is_authenticated else None
        session_obj = UserSession.objects.create(
            user=user,
            ip_address=ip or None,
            user_agent=user_agent
        )
        created = True
    else:
        # Скидання добового ліміту, якщо змінилася дата
        if session_obj.last_used_at.date() < now().date():
            session_obj.daily_parse_count = 0
            session_obj.save(update_fields=['daily_parse_count', 'last_used_at'])
        
        # Перевірка прив'язки користувача (якщо авторизувався в процесі)
        if request.user.is_authenticated and session_obj.user != request.user:
            session_obj.user = request.user
            session_obj.save(update_fields=['user', 'last_used_at'])

    return session_obj, created


def process_referral(new_user: User, ref_code_str: str) -> bool:
    """
    Прив'язує новий акаунт до реферера та нараховує бонусні відстеження.
    """
    if not ref_code_str:
        return False

    try:
        referrer = User.objects.get(referral_code=ref_code_str)
        if referrer.pk == new_user.pk or new_user.referred_by:
            return False

        with transaction.atomic():
            new_user.referred_by = referrer
            new_user.save(update_fields=['referred_by'])

            # Додаємо бонуси рефереру
            referrer.bonus_trackers += BONUS_TRACKERS_PER_REF
            referrer.save(update_fields=['bonus_trackers'])
            return True
    except (User.DoesNotExist, ValueError):
        return False