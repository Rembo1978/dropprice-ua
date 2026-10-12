# products/views.py
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_http_methods
from scrapers.services import UniversalProductScraper, ProductSaveService
from django.db.models import F, Q
from users.models import UserSession
from trackers.models import UserTracker
from users.middleware import SessionTokenMiddleware
from urllib.parse import urlparse
from stores.models import Store
from .models import Product
from django.shortcuts import render, redirect
from django.urls import reverse
from django.http import HttpResponse
from django.views.decorators.http import require_http_methods
from django.db.models import F

# Ваші моделі та сервіси
from users.models import  UserSession  # Замініть CashbackRate на вашу назву моделі кешбеку
from cashback.models import CashbackRate  # Замініть CashbackRate на вашу назву моделі кешбеку


def home_view(request):
    return render(request, 'products/home.html')



def product_detail(request, pk):
    product = get_object_or_404(Product.objects.select_related('store', 'brand'), pk=pk)
    
    # Пошук кешбеку
    product_domain = extract_domain(product.url)
    cashback_rate = None
    if product_domain:
        cashback_rate = CashbackRate.objects.filter(
            domain__iexact=product_domain
        ).select_related('service').first()

    # Схожі товари (наприклад, з цього ж магазину або бренду)
    similar_products = Product.objects.filter(
        store=product.store
    ).exclude(pk=product.pk)[:6]

    # Історія цін для графіка
    price_history = product.price_history.order_by('recorded_at')[:30]

    context = {
        'product': product,
        'cashback_rate': cashback_rate,
        'similar_products': similar_products,
        'price_history': price_history,
    }
    return render(request, 'products/product_detail.html', context)



def extract_domain(url: str) -> str:
    """Витягує чистий домен з URL (наприклад: https://rozetka.com.ua/p123 -> rozetka.com.ua)"""
    if not url:
        return ""
    
    parsed_url = urlparse(url)
    domain = parsed_url.netloc or parsed_url.path
    
    # Видаляємо 'www.' та номер порту, якщо він є
    domain = domain.split(':')[0]
    if domain.startswith('www.'):
        domain = domain[4:]
        
    return domain.lower()


# @require_http_methods(["POST"])
# def test_parse_product(request):
#     raw_url = request.POST.get('url', '').strip()
    
#     if not raw_url:
#         return render(request, 'products/partials/parse_result.html', {
#             'error': 'Будь ласка, вкажіть посилання на товар.'
#         })

#     # 1. Lazy Creation UserSession
#     ip_address = SessionTokenMiddleware.get_client_ip(request)
#     user_agent = request.META.get('HTTP_USER_AGENT', '')
#     user = request.user if request.user.is_authenticated else None

#     session_obj, created = UserSession.objects.get_or_create(
#         token=request.session_token,
#         defaults={
#             'user': user,
#             'ip_address': ip_address,
#             'user_agent': user_agent,
#             'daily_parse_count': 0
#         }
#     )

#     if user and session_obj.user != user:
#         session_obj.user = user
#         session_obj.save(update_fields=['user'])

#     # 2. Атомарне збільшення лічильника
#     UserSession.objects.filter(pk=session_obj.pk).update(
#         daily_parse_count=F('daily_parse_count') + 1
#     )
#     session_obj.refresh_from_db()

#     should_set_cookie = getattr(request, 'is_new_session_token', False) or created

#     # 3. Синхронний реалтайм парсинг
#     scraper = UniversalProductScraper()
#     product_data = scraper.fetch_product_data(raw_url)

#     if not product_data:
#         return render(request, 'products/partials/parse_result.html', {
#             'error': 'Не вдалося розпарсити товар. Перевірте посилання або структуру сторінки.'
#         })

#     # 4. Збереження у БД (Store, Brand, Product, PriceHistory)
#     product = ProductSaveService.save_parsed_product(product_data, session_obj)

#     # 5. Точний пошук CashbackRate за полем CashbackRate.domain
#     product_domain = extract_domain(product.url or raw_url)
#     cashback_rate = None

#     if product_domain:
#         # Шукаємо запис, де поле domain дорівнює витягнутому домену (без урахування регістру)
#         cashback_rate = CashbackRate.objects.filter(
#             domain__iexact=product_domain
#         ).select_related('service').first()

#         # Фолбек: якщо у вашій БД domain у когось записаний з www або як частка url
#         if not cashback_rate:
#             cashback_rate = CashbackRate.objects.filter(
#                 domain__icontains=product_domain
#             ).select_related('service').first()

#     context = {
#         'product': product,
#         'user_session': session_obj,
#         'daily_parse_count': session_obj.daily_parse_count,
#         'cashback_rate': cashback_rate,  # Передається у шаблон для {% if cashback_rate %}
#     }

#     response = render(request, 'products/partials/parse_result.html', context)

#     # Якщо створювалася нова сесія — встановлюємо cookie
#     if should_set_cookie:
#         response.set_cookie('session_token', session_obj.token, max_age=86400 * 30, httponly=True)

#     return response
# @require_http_methods(["POST"])
# def test_parse_product(request):
#     raw_url = request.POST.get('url', '').strip()
    
#     if not raw_url:
#         return render(request, 'products/partials/parse_result.html', {
#             'error': 'Будь ласка, вкажіть посилання на товар.'
#         })

#     # 1. Lazy Creation UserSession
#     ip_address = SessionTokenMiddleware.get_client_ip(request)
#     user_agent = request.META.get('HTTP_USER_AGENT', '')
#     user = request.user if request.user.is_authenticated else None

#     session_obj, created = UserSession.objects.get_or_create(
#         token=request.session_token,
#         defaults={
#             'user': user,
#             'ip_address': ip_address,
#             'user_agent': user_agent,
#             'daily_parse_count': 0
#         }
#     )

#     if user and session_obj.user != user:
#         session_obj.user = user
#         session_obj.save(update_fields=['user'])

#     # 2. Атомарне збільшення лічильника
#     UserSession.objects.filter(pk=session_obj.pk).update(
#         daily_parse_count=F('daily_parse_count') + 1
#     )
#     session_obj.refresh_from_db()

#     should_set_cookie = getattr(request, 'is_new_session_token', False) or created

#     # 3. Синхронний реалтайм парсинг (ВИПРАВЛЕНИЙ БЛОК)
#     # ------------------------------------------------------------------
#     # Отримуємо або створюємо магазин у БД з домену URL
#     store, _ = Store.get_or_create_from_url(raw_url)

#     # Передаємо об'єкт store в конструктор UniversalProductScraper
#     scraper = UniversalProductScraper(store=store)
#     product_data = scraper.fetch_product_data(raw_url)
#     # ------------------------------------------------------------------

#     if not product_data:
#         return render(request, 'products/partials/parse_result.html', {
#             'error': 'Не вдалося розпарсити товар. Перевірте посилання або структуру сторінки.'
#         })

#     # 4. Збереження у БД (Store, Brand, Product, PriceHistory)
#     product = ProductSaveService.save_parsed_product(product_data, session_obj)

#     # 5. Точний пошук CashbackRate за полем CashbackRate.domain
#     product_domain = extract_domain(product.url or raw_url)
#     cashback_rate = None

#     if product_domain:
#         cashback_rate = CashbackRate.objects.filter(
#             domain__iexact=product_domain
#         ).select_related('service').first()

#         if not cashback_rate:
#             cashback_rate = CashbackRate.objects.filter(
#                 domain__icontains=product_domain
#             ).select_related('service').first()

#     context = {
#         'product': product,
#         'user_session': session_obj,
#         'daily_parse_count': session_obj.daily_parse_count,
#         'cashback_rate': cashback_rate,
#     }

#     response = render(request, 'products/partials/parse_result.html', context)

#     if should_set_cookie:
#         response.set_cookie('session_token', session_obj.token, max_age=86400 * 30, httponly=True)

#     return response
@require_http_methods(["POST"])
def test_parse_product(request):
    raw_url = request.POST.get("url", "").strip()

    if not raw_url:
        return render(
            request,
            "products/partials/parse_result.html",
            {"error": "Будь ласка, вкажіть посилання на товар."}
        )

    # 1. Спроба отримати або створити Store та розпарсити URL
    try:
        store, _ = Store.get_or_create_from_url(raw_url)
    except ValueError as e:
        return render(
            request,
            "products/partials/parse_result.html",
            {"error": str(e)}
        )

    # 2. Lazy Creation UserSession
    ip_address = SessionTokenMiddleware.get_client_ip(request)
    user_agent = request.META.get("HTTP_USER_AGENT", "")
    user = request.user if request.user.is_authenticated else None

    session_obj, created = UserSession.objects.get_or_create(
        token=request.session_token,
        defaults={
            "user": user,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "daily_parse_count": 0,
        }
    )

    # Прив'язуємо сесію до користувача, якщо він щойно авторизувався
    if user and session_obj.user != user:
        session_obj.user = user
        session_obj.save(update_fields=["user"])

    # 3. Перевірка ліміту запитів на день (Rate Limiting)
    # Наприклад, макс 20 парсингів на добу для анонімів та 100 для залогінених
    max_daily_limit = 1000 if user else 20
    if session_obj.daily_parse_count >= max_daily_limit:
        return render(
            request,
            "products/partials/parse_result.html",
            {"error": f"Ви досягли ліміту парсингу на сьогодні ({max_daily_limit} товарів)."}
        )

    # 4. Атомарне збільшення лічильника
    UserSession.objects.filter(pk=session_obj.pk).update(
        daily_parse_count=F("daily_parse_count") + 1
    )

    # 5. Синхронний реалтайм парсинг
    try:
        scraper = UniversalProductScraper(store=store)
        product_data = scraper.fetch_product_data(raw_url)
    except Exception as e:
        # Логуємо помилку для розробки
        product_data = None

    if not product_data:
        return render(
            request,
            "products/partials/parse_result.html",
            {"error": "Не вдалося розпарсити товар. Перевірте посилання або спробуйте пізніше."}
        )

    # 6. Збереження у БД (Store, Brand, Product, PriceHistory)
    product = ProductSaveService.save_parsed_product(product_data, session_obj)

    # 7. Перенаправлення (HTMX vs Standard HTTP)
    product_url = reverse("product_detail", kwargs={"pk": product.pk})
    should_set_cookie = getattr(request, "is_new_session_token", False) or created

    if request.headers.get("HX-Request"):
        response = HttpResponse(status=200)
        response["HX-Redirect"] = product_url
    else:
        response = redirect(product_url)

    if should_set_cookie:
        response.set_cookie(
            "session_token",
            session_obj.token,
            max_age=86400 * 30,
            httponly=True,
            samesite="Lax"
        )

    return response
# @require_http_methods(["POST"])
# def test_parse_product(request):
#     url = request.POST.get('url', '').strip()
    
#     if not url:
#         return render(request, 'products/partials/parse_result.html', {
#             'error': 'Будь ласка, вкажіть посилання на товар.'
#         })

#     # -------------------------------------------------------------------------
#     # 1. Lazy Creation: Отримуємо або створюємо UserSession у БД тільки за дією
#     # -------------------------------------------------------------------------
#     ip_address = SessionTokenMiddleware.get_client_ip(request)
#     user_agent = request.META.get('HTTP_USER_AGENT', '')
#     user = request.user if request.user.is_authenticated else None

#     # Шукаємо сесію за токеном або створюємо новий запис
#     session_obj, created = UserSession.objects.get_or_create(
#         token=request.session_token,
#         defaults={
#             'user': user,
#             'ip_address': ip_address,
#             'user_agent': user_agent,
#             'daily_parse_count': 0
#         }
#     )

#     # Якщо користувач залогінений, але сесія раніше була анонімною — прив'язуємо її
#     if user and session_obj.user != user:
#         session_obj.user = user
#         session_obj.save(update_fields=['user'])

#     # -------------------------------------------------------------------------
#     # 2. Перевірка лімітів та атомарне збільшення daily_parse_count
#     # -------------------------------------------------------------------------
#     # Наприклад, ліміт 10 парсингів на добу для анонімних сесій
#     # if not user and session_obj.daily_parse_count >= 10:
#     #     return render(request, 'products/partials/parse_result.html', {
#     #         'error': 'Денний ліміт парсингу вичерпано. Прив'яжіть Telegram, щоб зняти обмеження!'
#     #     })

#     UserSession.objects.filter(pk=session_obj.pk).update(
#         daily_parse_count=F('daily_parse_count') + 1
#     )
#     session_obj.refresh_from_db()

#     # Повідомляємо middleware про необхідність встановити cookie в браузері
#     if request.is_new_session_token or created:
#         request.should_set_cookie = True

#     # -------------------------------------------------------------------------
#     # 3. Синхронний/Реалтайм парсинг через curl_cffi
#     # -------------------------------------------------------------------------
#     scraper = UniversalProductScraper()
#     product_data = scraper.fetch_product_data(url)

#     if not product_data:
#         return render(request, 'products/partials/parse_result.html', {
#             'error': 'Не вдалося розпарсити товар. Перевірте посилання або структуру сторінки.'
#         })

#     # -------------------------------------------------------------------------
#     # 4. Передача даних у шаблон
#     # -------------------------------------------------------------------------
#     context = {
#         'product': product_data,
#         'user_session': session_obj,
#         'daily_parse_count': session_obj.daily_parse_count
#     }

#     return render(request, 'products/partials/parse_result.html', context)