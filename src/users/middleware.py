# src/users/middleware.py
import uuid
from .models import UserSession
import logging
from django.utils import timezone
from main.utils import get_client_ip, get_geo_info  # Ваш хелпер для GeoIP2
from .models import UserSession


logger = logging.getLogger(__name__)


class SessionTokenMiddleware:
    COOKIE_NAME = 'dropprice_session_token'
    COOKIE_AGE = 60 * 60 * 24 * 365 * 2  # 2 роки

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token_str = request.COOKIES.get(self.COOKIE_NAME)
        session_uuid = None
        set_cookie_needed = False

        # 1. Валідація UUID з Cookie
        if token_str:
            try:
                session_uuid = uuid.UUID(token_str)
            except (ValueError, TypeError):
                session_uuid = None

        # 2. Якщо куки немає або вона зламана — генеруємо новий токен у Cookie
        if not session_uuid:
            session_uuid = uuid.uuid4()
            set_cookie_needed = True

        request.session_token = session_uuid

        # 3. Легка перевірка: чи існує ВЖЕ створена сесія в БД для цього токена?
        user_session = UserSession.objects.filter(token=session_uuid).first()

        # Якщо сесія в БД вже існує — оновлюємо її IP/Geo/User за потреби
        if user_session:
            client_ip = get_client_ip(request)
            update_fields = []

            # Перевіряємо зміну IP
            if user_session.ip_address != client_ip:
                geo_data = get_geo_info(client_ip)
                user_session.ip_address = client_ip
                user_session.country = geo_data.get('country')
                user_session.city = geo_data.get('city')
                update_fields.extend(['ip_address', 'country', 'city'])

            # Перевіряємо прив'язку авторизованого користувача
            if request.user.is_authenticated and user_session.user != request.user:
                user_session.user = request.user
                update_fields.append('user')

            # Оновлюємо timestamp активності (не частіше ніж раз на 5 хвилин)
            if not user_session.last_used_at or (timezone.now() - user_session.last_used_at).total_seconds() > 300:
                user_session.last_used_at = timezone.now()
                update_fields.append('last_used_at')

            if update_fields:
                user_session.save(update_fields=update_fields)

        request.user_session = user_session

        # 4. Додаємо метод-хелпер до request для ЛІНИВОГО створення сесії у БД
        def get_or_create_user_session():
            """Створює об'єкт UserSession у БД з GeoIP тільки за вимогою View."""
            if request.user_session:
                return request.user_session

            client_ip = get_client_ip(request)
            user_agent = request.META.get('HTTP_USER_AGENT', '')
            geo_data = get_geo_info(client_ip)

            session_obj, created = UserSession.objects.get_or_create(
                token=request.session_token,
                defaults={
                    'ip_address': client_ip,
                    'user_agent': user_agent,
                    'country': geo_data.get('country'),
                    'city': geo_data.get('city'),
                    'user': request.user if request.user.is_authenticated else None,
                }
            )
            request.user_session = session_obj
            return session_obj

        request.get_or_create_user_session = get_or_create_user_session

        response = self.get_response(request)

        # 5. Встановлюємо Cookie, якщо вона нова або View попросив `should_set_cookie`
        if set_cookie_needed or getattr(request, 'should_set_cookie', False):
            response.set_cookie(
                self.COOKIE_NAME,
                str(request.session_token),
                max_age=self.COOKIE_AGE,
                httponly=True,
                samesite='Lax'
            )

        return response

    @staticmethod
    def get_client_ip(request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')