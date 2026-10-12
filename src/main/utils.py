# main/utils.py (або у вашому сервісному модулі)
import logging
from django.contrib.gis.geoip2 import GeoIP2

logger = logging.getLogger(__name__)

def get_client_ip(request) -> str:
    """Отримання реального IP з урахуванням Nginx / Cloudflare проксі"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '')
    return ip

def get_geo_info(ip_address: str) -> dict:
    """Визначення країни та міста за IP-адресою"""
    default_geo = {'country': None, 'city': None}
    
    # Пропускаємо порожні або локальні IP
    if not ip_address or ip_address in ('127.0.0.1', 'localhost') or ip_address.startswith(('192.168.', '10.')):
        return default_geo

    try:
        g = GeoIP2()
        city_info = g.city(ip_address)
        return {
            'country': city_info.get('country_name'), # наприклад: 'Ukraine'
            'city': city_info.get('city'),             # наприклад: 'Kyiv' або 'Lviv'
        }
    except Exception as e:
        # Не падаємо, якщо IP відсутній у базі даних GeoIP2
        logger.debug(f"GeoIP2 lookup error for IP {ip_address}: {e}")
        return default_geo