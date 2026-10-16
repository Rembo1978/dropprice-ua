from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import CashbackRateIngestSerializer
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST
from products.models import Product
from django.shortcuts import get_object_or_404, redirect
from .models import CashbackClick, CashbackRate
from users.models import UserSession
from main.utils import get_client_ip, get_geo_info


class BulkCashbackRateIngestView(APIView):
    """
    API для імпорту ставок кешбеку з парсера LetyShops.
    Вимагає Token-авторизацію у заголовку Header:
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        data = request.data
        is_many = isinstance(data, list)

        serializer = CashbackRateIngestSerializer(data=data, many=is_many)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"status": "success", "processed": len(data) if is_many else 1},
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    


  # Замініть на імпорт вашої моделі Product


# @require_POST
# def cashback_click(request):
#     """
#     Обробляє клік по кнопці кешбеку:
#     1. Отримує ID товару або URL магазину.
#     2. Встановлює cookie 'letyshops_clicked', щоб більше не показувати баннер.
#     3. Повертає HTMX-партіал зі стандартною кнопкою магазину.
#     """
#     product_id = request.GET.get('product_id') or request.POST.get('product_id')
#     product_url = request.GET.get('product_url') or request.POST.get('product_url')

#     product = None
#     if product_id:
#         product = get_object_or_404(Product, pk=product_id)

#     # Рендеримо партіал стандартної кнопки
#     context = {
#         'product': product,
#         'product_url': product_url or (product.url if product else '#'),
#     }
#     response = render(request, 'products/partials/store_button.html', context)

#     # Встановлюємо cookie letyshops_clicked на 30 днів (86400 * 30 секунд)
#     response.set_cookie(
#         key='letyshops_clicked',
#         value='true',
#         max_age=30 * 24 * 60 * 60,  # 30 днів
#         httponly=False,  # Дозволяє JS/HTMX за потреби читати cookie (або True для безпеки)
#         samesite='Lax'
#     )

#     return response
def cashback_click(request, rate_id):
    cashback_rate = get_object_or_404(
        CashbackRate.objects.select_related('service'), 
        pk=rate_id
    )

    product_id = request.GET.get('product_id')
    product = Product.objects.select_related('store').filter(id=product_id).first() if product_id else None

    # Отримуємо IP та геолокацію
    ip_address = get_client_ip(request)
    geo_data = get_geo_info(ip_address)
    user_agent = request.META.get('HTTP_USER_AGENT', '')

    session_token = getattr(request, 'session_token', None) or request.COOKIES.get('session_token')
    user_session = UserSession.objects.filter(token=session_token).first() if session_token else None

    # Записуємо клік разом із гео-даними
    CashbackClick.objects.create(
        service=cashback_rate.service,
        store=product.store if product else None,
        user=request.user if request.user.is_authenticated else None,
        session=user_session,
        product_url=product.url if product else (request.GET.get('product_url') or ''),
        user_ip=ip_address,
        user_agent=user_agent,
        country=geo_data['country'],
        city=geo_data['city'],
    )

    target_url = cashback_rate.service.referral_base_url or '#'
    response = redirect(target_url)
    
    response.set_cookie(
        key='letyshops_clicked',
        value='true',
        max_age=30 * 24 * 60 * 60,
        httponly=False,
        samesite='Lax'
    )

    return response